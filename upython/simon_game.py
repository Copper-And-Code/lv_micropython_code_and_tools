"""
Simon Memory Game — MicroPython + LVGL 9.3
───────────────────────────────────────────
Target displays : 1024 × 600  or  800 × 480 (touch)
Language        : English / Italiano (toggle in‑game)

Hardware setup (display driver, touch driver, lv.init(), tick source)
must be done *before* importing this module.  This file only creates
the UI and game logic on top of an already‑initialised LVGL.

Usage:
    import simon_game
    simon_game.start()
"""

import lvgl as lv
import time
import random


# ─────────────────────────── configuration ───────────────────────────

# Auto‑detect resolution from the active display
_disp = lv.display_get_default()
SCR_W = _disp.get_horizontal_resolution() if _disp else 1024
SCR_H = _disp.get_vertical_resolution() if _disp else 600

# Timing (ms)
FLASH_ON_MS      = 420      # how long a pad lights up during playback
FLASH_OFF_MS     = 180      # gap between flashes
INPUT_TIMEOUT_MS = 3000     # time allowed per tap
RESULT_SHOW_MS   = 1800     # "correct / wrong" banner duration
NEXT_ROUND_MS    = 900      # pause before next round starts

# ─────────────────────────── translations ────────────────────────────

LANG_EN = "en"
LANG_IT = "it"

_strings = {
    "title":       {"en": "SIMON",            "it": "SIMON"},
    "start":       {"en": "START",            "it": "INIZIA"},
    "score":       {"en": "Score: {}",        "it": "Punteggio: {}"},
    "best":        {"en": "Best: {}",         "it": "Record: {}"},
    "round":       {"en": "Round {}",         "it": "Turno {}"},
    "watch":       {"en": "Watch!",           "it": "Osserva!"},
    "your_turn":   {"en": "Your turn!",       "it": "Tocca a te!"},
    "correct":     {"en": "Correct!",         "it": "Corretto!"},
    "wrong":       {"en": "Wrong!",           "it": "Sbagliato!"},
    "game_over":   {"en": "Game Over",        "it": "Fine Partita"},
    "new_best":    {"en": "New Record!",      "it": "Nuovo Record!"},
    "play_again":  {"en": "PLAY AGAIN",       "it": "GIOCA ANCORA"},
    "lang_toggle": {"en": "IT 🇮🇹",           "it": "EN 🇬🇧"},
    "easy":        {"en": "Easy",             "it": "Facile"},
    "normal":      {"en": "Normal",           "it": "Normale"},
    "hard":        {"en": "Hard",             "it": "Difficile"},
    "difficulty":  {"en": "Difficulty",       "it": "Difficoltà"},
    "level":       {"en": "Level: {}",        "it": "Livello: {}"},
}

# ─────────────────────────── colour palette ──────────────────────────

# Pad colours — normal / lit / dark‑idle
PAD_COLORS = [
    # (normal,          lit/flash,       dark/idle)
    (0xD32F2F, 0xFF8A80, 0x8B1A1A),   # RED
    (0x1976D2, 0x82B1FF, 0x0D3B6F),   # BLUE
    (0x388E3C, 0x69F0AE, 0x1B4D1E),   # GREEN
    (0xFBC02D, 0xFFFF8D, 0x8C6D0B),   # YELLOW
]

BG_COLOR       = lv.color_hex(0x121212)
PANEL_BG       = lv.color_hex(0x1E1E1E)
TEXT_PRIMARY   = lv.color_hex(0xEEEEEE)
TEXT_SECONDARY = lv.color_hex(0x999999)
ACCENT         = lv.color_hex(0xBB86FC)

# ─────────────────────────── difficulty presets ──────────────────────

DIFFICULTY = {
    "easy":   {"flash_on": 600, "flash_off": 250, "timeout": 5000},
    "normal": {"flash_on": 420, "flash_off": 180, "timeout": 3000},
    "hard":   {"flash_on": 260, "flash_off": 120, "timeout": 2000},
}

# ════════════════════════════════════════════════════════════════════
#  Game class
# ════════════════════════════════════════════════════════════════════

class SimonGame:
    """Full Simon game UI and logic on LVGL 9.3."""

    # ── construction ──────────────────────────────────────────────
    def __init__(self):
        self.lang = LANG_EN
        self.difficulty = "normal"
        self.sequence = []
        self.input_idx = 0
        self.score = 0
        self.best_score = 0
        self.playing = False
        self.accepting_input = False
        self._timers = []

        # Responsive sizing
        self._is_large = SCR_W >= 1024
        self._pad_size = 200 if self._is_large else 155
        self._pad_gap  = 24  if self._is_large else 16
        self._font_lg  = lv.font_montserrat_28 if self._is_large else lv.font_montserrat_22
        self._font_md  = lv.font_montserrat_22 if self._is_large else lv.font_montserrat_16
        self._font_sm  = lv.font_montserrat_16 if self._is_large else lv.font_montserrat_14

        self._build_ui()

    # ── localisation helper ──────────────────────────────────────
    def t(self, key, *args):
        s = _strings.get(key, {}).get(self.lang, key)
        return s.format(*args) if args else s

    # ══════════════════════════════════════════════════════════════
    #  UI construction
    # ══════════════════════════════════════════════════════════════

    def _build_ui(self):
        scr = lv.screen_active()
        scr.set_style_bg_color(BG_COLOR, 0)
        scr.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        scr.clean()

        # ── main container (column flex) ─────────────────────────
        self.root = lv.obj(scr)
        self.root.set_size(SCR_W, SCR_H)
        self.root.center()
        self.root.set_style_bg_opa(lv.OPA.TRANSP, 0)
        self.root.set_style_border_width(0, 0)
        self.root.set_style_pad_all(0, 0)
        self.root.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)

        # ── top bar ──────────────────────────────────────────────
        self._build_top_bar()

        # ── centre: pads area ────────────────────────────────────
        self._build_pads()

        # ── status label (below pads) ────────────────────────────
        self._build_status_area()

        # ── start / menu overlay ─────────────────────────────────
        self._build_menu_overlay()

    # ── top bar ──────────────────────────────────────────────────
    def _build_top_bar(self):
        bar = lv.obj(self.root)
        bar_h = 54 if self._is_large else 44
        bar.set_size(SCR_W, bar_h)
        bar.set_pos(0, 0)
        bar.set_style_bg_color(PANEL_BG, 0)
        bar.set_style_border_width(0, 0)
        bar.set_style_radius(0, 0)
        bar.set_style_pad_left(16, 0)
        bar.set_style_pad_right(16, 0)
        bar.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)

        # Title
        self.lbl_title = lv.label(bar)
        self.lbl_title.set_text(self.t("title"))
        self.lbl_title.set_style_text_color(ACCENT, 0)
        self.lbl_title.set_style_text_font(self._font_lg, 0)
        self.lbl_title.align(lv.ALIGN.LEFT_MID, 8, 0)

        # Score
        self.lbl_score = lv.label(bar)
        self.lbl_score.set_text(self.t("score", 0))
        self.lbl_score.set_style_text_color(TEXT_PRIMARY, 0)
        self.lbl_score.set_style_text_font(self._font_md, 0)
        self.lbl_score.align(lv.ALIGN.CENTER, 0, 0)

        # Best
        self.lbl_best = lv.label(bar)
        self.lbl_best.set_text(self.t("best", 0))
        self.lbl_best.set_style_text_color(TEXT_SECONDARY, 0)
        self.lbl_best.set_style_text_font(self._font_sm, 0)
        self.lbl_best.align(lv.ALIGN.CENTER, 160 if self._is_large else 120, 0)

        # Language toggle button
        self.btn_lang = lv.button(bar)
        self.btn_lang.set_size(lv.SIZE_CONTENT, 36)
        self.btn_lang.align(lv.ALIGN.RIGHT_MID, -8, 0)
        self.btn_lang.set_style_bg_color(lv.color_hex(0x333333), 0)
        self.btn_lang.set_style_radius(6, 0)
        self.btn_lang.add_event_cb(self._on_lang_toggle, lv.EVENT.CLICKED, None)

        self.lbl_lang_btn = lv.label(self.btn_lang)
        self.lbl_lang_btn.set_text(self.t("lang_toggle"))
        self.lbl_lang_btn.set_style_text_color(TEXT_PRIMARY, 0)
        self.lbl_lang_btn.set_style_text_font(self._font_sm, 0)
        self.lbl_lang_btn.center()

    # ── game pads (2×2 grid) ─────────────────────────────────────
    def _build_pads(self):
        ps = self._pad_size
        gap = self._pad_gap
        grid_w = ps * 2 + gap
        grid_h = ps * 2 + gap
        ox = (SCR_W - grid_w) // 2
        bar_h = 54 if self._is_large else 44
        oy = bar_h + (SCR_H - bar_h - grid_h - 60) // 2  # 60 for status area

        self.pads = []
        self.pad_styles_normal = []
        self.pad_styles_lit = []

        positions = [
            (ox,          oy),            # top‑left  → RED
            (ox + ps + gap, oy),          # top‑right → BLUE
            (ox,          oy + ps + gap), # bot‑left  → GREEN
            (ox + ps + gap, oy + ps + gap),  # bot‑right → YELLOW
        ]

        # Corner radius per pad for the classic Simon look
        radii = [
            (ps // 2, 12, ps // 2, 12),  # TL, TR, BL, BR — top‑left big
            (12, ps // 2, 12, ps // 2),   # top‑right big
            (ps // 2, 12, ps // 2, 12),   # bot‑left big (reuse for simplicity)
            (12, ps // 2, 12, ps // 2),   # bot‑right big
        ]

        for i in range(4):
            normal_c, lit_c, idle_c = PAD_COLORS[i]

            # Normal style
            sn = lv.style_t()
            sn.init()
            sn.set_bg_color(lv.color_hex(normal_c))
            sn.set_bg_opa(lv.OPA.COVER)
            sn.set_border_width(0)
            sn.set_radius(24)
            sn.set_shadow_width(16)
            sn.set_shadow_color(lv.color_hex(normal_c))
            sn.set_shadow_opa(80)

            # Lit (flash) style
            sl = lv.style_t()
            sl.init()
            sl.set_bg_color(lv.color_hex(lit_c))
            sl.set_bg_opa(lv.OPA.COVER)
            sl.set_shadow_width(40)
            sl.set_shadow_color(lv.color_hex(lit_c))
            sl.set_shadow_opa(200)

            # Pressed style
            sp = lv.style_t()
            sp.init()
            sp.set_bg_color(lv.color_hex(lit_c))
            sp.set_bg_opa(lv.OPA.COVER)
            sp.set_shadow_width(30)
            sp.set_shadow_color(lv.color_hex(lit_c))
            sp.set_shadow_opa(180)

            obj = lv.obj(self.root)
            obj.set_size(ps, ps)
            obj.set_pos(positions[i][0], positions[i][1])
            obj.add_style(sn, 0)
            obj.add_style(sp, lv.STATE.PRESSED)
            obj.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
            obj.add_flag(lv.obj.FLAG.CLICKABLE)
            obj.add_event_cb(lambda e, idx=i: self._on_pad_press(idx), lv.EVENT.CLICKED, None)

            self.pads.append(obj)
            self.pad_styles_normal.append(sn)
            self.pad_styles_lit.append(sl)

        # Centre circle decoration
        cc = lv.obj(self.root)
        cc_size = gap + 40 if self._is_large else gap + 28
        cc.set_size(cc_size, cc_size)
        cc.set_pos(ox + ps - cc_size // 2 + gap // 2,
                    oy + ps - cc_size // 2 + gap // 2)
        cc.set_style_bg_color(PANEL_BG, 0)
        cc.set_style_border_width(3, 0)
        cc.set_style_border_color(ACCENT, 0)
        cc.set_style_radius(lv.RADIUS_CIRCLE, 0)
        cc.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        cc.clear_flag(lv.obj.FLAG.CLICKABLE)

        self.lbl_round = lv.label(cc)
        self.lbl_round.set_text("")
        self.lbl_round.set_style_text_color(TEXT_PRIMARY, 0)
        self.lbl_round.set_style_text_font(self._font_sm, 0)
        self.lbl_round.center()

    # ── status area ──────────────────────────────────────────────
    def _build_status_area(self):
        self.lbl_status = lv.label(self.root)
        self.lbl_status.set_text("")
        self.lbl_status.set_style_text_color(TEXT_SECONDARY, 0)
        self.lbl_status.set_style_text_font(self._font_md, 0)
        self.lbl_status.set_width(SCR_W)
        self.lbl_status.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        self.lbl_status.align(lv.ALIGN.BOTTOM_MID, 0, -14)

    # ── menu overlay ─────────────────────────────────────────────
    def _build_menu_overlay(self):
        self.overlay = lv.obj(self.root)
        self.overlay.set_size(SCR_W, SCR_H)
        self.overlay.set_pos(0, 0)
        self.overlay.set_style_bg_color(lv.color_hex(0x000000), 0)
        self.overlay.set_style_bg_opa(200, 0)
        self.overlay.set_style_border_width(0, 0)
        self.overlay.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)

        # Panel card
        pw = 360 if self._is_large else 290
        ph = 340 if self._is_large else 290
        panel = lv.obj(self.overlay)
        panel.set_size(pw, ph)
        panel.center()
        panel.set_style_bg_color(PANEL_BG, 0)
        panel.set_style_radius(20, 0)
        panel.set_style_border_width(2, 0)
        panel.set_style_border_color(ACCENT, 0)
        panel.set_style_pad_all(20, 0)
        panel.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        self._menu_panel = panel

        # Title on card
        self.lbl_menu_title = lv.label(panel)
        self.lbl_menu_title.set_text(self.t("title"))
        self.lbl_menu_title.set_style_text_color(ACCENT, 0)
        self.lbl_menu_title.set_style_text_font(self._font_lg, 0)
        self.lbl_menu_title.align(lv.ALIGN.TOP_MID, 0, 4)

        # Game‑over subtitle (hidden initially)
        self.lbl_menu_sub = lv.label(panel)
        self.lbl_menu_sub.set_text("")
        self.lbl_menu_sub.set_style_text_color(TEXT_SECONDARY, 0)
        self.lbl_menu_sub.set_style_text_font(self._font_sm, 0)
        self.lbl_menu_sub.align(lv.ALIGN.TOP_MID, 0, 42 if self._is_large else 34)

        # Difficulty label
        self.lbl_diff = lv.label(panel)
        self.lbl_diff.set_text(self.t("difficulty"))
        self.lbl_diff.set_style_text_color(TEXT_SECONDARY, 0)
        self.lbl_diff.set_style_text_font(self._font_sm, 0)
        self.lbl_diff.align(lv.ALIGN.TOP_MID, 0, 80 if self._is_large else 68)

        # Difficulty buttons row
        diff_y = 112 if self._is_large else 96
        btn_w = 90 if self._is_large else 72
        btn_h = 38 if self._is_large else 32
        spacing = 8
        total_w = btn_w * 3 + spacing * 2
        start_x = (pw - total_w) // 2 - 20  # account for padding

        self.diff_btns = {}
        for j, key in enumerate(["easy", "normal", "hard"]):
            btn = lv.button(panel)
            btn.set_size(btn_w, btn_h)
            btn.set_pos(start_x + j * (btn_w + spacing), diff_y)
            btn.set_style_radius(8, 0)
            btn.add_event_cb(lambda e, k=key: self._on_diff_select(k), lv.EVENT.CLICKED, None)

            lbl = lv.label(btn)
            lbl.set_text(self.t(key))
            lbl.set_style_text_font(self._font_sm, 0)
            lbl.center()

            self.diff_btns[key] = (btn, lbl)

        self._update_diff_highlight()

        # Start / Play Again button
        self.btn_start = lv.button(panel)
        sb_w = 220 if self._is_large else 180
        sb_h = 56 if self._is_large else 46
        self.btn_start.set_size(sb_w, sb_h)
        self.btn_start.align(lv.ALIGN.BOTTOM_MID, 0, -10)
        self.btn_start.set_style_bg_color(ACCENT, 0)
        self.btn_start.set_style_radius(sb_h // 2, 0)
        self.btn_start.set_style_shadow_width(20, 0)
        self.btn_start.set_style_shadow_color(ACCENT, 0)
        self.btn_start.set_style_shadow_opa(120, 0)
        self.btn_start.add_event_cb(self._on_start, lv.EVENT.CLICKED, None)

        self.lbl_start = lv.label(self.btn_start)
        self.lbl_start.set_text(self.t("start"))
        self.lbl_start.set_style_text_color(lv.color_hex(0x000000), 0)
        self.lbl_start.set_style_text_font(self._font_md, 0)
        self.lbl_start.center()

    # ── helper: refresh all text for current language ────────────
    def _refresh_lang(self):
        self.lbl_title.set_text(self.t("title"))
        self.lbl_score.set_text(self.t("score", self.score))
        self.lbl_best.set_text(self.t("best", self.best_score))
        self.lbl_lang_btn.set_text(self.t("lang_toggle"))
        self.lbl_menu_title.set_text(self.t("title") if not self.playing else self.t("game_over"))
        self.lbl_diff.set_text(self.t("difficulty"))
        self.lbl_start.set_text(self.t("start") if self.score == 0 else self.t("play_again"))
        for key in ["easy", "normal", "hard"]:
            _, lbl = self.diff_btns[key]
            lbl.set_text(self.t(key))

    # ══════════════════════════════════════════════════════════════
    #  Event handlers
    # ══════════════════════════════════════════════════════════════

    def _on_lang_toggle(self, e):
        self.lang = LANG_IT if self.lang == LANG_EN else LANG_EN
        self._refresh_lang()

    def _on_diff_select(self, key):
        self.difficulty = key
        self._update_diff_highlight()

    def _update_diff_highlight(self):
        for key, (btn, _) in self.diff_btns.items():
            if key == self.difficulty:
                btn.set_style_bg_color(ACCENT, 0)
                btn.set_style_bg_opa(lv.OPA.COVER, 0)
            else:
                btn.set_style_bg_color(lv.color_hex(0x333333), 0)
                btn.set_style_bg_opa(lv.OPA.COVER, 0)

    def _on_start(self, e):
        self.overlay.add_flag(lv.obj.FLAG.HIDDEN)
        self._start_game()

    def _on_pad_press(self, idx):
        if not self.accepting_input:
            return
        self._cancel_timers()
        self._flash_pad(idx, 150)

        if idx == self.sequence[self.input_idx]:
            self.input_idx += 1
            if self.input_idx >= len(self.sequence):
                # Round complete
                self.accepting_input = False
                self.score = len(self.sequence)
                self.lbl_score.set_text(self.t("score", self.score))
                self.lbl_status.set_text(self.t("correct"))
                self._schedule(self._next_round, NEXT_ROUND_MS)
            else:
                # Waiting for next tap — restart timeout
                self._start_input_timeout()
        else:
            # Wrong!
            self.accepting_input = False
            self._game_over()

    # ══════════════════════════════════════════════════════════════
    #  Game logic
    # ══════════════════════════════════════════════════════════════

    def _start_game(self):
        self.sequence = []
        self.score = 0
        self.input_idx = 0
        self.playing = True
        self.lbl_score.set_text(self.t("score", 0))
        self._next_round()

    def _next_round(self):
        self.accepting_input = False
        self.sequence.append(random.randint(0, 3))
        rnd = len(self.sequence)
        self.lbl_round.set_text(str(rnd))
        self.lbl_status.set_text(self.t("watch"))
        self._play_sequence(0)

    def _play_sequence(self, step):
        if step >= len(self.sequence):
            # Sequence done → player's turn
            self.input_idx = 0
            self.accepting_input = True
            self.lbl_status.set_text(self.t("your_turn"))
            self._start_input_timeout()
            return

        diff = DIFFICULTY[self.difficulty]
        idx = self.sequence[step]
        self._flash_pad(idx, diff["flash_on"])
        total = diff["flash_on"] + diff["flash_off"]
        self._schedule(lambda s=step: self._play_sequence(s + 1), total)

    def _flash_pad(self, idx, duration_ms):
        """Briefly swap to the 'lit' style, then revert."""
        pad = self.pads[idx]
        sn = self.pad_styles_normal[idx]
        sl = self.pad_styles_lit[idx]

        pad.remove_style(sn, 0)
        pad.add_style(sl, 0)

        def _revert():
            pad.remove_style(sl, 0)
            pad.add_style(sn, 0)

        self._schedule(_revert, duration_ms)

    def _start_input_timeout(self):
        diff = DIFFICULTY[self.difficulty]
        self._timeout_timer = self._schedule(self._input_timed_out, diff["timeout"])

    def _input_timed_out(self):
        if self.accepting_input:
            self.accepting_input = False
            self._game_over()

    def _game_over(self):
        self.playing = False
        new_best = self.score > self.best_score
        if new_best:
            self.best_score = self.score
            self.lbl_best.set_text(self.t("best", self.best_score))

        self.lbl_status.set_text(self.t("wrong"))

        def _show_overlay():
            self.lbl_menu_title.set_text(self.t("game_over"))
            sub = self.t("score", self.score)
            if new_best:
                sub += "  —  " + self.t("new_best")
            self.lbl_menu_sub.set_text(sub)
            self.lbl_start.set_text(self.t("play_again"))
            self.overlay.clear_flag(lv.obj.FLAG.HIDDEN)

        self._schedule(_show_overlay, RESULT_SHOW_MS)

    # ══════════════════════════════════════════════════════════════
    #  Timer helpers
    # ══════════════════════════════════════════════════════════════

    def _schedule(self, callback, ms):
        """One‑shot LVGL timer wrapper."""
        def _wrapper(timer):
            timer.delete()
            if timer in self._timers:
                self._timers.remove(timer)
            callback()

        t = lv.timer_create(_wrapper, ms, None)
        t.set_repeat_count(1)
        self._timers.append(t)
        return t

    def _cancel_timers(self):
        for t in self._timers:
            try:
                t.delete()
            except Exception:
                pass
        self._timers = []


# ════════════════════════════════════════════════════════════════════
#  Public entry point
# ════════════════════════════════════════════════════════════════════

_game = None

def start():
    """Call once after LVGL + display + touch drivers are initialised."""
    global _game
    _game = SimonGame()
    return _game
