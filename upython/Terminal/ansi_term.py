# ansi_term.py — ANSI/VT100 Terminal Emulator Buffer
# For MicroPython + LVGL on STM32H743
# Supports: SGR colors (16 colors), cursor movement, erase, scroll, line wrap

# ── ANSI Color Palette (standard 16) ──────────────────────────────
COLORS_16 = [
    0x000000,  # 0  black
    0xAA0000,  # 1  red
    0x00AA00,  # 2  green
    0xAA5500,  # 3  yellow/brown
    0x0000AA,  # 4  blue
    0xAA00AA,  # 5  magenta
    0x00AAAA,  # 6  cyan
    0xAAAAAA,  # 7  white
    0x555555,  # 8  bright black (gray)
    0xFF5555,  # 9  bright red
    0x55FF55,  # 10 bright green
    0xFFFF55,  # 11 bright yellow
    0x5555FF,  # 12 bright blue
    0xFF55FF,  # 13 bright magenta
    0x55FFFF,  # 14 bright cyan
    0xFFFFFF,  # 15 bright white
]

# Default colors
DEF_FG = 7   # white
DEF_BG = 0   # black

# Attribute flags
ATTR_BOLD      = 0x01
ATTR_UNDERLINE = 0x04
ATTR_REVERSE   = 0x08

# Parser states
S_GROUND = 0
S_ESC    = 1
S_CSI    = 2
S_OSC    = 3


class Cell:
    """Single character cell in the terminal buffer."""
    __slots__ = ('char', 'fg', 'bg', 'attr')

    def __init__(self, char=' ', fg=DEF_FG, bg=DEF_BG, attr=0):
        self.char = char
        self.fg = fg
        self.bg = bg
        self.attr = attr

    def copy_from(self, other):
        self.char = other.char
        self.fg = other.fg
        self.bg = other.bg
        self.attr = other.attr

    def reset(self, fg=DEF_FG, bg=DEF_BG):
        self.char = ' '
        self.fg = fg
        self.bg = bg
        self.attr = 0

    def equals(self, other):
        return (self.char == other.char and self.fg == other.fg
                and self.bg == other.bg and self.attr == other.attr)


class AnsiTerminal:
    """
    ANSI/VT100 terminal emulator with character cell buffer.
    
    Parses incoming byte stream, maintains a 2D grid of Cell objects,
    and tracks which lines are dirty for efficient display updates.
    """

    def __init__(self, cols=128, rows=75, onlcr=True):
        self.cols = cols
        self.rows = rows

        # Output NL→CR+LF translation (standard terminal behavior)
        self.onlcr = onlcr

        # Cursor position (0-based)
        self.cx = 0
        self.cy = 0

        # Current text attributes
        self.cur_fg = DEF_FG
        self.cur_bg = DEF_BG
        self.cur_attr = 0

        # Scroll region (top, bottom inclusive, 0-based)
        self.scroll_top = 0
        self.scroll_bot = rows - 1

        # Screen buffer: rows × cols of Cell
        self.buf = [[Cell() for _ in range(cols)] for _ in range(rows)]

        # Dirty lines tracking (set of row indices)
        self.dirty = set()

        # Parser state
        self._state = S_GROUND
        self._esc_buf = ''

        # Saved cursor position (for ESC 7 / ESC 8)
        self._saved_cx = 0
        self._saved_cy = 0
        self._saved_fg = DEF_FG
        self._saved_bg = DEF_BG
        self._saved_attr = 0

        # Callbacks
        self.on_bell = None       # called on BEL (0x07)
        self.on_title = None      # called on OSC title change

        # Mark all lines dirty initially
        self.dirty = set(range(rows))

    # ── Public API ────────────────────────────────────────────────

    def write(self, data):
        """
        Feed a string (or bytes decoded to str) into the terminal.
        This is the main entry point — call with output from shell commands
        or from UART.
        """
        for ch in data:
            self._feed_char(ch)

    def get_dirty_lines(self):
        """Return set of dirty line indices and clear the dirty set."""
        d = self.dirty
        self.dirty = set()
        return d

    def get_line(self, row):
        """Return the list of Cell objects for a given row."""
        return self.buf[row]

    def get_cursor(self):
        """Return (col, row) cursor position."""
        return (self.cx, self.cy)

    def clear_screen(self):
        """Clear entire screen and home cursor."""
        for r in range(self.rows):
            for c in range(self.cols):
                self.buf[r][c].reset()
            self.dirty.add(r)
        self.cx = 0
        self.cy = 0

    def resize(self, cols, rows):
        """Resize terminal buffer (clears content)."""
        self.cols = cols
        self.rows = rows
        self.scroll_top = 0
        self.scroll_bot = rows - 1
        self.buf = [[Cell() for _ in range(cols)] for _ in range(rows)]
        self.dirty = set(range(rows))
        self.cx = 0
        self.cy = 0

    # ── Character Processing ──────────────────────────────────────

    def _feed_char(self, ch):
        if self._state == S_GROUND:
            self._ground(ch)
        elif self._state == S_ESC:
            self._state_esc(ch)
        elif self._state == S_CSI:
            self._state_csi(ch)
        elif self._state == S_OSC:
            self._state_osc(ch)

    def _ground(self, ch):
        o = ord(ch)

        if o == 0x1B:  # ESC
            self._state = S_ESC
            self._esc_buf = ''
        elif o == 0x07:  # BEL
            if self.on_bell:
                self.on_bell()
        elif o == 0x08:  # BS (backspace)
            if self.cx > 0:
                self.cx -= 1
        elif o == 0x09:  # TAB
            self.cx = min((self.cx // 8 + 1) * 8, self.cols - 1)
        elif o == 0x0A or o == 0x0B or o == 0x0C:  # LF, VT, FF
            if self.onlcr:
                self.cx = 0  # Implicit CR
            self._line_feed()
        elif o == 0x0D:  # CR
            self.cx = 0
        elif o >= 0x20:  # Printable character
            self._put_char(ch)

    def _state_esc(self, ch):
        if ch == '[':
            self._state = S_CSI
            self._esc_buf = ''
        elif ch == ']':
            self._state = S_OSC
            self._esc_buf = ''
        elif ch == '7':  # Save cursor
            self._save_cursor()
            self._state = S_GROUND
        elif ch == '8':  # Restore cursor
            self._restore_cursor()
            self._state = S_GROUND
        elif ch == 'D':  # Index (move down, scroll if needed)
            self._line_feed()
            self._state = S_GROUND
        elif ch == 'M':  # Reverse index (move up, scroll if needed)
            self._reverse_index()
            self._state = S_GROUND
        elif ch == 'c':  # Full reset (RIS)
            self._full_reset()
            self._state = S_GROUND
        else:
            self._state = S_GROUND  # Unknown sequence, ignore

    def _state_csi(self, ch):
        o = ord(ch)
        # Collect parameter bytes (0x30-0x3F) and intermediate (0x20-0x2F)
        if 0x20 <= o <= 0x3F:
            self._esc_buf += ch
        elif 0x40 <= o <= 0x7E:
            # Final byte — dispatch
            self._dispatch_csi(ch, self._esc_buf)
            self._state = S_GROUND
        else:
            # Invalid, abort
            self._state = S_GROUND

    def _state_osc(self, ch):
        if ch == '\x07' or ch == '\\':
            # OSC terminated
            if self.on_title and self._esc_buf.startswith(('0;', '2;')):
                self.on_title(self._esc_buf[2:])
            self._state = S_GROUND
        else:
            self._esc_buf += ch
            if len(self._esc_buf) > 256:
                self._state = S_GROUND  # Safety limit

    # ── CSI Dispatch ──────────────────────────────────────────────

    def _parse_params(self, buf, default=0):
        """Parse semicolon-separated numeric parameters."""
        params = []
        for p in buf.split(';'):
            p = p.strip()
            if p == '':
                params.append(default)
            else:
                try:
                    params.append(int(p))
                except ValueError:
                    params.append(default)
        if not params:
            params.append(default)
        return params

    def _dispatch_csi(self, final, buf):
        if final == 'm':       # SGR — Select Graphic Rendition
            self._sgr(buf)
        elif final == 'H' or final == 'f':  # CUP — Cursor Position
            p = self._parse_params(buf, 1)
            row = max(0, min(p[0] - 1, self.rows - 1))
            col = max(0, min((p[1] - 1) if len(p) > 1 else 0, self.cols - 1))
            self.cy = row
            self.cx = col
        elif final == 'A':     # CUU — Cursor Up
            p = self._parse_params(buf, 1)
            self.cy = max(self.scroll_top, self.cy - p[0])
        elif final == 'B':     # CUD — Cursor Down
            p = self._parse_params(buf, 1)
            self.cy = min(self.scroll_bot, self.cy + p[0])
        elif final == 'C':     # CUF — Cursor Forward
            p = self._parse_params(buf, 1)
            self.cx = min(self.cols - 1, self.cx + p[0])
        elif final == 'D':     # CUB — Cursor Back
            p = self._parse_params(buf, 1)
            self.cx = max(0, self.cx - p[0])
        elif final == 'J':     # ED — Erase in Display
            p = self._parse_params(buf, 0)
            self._erase_display(p[0])
        elif final == 'K':     # EL — Erase in Line
            p = self._parse_params(buf, 0)
            self._erase_line(p[0])
        elif final == 'r':     # DECSTBM — Set Scroll Region
            p = self._parse_params(buf, 0)
            top = max(0, p[0] - 1) if p[0] > 0 else 0
            bot = (min(self.rows, p[1]) - 1) if len(p) > 1 and p[1] > 0 else self.rows - 1
            if top < bot:
                self.scroll_top = top
                self.scroll_bot = bot
                self.cx = 0
                self.cy = 0
        elif final == 'G':     # CHA — Cursor Horizontal Absolute
            p = self._parse_params(buf, 1)
            self.cx = max(0, min(p[0] - 1, self.cols - 1))
        elif final == 'd':     # VPA — Vertical Position Absolute
            p = self._parse_params(buf, 1)
            self.cy = max(0, min(p[0] - 1, self.rows - 1))
        elif final == 'S':     # SU — Scroll Up
            p = self._parse_params(buf, 1)
            for _ in range(p[0]):
                self._scroll_up()
        elif final == 'T':     # SD — Scroll Down
            p = self._parse_params(buf, 1)
            for _ in range(p[0]):
                self._scroll_down()
        elif final == 'n':     # DSR — Device Status Report
            pass  # Could respond with cursor position, but UART output not wired here
        elif final == 's':     # SCP — Save Cursor Position
            self._save_cursor()
        elif final == 'u':     # RCP — Restore Cursor Position
            self._restore_cursor()

    # ── SGR (Select Graphic Rendition) ────────────────────────────

    def _sgr(self, buf):
        params = self._parse_params(buf, 0)
        i = 0
        while i < len(params):
            p = params[i]
            if p == 0:
                self.cur_fg = DEF_FG
                self.cur_bg = DEF_BG
                self.cur_attr = 0
            elif p == 1:
                self.cur_attr |= ATTR_BOLD
            elif p == 4:
                self.cur_attr |= ATTR_UNDERLINE
            elif p == 7:
                self.cur_attr |= ATTR_REVERSE
            elif p == 22:
                self.cur_attr &= ~ATTR_BOLD
            elif p == 24:
                self.cur_attr &= ~ATTR_UNDERLINE
            elif p == 27:
                self.cur_attr &= ~ATTR_REVERSE
            elif 30 <= p <= 37:
                self.cur_fg = p - 30
                if self.cur_attr & ATTR_BOLD:
                    self.cur_fg += 8
            elif 40 <= p <= 47:
                self.cur_bg = p - 40
            elif 90 <= p <= 97:
                self.cur_fg = p - 90 + 8
            elif 100 <= p <= 107:
                self.cur_bg = p - 100 + 8
            elif p == 39:
                self.cur_fg = DEF_FG
            elif p == 49:
                self.cur_bg = DEF_BG
            # 256-color: ESC[38;5;Nm
            elif p == 38:
                if i + 1 < len(params) and params[i + 1] == 5:
                    if i + 2 < len(params):
                        cn = params[i + 2]
                        if cn < 16:
                            self.cur_fg = cn
                        # Extended 256 colors mapped to nearest 16
                        # (keep it simple for 16-color terminal)
                        i += 2
            elif p == 48:
                if i + 1 < len(params) and params[i + 1] == 5:
                    if i + 2 < len(params):
                        cn = params[i + 2]
                        if cn < 16:
                            self.cur_bg = cn
                        i += 2
            i += 1

    # ── Character Output ──────────────────────────────────────────

    def _put_char(self, ch):
        """Place a character at current cursor position and advance."""
        if self.cx >= self.cols:
            # Wrap to next line
            self.cx = 0
            self._line_feed()

        fg = self.cur_fg
        bg = self.cur_bg

        # Bold makes standard colors bright
        if (self.cur_attr & ATTR_BOLD) and fg < 8:
            fg += 8

        # Reverse video
        if self.cur_attr & ATTR_REVERSE:
            fg, bg = bg, fg

        cell = self.buf[self.cy][self.cx]
        cell.char = ch
        cell.fg = fg
        cell.bg = bg
        cell.attr = self.cur_attr

        self.dirty.add(self.cy)
        self.cx += 1

    # ── Line Feed & Scroll ────────────────────────────────────────

    def _line_feed(self):
        """Move cursor down one line, scrolling if at bottom of scroll region."""
        if self.cy == self.scroll_bot:
            self._scroll_up()
        elif self.cy < self.rows - 1:
            self.cy += 1

    def _reverse_index(self):
        """Move cursor up one line, scrolling down if at top of scroll region."""
        if self.cy == self.scroll_top:
            self._scroll_down()
        elif self.cy > 0:
            self.cy -= 1

    def _scroll_up(self):
        """Scroll the scroll region up by one line."""
        # Move lines up: line[top] gets discarded, line[top+1]→line[top], etc.
        old_top = self.buf[self.scroll_top]
        for r in range(self.scroll_top, self.scroll_bot):
            self.buf[r] = self.buf[r + 1]
            self.dirty.add(r)

        # Clear the bottom line (reuse the old top row object)
        for c in range(self.cols):
            old_top[c].reset()
        self.buf[self.scroll_bot] = old_top
        self.dirty.add(self.scroll_bot)

    def _scroll_down(self):
        """Scroll the scroll region down by one line."""
        old_bot = self.buf[self.scroll_bot]
        for r in range(self.scroll_bot, self.scroll_top, -1):
            self.buf[r] = self.buf[r - 1]
            self.dirty.add(r)

        for c in range(self.cols):
            old_bot[c].reset()
        self.buf[self.scroll_top] = old_bot
        self.dirty.add(self.scroll_top)

    # ── Erase Operations ──────────────────────────────────────────

    def _erase_display(self, mode):
        if mode == 0:  # Erase from cursor to end
            self._erase_line(0)
            for r in range(self.cy + 1, self.rows):
                self._clear_line(r)
        elif mode == 1:  # Erase from start to cursor
            for r in range(0, self.cy):
                self._clear_line(r)
            for c in range(0, self.cx + 1):
                self.buf[self.cy][c].reset()
            self.dirty.add(self.cy)
        elif mode == 2 or mode == 3:  # Erase entire display
            for r in range(self.rows):
                self._clear_line(r)
            self.cx = 0
            self.cy = 0

    def _erase_line(self, mode):
        if mode == 0:  # From cursor to end of line
            for c in range(self.cx, self.cols):
                self.buf[self.cy][c].reset()
        elif mode == 1:  # From start to cursor
            for c in range(0, self.cx + 1):
                self.buf[self.cy][c].reset()
        elif mode == 2:  # Entire line
            self._clear_line(self.cy)
        self.dirty.add(self.cy)

    def _clear_line(self, row):
        for c in range(self.cols):
            self.buf[row][c].reset()
        self.dirty.add(row)

    # ── Save/Restore ──────────────────────────────────────────────

    def _save_cursor(self):
        self._saved_cx = self.cx
        self._saved_cy = self.cy
        self._saved_fg = self.cur_fg
        self._saved_bg = self.cur_bg
        self._saved_attr = self.cur_attr

    def _restore_cursor(self):
        self.cx = self._saved_cx
        self.cy = self._saved_cy
        self.cur_fg = self._saved_fg
        self.cur_bg = self._saved_bg
        self.cur_attr = self._saved_attr

    def _full_reset(self):
        self.cur_fg = DEF_FG
        self.cur_bg = DEF_BG
        self.cur_attr = 0
        self.scroll_top = 0
        self.scroll_bot = self.rows - 1
        self.cx = 0
        self.cy = 0
        self.clear_screen()
