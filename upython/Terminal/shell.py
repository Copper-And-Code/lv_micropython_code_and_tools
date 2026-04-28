# shell.py — Minimal Shell Interpreter for MicroPython
# Features: line editing, command history, ANSI colored output,
#           filesystem ops, .py execution, binary PIC loader.

import os
import gc
import sys
import time

try:
    from editor import Editor
    HAS_EDITOR = True
except ImportError:
    HAS_EDITOR = False

try:
    import machine
    import micropython
    import uctypes
    HAS_MACHINE = True
except ImportError:
    HAS_MACHINE = False  # For testing on desktop

# ── Binary execution trampoline (module-level, compiled once) ─────
# MicroPython compiles @asm_thumb at import time, so it must be
# at module scope and guarded by HAS_MACHINE.

if HAS_MACHINE:
    @micropython.asm_thumb
    def _asm_call_thumb(r0):
        # r0 = execution address (must be Thumb-aligned)
        # Set bit 0 for Thumb mode (BLX requirement)
        mov(r1, 1)
        orr(r0, r1)
        # BLX r0 — branch-with-link to register
        # Not available as mnemonic in MicroPython inline asm,
        # so we emit the raw Thumb opcode:
        #   BLX Rm = 0100 0111 1 Rm(4bit) 000
        #   BLX r0 = 0100 0111 1 0000 000 = 0x4780
        data(2, 0x4780)
else:
    _asm_call_thumb = None

# ── ANSI escape helpers ───────────────────────────────────────────

ESC = '\x1b'
CSI = ESC + '['

def sgr(*codes):
    return CSI + ';'.join(str(c) for c in codes) + 'm'

RST   = sgr(0)
BOLD  = sgr(1)
RED   = sgr(91)
GREEN = sgr(92)
YELLOW = sgr(93)
BLUE  = sgr(94)
CYAN  = sgr(96)
DIM   = sgr(2)
B_RED = sgr(1, 91)
B_GREEN = sgr(1, 92)
B_CYAN = sgr(1, 96)
B_YELLOW = sgr(1, 93)
B_WHITE = sgr(1, 97)

# ── String padding helpers (MicroPython lacks str.ljust/rjust) ────

def _lj(s, width):
    """Left-justify string to width (pad with spaces on right)."""
    n = len(s)
    return s + ' ' * (width - n) if n < width else s

def _rj(s, width):
    """Right-justify string to width (pad with spaces on left)."""
    n = len(s)
    return ' ' * (width - n) + s if n < width else s

# ── SDRAM Execution Config (STM32H743) ───────────────────────────
# Typical SDRAM mapping: 0xC0000000 (Bank 1) or 0xD0000000 (Bank 2)
# Reserve a region for binary loading — adjust to your memory map.
SDRAM_EXEC_BASE = 0xC0100000   # 1MB offset into SDRAM
SDRAM_EXEC_SIZE = 0x00100000   # 1MB max binary size


class Shell:
    """
    Minimal shell with line editing and built-in commands.
    
    Usage:
        shell = Shell(terminal)   # terminal is AnsiTerminal instance
        # In main loop, feed chars from UART:
        shell.feed(char)
    """

    PROMPT = B_GREEN + 'upy' + RST + ':' + B_CYAN + '{cwd}' + RST + '$ '
    BANNER = (
        B_WHITE + '+------------------------------------------+\n'
        '|  ' + B_CYAN + 'MicroPython Shell' + B_WHITE + '  -  STM32H743       |\n'
        '|  ' + DIM + 'Type "help" for available commands' + B_WHITE + '      |\n'
        '+------------------------------------------+' + RST + '\n\n'
    )

    # Built-in commands registry
    BUILTINS = {}

    def __init__(self, terminal, stdout_cb=None):
        """
        Args:
            terminal:   AnsiTerminal instance (write output here)
            stdout_cb:  Optional callback(str) for additional output routing
        """
        self.term = terminal
        self.stdout_cb = stdout_cb

        # Line editing state
        self._line = []          # Current input line as list of chars
        self._cursor = 0         # Cursor position within _line
        self._history = []       # Command history
        self._hist_idx = -1      # Current history browse index
        self._hist_saved = ''    # Saved partial line when browsing history

        # Current working directory
        self._cwd = '/'

        # ESC sequence accumulator for input
        self._esc_seq = ''
        self._in_esc = False

        # Environment / aliases
        self.env = {
            'SDRAM_EXEC_BASE': hex(SDRAM_EXEC_BASE),
            'SDRAM_EXEC_SIZE': hex(SDRAM_EXEC_SIZE),
        }
        self.aliases = {}

        # Active sub-application (editor, etc.)
        self._editor = None

        # Pipe data for piped commands
        self._pipe_input = None

        # Top mode state
        self._top_active = False

        # LVGL widget container ref (set by main.py for runlv)
        self._term_widget_cont = None

        # testlv diagnostic state
        self._testlv_active = False
        self._testlv_label = None

        # Input poll function (set by main.py for runlv)
        self._input_poll = None

        # Mount points to scan
        self.mount_points = ['/flash', '/sd', '/qspi']

        # Register built-in commands
        self._register_builtins()

        # Show banner and first prompt
        self.write(self.BANNER)
        self._show_prompt()

    # ── Output ────────────────────────────────────────────────────

    def write(self, text):
        """Write text to the terminal (goes through ANSI parser)."""
        self.term.write(text)
        if self.stdout_cb:
            self.stdout_cb(text)

    def writeln(self, text=''):
        self.write(text + '\n')

    # ── Input Handling ────────────────────────────────────────────

    def feed(self, ch):
        """
        Feed a single character from the input source (UART/keyboard).
        Handles line editing, history, and escape sequences.
        If an editor is active, delegates input to the editor.
        """
        # ── Delegate to active editor ──
        if self._editor is not None:
            self._editor.feed(ch)
            if not self._editor.active:
                # Editor closed — return to shell
                self._editor = None
                self._show_prompt()
            return

        o = ord(ch) if isinstance(ch, str) else ch
        if isinstance(ch, int):
            ch = chr(ch)

        # ── Top (live monitor) mode ──
        if self._top_active:
            if ch in ('q', 'Q'):
                self._top_active = False
                self.writeln()
                self._show_prompt()
            elif ch in ('g', 'G'):
                gc.collect()
                self._top_refresh()
            else:
                self._top_refresh()
            return

        # ── testlv diagnostic mode ──
        if self._testlv_active:
            if ch in ('q', 'Q'):
                self._testlv_active = False
                if self._testlv_label:
                    try:
                        self._testlv_label.delete()
                    except:
                        pass
                    self._testlv_label = None
                self.writeln('testlv: label deleted')
                self._show_prompt()
            return

        # ── ESC sequence collection ──
        if self._in_esc:
            self._esc_seq += ch
            if len(self._esc_seq) >= 2:
                if self._esc_seq == '[A':      # Up arrow
                    self._history_prev()
                elif self._esc_seq == '[B':    # Down arrow
                    self._history_next()
                elif self._esc_seq == '[C':    # Right arrow
                    self._cursor_right()
                elif self._esc_seq == '[D':    # Left arrow
                    self._cursor_left()
                elif self._esc_seq == '[H':    # Home
                    self._cursor_home()
                elif self._esc_seq == '[F':    # End
                    self._cursor_end()
                elif self._esc_seq == '[3~':   # Delete
                    self._delete_char()
                elif len(self._esc_seq) >= 3:
                    pass  # Unknown sequence, discard
                else:
                    return  # Need more chars
                self._in_esc = False
                self._esc_seq = ''
            return

        if o == 0x1B:  # ESC
            self._in_esc = True
            self._esc_seq = ''
            return

        # ── Control characters ──
        if o == 0x0D or o == 0x0A:  # Enter
            self.write('\n')
            self._execute_line()
            return

        if o == 0x08 or o == 0x7F:  # Backspace / DEL
            self._backspace()
            return

        if o == 0x03:  # Ctrl+C
            self.write('^C\n')
            self._line = []
            self._cursor = 0
            self._show_prompt()
            return

        if o == 0x0C:  # Ctrl+L — clear screen
            self.term.clear_screen()
            self._show_prompt()
            self._redraw_line()
            return

        if o == 0x15:  # Ctrl+U — clear line
            self._clear_input_line()
            return

        if o == 0x01:  # Ctrl+A — home
            self._cursor_home()
            return

        if o == 0x05:  # Ctrl+E — end
            self._cursor_end()
            return

        if o == 0x09:  # Tab — autocomplete
            self._autocomplete()
            return

        # ── Printable character ──
        if o >= 0x20 and o < 0x7F:
            self._insert_char(ch)

    # ── Line Editing ──────────────────────────────────────────────

    def _insert_char(self, ch):
        self._line.insert(self._cursor, ch)
        self._cursor += 1
        # Re-render from cursor to end of line
        tail = ''.join(self._line[self._cursor - 1:])
        self.write(tail)
        # Move cursor back to correct position
        move_back = len(self._line) - self._cursor
        if move_back > 0:
            self.write(CSI + str(move_back) + 'D')

    def _backspace(self):
        if self._cursor > 0:
            self._cursor -= 1
            del self._line[self._cursor]
            # Move back, rewrite tail, erase last char
            self.write('\x08')
            tail = ''.join(self._line[self._cursor:]) + ' '
            self.write(tail)
            move_back = len(tail)
            if move_back > 0:
                self.write(CSI + str(move_back) + 'D')

    def _delete_char(self):
        if self._cursor < len(self._line):
            del self._line[self._cursor]
            tail = ''.join(self._line[self._cursor:]) + ' '
            self.write(tail)
            move_back = len(tail)
            if move_back > 0:
                self.write(CSI + str(move_back) + 'D')

    def _cursor_left(self):
        if self._cursor > 0:
            self._cursor -= 1
            self.write(CSI + '1D')

    def _cursor_right(self):
        if self._cursor < len(self._line):
            self._cursor += 1
            self.write(CSI + '1C')

    def _cursor_home(self):
        if self._cursor > 0:
            self.write(CSI + str(self._cursor) + 'D')
            self._cursor = 0

    def _cursor_end(self):
        move = len(self._line) - self._cursor
        if move > 0:
            self.write(CSI + str(move) + 'C')
            self._cursor = len(self._line)

    def _clear_input_line(self):
        # Move to start, erase to end of line
        if self._cursor > 0:
            self.write(CSI + str(self._cursor) + 'D')
        self.write(CSI + 'K')
        self._line = []
        self._cursor = 0

    def _redraw_line(self):
        text = ''.join(self._line)
        self.write(text)
        move_back = len(self._line) - self._cursor
        if move_back > 0:
            self.write(CSI + str(move_back) + 'D')

    # ── History ───────────────────────────────────────────────────

    def _history_prev(self):
        if not self._history:
            return
        if self._hist_idx == -1:
            self._hist_saved = ''.join(self._line)
            self._hist_idx = len(self._history) - 1
        elif self._hist_idx > 0:
            self._hist_idx -= 1
        else:
            return

        self._set_line(self._history[self._hist_idx])

    def _history_next(self):
        if self._hist_idx == -1:
            return
        if self._hist_idx < len(self._history) - 1:
            self._hist_idx += 1
            self._set_line(self._history[self._hist_idx])
        else:
            self._hist_idx = -1
            self._set_line(self._hist_saved)

    def _set_line(self, text):
        self._clear_input_line()
        self._line = list(text)
        self._cursor = len(self._line)
        self.write(text)

    # ── Prompt ────────────────────────────────────────────────────

    def _show_prompt(self):
        cwd = self._cwd
        if len(cwd) > 30:
            cwd = '...' + cwd[-27:]
        prompt = self.PROMPT.format(cwd=cwd)
        self.write(prompt)

    # ── Command Execution ─────────────────────────────────────────

    def _execute_line(self):
        line_str = ''.join(self._line).strip()
        self._line = []
        self._cursor = 0
        self._hist_idx = -1

        if not line_str:
            self._show_prompt()
            return

        # Add to history (avoid duplicates at tail)
        if not self._history or self._history[-1] != line_str:
            self._history.append(line_str)
            if len(self._history) > 50:
                self._history.pop(0)

        # ── Check for output redirection: cmd > file ──
        redirect_file = None
        if ' > ' in line_str:
            parts_redir = line_str.split(' > ', 1)
            line_str = parts_redir[0].strip()
            redirect_file = parts_redir[1].strip()

        # ── Check for pipe: cmd1 | cmd2 ──
        if ' | ' in line_str:
            self._execute_pipe(line_str, redirect_file)
            self._show_prompt()
            return

        # ── Normal execution ──
        if redirect_file:
            # Capture output to a buffer, then write to file
            capture_buf = []
            old_write = self.write
            self.write = lambda text: capture_buf.append(text)
            try:
                self._dispatch_command(line_str)
            finally:
                self.write = old_write
            # Write captured output to file
            captured = ''.join(capture_buf)
            rpath = self._normalize_path(redirect_file)
            try:
                with open(rpath, 'w') as f:
                    # Strip ANSI escape sequences for file output
                    f.write(self._strip_ansi(captured))
                self.writeln(DIM + 'Written to: ' + rpath + RST)
            except OSError as e:
                self.writeln(RED + 'Redirect error: {}'.format(e) + RST)
        else:
            self._dispatch_command(line_str)

        self._show_prompt()

    def _dispatch_command(self, line_str):
        """Parse and dispatch a single command string."""
        # Check aliases
        parts = line_str.split()
        if not parts:
            return
        cmd = parts[0]
        if cmd in self.aliases:
            line_str = self.aliases[cmd] + ' ' + ' '.join(parts[1:])
            parts = line_str.split()
            cmd = parts[0]
        args = parts[1:]

        handler = self.BUILTINS.get(cmd)
        if handler:
            try:
                handler(self, args)
            except Exception as e:
                self.writeln(RED + 'Error: ' + str(e) + RST)
        else:
            self._try_run_file(cmd, args)

    def _execute_pipe(self, line_str, final_redirect):
        """Execute a pipeline: cmd1 | cmd2 [| cmd3 ...] [> file]."""
        stages = [s.strip() for s in line_str.split(' | ')]

        # Execute first stage, capture output
        capture_buf = []
        old_write = self.write
        self.write = lambda text: capture_buf.append(text)
        try:
            self._dispatch_command(stages[0])
        finally:
            self.write = old_write

        pipe_data = ''.join(capture_buf)

        # Execute subsequent stages with piped input
        for stage in stages[1:]:
            parts = stage.split()
            if not parts:
                continue
            cmd = parts[0]
            args = parts[1:]

            capture_buf = []
            self.write = lambda text: capture_buf.append(text)
            try:
                # For pipe-aware commands, pass pipe_data via _pipe_input
                self._pipe_input = pipe_data
                handler = self.BUILTINS.get(cmd)
                if handler:
                    handler(self, args)
                self._pipe_input = None
            finally:
                self.write = old_write

            pipe_data = ''.join(capture_buf)

        self._pipe_input = None

        # Final output (to terminal or redirect file)
        if final_redirect:
            rpath = self._normalize_path(final_redirect)
            try:
                with open(rpath, 'w') as f:
                    f.write(self._strip_ansi(pipe_data))
                self.writeln(DIM + 'Written to: ' + rpath + RST)
            except OSError as e:
                self.writeln(RED + 'Redirect error: {}'.format(e) + RST)
        else:
            self.write(pipe_data)

    @staticmethod
    def _strip_ansi(text):
        """Remove ANSI escape sequences from text (for file redirection)."""
        result = []
        i = 0
        n = len(text)
        while i < n:
            if text[i] == '\x1b':
                # Skip ESC sequence
                i += 1
                if i < n and text[i] == '[':
                    i += 1
                    while i < n and text[i] not in 'ABCDEFGHJKSTfmnsurlh':
                        i += 1
                    if i < n:
                        i += 1  # Skip final char
                elif i < n:
                    i += 1  # Skip single char after ESC
            else:
                result.append(text[i])
                i += 1
        return ''.join(result)

    def _try_run_file(self, name, args):
        """Try to find and execute a file by name."""
        # Check if it's a direct path
        candidates = [name]
        if not name.startswith('/'):
            candidates.append(self._resolve_path(name))
            if not name.endswith('.py'):
                candidates.append(self._resolve_path(name + '.py'))

        for path in candidates:
            try:
                os.stat(path)
                if path.endswith('.py'):
                    self._exec_py(path, args)
                    return
                elif path.endswith('.bin'):
                    self._exec_bin(path, args)
                    return
            except OSError:
                continue

        self.writeln(RED + "Command not found: " + name + RST)
        self.writeln(DIM + "Type 'help' for available commands" + RST)

    # ── Path Resolution ───────────────────────────────────────────

    def _resolve_path(self, path):
        if path.startswith('/'):
            return path
        if self._cwd == '/':
            return '/' + path
        return self._cwd + '/' + path

    def _normalize_path(self, path):
        """Normalize path (resolve .. and .)"""
        if not path.startswith('/'):
            if self._cwd == '/':
                path = '/' + path
            else:
                path = self._cwd + '/' + path

        parts = path.split('/')
        result = []
        for p in parts:
            if p == '' or p == '.':
                continue
            elif p == '..':
                if result:
                    result.pop()
            else:
                result.append(p)
        return '/' + '/'.join(result)

    # ── Built-in Command Registration ─────────────────────────────

    def _register_builtins(self):
        Shell.BUILTINS = {
            'help':    Shell.cmd_help,
            'cls':     Shell.cmd_cls,
            'clear':   Shell.cmd_cls,
            'ls':      Shell.cmd_ls,
            'dir':     Shell.cmd_ls,
            'll':      Shell.cmd_ll,
            'cd':      Shell.cmd_cd,
            'pwd':     Shell.cmd_pwd,
            'cat':     Shell.cmd_cat,
            'run':     Shell.cmd_run,
            'exec':    Shell.cmd_exec_bin,
            'free':    Shell.cmd_free,
            'uname':   Shell.cmd_uname,
            'echo':    Shell.cmd_echo,
            'mkdir':   Shell.cmd_mkdir,
            'rm':      Shell.cmd_rm,
            'mv':      Shell.cmd_mv,
            'cp':      Shell.cmd_cp,
            'hexdump': Shell.cmd_hexdump,
            'mount':   Shell.cmd_mount,
            'df':      Shell.cmd_df,
            'reset':   Shell.cmd_reset,
            'alias':   Shell.cmd_alias,
            'env':     Shell.cmd_env,
            'history': Shell.cmd_history,
            'repl':    Shell.cmd_repl,
            'vi':      Shell.cmd_edit,
            'vim':     Shell.cmd_edit,
            'edit':    Shell.cmd_edit,
            'nano':    Shell.cmd_edit,
            'touch':   Shell.cmd_touch,
            'runlv':   Shell.cmd_runlv,
            'testlv':  Shell.cmd_testlv,
            'grep':    Shell.cmd_grep,
            'head':    Shell.cmd_head,
            'tail':    Shell.cmd_tail,
            'wc':      Shell.cmd_wc,
            'top':     Shell.cmd_top,
            'date':    Shell.cmd_date,
            'uptime':  Shell.cmd_uptime,
            'xxd':     Shell.cmd_hexdump,
        }

    # ── Built-in Commands ─────────────────────────────────────────

    def cmd_help(self, args):
        """Display available commands."""
        self.writeln(B_WHITE + 'Available commands:' + RST)
        self.writeln()
        cmds = [
            ('help',            'Show this help'),
            ('cls / clear',     'Clear terminal screen'),
            ('ls [path]',       'List directory contents'),
            ('ll [path]',       'List with details (size, type)'),
            ('cd <path>',       'Change directory'),
            ('pwd',             'Print working directory'),
            ('cat <file>',      'Display file contents'),
            ('run <file.py>',   'Execute MicroPython script'),
            ('runlv <file.py>', 'Run LVGL app (own screen, auto-restore)'),
            ('exec <file.bin>', 'Load and execute binary (PIC) from SDRAM'),
            ('hexdump <file> [n]', 'Hex dump first N bytes of file'),
            ('free',            'Show memory usage'),
            ('df',              'Show filesystem usage'),
            ('mount',           'List mount points'),
            ('uname',           'System information'),
            ('mkdir <dir>',     'Create directory'),
            ('rm <file>',       'Remove file'),
            ('mv <src> <dst>',  'Move/rename file'),
            ('cp <src> <dst>',  'Copy file'),
            ('vi <file>',       'Open vi editor (also: vim, edit, nano)'),
            ('touch <file>',    'Create empty file'),
            ('grep <pat> <file>','Search for pattern in file'),
            ('head [-n N] <file>','Show first N lines (default 10)'),
            ('tail [-n N] <file>','Show last N lines (default 10)'),
            ('wc <file>',       'Count lines, words, bytes'),
            ('top',             'Live memory/task monitor (q to quit)'),
            ('date',            'Show current date/time'),
            ('uptime',          'Show system uptime'),
            ('echo <text>',     'Print text (supports > redirect)'),
            ('alias [name=cmd]','Set or show aliases'),
            ('env',             'Show environment variables'),
            ('history',         'Show command history'),
            ('reset',           'Soft reset the board'),
            ('repl',            'Enter MicroPython REPL'),
        ]
        max_cmd = max(len(c[0]) for c in cmds)
        for cmd, desc in cmds:
            self.writeln('  ' + B_CYAN + _lj(cmd, max_cmd + 2) + RST + DIM + desc + RST)
        self.writeln()
        self.writeln(DIM + 'Shortcuts: Ctrl+C=cancel  Ctrl+L=clear  Ctrl+U=clear line  Tab=autocomplete' + RST)
        self.writeln(DIM + 'Pipe: cmd1 | cmd2     Redirect: cmd > file' + RST)

    def cmd_cls(self, args):
        """Clear screen."""
        self.term.clear_screen()

    def cmd_ls(self, args):
        """List directory."""
        path = self._normalize_path(args[0]) if args else self._cwd
        try:
            entries = os.listdir(path)
        except OSError as e:
            self.writeln(RED + "ls: cannot access '{}': {}".format(path, e) + RST)
            return

        entries.sort()
        for name in entries:
            full = path + '/' + name if path != '/' else '/' + name
            try:
                st = os.stat(full)
                is_dir = st[0] & 0x4000
            except OSError:
                is_dir = False

            if is_dir:
                self.write(B_CYAN + name + '/' + RST + '  ')
            elif name.endswith('.py'):
                self.write(B_GREEN + name + RST + '  ')
            elif name.endswith('.bin'):
                self.write(B_YELLOW + name + RST + '  ')
            else:
                self.write(name + '  ')
        self.writeln()

    def cmd_ll(self, args):
        """List directory with details."""
        path = self._normalize_path(args[0]) if args else self._cwd
        try:
            entries = os.listdir(path)
        except OSError as e:
            self.writeln(RED + "ls: cannot access '{}': {}".format(path, e) + RST)
            return

        entries.sort()
        total = 0
        for name in entries:
            full = path + '/' + name if path != '/' else '/' + name
            try:
                st = os.stat(full)
                is_dir = st[0] & 0x4000
                size = st[6]
                total += size
            except OSError:
                is_dir = False
                size = 0

            size_str = self._format_size(size)
            if is_dir:
                self.writeln(
                    BLUE + 'd' + RST + '  ' +
                    _rj(size_str, 10) + '  ' +
                    B_CYAN + name + '/' + RST
                )
            elif name.endswith('.py'):
                self.writeln(
                    GREEN + '-' + RST + '  ' +
                    _rj(size_str, 10) + '  ' +
                    B_GREEN + name + RST
                )
            elif name.endswith('.bin'):
                self.writeln(
                    YELLOW + 'x' + RST + '  ' +
                    _rj(size_str, 10) + '  ' +
                    B_YELLOW + name + RST
                )
            else:
                self.writeln(
                    DIM + '-' + RST + '  ' +
                    _rj(size_str, 10) + '  ' +
                    name
                )
        self.writeln(DIM + 'Total: ' + self._format_size(total) + RST)

    def cmd_cd(self, args):
        """Change directory."""
        if not args:
            self._cwd = '/'
            return
        path = self._normalize_path(args[0])
        try:
            st = os.stat(path)
            if st[0] & 0x4000:
                self._cwd = path
            else:
                self.writeln(RED + "cd: not a directory: " + path + RST)
        except OSError:
            self.writeln(RED + "cd: no such directory: " + path + RST)

    def cmd_pwd(self, args):
        self.writeln(self._cwd)

    def cmd_cat(self, args):
        """Display file contents."""
        if not args:
            self.writeln(RED + "cat: missing filename" + RST)
            return
        path = self._normalize_path(args[0])
        try:
            with open(path, 'r') as f:
                while True:
                    chunk = f.read(512)
                    if not chunk:
                        break
                    self.write(chunk)
            self.writeln()
        except OSError as e:
            self.writeln(RED + "cat: {}: {}".format(path, e) + RST)

    def cmd_run(self, args):
        """Execute a MicroPython .py file."""
        if not args:
            self.writeln(RED + "run: missing filename" + RST)
            return
        path = self._normalize_path(args[0])
        if not path.endswith('.py'):
            path += '.py'
        self._exec_py(path, args[1:])

    def cmd_exec_bin(self, args):
        """Load and execute a binary PIC file."""
        if not args:
            self.writeln(RED + "exec: missing filename" + RST)
            return
        path = self._normalize_path(args[0])
        if not path.endswith('.bin'):
            path += '.bin'
        self._exec_bin(path, args[1:])

    def cmd_free(self, args):
        """Show memory info."""
        gc.collect()
        free_mem = gc.mem_free()
        alloc_mem = gc.mem_alloc()
        total = free_mem + alloc_mem

        self.writeln(B_WHITE + 'Memory Usage:' + RST)
        self.writeln('  Total:     ' + self._format_size(total))
        self.writeln('  Used:      ' + YELLOW + self._format_size(alloc_mem) + RST
                     + '  ({:.1f}%)'.format(alloc_mem * 100 / total if total else 0))
        self.writeln('  Free:      ' + GREEN + self._format_size(free_mem) + RST
                     + '  ({:.1f}%)'.format(free_mem * 100 / total if total else 0))

        if HAS_MACHINE:
            self.writeln('  SDRAM exec region: ' + DIM +
                         hex(SDRAM_EXEC_BASE) + ' (' +
                         self._format_size(SDRAM_EXEC_SIZE) + ')' + RST)

    def cmd_uname(self, args):
        """System information."""
        self.writeln(B_WHITE + 'System Information:' + RST)
        self.writeln('  Platform:  ' + sys.platform)
        self.writeln('  Version:   ' + sys.version)
        impl = getattr(sys, 'implementation', None)
        if impl:
            self.writeln('  Impl:      ' + str(impl.name) +
                         ' v' + '.'.join(str(x) for x in impl.version))
        try:
            freq = machine.freq()
            if isinstance(freq, tuple):
                self.writeln('  CPU freq:  ' + ', '.join(str(f // 1_000_000) + ' MHz' for f in freq))
            else:
                self.writeln('  CPU freq:  ' + str(freq // 1_000_000) + ' MHz')
        except:
            pass

    def cmd_echo(self, args):
        self.writeln(' '.join(args))

    def cmd_mkdir(self, args):
        if not args:
            self.writeln(RED + "mkdir: missing directory name" + RST)
            return
        path = self._normalize_path(args[0])
        try:
            os.mkdir(path)
        except OSError as e:
            self.writeln(RED + "mkdir: {}: {}".format(path, e) + RST)

    def cmd_rm(self, args):
        if not args:
            self.writeln(RED + "rm: missing filename" + RST)
            return
        path = self._normalize_path(args[0])
        try:
            os.remove(path)
        except OSError as e:
            self.writeln(RED + "rm: {}: {}".format(path, e) + RST)

    def cmd_mv(self, args):
        if len(args) < 2:
            self.writeln(RED + "mv: need source and destination" + RST)
            return
        src = self._normalize_path(args[0])
        dst = self._normalize_path(args[1])
        try:
            os.rename(src, dst)
        except OSError as e:
            self.writeln(RED + "mv: {}: {}".format(src, e) + RST)

    def cmd_cp(self, args):
        if len(args) < 2:
            self.writeln(RED + "cp: need source and destination" + RST)
            return
        src = self._normalize_path(args[0])
        dst = self._normalize_path(args[1])
        try:
            with open(src, 'rb') as sf:
                with open(dst, 'wb') as df:
                    while True:
                        chunk = sf.read(4096)
                        if not chunk:
                            break
                        df.write(chunk)
        except OSError as e:
            self.writeln(RED + "cp: {}".format(e) + RST)

    def cmd_hexdump(self, args):
        """Hex dump of file."""
        if not args:
            self.writeln(RED + "hexdump: missing filename" + RST)
            return
        path = self._normalize_path(args[0])
        nbytes = int(args[1]) if len(args) > 1 else 256
        try:
            with open(path, 'rb') as f:
                offset = 0
                while offset < nbytes:
                    data = f.read(16)
                    if not data:
                        break
                    # Address
                    self.write(YELLOW + '{:08x}'.format(offset) + RST + '  ')
                    # Hex bytes
                    hex_str = ''
                    ascii_str = ''
                    for i in range(16):
                        if i < len(data):
                            b = data[i]
                            hex_str += '{:02x} '.format(b)
                            ascii_str += chr(b) if 0x20 <= b < 0x7F else '.'
                        else:
                            hex_str += '   '
                            ascii_str += ' '
                        if i == 7:
                            hex_str += ' '
                    self.write(hex_str + ' |' + CYAN + ascii_str + RST + '|\n')
                    offset += len(data)
        except OSError as e:
            self.writeln(RED + "hexdump: {}: {}".format(path, e) + RST)

    def cmd_mount(self, args):
        """List detected mount points."""
        self.writeln(B_WHITE + 'Mount points:' + RST)
        for mp in ['/', '/flash', '/sd', '/qspi']:
            try:
                os.listdir(mp)
                self.writeln('  ' + GREEN + mp + RST + '  [mounted]')
            except OSError:
                self.writeln('  ' + DIM + mp + '  [not available]' + RST)

    def cmd_df(self, args):
        """Show filesystem disk usage."""
        for mp in ['/', '/flash', '/sd', '/qspi']:
            try:
                st = os.statvfs(mp)
                # st: (f_bsize, f_frsize, f_blocks, f_bfree, f_bavail, ...)
                block_size = st[1]  # f_frsize
                total = st[2] * block_size
                free = st[3] * block_size
                used = total - free
                pct = used * 100 // total if total else 0
                self.writeln(
                    B_WHITE + _lj(mp, 10) + RST +
                    '  Total: ' + _rj(self._format_size(total), 8) +
                    '  Used: ' + YELLOW + _rj(self._format_size(used), 8) + RST +
                    '  Free: ' + GREEN + _rj(self._format_size(free), 8) + RST +
                    '  [' + self._bar(pct, 20) + '] {:3d}%'.format(pct)
                )
            except OSError:
                pass

    def cmd_reset(self, args):
        """Soft reset."""
        self.writeln(YELLOW + 'Performing soft reset...' + RST)
        if HAS_MACHINE:
            time.sleep_ms(200)
            machine.soft_reset()
        else:
            self.writeln(RED + "Not running on real hardware" + RST)

    def cmd_alias(self, args):
        """Set or show aliases."""
        if not args:
            if self.aliases:
                for k, v in self.aliases.items():
                    self.writeln('  {} = {}'.format(k, v))
            else:
                self.writeln(DIM + 'No aliases defined' + RST)
            return
        # Parse name=value
        text = ' '.join(args)
        if '=' in text:
            name, val = text.split('=', 1)
            self.aliases[name.strip()] = val.strip()
        else:
            self.writeln(RED + "alias: use 'alias name=command'" + RST)

    def cmd_env(self, args):
        for k, v in self.env.items():
            self.writeln('  ' + CYAN + k + RST + '=' + v)

    def cmd_history(self, args):
        for i, cmd in enumerate(self._history):
            self.writeln('  {:3d}  {}'.format(i + 1, cmd))

    def cmd_repl(self, args):
        """Drop to MicroPython REPL (only via UART)."""
        self.writeln(YELLOW + 'Entering MicroPython REPL... (Ctrl+D to return)' + RST)
        # The main loop should catch this flag and redirect UART to REPL
        self._repl_requested = True

    def cmd_edit(self, args):
        """Open vi-like editor."""
        if not HAS_EDITOR:
            self.writeln(RED + 'Editor not available (editor.py not found)' + RST)
            return
        path = None
        if args:
            path = self._normalize_path(args[0])
        self._editor = Editor(
            self.term,
            filepath=path,
            cols=self.term.cols,
            rows=self.term.rows,
        )

    def cmd_touch(self, args):
        """Create an empty file."""
        if not args:
            self.writeln(RED + "touch: missing filename" + RST)
            return
        path = self._normalize_path(args[0])
        try:
            with open(path, 'a') as f:
                pass
        except OSError as e:
            self.writeln(RED + "touch: {}: {}".format(path, e) + RST)

    def cmd_runlv(self, args):
        """Run a MicroPython LVGL application on its own screen."""
        if not args:
            self.writeln(RED + "runlv: missing filename" + RST)
            return
        path = self._normalize_path(args[0])
        if not path.endswith('.py'):
            path += '.py'
        self._exec_py_lvgl(path, args[1:])

    def cmd_testlv(self, args):
        """Inline LVGL diagnostic -- no file needed."""
        import lvgl as lv
        scr = lv.screen_active()
        self.writeln('screen: ' + str(scr))
        cnt = scr.get_child_count()
        self.writeln('children: ' + str(cnt))

        # Create label directly on screen (no hide, no container)
        lbl = lv.label(scr)
        self.writeln('label: ' + str(lbl))

        lbl.set_pos(50, 50)
        lbl.set_style_text_color(lv.color_hex(0xFF0000), 0)
        try:
            lbl.set_style_text_font(lv.font_unscii_16, 0)
        except:
            pass
        lbl.set_text('LVGL TEST - press q')
        lbl.move_foreground()

        lv.task_handler()
        self.writeln('label created, visible on LCD?')
        self.writeln('press q to delete and continue...')

        # Wait for 'q' using shell's own feed mechanism
        self._testlv_label = lbl
        self._testlv_active = True

    def cmd_grep(self, args):
        """Search for pattern in file or piped input."""
        if not args:
            self.writeln(RED + "grep: usage: grep [-i] [-n] [-c] <pattern> [file]" + RST)
            return

        # Parse flags
        ignore_case = False
        show_line_nums = False
        count_only = False
        remaining = []
        for a in args:
            if a.startswith('-') and len(a) > 1 and not a[1].isdigit():
                for flag in a[1:]:
                    if flag == 'i':
                        ignore_case = True
                    elif flag == 'n':
                        show_line_nums = True
                    elif flag == 'c':
                        count_only = True
            else:
                remaining.append(a)

        if not remaining:
            self.writeln(RED + "grep: missing pattern" + RST)
            return

        pattern = remaining[0]
        search_pat = pattern.lower() if ignore_case else pattern

        # Get input: from file or from pipe
        lines = []
        if len(remaining) > 1:
            path = self._normalize_path(remaining[1])
            try:
                with open(path, 'r') as f:
                    for line in f:
                        lines.append(line.rstrip('\n').rstrip('\r'))
            except OSError as e:
                self.writeln(RED + "grep: {}: {}".format(path, e) + RST)
                return
        elif hasattr(self, '_pipe_input') and self._pipe_input:
            lines = self._pipe_input.split('\n')
        else:
            self.writeln(RED + "grep: missing file argument" + RST)
            return

        match_count = 0
        for i, line in enumerate(lines):
            check_line = line.lower() if ignore_case else line
            if search_pat in check_line:
                match_count += 1
                if not count_only:
                    # Highlight matches
                    if show_line_nums:
                        self.write(YELLOW + str(i + 1) + ':' + RST)
                    # Highlight pattern in line
                    idx = 0
                    displayed = ''
                    cl = check_line
                    while True:
                        pos = cl.find(search_pat, idx)
                        if pos < 0:
                            displayed += line[idx:]
                            break
                        displayed += line[idx:pos]
                        displayed += B_RED + line[pos:pos + len(pattern)] + RST
                        idx = pos + len(pattern)
                    self.writeln(displayed)

        if count_only:
            self.writeln(str(match_count))

    def cmd_head(self, args):
        """Show first N lines of a file."""
        n_lines = 10
        filepath = None
        i = 0
        while i < len(args):
            if args[i] == '-n' and i + 1 < len(args):
                try:
                    n_lines = int(args[i + 1])
                except ValueError:
                    pass
                i += 2
            elif args[i].startswith('-') and args[i][1:].isdigit():
                n_lines = int(args[i][1:])
                i += 1
            else:
                filepath = args[i]
                i += 1

        # From pipe or file
        lines = []
        if filepath:
            path = self._normalize_path(filepath)
            try:
                with open(path, 'r') as f:
                    count = 0
                    for line in f:
                        if count >= n_lines:
                            break
                        lines.append(line.rstrip('\n').rstrip('\r'))
                        count += 1
            except OSError as e:
                self.writeln(RED + "head: {}: {}".format(path, e) + RST)
                return
        elif hasattr(self, '_pipe_input') and self._pipe_input:
            all_lines = self._pipe_input.split('\n')
            lines = all_lines[:n_lines]
        else:
            self.writeln(RED + "head: missing file argument" + RST)
            return

        for line in lines:
            self.writeln(line)

    def cmd_tail(self, args):
        """Show last N lines of a file."""
        n_lines = 10
        filepath = None
        i = 0
        while i < len(args):
            if args[i] == '-n' and i + 1 < len(args):
                try:
                    n_lines = int(args[i + 1])
                except ValueError:
                    pass
                i += 2
            elif args[i].startswith('-') and args[i][1:].isdigit():
                n_lines = int(args[i][1:])
                i += 1
            else:
                filepath = args[i]
                i += 1

        lines = []
        if filepath:
            path = self._normalize_path(filepath)
            try:
                with open(path, 'r') as f:
                    # Ring buffer to keep last N lines (memory efficient)
                    ring = [None] * n_lines
                    total = 0
                    for line in f:
                        ring[total % n_lines] = line.rstrip('\n').rstrip('\r')
                        total += 1
                    if total <= n_lines:
                        lines = [ring[j] for j in range(total)]
                    else:
                        start = total % n_lines
                        lines = [ring[(start + j) % n_lines] for j in range(n_lines)]
            except OSError as e:
                self.writeln(RED + "tail: {}: {}".format(path, e) + RST)
                return
        elif hasattr(self, '_pipe_input') and self._pipe_input:
            all_lines = self._pipe_input.split('\n')
            lines = all_lines[-n_lines:]
        else:
            self.writeln(RED + "tail: missing file argument" + RST)
            return

        for line in lines:
            self.writeln(line)

    def cmd_wc(self, args):
        """Count lines, words, bytes in a file."""
        if not args:
            # Maybe from pipe
            if hasattr(self, '_pipe_input') and self._pipe_input:
                text = self._pipe_input
                n_lines = text.count('\n')
                n_words = len(text.split())
                n_bytes = len(text)
                self.writeln('  {} {} {}'.format(n_lines, n_words, n_bytes))
                return
            self.writeln(RED + "wc: missing filename" + RST)
            return

        path = self._normalize_path(args[0])
        try:
            n_lines = 0
            n_words = 0
            n_bytes = 0
            with open(path, 'r') as f:
                while True:
                    chunk = f.read(1024)
                    if not chunk:
                        break
                    n_bytes += len(chunk)
                    n_lines += chunk.count('\n')
                    n_words += len(chunk.split())
            self.writeln('  {:>6} {:>6} {:>8}  {}'.format(
                n_lines, n_words, n_bytes, args[0]))
        except OSError as e:
            self.writeln(RED + "wc: {}: {}".format(path, e) + RST)

    def cmd_top(self, args):
        """Live memory/system monitor. Press 'q' to quit."""
        self._top_active = True
        # Draw initial 5 blank lines so _top_refresh can overwrite them
        for _ in range(5):
            self.writeln()
        self._top_refresh()

    def cmd_date(self, args):
        """Show current date/time."""
        try:
            import machine
            rtc = machine.RTC()
            dt = rtc.datetime()
            # dt = (year, month, day, weekday, hours, minutes, seconds, subseconds)
            self.writeln('{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}'.format(
                dt[0], dt[1], dt[2], dt[4], dt[5], dt[6]))
        except Exception:
            t = time.localtime()
            self.writeln('{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}'.format(
                t[0], t[1], t[2], t[3], t[4], t[5]))

    def cmd_uptime(self, args):
        """Show system uptime."""
        try:
            ms = time.ticks_ms()
            secs = ms // 1000
            mins = secs // 60
            hrs = mins // 60
            days = hrs // 24
            self.writeln('Uptime: {}d {:02d}:{:02d}:{:02d}'.format(
                days, hrs % 24, mins % 60, secs % 60))
        except Exception:
            self.writeln(DIM + 'Uptime not available' + RST)

    # ── File Execution ────────────────────────────────────────────

    def _exec_py(self, path, args):
        """Execute a MicroPython script."""
        self.writeln(DIM + '>>> Executing: ' + path + RST)
        try:
            # Set sys.argv for the script
            old_argv = getattr(sys, "argv", None)
            try:
                sys.argv = [path] + list(args)
            except:
                pass

            with open(path, 'r') as f:
                code = f.read()

            # Create a namespace for the script with output redirected
            ns = {
                '__name__': '__main__',
                '__file__': path,
                'print': self._shell_print,
            }
            exec(code, ns)
            if old_argv is not None:
                try:
                    sys.argv = old_argv
                except:
                    pass
        except Exception as e:
            self.writeln(RED + 'Error executing {}: {}'.format(path, e) + RST)
            if old_argv is not None:
                try:
                    sys.argv = old_argv
                except:
                    pass

    def _shell_print(self, *args, **kwargs):
        """Replacement print() that routes to terminal."""
        sep = kwargs.get('sep', ' ')
        end = kwargs.get('end', '\n')
        text = sep.join(str(a) for a in args) + end
        self.write(text)

    def _exec_py_lvgl(self, path, args):
        """
        Execute an LVGL app. Widgets go directly on the active screen.
        Terminal is hidden during execution, restored after.
        """
        import lvgl as lv

        # ── Read file FIRST (before hiding anything) ──
        try:
            with open(path, 'r') as f:
                code = f.read()
            sys.stdout.write('[runlv] file read OK: {} bytes\n'.format(len(code)))
        except OSError as e:
            self.writeln(RED + 'runlv: {}: {}'.format(path, e) + RST)
            return

        self.writeln(DIM + '>>> LVGL app: ' + path + RST)

        scr = lv.screen_active()

        # ── Display dimensions ──
        try:
            d = lv.display_get_default()
            disp_w = d.get_horizontal_resolution()
            disp_h = d.get_vertical_resolution()
        except:
            disp_w = 1024
            disp_h = 600

        # ── Count existing children (to delete app widgets later) ──
        try:
            children_before = scr.get_child_count()
        except:
            children_before = 0

        # ── Hide terminal widget ──
        term_cont = self._term_widget_cont
        if term_cont:
            try:
                term_cont.add_flag(lv.obj.FLAG.HIDDEN)
            except:
                pass

        scr.set_style_bg_color(lv.color_hex(0x000000), 0)
        lv.task_handler()
        sys.stdout.write('[runlv] terminal hidden, screen ready\n')

        # ── Input reader: reuse the main loop's input provider ──
        _poll_fn = self._input_poll

        def _get_key():
            if _poll_fn:
                data = _poll_fn()
                if data:
                    # poll() returns a string (possibly multiple chars)
                    return data[0] if len(data) > 0 else None
            return None

        # ── Run ──
        error_msg = None
        try:
            old_argv = getattr(sys, "argv", None)
            try:
                sys.argv = [path] + list(args)
            except:
                pass

            # print during LVGL app goes to serial (terminal is hidden)
            def _app_print(*a, **kw):
                sep = kw.get('sep', ' ')
                end = kw.get('end', '\n')
                sys.stdout.write(sep.join(str(x) for x in a) + end)

            ns = {
                '__name__': '__main__',
                '__file__': path,
                'lv': lv,
                'screen': scr,
                'get_key': _get_key,
                'sleep_ms': time.sleep_ms,
                'gc': gc,
                'print': _app_print,
                'DISPLAY_W': disp_w,
                'DISPLAY_H': disp_h,
            }

            gc.collect()
            sys.stdout.write('[runlv] starting: ' + path + '\n')
            exec(code, ns)
            sys.stdout.write('[runlv] finished OK\n')

        except KeyboardInterrupt:
            error_msg = 'Interrupted (Ctrl+C)'
        except SystemExit:
            pass
        except Exception as e:
            error_msg = str(e)
            # Print to serial so it's visible even if terminal is hidden
            try:
                sys.stdout.write('[runlv] ERROR: ' + error_msg + '\n')
            except:
                pass
        finally:
            if old_argv is not None:
                try:
                    sys.argv = old_argv
                except:
                    pass

            # ── Delete all children added by the app ──
            try:
                total_now = scr.get_child_count()
                for i in range(total_now - 1, children_before - 1, -1):
                    try:
                        child = scr.get_child(i)
                        if child:
                            child.delete()
                    except:
                        pass
            except:
                pass

            gc.collect()

            # ── Restore terminal ──
            if term_cont:
                try:
                    term_cont.remove_flag(lv.obj.FLAG.HIDDEN)
                except:
                    pass

            try:
                lv.task_handler()
            except:
                pass

            self.term.dirty = set(range(self.term.rows))
            sys.stdout.write('[runlv] terminal restored\n')

        if error_msg:
            self.writeln(RED + 'LVGL app error: ' + error_msg + RST)
        else:
            self.writeln(DIM + '>>> LVGL app finished' + RST)

    def _exec_bin(self, path, args):
        """Load a PIC binary into SDRAM and execute it."""
        if not HAS_MACHINE:
            self.writeln(RED + "exec: binary execution requires real hardware" + RST)
            return

        self.writeln(DIM + '>>> Loading binary: ' + path + RST)
        try:
            # Read binary file
            with open(path, 'rb') as f:
                data = f.read()

            size = len(data)
            if size > SDRAM_EXEC_SIZE:
                self.writeln(RED + 'exec: binary too large ({} > {})'.format(
                    self._format_size(size),
                    self._format_size(SDRAM_EXEC_SIZE)
                ) + RST)
                return

            self.writeln('  Size:    ' + self._format_size(size))
            self.writeln('  Target:  ' + hex(SDRAM_EXEC_BASE))

            # Copy to SDRAM execution region
            dest = uctypes.bytearray_at(SDRAM_EXEC_BASE, size)
            dest[:] = data

            self.writeln(YELLOW + '  Executing at ' + hex(SDRAM_EXEC_BASE) + '...' + RST)

            # Flush D-cache to ensure SDRAM is coherent before execution
            gc.collect()

            # Jump to binary via module-level trampoline
            _asm_call_thumb(SDRAM_EXEC_BASE)
            self.writeln(GREEN + '  Binary execution returned.' + RST)

        except OSError as e:
            self.writeln(RED + "exec: {}: {}".format(path, e) + RST)
        except Exception as e:
            self.writeln(RED + "exec: runtime error: {}".format(e) + RST)

    # ── Autocomplete ──────────────────────────────────────────────

    def _autocomplete(self):
        """Simple Tab-completion for filenames and commands."""
        line_str = ''.join(self._line)
        parts = line_str.split()

        if len(parts) <= 1:
            # Complete command name or first argument
            prefix = line_str.strip()
            # Try built-in commands first
            matches = [c for c in self.BUILTINS.keys() if c.startswith(prefix)]
            if not matches:
                # Try files in cwd
                matches = self._complete_path(prefix)
        else:
            # Complete file path argument
            prefix = parts[-1]
            matches = self._complete_path(prefix)

        if len(matches) == 1:
            # Single match — complete it
            completion = matches[0][len(prefix.split('/')[-1]):]
            for ch in completion:
                self._insert_char(ch)
            # Add space if it's a command
            if len(parts) <= 1:
                self._insert_char(' ')
        elif len(matches) > 1:
            # Multiple matches — show them
            self.writeln()
            for m in matches:
                self.write(CYAN + m + RST + '  ')
            self.writeln()
            self._show_prompt()
            self._redraw_line()

    def _complete_path(self, prefix):
        """Complete a partial filename/path."""
        if '/' in prefix:
            dir_part = prefix.rsplit('/', 1)[0]
            name_part = prefix.rsplit('/', 1)[1]
            dir_path = self._normalize_path(dir_part)
        else:
            dir_path = self._cwd
            name_part = prefix

        try:
            entries = os.listdir(dir_path)
            return [e for e in entries if e.startswith(name_part)]
        except OSError:
            return []

    # ── Top (Live Monitor) ────────────────────────────────────────

    def _top_refresh(self):
        """Redraw the top monitor display."""
        gc.collect()
        free_mem = gc.mem_free()
        alloc_mem = gc.mem_alloc()
        total = free_mem + alloc_mem
        pct = alloc_mem * 100 // total if total else 0

        # Move cursor up and overwrite (simple refresh)
        self.write(CSI + '5A')  # Move up 5 lines
        self.write(CSI + '0J')  # Erase below

        self.writeln(B_WHITE + '+-- Memory ----------------------------+' + RST)
        bar = self._bar(pct, 28)
        self.writeln(B_WHITE + '|' + RST + ' [' + bar + '] {:3d}% '.format(pct) + B_WHITE + '|' + RST)
        self.writeln(B_WHITE + '|' + RST +
                     '  Used: ' + YELLOW + _lj(self._format_size(alloc_mem), 10) + RST +
                     '  Free: ' + GREEN + _lj(self._format_size(free_mem), 10) + RST +
                     B_WHITE + '|' + RST)
        self.writeln(B_WHITE + '+--------------------------------------+' + RST)
        self.writeln(DIM + ' q=quit  g=GC  (any key=refresh)' + RST)

    # ── Utilities ─────────────────────────────────────────────────

    @staticmethod
    def _format_size(size):
        if size < 1024:
            return '{}B'.format(size)
        elif size < 1024 * 1024:
            return '{:.1f}KB'.format(size / 1024)
        elif size < 1024 * 1024 * 1024:
            return '{:.1f}MB'.format(size / (1024 * 1024))
        else:
            return '{:.1f}GB'.format(size / (1024 * 1024 * 1024))

    @staticmethod
    def _bar(pct, width):
        filled = pct * width // 100
        return GREEN + '#' * filled + DIM + '.' * (width - filled) + RST
