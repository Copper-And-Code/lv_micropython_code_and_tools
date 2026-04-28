# term_widget.py — LVGL Terminal Widget v5
# Renders AnsiTerminal cell buffer onto LVGL display.
#
# v5: Progressive init to avoid watchdog reset.
#     Label renderer first (lighter), spangroup optional.
#     Calls lv.task_handler() during row creation to feed WDT.

import lvgl as lv
import gc

try:
    from config import (
        FONT_NAME, FONT_WIDTH, FONT_HEIGHT, DEFAULT_FG, DEFAULT_BG,
        COLOR_PALETTE, CURSOR_BLINK_MS
    )
except ImportError:
    FONT_NAME = 'font_unscii_16'
    FONT_WIDTH = 16
    FONT_HEIGHT = 16
    DEFAULT_FG = 7
    DEFAULT_BG = 0
    CURSOR_BLINK_MS = 500
    COLOR_PALETTE = [
        0x000000, 0xAA0000, 0x00AA00, 0xAA5500,
        0x0000AA, 0xAA00AA, 0x00AAAA, 0xAAAAAA,
        0x555555, 0xFF5555, 0x55FF55, 0xFFFF55,
        0x5555FF, 0xFF55FF, 0x55FFFF, 0xFFFFFF,
    ]

from ansi_term import DEF_FG, DEF_BG

# ── Pre-computed color hex strings for label recolor ──────────────
_HEX_COLORS = ['{:06x}'.format(c) for c in COLOR_PALETTE]

# ── Lazy API probe ────────────────────────────────────────────────
_API = None

def _probe_api():
    caps = {
        'set_recolor': False,
        'long_mode_clip': None,
    }
    scr = lv.screen_active()
    if scr is None:
        return caps

    tmp = None
    try:
        tmp = lv.obj(scr)
        lbl = lv.label(tmp)

        if hasattr(lbl, 'set_recolor'):
            try:
                lbl.set_recolor(True)
                caps['set_recolor'] = True
            except:
                pass

        if hasattr(lbl, 'set_long_mode'):
            for getter in [
                lambda: lv.label.LONG_MODE.CLIP,
                lambda: lv.label.LONG.CLIP,
                lambda: lv.label.LONG_CLIP,
            ]:
                try:
                    val = getter()
                    lbl.set_long_mode(val)
                    caps['long_mode_clip'] = val
                    break
                except:
                    continue

        lbl.delete()
    except:
        pass
    finally:
        try:
            if tmp is not None:
                tmp.delete()
        except:
            pass
    return caps


class TermWidget:
    """
    LVGL terminal renderer using label + recolor.
    
    Creates rows progressively (feeds lv.task_handler every N rows)
    to avoid watchdog reset during init.
    
    Does NOT do a full render at init — the first refresh() call
    will render the dirty lines written by the shell banner.
    """

    # How many rows to create before calling lv.task_handler()
    BATCH_SIZE = 10

    def __init__(self, parent, terminal, font=None):
        global _API
        if _API is None:
            _API = _probe_api()

        self.term = terminal
        self.font = font or getattr(lv, FONT_NAME, lv.font_unscii_8)
        self.font_w = FONT_WIDTH
        self.font_h = FONT_HEIGHT

        self._lv_colors = [lv.color_hex(c) for c in COLOR_PALETTE]
        self._bg_color = self._lv_colors[DEFAULT_BG]

        # ── Container ──
        self.cont = lv.obj(parent)
        self.cont.set_size(terminal.cols * self.font_w,
                           terminal.rows * self.font_h)
        self.cont.set_style_bg_color(self._bg_color, 0)
        self.cont.set_style_bg_opa(lv.OPA.COVER, 0)
        self.cont.set_style_radius(0, 0)
        self.cont.set_style_border_width(0, 0)
        self.cont.set_style_pad_all(0, 0)
        self.cont.remove_flag(lv.obj.FLAG.SCROLLABLE)
        self.cont.set_style_layout(0, 0)

        # ── Create row labels PROGRESSIVELY ──
        # Feed lv.task_handler() every BATCH_SIZE rows to keep WDT alive
        self._rows = []
        for r in range(terminal.rows):
            self._rows.append(self._make_label(r))
            if (r + 1) % self.BATCH_SIZE == 0:
                lv.task_handler()

        # Final task_handler after last batch
        lv.task_handler()

        # ── Cursor overlay ──
        self._cursor_obj = lv.obj(self.cont)
        self._cursor_obj.set_size(self.font_w, self.font_h)
        self._cursor_obj.set_style_bg_color(self._lv_colors[DEF_FG], 0)
        self._cursor_obj.set_style_radius(0, 0)
        self._cursor_obj.set_style_border_width(0, 0)
        self._cursor_obj.set_style_pad_all(0, 0)
        self._cursor_obj.remove_flag(lv.obj.FLAG.CLICKABLE)
        # Bring cursor on top of all row labels
        self._cursor_obj.move_foreground()

        # Detect safe opacity value (OPA._70 doesn't exist in all builds)
        self._opa_on = getattr(lv.OPA, '_50', 127)
        self._cursor_obj.set_style_bg_opa(self._opa_on, 0)

        # Cursor blink
        self._cursor_visible = True
        self._blink_timer = lv.timer_create(self._blink_cb, CURSOR_BLINK_MS, None)

        # GC counter
        self._frame_count = 0

        # NOTE: No _force_full_render() here!
        # The shell writes a banner → marks lines dirty → first refresh() renders them.
        # This keeps init fast and avoids WDT reset.

    # ── Factory ───────────────────────────────────────────────────

    def _make_label(self, row_idx):
        lbl = lv.label(self.cont)
        lbl.set_pos(0, row_idx * self.font_h)
        lbl.set_size(self.term.cols * self.font_w, self.font_h)
        lbl.set_style_text_font(self.font, 0)
        lbl.set_style_text_color(self._lv_colors[DEF_FG], 0)
        lbl.set_style_bg_opa(lv.OPA.TRANSP, 0)
        lbl.set_style_pad_all(0, 0)
        if _API['long_mode_clip'] is not None:
            try:
                lbl.set_long_mode(_API['long_mode_clip'])
            except:
                pass
        if _API['set_recolor']:
            try:
                lbl.set_recolor(True)
            except:
                pass
        lbl.set_text(' ')
        return lbl

    # ── Public API ────────────────────────────────────────────────

    def refresh(self):
        """Update only dirty lines from the terminal buffer."""
        dirty = self.term.get_dirty_lines()
        for row_idx in dirty:
            self._render_row(row_idx)

        cx, cy = self.term.get_cursor()
        self._cursor_obj.set_pos(cx * self.font_w, cy * self.font_h)
        self._cursor_obj.move_foreground()

        self._frame_count += 1
        if self._frame_count >= 60:
            self._frame_count = 0
            gc.collect()

    def set_font(self, font, fw, fh):
        self.font = font
        self.font_w = fw
        self.font_h = fh
        self.cont.set_size(self.term.cols * fw, self.term.rows * fh)
        for r in range(self.term.rows):
            self._rows[r].set_pos(0, r * fh)
            self._rows[r].set_size(self.term.cols * fw, fh)
            self._rows[r].set_style_text_font(font, 0)
        self._cursor_obj.set_size(fw, fh)
        # Mark all lines dirty so next refresh() redraws
        self.term.dirty = set(range(self.term.rows))

    def destroy(self):
        if self._blink_timer:
            self._blink_timer.delete()
            self._blink_timer = None
        self.cont.delete()

    # ── Row Rendering ─────────────────────────────────────────────

    def _render_row(self, row_idx):
        """Render one row via label with recolor markup."""
        lbl = self._rows[row_idx]
        line = self.term.get_line(row_idx)

        if _API['set_recolor']:
            text = self._build_recolor_text(line)
        else:
            text = self._build_plain_text(line)

        lbl.set_text(text)

    def _build_recolor_text(self, line):
        """
        Build LVGL recolor string: #RRGGBB text#
        Groups consecutive same-color chars for efficiency.
        """
        if not line:
            return ' '

        parts = []
        cur_fg = line[0].fg
        chars = []

        for cell in line:
            if cell.fg == cur_fg:
                ch = cell.char
                if ch == '#':
                    chars.append('\\#')
                else:
                    chars.append(ch)
            else:
                self._flush_recolor(parts, chars, cur_fg)
                cur_fg = cell.fg
                ch = cell.char
                chars = ['\\#' if ch == '#' else ch]

        self._flush_recolor(parts, chars, cur_fg)
        result = ''.join(parts).rstrip()
        return result if result else ' '

    def _flush_recolor(self, parts, chars, fg):
        if not chars:
            return
        text = ''.join(chars)
        if fg == DEF_FG:
            parts.append(text)
        else:
            parts.append('#')
            parts.append(_HEX_COLORS[fg])
            parts.append(' ')
            parts.append(text)
            parts.append('#')

    def _build_plain_text(self, line):
        if not line:
            return ' '
        text = ''.join(cell.char for cell in line).rstrip()
        return text if text else ' '

    # ── Cursor Blink ──────────────────────────────────────────────

    def _blink_cb(self, timer):
        self._cursor_visible = not self._cursor_visible
        if self._cursor_visible:
            self._cursor_obj.set_style_bg_opa(self._opa_on, 0)
        else:
            self._cursor_obj.set_style_bg_opa(lv.OPA.TRANSP, 0)
