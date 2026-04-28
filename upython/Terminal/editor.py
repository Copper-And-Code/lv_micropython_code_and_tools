# editor.py -- Vi-like Text Editor for MicroPython Shell
# Modal editor (Normal / Insert / Visual / Command) rendered via AnsiTerminal.
# Designed for STM32H743 with constrained memory: streams file lines,
# avoids large allocations.
#
# Supports: motions (hjkl, w, b, e, 0, $, gg, G), editing (i, a, o, O,
# x, dd, yy, p, P, u), visual select, search (/pattern, n, N),
# command mode (:w, :q, :wq, :q!, :set, :%), Python syntax highlighting.

import gc

# ── ANSI helpers ──────────────────────────────────────────────────

ESC = '\x1b'
CSI = ESC + '['

def _rj(s, width):
    """Right-justify (MicroPython lacks str.rjust)."""
    n = len(s)
    return ' ' * (width - n) + s if n < width else s

def sgr(*codes):
    return CSI + ';'.join(str(c) for c in codes) + 'm'

RST       = sgr(0)
BOLD      = sgr(1)
DIM       = sgr(2)
UNDERLINE = sgr(4)
REVERSE   = sgr(7)

# Editor color scheme
C_NORMAL    = sgr(0)           # Normal text
C_KEYWORD   = sgr(1, 93)      # Bold yellow -- Python keywords
C_STRING    = sgr(32)          # Green -- strings
C_COMMENT   = sgr(36)         # Cyan -- comments
C_NUMBER    = sgr(91)          # Bright red -- numbers
C_BUILTIN   = sgr(95)         # Bright magenta -- builtins
C_OPERATOR  = sgr(33)          # Yellow -- operators
C_DECORATOR = sgr(96)         # Bright cyan -- decorators
C_LINENUM   = sgr(2, 33)      # Dim yellow -- line numbers
C_STATUS    = sgr(0, 30, 47)   # Black on white -- status bar
C_STATUS_MODE = sgr(1, 97, 44) # Bold white on blue -- mode indicator
C_STATUS_FILE = sgr(1, 97, 42) # Bold white on green -- filename
C_STATUS_ERR  = sgr(1, 97, 41) # Bold white on red -- error
C_CMDLINE   = sgr(0, 97)      # Bright white -- command line
C_SEARCH_HL = sgr(30, 43)     # Black on yellow -- search highlight
C_VISUAL    = sgr(30, 46)     # Black on cyan -- visual selection
C_CURSOR_LINE = sgr(48, 5, 236) # Subtle bg for current line (256-color)
C_MATCH_PAREN = sgr(1, 93, 4) # Bold yellow underline -- matching bracket
C_TILDE     = sgr(34)         # Blue -- tilde for empty lines (like vim)

# Python syntax data
PY_KEYWORDS = frozenset([
    'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await',
    'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
    'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is',
    'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'try',
    'while', 'with', 'yield',
])

PY_BUILTINS = frozenset([
    'print', 'len', 'range', 'int', 'str', 'float', 'list', 'dict',
    'tuple', 'set', 'bool', 'bytes', 'bytearray', 'type', 'isinstance',
    'hasattr', 'getattr', 'setattr', 'open', 'super', 'property',
    'staticmethod', 'classmethod', 'enumerate', 'zip', 'map', 'filter',
    'sorted', 'reversed', 'any', 'all', 'min', 'max', 'sum', 'abs',
    'round', 'hex', 'oct', 'bin', 'chr', 'ord', 'repr', 'input',
    'Exception', 'ValueError', 'TypeError', 'KeyError', 'IndexError',
    'RuntimeError', 'OSError', 'IOError', 'StopIteration', 'AttributeError',
    'ImportError', 'NameError', 'NotImplementedError', 'MemoryError',
])

# ── Editor Modes ──────────────────────────────────────────────────

MODE_NORMAL  = 0
MODE_INSERT  = 1
MODE_COMMAND = 2
MODE_VISUAL  = 3
MODE_SEARCH  = 4

MODE_NAMES = {
    MODE_NORMAL:  'NORMAL',
    MODE_INSERT:  'INSERT',
    MODE_COMMAND: 'COMMAND',
    MODE_VISUAL:  'VISUAL',
    MODE_SEARCH:  'SEARCH',
}

# ── Undo Entry ────────────────────────────────────────────────────

class UndoEntry:
    __slots__ = ('lines_snapshot', 'cx', 'cy')
    def __init__(self, lines, cx, cy):
        # Store a shallow copy of lines (list of strings)
        self.lines_snapshot = lines[:]
        self.cx = cx
        self.cy = cy


class Editor:
    """
    Vi-like modal text editor running inside AnsiTerminal.

    Usage from Shell:
        ed = Editor(terminal, filepath='/flash/main.py')
        # Then feed chars:  ed.feed(ch)
        # Check ed.active to know when user quits
    """

    def __init__(self, terminal, filepath=None, cols=None, rows=None, syntax=True):
        """
        Args:
            terminal:  AnsiTerminal instance
            filepath:  File to open (None for new buffer)
            cols/rows: Override terminal dimensions (default: from terminal)
            syntax:    Enable syntax highlighting for .py files
        """
        self.term = terminal
        self.filepath = filepath
        self.cols = cols or terminal.cols
        self.rows = rows or terminal.rows
        self.active = True

        # Reserve 2 rows: status bar + command line
        self.text_rows = self.rows - 2
        self.linenum_width = 4  # "NNN " -- adjusted dynamically

        # ── Document buffer ──
        self.lines = ['']  # List of strings (no trailing \n)
        self.modified = False

        # ── Cursor ──
        self.cx = 0       # Column in document (0-based)
        self.cy = 0       # Line in document (0-based)

        # ── Viewport scroll ──
        self.scroll_y = 0  # First visible document line
        self.scroll_x = 0  # Horizontal scroll offset

        # ── Mode ──
        self.mode = MODE_NORMAL

        # ── Registers ──
        self.yank_buf = []          # Yanked lines
        self.yank_is_linewise = True

        # ── Search ──
        self.search_pattern = ''
        self.search_forward = True
        self._search_buf = ''

        # ── Command line ──
        self._cmd_buf = ''

        # ── Visual mode ──
        self.visual_start_y = 0
        self.visual_start_x = 0

        # ── Undo stack ──
        self._undo_stack = []
        self._max_undo = 30

        # ── Pending operator (for d, y, c + motion) ──
        self._pending_op = None
        self._count_buf = ''

        # ── ESC sequence state ──
        self._esc_seq = ''
        self._in_esc = False

        # ── Syntax highlighting ──
        self.syntax_enabled = syntax and (
            filepath is not None and filepath.endswith('.py')
        )

        # ── Status message (temporary) ──
        self._status_msg = ''
        self._status_is_error = False

        # ── Smart redraw tracking ──
        self._prev_cy = 0
        self._prev_cx = 0
        self._prev_scroll_y = 0
        self._prev_scroll_x = 0
        self._force_full = True   # First draw is always full

        # ── Load file ──
        if filepath:
            self._load_file(filepath)

        self._update_linenum_width()
        self._full_redraw()
        self._force_full = False

    # ── File I/O ──────────────────────────────────────────────────

    def _load_file(self, path):
        """Load file into buffer."""
        try:
            with open(path, 'r') as f:
                self.lines = []
                for line in f:
                    # Strip trailing newline/CR
                    self.lines.append(line.rstrip('\n').rstrip('\r'))
            if not self.lines:
                self.lines = ['']
            self.modified = False
            self._set_status('"{}" {}L'.format(path, len(self.lines)))
        except OSError as e:
            self.lines = ['']
            self._set_status('New file: {}'.format(path))

    def _save_file(self, path=None):
        """Save buffer to file."""
        path = path or self.filepath
        if not path:
            self._set_status('No filename (use :w filename)', error=True)
            return False
        try:
            with open(path, 'w') as f:
                for i, line in enumerate(self.lines):
                    f.write(line)
                    if i < len(self.lines) - 1:
                        f.write('\n')
            self.filepath = path
            self.modified = False
            self._set_status('"{}" {}L written'.format(path, len(self.lines)))
            return True
        except OSError as e:
            msg = str(e)
            if 'ENODEV' in msg or 'EROFS' in msg or 'EPERM' in msg:
                self._set_status(
                    'Filesystem read-only! Try :w /sd/' + path.split('/')[-1],
                    error=True)
            else:
                self._set_status('Write error: {}'.format(e), error=True)
            return False

    # ── Input Handling ────────────────────────────────────────────

    def feed(self, ch):
        """
        Feed one character from the input source.
        Returns True if the editor consumed it.
        """
        if not self.active:
            return False

        o = ord(ch) if isinstance(ch, str) else ch
        if isinstance(ch, int):
            ch = chr(ch)

        # ── ESC sequence collection ──
        if self._in_esc:
            self._esc_seq += ch
            if len(self._esc_seq) >= 2:
                self._handle_escape_seq(self._esc_seq)
                self._in_esc = False
                self._esc_seq = ''
            elif len(self._esc_seq) >= 4:
                self._in_esc = False
                self._esc_seq = ''
            return True

        if o == 0x1B:
            if self.mode in (MODE_INSERT, MODE_VISUAL, MODE_SEARCH, MODE_COMMAND):
                self._exit_to_normal()
            else:
                self._in_esc = True
                self._esc_seq = ''
            return True

        # Dispatch by mode
        if self.mode == MODE_NORMAL:
            self._handle_normal(ch, o)
        elif self.mode == MODE_INSERT:
            self._handle_insert(ch, o)
        elif self.mode == MODE_COMMAND:
            self._handle_command(ch, o)
        elif self.mode == MODE_VISUAL:
            self._handle_visual(ch, o)
        elif self.mode == MODE_SEARCH:
            self._handle_search_input(ch, o)

        self._ensure_cursor_bounds()
        self._scroll_into_view()
        self._smart_redraw()
        return True

    def _handle_escape_seq(self, seq):
        """Handle arrow keys and special keys from ESC sequences."""
        if seq == '[A':    # Up
            self._motion_up(self._get_count())
        elif seq == '[B':  # Down
            self._motion_down(self._get_count())
        elif seq == '[C':  # Right
            if self.mode == MODE_INSERT:
                self._motion_right(1)
            else:
                self._motion_right(self._get_count())
        elif seq == '[D':  # Left
            if self.mode == MODE_INSERT:
                self._motion_left(1)
            else:
                self._motion_left(self._get_count())
        elif seq == '[H':  # Home
            self.cx = 0
        elif seq == '[F':  # End
            self.cx = len(self._cur_line())
        elif seq == '[3~': # Delete
            if self.mode == MODE_INSERT:
                self._delete_char_at_cursor()

    # ── NORMAL MODE ───────────────────────────────────────────────

    def _handle_normal(self, ch, o):
        # ── Count prefix ──
        if ch in '123456789' or (ch == '0' and self._count_buf):
            self._count_buf += ch
            return

        count = self._get_count()

        # ── Pending operator (d, y, c) ──
        if self._pending_op:
            self._handle_operator_motion(ch, count)
            return

        # ── Motions ──
        if ch == 'h':
            self._motion_left(count)
        elif ch == 'l':
            self._motion_right(count)
        elif ch == 'k':
            self._motion_up(count)
        elif ch == 'j':
            self._motion_down(count)
        elif ch == 'w':
            self._motion_word_forward(count)
        elif ch == 'b':
            self._motion_word_backward(count)
        elif ch == 'e':
            self._motion_word_end(count)
        elif ch == '0':
            self.cx = 0
        elif ch == '^':
            self._motion_first_nonblank()
        elif ch == '$':
            self.cx = max(0, len(self._cur_line()) - 1)
        elif ch == 'g':
            # gg = go to first line (wait for second g)
            self._pending_op = 'g'
        elif ch == 'G':
            if count > 1:
                self.cy = min(count - 1, len(self.lines) - 1)
            else:
                self.cy = len(self.lines) - 1
            self._motion_first_nonblank()
        elif ch == '{':
            self._motion_paragraph_up(count)
        elif ch == '}':
            self._motion_paragraph_down(count)
        elif ch == '%':
            self._motion_match_bracket()

        # ── Mode switches ──
        elif ch == 'i':
            self._push_undo()
            self.mode = MODE_INSERT
        elif ch == 'I':
            self._push_undo()
            self._motion_first_nonblank()
            self.mode = MODE_INSERT
        elif ch == 'a':
            self._push_undo()
            if self._cur_line():
                self.cx = min(self.cx + 1, len(self._cur_line()))
            self.mode = MODE_INSERT
        elif ch == 'A':
            self._push_undo()
            self.cx = len(self._cur_line())
            self.mode = MODE_INSERT
        elif ch == 'o':
            self._push_undo()
            self.cy += 1
            self.lines.insert(self.cy, '')
            self.cx = 0
            self.mode = MODE_INSERT
            self.modified = True
        elif ch == 'O':
            self._push_undo()
            self.lines.insert(self.cy, '')
            self.cx = 0
            self.mode = MODE_INSERT
            self.modified = True
        elif ch == 'v':
            self.mode = MODE_VISUAL
            self.visual_start_y = self.cy
            self.visual_start_x = self.cx
        elif ch == ':':
            self.mode = MODE_COMMAND
            self._cmd_buf = ''
        elif ch == '/':
            self.mode = MODE_SEARCH
            self._search_buf = ''
            self.search_forward = True
        elif ch == '?':
            self.mode = MODE_SEARCH
            self._search_buf = ''
            self.search_forward = False

        # ── Editing ──
        elif ch == 'x':
            self._push_undo()
            for _ in range(count):
                self._delete_char_x()
        elif ch == 'r':
            # Replace -- next char replaces current
            self._pending_op = 'r'
        elif ch == 'd':
            self._pending_op = 'd'
        elif ch == 'y':
            self._pending_op = 'y'
        elif ch == 'c':
            self._pending_op = 'c'
        elif ch == 'p':
            self._push_undo()
            self._paste_after(count)
        elif ch == 'P':
            self._push_undo()
            self._paste_before(count)
        elif ch == 'u':
            self._undo()
        elif ch == 'J':
            self._push_undo()
            self._join_lines()

        # ── Search navigation ──
        elif ch == 'n':
            self._search_next()
        elif ch == 'N':
            self._search_prev()

        # ── Misc ──
        elif o == 0x0C:  # Ctrl+L: force redraw
            self._full_redraw()
        elif o == 0x07:  # Ctrl+G: show file info
            self._show_file_info()
        elif o == 0x04:  # Ctrl+D: half page down
            self._motion_down(self.text_rows // 2)
        elif o == 0x15:  # Ctrl+U: half page up
            self._motion_up(self.text_rows // 2)
        elif o == 0x06:  # Ctrl+F: page down
            self._motion_down(self.text_rows)
        elif o == 0x02:  # Ctrl+B: page up
            self._motion_up(self.text_rows)

    def _handle_operator_motion(self, ch, count):
        """Handle second keystroke for d/y/c + motion."""
        op = self._pending_op
        self._pending_op = None

        if op == 'g' and ch == 'g':
            # gg -- go to top
            self.cy = 0
            self._motion_first_nonblank()
            return

        if op == 'r':
            # Replace current char
            if len(self._cur_line()) > 0 and self.cx < len(self._cur_line()):
                self._push_undo()
                line = self._cur_line()
                self.lines[self.cy] = line[:self.cx] + ch + line[self.cx + 1:]
                self.modified = True
            return

        # dd / yy / cc -- line-wise operation
        if ch == op:
            start_y = self.cy
            end_y = min(self.cy + count - 1, len(self.lines) - 1)
            if op == 'd':
                self._push_undo()
                self._delete_lines(start_y, end_y)
            elif op == 'y':
                self._yank_lines(start_y, end_y)
                self._set_status('{} lines yanked'.format(end_y - start_y + 1))
            elif op == 'c':
                self._push_undo()
                self._delete_lines(start_y, end_y)
                self.lines.insert(self.cy, '')
                self.cx = 0
                self.mode = MODE_INSERT
                self.modified = True
            return

        # d/y/c + motion
        old_cy = self.cy
        old_cx = self.cx
        self._exec_motion(ch, count)
        new_cy = self.cy
        new_cx = self.cx

        if old_cy != new_cy:
            # Line-wise
            start_y = min(old_cy, new_cy)
            end_y = max(old_cy, new_cy)
            if op == 'd':
                self._push_undo()
                self.cy = old_cy
                self._delete_lines(start_y, end_y)
            elif op == 'y':
                self._yank_lines(start_y, end_y)
                self.cy = old_cy
                self.cx = old_cx
                self._set_status('{} lines yanked'.format(end_y - start_y + 1))
            elif op == 'c':
                self._push_undo()
                self.cy = old_cy
                self._delete_lines(start_y, end_y)
                self.lines.insert(self.cy, '')
                self.cx = 0
                self.mode = MODE_INSERT
                self.modified = True
        elif old_cx != new_cx:
            # Character-wise
            start = min(old_cx, new_cx)
            end = max(old_cx, new_cx)
            line = self.lines[self.cy]
            if op == 'd':
                self._push_undo()
                self.lines[self.cy] = line[:start] + line[end:]
                self.cx = start
                self.modified = True
            elif op == 'y':
                self.yank_buf = [line[start:end]]
                self.yank_is_linewise = False
                self.cx = old_cx
                self._set_status('yanked')
            elif op == 'c':
                self._push_undo()
                self.lines[self.cy] = line[:start] + line[end:]
                self.cx = start
                self.mode = MODE_INSERT
                self.modified = True

    def _exec_motion(self, ch, count):
        """Execute a motion command (used by operator+motion)."""
        if ch == 'h':
            self._motion_left(count)
        elif ch == 'l':
            self._motion_right(count)
        elif ch == 'k':
            self._motion_up(count)
        elif ch == 'j':
            self._motion_down(count)
        elif ch == 'w':
            self._motion_word_forward(count)
        elif ch == 'b':
            self._motion_word_backward(count)
        elif ch == 'e':
            self._motion_word_end(count)
        elif ch == '0':
            self.cx = 0
        elif ch == '$':
            self.cx = len(self._cur_line())
        elif ch == 'G':
            self.cy = len(self.lines) - 1
        elif ch == '{':
            self._motion_paragraph_up(count)
        elif ch == '}':
            self._motion_paragraph_down(count)

    # ── INSERT MODE ───────────────────────────────────────────────

    def _handle_insert(self, ch, o):
        if o == 0x0D or o == 0x0A:  # Enter
            self._insert_newline()
        elif o == 0x08 or o == 0x7F:  # Backspace
            self._backspace_insert()
        elif o == 0x09:  # Tab → 4 spaces
            for _ in range(4):
                self._insert_char(' ')
        elif o >= 0x20 and o < 0x7F:
            self._insert_char(ch)

    def _insert_char(self, ch):
        line = self._cur_line()
        self.lines[self.cy] = line[:self.cx] + ch + line[self.cx:]
        self.cx += 1
        self.modified = True

    def _insert_newline(self):
        self._force_full = True
        line = self._cur_line()
        # Auto-indent: copy leading whitespace
        indent = ''
        for c in line:
            if c in (' ', '\t'):
                indent += c
            else:
                break
        # Extra indent after ':'
        stripped = line[:self.cx].rstrip()
        if stripped.endswith(':'):
            indent += '    '

        rest = line[self.cx:]
        self.lines[self.cy] = line[:self.cx]
        self.cy += 1
        self.lines.insert(self.cy, indent + rest)
        self.cx = len(indent)
        self.modified = True

    def _backspace_insert(self):
        if self.cx > 0:
            line = self._cur_line()
            self.lines[self.cy] = line[:self.cx - 1] + line[self.cx:]
            self.cx -= 1
            self.modified = True
        elif self.cy > 0:
            # Join with previous line
            self._force_full = True
            prev = self.lines[self.cy - 1]
            cur = self.lines.pop(self.cy)
            self.cy -= 1
            self.cx = len(prev)
            self.lines[self.cy] = prev + cur
            self.modified = True

    # ── COMMAND MODE ──────────────────────────────────────────────

    def _handle_command(self, ch, o):
        if o == 0x0D or o == 0x0A:  # Enter
            self._execute_command(self._cmd_buf)
            if self.active:
                self.mode = MODE_NORMAL
        elif o == 0x08 or o == 0x7F:  # Backspace
            if self._cmd_buf:
                self._cmd_buf = self._cmd_buf[:-1]
            else:
                self.mode = MODE_NORMAL
        elif o == 0x09:  # Tab - filename completion
            self._cmd_tab_complete()
        elif o >= 0x20:
            self._cmd_buf += ch

    def _execute_command(self, cmd):
        """Execute an ex command."""
        cmd = cmd.strip()
        if not cmd:
            return

        # :w [filename]
        if cmd == 'w' or cmd.startswith('w '):
            path = cmd[2:].strip() if cmd.startswith('w ') else None
            self._save_file(path)

        # :q
        elif cmd == 'q':
            if self.modified:
                self._set_status('Unsaved changes! Use :q! to force quit or :wq', error=True)
            else:
                self._quit()

        # :q!
        elif cmd == 'q!':
            self._quit()

        # :wq / :x
        elif cmd in ('wq', 'x'):
            if self._save_file():
                self._quit()

        # :e [filename]
        elif cmd.startswith('e '):
            path = cmd[2:].strip()
            if path:
                self._push_undo()
                self.filepath = path
                self._load_file(path)
                self.syntax_enabled = path.endswith('.py')
                self.cy = 0
                self.cx = 0
                self.scroll_y = 0

        # :[number] -- go to line
        elif cmd.isdigit():
            line_num = int(cmd)
            self.cy = max(0, min(line_num - 1, len(self.lines) - 1))
            self._motion_first_nonblank()

        # :set [option]
        elif cmd.startswith('set '):
            self._handle_set(cmd[4:].strip())

        # :%s/old/new/[g] -- search & replace
        elif cmd.startswith('%s/') or cmd.startswith('s/'):
            self._search_replace(cmd)

        # :noh -- clear search highlight
        elif cmd == 'noh':
            self.search_pattern = ''

        else:
            self._set_status('Unknown command: {}'.format(cmd), error=True)

    def _handle_set(self, opt):
        if opt == 'nu' or opt == 'number':
            self.linenum_width = 4
            self._set_status('Line numbers on')
        elif opt == 'nonu' or opt == 'nonumber':
            self.linenum_width = 0
            self._set_status('Line numbers off')
        elif opt.startswith('syntax='):
            val = opt.split('=')[1]
            self.syntax_enabled = val in ('on', 'yes', '1', 'true')
        else:
            self._set_status('Unknown option: {}'.format(opt), error=True)

    def _search_replace(self, cmd):
        """Handle :%s/old/new/g command."""
        global_mode = cmd.startswith('%')
        if global_mode:
            cmd = cmd[1:]

        parts = cmd.split('/')
        if len(parts) < 3:
            self._set_status('Usage: [%]s/old/new/[g]', error=True)
            return

        old = parts[1]
        new = parts[2]
        flags = parts[3] if len(parts) > 3 else ''
        replace_all = 'g' in flags

        self._push_undo()
        self._force_full = True
        total = 0
        start_line = 0 if global_mode else self.cy
        end_line = len(self.lines) if global_mode else self.cy + 1

        for i in range(start_line, end_line):
            line = self.lines[i]
            if old in line:
                if replace_all:
                    new_line = line.replace(old, new)
                    total += line.count(old)
                else:
                    idx = line.find(old)
                    if idx >= 0:
                        new_line = line[:idx] + new + line[idx + len(old):]
                        total += 1
                    else:
                        new_line = line
                if new_line != line:
                    self.lines[i] = new_line
                    self.modified = True

        self._set_status('{} replacement{}'.format(total, 's' if total != 1 else ''))

    def _cmd_tab_complete(self):
        """Tab completion for filenames in command mode."""
        # Extract last word from command buffer
        parts = self._cmd_buf.split()
        if len(parts) < 2:
            return
        prefix = parts[-1]
        import os
        if '/' in prefix:
            dir_part = prefix.rsplit('/', 1)[0] or '/'
            name_part = prefix.rsplit('/', 1)[1]
        else:
            dir_part = '.'
            name_part = prefix

        try:
            entries = os.listdir(dir_part)
            matches = [e for e in entries if e.startswith(name_part)]
            if len(matches) == 1:
                completion = matches[0][len(name_part):]
                self._cmd_buf += completion
        except OSError:
            pass

    # ── VISUAL MODE ───────────────────────────────────────────────

    def _handle_visual(self, ch, o):
        count = self._get_count()

        # Motions work the same as normal
        if ch in 'hjkl0$wbeG{}':
            self._exec_motion(ch, count)
        elif ch == 'd' or ch == 'x':
            self._push_undo()
            self._visual_delete()
            self.mode = MODE_NORMAL
        elif ch == 'y':
            self._visual_yank()
            self.mode = MODE_NORMAL
        elif ch == 'c':
            self._push_undo()
            self._visual_delete()
            self.mode = MODE_INSERT

    def _visual_range(self):
        """Return (start_y, start_x, end_y, end_x) of visual selection, normalized."""
        sy, sx = self.visual_start_y, self.visual_start_x
        ey, ex = self.cy, self.cx
        if sy > ey or (sy == ey and sx > ex):
            sy, sx, ey, ex = ey, ex, sy, sx
        return sy, sx, ey, ex

    def _visual_delete(self):
        sy, sx, ey, ex = self._visual_range()
        if sy == ey:
            # Same line
            line = self.lines[sy]
            self.lines[sy] = line[:sx] + line[ex + 1:]
            self.cx = sx
        else:
            # Multi-line: keep start of first line, end of last line
            first = self.lines[sy][:sx]
            last = self.lines[ey][ex + 1:]
            self.lines[sy] = first + last
            for _ in range(ey - sy):
                if sy + 1 < len(self.lines):
                    self.lines.pop(sy + 1)
            self.cy = sy
            self.cx = sx
        self.modified = True

    def _visual_yank(self):
        sy, sx, ey, ex = self._visual_range()
        if sy == ey:
            self.yank_buf = [self.lines[sy][sx:ex + 1]]
            self.yank_is_linewise = False
        else:
            self.yank_buf = self.lines[sy:ey + 1]
            self.yank_is_linewise = True
        self._set_status('yanked')

    # ── SEARCH MODE ───────────────────────────────────────────────

    def _handle_search_input(self, ch, o):
        if o == 0x0D or o == 0x0A:
            self.search_pattern = self._search_buf
            self.mode = MODE_NORMAL
            if self.search_pattern:
                self._search_next()
        elif o == 0x08 or o == 0x7F:
            if self._search_buf:
                self._search_buf = self._search_buf[:-1]
            else:
                self.mode = MODE_NORMAL
        elif o >= 0x20:
            self._search_buf += ch

    def _search_next(self):
        if not self.search_pattern:
            return
        start = self.cy
        cx = self.cx + 1
        for i in range(len(self.lines)):
            idx = (start + i) % len(self.lines) if i > 0 else start
            line = self.lines[idx]
            search_from = cx if i == 0 else 0
            pos = line.find(self.search_pattern, search_from)
            if pos >= 0:
                self.cy = idx
                self.cx = pos
                return
        self._set_status('Pattern not found: {}'.format(self.search_pattern), error=True)

    def _search_prev(self):
        if not self.search_pattern:
            return
        start = self.cy
        cx = self.cx
        for i in range(len(self.lines)):
            idx = (start - i) % len(self.lines) if i > 0 else start
            line = self.lines[idx]
            search_until = cx if i == 0 else len(line)
            pos = line.rfind(self.search_pattern, 0, search_until)
            if pos >= 0:
                self.cy = idx
                self.cx = pos
                return
        self._set_status('Pattern not found: {}'.format(self.search_pattern), error=True)

    # ── Motions ───────────────────────────────────────────────────

    def _motion_left(self, n=1):
        self.cx = max(0, self.cx - n)

    def _motion_right(self, n=1):
        max_x = len(self._cur_line())
        if self.mode == MODE_NORMAL and max_x > 0:
            max_x -= 1
        self.cx = min(max_x, self.cx + n)

    def _motion_up(self, n=1):
        self.cy = max(0, self.cy - n)

    def _motion_down(self, n=1):
        self.cy = min(len(self.lines) - 1, self.cy + n)

    def _motion_word_forward(self, n=1):
        for _ in range(n):
            line = self._cur_line()
            x = self.cx
            # Skip current word chars
            while x < len(line) and line[x].isalnum():
                x += 1
            # Skip non-word chars
            while x < len(line) and not line[x].isalnum():
                x += 1
            if x >= len(line) and self.cy < len(self.lines) - 1:
                self.cy += 1
                self.cx = 0
                self._motion_first_nonblank()
            else:
                self.cx = x

    def _motion_word_backward(self, n=1):
        for _ in range(n):
            if self.cx == 0 and self.cy > 0:
                self.cy -= 1
                self.cx = len(self._cur_line())
            line = self._cur_line()
            x = self.cx - 1
            # Skip non-word chars backward
            while x > 0 and not line[x].isalnum():
                x -= 1
            # Skip word chars backward
            while x > 0 and line[x - 1].isalnum():
                x -= 1
            self.cx = max(0, x)

    def _motion_word_end(self, n=1):
        for _ in range(n):
            line = self._cur_line()
            x = self.cx + 1
            if x >= len(line):
                if self.cy < len(self.lines) - 1:
                    self.cy += 1
                    self.cx = 0
                    line = self._cur_line()
                    x = 0
                else:
                    return
            while x < len(line) and not line[x].isalnum():
                x += 1
            while x < len(line) - 1 and line[x + 1].isalnum():
                x += 1
            self.cx = min(x, max(0, len(line) - 1))

    def _motion_first_nonblank(self):
        line = self._cur_line()
        for i, c in enumerate(line):
            if c not in (' ', '\t'):
                self.cx = i
                return
        self.cx = 0

    def _motion_paragraph_up(self, n=1):
        for _ in range(n):
            y = self.cy - 1
            while y > 0 and self.lines[y].strip():
                y -= 1
            self.cy = max(0, y)

    def _motion_paragraph_down(self, n=1):
        for _ in range(n):
            y = self.cy + 1
            while y < len(self.lines) - 1 and self.lines[y].strip():
                y += 1
            self.cy = min(len(self.lines) - 1, y)

    def _motion_match_bracket(self):
        """Jump to matching bracket."""
        line = self._cur_line()
        if self.cx >= len(line):
            return
        ch = line[self.cx]
        pairs = {'(': ')', ')': '(', '[': ']', ']': '[', '{': '}', '}': '{'}
        if ch not in pairs:
            return
        target = pairs[ch]
        forward = ch in ('(', '[', '{')
        depth = 1
        y, x = self.cy, self.cx

        while depth > 0:
            if forward:
                x += 1
                if x >= len(self.lines[y]):
                    y += 1
                    x = 0
                    if y >= len(self.lines):
                        return
            else:
                x -= 1
                if x < 0:
                    y -= 1
                    if y < 0:
                        return
                    x = len(self.lines[y]) - 1
                    if x < 0:
                        continue

            if x < len(self.lines[y]):
                c = self.lines[y][x]
                if c == ch:
                    depth += 1
                elif c == target:
                    depth -= 1

        self.cy = y
        self.cx = x

    # ── Editing Operations ────────────────────────────────────────

    def _delete_char_x(self):
        """Delete char under cursor (x command)."""
        line = self._cur_line()
        if self.cx < len(line):
            self.lines[self.cy] = line[:self.cx] + line[self.cx + 1:]
            self.modified = True

    def _delete_char_at_cursor(self):
        """Delete char at cursor (Insert mode Delete key)."""
        self._delete_char_x()

    def _delete_lines(self, start, end):
        """Delete lines from start to end (inclusive)."""
        self._force_full = True
        self.yank_buf = self.lines[start:end + 1]
        self.yank_is_linewise = True
        del self.lines[start:end + 1]
        if not self.lines:
            self.lines = ['']
        self.cy = min(start, len(self.lines) - 1)
        self._ensure_cursor_bounds()
        self.modified = True

    def _yank_lines(self, start, end):
        self.yank_buf = self.lines[start:end + 1]
        self.yank_is_linewise = True

    def _paste_after(self, count=1):
        self._force_full = True
        if not self.yank_buf:
            return
        for _ in range(count):
            if self.yank_is_linewise:
                idx = self.cy + 1
                for line in self.yank_buf:
                    self.lines.insert(idx, line)
                    idx += 1
                self.cy += 1
                self._motion_first_nonblank()
            else:
                line = self._cur_line()
                text = self.yank_buf[0]
                self.lines[self.cy] = line[:self.cx + 1] + text + line[self.cx + 1:]
                self.cx += len(text)
        self.modified = True

    def _paste_before(self, count=1):
        self._force_full = True
        if not self.yank_buf:
            return
        for _ in range(count):
            if self.yank_is_linewise:
                idx = self.cy
                for line in self.yank_buf:
                    self.lines.insert(idx, line)
                    idx += 1
                self._motion_first_nonblank()
            else:
                line = self._cur_line()
                text = self.yank_buf[0]
                self.lines[self.cy] = line[:self.cx] + text + line[self.cx:]
        self.modified = True

    def _join_lines(self):
        """Join current line with next (J command)."""
        self._force_full = True
        if self.cy < len(self.lines) - 1:
            cur = self.lines[self.cy].rstrip()
            nxt = self.lines[self.cy + 1].lstrip()
            self.lines[self.cy] = cur + ' ' + nxt if cur else nxt
            self.lines.pop(self.cy + 1)
            self.cx = len(cur)
            self.modified = True

    # ── Undo ──────────────────────────────────────────────────────

    def _push_undo(self):
        entry = UndoEntry(self.lines, self.cx, self.cy)
        self._undo_stack.append(entry)
        if len(self._undo_stack) > self._max_undo:
            self._undo_stack.pop(0)

    def _undo(self):
        self._force_full = True
        if not self._undo_stack:
            self._set_status('Already at oldest change', error=True)
            return
        entry = self._undo_stack.pop()
        self.lines = entry.lines_snapshot
        self.cx = entry.cx
        self.cy = entry.cy
        self.modified = True
        self._set_status('Undo')

    # ── Rendering ─────────────────────────────────────────────────

    def _smart_redraw(self):
        """
        Intelligent partial redraw -- only updates changed rows.
        ~10-18x faster than _full_redraw for cursor movement and typing.
        """
        # Detect what changed
        scrolled = (self.scroll_y != self._prev_scroll_y or
                    self.scroll_x != self._prev_scroll_x)

        if scrolled or self._force_full:
            self._full_redraw()
            self._force_full = False
        else:
            # Partial redraw: old cursor line + new cursor line + status/cmd
            out = []
            rows_to_draw = set()

            # Previous cursor line (remove old cursor highlight)
            prev_screen = self._prev_cy - self.scroll_y
            if 0 <= prev_screen < self.text_rows:
                rows_to_draw.add(prev_screen)

            # Current cursor line (draw new cursor highlight)
            cur_screen = self.cy - self.scroll_y
            if 0 <= cur_screen < self.text_rows:
                rows_to_draw.add(cur_screen)

            # In insert mode, text changes on current line -- already included
            # For dd/yy/p etc., force full redraw
            if self.mode == MODE_VISUAL or self._force_full:
                self._full_redraw()
                return

            # Render only the changed rows
            for sr in rows_to_draw:
                self._render_row_ansi(out, sr)

            # Always update status bar and command line
            self._render_status_bar(out)
            self._render_command_line(out)
            self._render_cursor_pos(out)

            self.term.write(''.join(out))

        # Save state for next comparison
        self._prev_cy = self.cy
        self._prev_cx = self.cx
        self._prev_scroll_y = self.scroll_y
        self._prev_scroll_x = self.scroll_x

    def _render_row_ansi(self, out, screen_row):
        """Render a single screen row into the output buffer."""
        edit_width = self.cols - self.linenum_width
        doc_line = self.scroll_y + screen_row

        out.append(CSI + str(screen_row + 1) + ';1H')

        if doc_line < len(self.lines):
            # Line number
            if self.linenum_width > 0:
                ln_str = _rj(str(doc_line + 1), self.linenum_width - 1) + ' '
                out.append(C_LINENUM + ln_str + RST)

            line = self.lines[doc_line]
            vis_line = line[self.scroll_x:self.scroll_x + edit_width]

            # Render text (syntax or plain)
            if self.syntax_enabled:
                out.append(self._syntax_highlight(vis_line))
            else:
                out.append(vis_line)

            # Clear rest of line
            out.append(CSI + 'K')

            # Cursor on this line?
            if doc_line == self.cy:
                cursor_screen_x = self.cx - self.scroll_x + self.linenum_width
                if 0 <= cursor_screen_x < self.cols:
                    out.append(CSI + str(screen_row + 1) + ';' + str(cursor_screen_x + 1) + 'H')
                    if self.cx < len(line):
                        ch = line[self.cx]
                    else:
                        ch = ' '
                    if self.mode == MODE_INSERT:
                        out.append(sgr(1, 97) + ch + RST)
                    else:
                        out.append(sgr(1, 93) + ch + RST)
        else:
            # Beyond end of file
            if self.linenum_width > 0:
                out.append(' ' * self.linenum_width)
            out.append(C_TILDE + '~' + RST + CSI + 'K')

    def _render_cursor_pos(self, out):
        """Position terminal cursor for TermWidget overlay tracking."""
        if self.mode in (MODE_COMMAND, MODE_SEARCH):
            cmd_len = len(self._cmd_buf) if self.mode == MODE_COMMAND else len(self._search_buf)
            out.append(CSI + '{};{}H'.format(self.text_rows + 2, cmd_len + 2))
        else:
            screen_row = self.cy - self.scroll_y + 1
            screen_col = self.cx - self.scroll_x + self.linenum_width + 1
            if 1 <= screen_row <= self.text_rows and screen_col >= 1:
                out.append(CSI + '{};{}H'.format(screen_row, screen_col))

    def _full_redraw(self):
        """Redraw entire editor screen. Used for init, scroll, Ctrl+L."""
        out = []
        out.append(CSI + 'H')  # Home

        for screen_row in range(self.text_rows):
            vis_sy, vis_sx, vis_ey, vis_ex = (0, 0, 0, 0)
            if self.mode == MODE_VISUAL:
                vis_sy, vis_sx, vis_ey, vis_ex = self._visual_range()

            doc_line = self.scroll_y + screen_row

            if self.mode == MODE_VISUAL and doc_line < len(self.lines):
                edit_width = self.cols - self.linenum_width
                out.append(CSI + str(screen_row + 1) + ';1H')
                if self.linenum_width > 0:
                    ln_str = _rj(str(doc_line + 1), self.linenum_width - 1) + ' '
                    out.append(C_LINENUM + ln_str + RST)
                line = self.lines[doc_line]
                vis_line = line[self.scroll_x:self.scroll_x + edit_width]
                if vis_sy <= doc_line <= vis_ey:
                    out.append(self._render_visual_line(
                        doc_line, vis_line, vis_sy, vis_sx, vis_ey, vis_ex))
                else:
                    out.append(vis_line)
                out.append(CSI + 'K')
            else:
                self._render_row_ansi(out, screen_row)

        self._render_status_bar(out)
        self._render_command_line(out)
        self._render_cursor_pos(out)

        self.term.write(''.join(out))

        # Update tracking
        self._prev_cy = self.cy
        self._prev_cx = self.cx
        self._prev_scroll_y = self.scroll_y
        self._prev_scroll_x = self.scroll_x

    def _render_visual_line(self, doc_line, vis_line, sy, sx, ey, ex):
        """Render a line with visual selection highlight."""
        out = []
        for i, ch in enumerate(vis_line):
            actual_x = i + self.scroll_x
            in_sel = False
            if sy == ey:
                in_sel = doc_line == sy and sx <= actual_x <= ex
            elif doc_line == sy:
                in_sel = actual_x >= sx
            elif doc_line == ey:
                in_sel = actual_x <= ex
            else:
                in_sel = True

            if in_sel:
                out.append(C_VISUAL + ch + RST)
            else:
                out.append(ch)
        return ''.join(out)

    def _render_status_bar(self, out):
        """Render the status bar."""
        row = self.text_rows + 1
        out.append(CSI + str(row) + ';1H')

        # Mode indicator
        mode_name = MODE_NAMES.get(self.mode, '?')
        mode_str = C_STATUS_MODE + ' {} '.format(mode_name) + RST

        # Filename
        fname = self.filepath or '[No Name]'
        mod_flag = ' [+]' if self.modified else ''
        file_str = C_STATUS_FILE + ' {} '.format(fname + mod_flag) + RST

        # Position info
        pos_str = ' {}:{} '.format(self.cy + 1, self.cx + 1)
        pct = (self.cy + 1) * 100 // len(self.lines) if self.lines else 0
        pct_str = ' {}% '.format(pct)
        lines_str = ' {}L '.format(len(self.lines))

        # Build status bar
        left = mode_str + file_str
        right = C_STATUS + pos_str + lines_str + pct_str + RST

        # Calculate padding (approximate, ignoring ANSI escape lengths)
        left_visible = len(mode_name) + 2 + len(fname + mod_flag) + 2
        right_visible = len(pos_str) + len(lines_str) + len(pct_str)
        pad = self.cols - left_visible - right_visible
        if pad < 0:
            pad = 0

        out.append(left + C_STATUS + ' ' * pad + RST + right)

    def _render_command_line(self, out):
        """Render the command/message line."""
        row = self.text_rows + 2
        out.append(CSI + str(row) + ';1H')

        if self.mode == MODE_COMMAND:
            out.append(C_CMDLINE + ':' + self._cmd_buf + RST + CSI + 'K')
        elif self.mode == MODE_SEARCH:
            prefix = '/' if self.search_forward else '?'
            out.append(C_CMDLINE + prefix + self._search_buf + RST + CSI + 'K')
        elif self._status_msg:
            if self._status_is_error:
                out.append(C_STATUS_ERR + ' ' + self._status_msg + ' ' + RST + CSI + 'K')
            else:
                out.append(DIM + self._status_msg + RST + CSI + 'K')
            self._status_msg = ''
        else:
            out.append(CSI + 'K')

    # ── Syntax Highlighting ───────────────────────────────────────

    def _syntax_highlight(self, line):
        """Simple Python syntax highlighter. Returns ANSI-colored string."""
        if not line:
            return ''

        out = []
        i = 0
        n = len(line)

        while i < n:
            ch = line[i]

            # ── Comments ──
            if ch == '#':
                out.append(C_COMMENT + line[i:] + RST)
                break

            # ── Strings ──
            if ch in ('"', "'"):
                end, s = self._scan_string(line, i)
                out.append(C_STRING + s + RST)
                i = end
                continue

            # ── Decorators ──
            if ch == '@' and (i == 0 or not line[i - 1].isalnum()):
                j = i + 1
                while j < n and (line[j].isalnum() or line[j] in '_.'):
                    j += 1
                out.append(C_DECORATOR + line[i:j] + RST)
                i = j
                continue

            # ── Numbers ──
            if ch.isdigit() and (i == 0 or not line[i - 1].isalnum()):
                j = i
                while j < n and (line[j].isdigit() or line[j] in '.xXoObBaAbBcCdDeEfF_'):
                    j += 1
                out.append(C_NUMBER + line[i:j] + RST)
                i = j
                continue

            # ── Identifiers / keywords ──
            if ch.isalpha() or ch == '_':
                j = i
                while j < n and (line[j].isalnum() or line[j] == '_'):
                    j += 1
                word = line[i:j]
                if word in PY_KEYWORDS:
                    out.append(C_KEYWORD + word + RST)
                elif word in PY_BUILTINS:
                    out.append(C_BUILTIN + word + RST)
                else:
                    out.append(word)
                i = j
                continue

            # ── Operators ──
            if ch in '+-*/%=<>!&|^~':
                out.append(C_OPERATOR + ch + RST)
                i += 1
                continue

            # ── Search highlight ──
            if self.search_pattern and line[i:i + len(self.search_pattern)] == self.search_pattern:
                out.append(C_SEARCH_HL + self.search_pattern + RST)
                i += len(self.search_pattern)
                continue

            # ── Default ──
            out.append(ch)
            i += 1

        return ''.join(out)

    def _scan_string(self, line, start):
        """Scan a string literal, return (end_index, string_text)."""
        quote = line[start]
        n = len(line)
        i = start + 1

        # Triple-quote?
        if i + 1 < n and line[i] == quote and line[i + 1] == quote:
            # Triple-quoted: scan to matching triple
            triple = quote * 3
            i = start + 3
            while i < n:
                if line[i:i + 3] == triple:
                    return i + 3, line[start:i + 3]
                i += 1
            return n, line[start:]  # Unterminated

        # Regular string
        while i < n:
            if line[i] == '\\':
                i += 2
                continue
            if line[i] == quote:
                return i + 1, line[start:i + 1]
            i += 1
        return n, line[start:]  # Unterminated

    # ── Helpers ───────────────────────────────────────────────────

    def _cur_line(self):
        return self.lines[self.cy] if self.cy < len(self.lines) else ''

    def _ensure_cursor_bounds(self):
        self.cy = max(0, min(self.cy, len(self.lines) - 1))
        max_x = len(self._cur_line())
        if self.mode == MODE_NORMAL and max_x > 0:
            max_x -= 1
        self.cx = max(0, min(self.cx, max_x))

    def _scroll_into_view(self):
        """Ensure cursor is within the visible viewport."""
        if self.cy < self.scroll_y:
            self.scroll_y = self.cy
        elif self.cy >= self.scroll_y + self.text_rows:
            self.scroll_y = self.cy - self.text_rows + 1

        edit_width = self.cols - self.linenum_width
        if self.cx < self.scroll_x:
            self.scroll_x = self.cx
        elif self.cx >= self.scroll_x + edit_width:
            self.scroll_x = self.cx - edit_width + 1

    def _exit_to_normal(self):
        self.mode = MODE_NORMAL
        self._pending_op = None
        self._count_buf = ''
        if self.cx > 0 and self.cx >= len(self._cur_line()):
            self.cx = len(self._cur_line()) - 1

    def _quit(self):
        """Exit editor."""
        self.active = False
        self.term.clear_screen()

    def _get_count(self):
        """Get numeric count prefix, default 1."""
        if self._count_buf:
            try:
                n = int(self._count_buf)
            except ValueError:
                n = 1
            self._count_buf = ''
            return max(1, n)
        return 1

    def _update_linenum_width(self):
        if self.linenum_width > 0:
            digits = len(str(len(self.lines)))
            self.linenum_width = max(4, digits + 1)

    def _set_status(self, msg, error=False):
        self._status_msg = msg
        self._status_is_error = error

    def _show_file_info(self):
        """Ctrl+G: show file info."""
        total = len(self.lines)
        pct = (self.cy + 1) * 100 // total if total else 0
        name = self.filepath or '[No Name]'
        mod = ' [Modified]' if self.modified else ''
        self._set_status('"{}"{} line {}/{} ({}%)'.format(name, mod, self.cy + 1, total, pct))
