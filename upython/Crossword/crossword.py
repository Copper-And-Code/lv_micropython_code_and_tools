# -*- coding: utf-8 -*-
# ======================================================================
#  CRUCIVERBA / CROSSWORD PUZZLE
#  MicroPython + LVGL 9.3  —  Display 1024 x 600
# ======================================================================
#
#  Struttura file di progetto / Project file structure:
#    main.py              ← questo file (UI + logica di gioco)
#    crossword_engine.py  ← motore di generazione griglia
#    words_it.py          ← database parole italiane
#    words_en.py          ← database parole inglesi
#
#  Per avviare / To start:
#    >>> import main
# ======================================================================

import lvgl as lv
from crossword_engine import generate_crossword, ACROSS, DOWN
import display_driver

# ── Rilevamento font disponibili / Available font detection ──────────
# LVGL compila solo i font abilitati in lv_conf.h.
# Questo blocco rileva quali sono disponibili e usa fallback.
def _detect_font(size, fallback_size=14):
    """Prova a caricare un font Montserrat della dimensione richiesta.
       Se non disponibile, usa il fallback."""
    attr = "font_montserrat_{}".format(size)
    if hasattr(lv, attr):
        return getattr(lv, attr)
    # Prova dimensioni vicine decrescenti fino al fallback
    for try_size in range(size, fallback_size - 1, -2):
        attr2 = "font_montserrat_{}".format(try_size)
        if hasattr(lv, attr2):
            return getattr(lv, attr2)
    # Ultima risorsa: default di LVGL
    if hasattr(lv, "font_montserrat_{}".format(fallback_size)):
        return getattr(lv, "font_montserrat_{}".format(fallback_size))
    return lv.font_default()

# Font usati nel gioco (risolti a font realmente disponibili)
FONT_XL    = _detect_font(28)   # Titolo grande schermata lingua
FONT_L     = _detect_font(22)   # Bottoni lingua
FONT_M     = _detect_font(20)   # Titolo barra superiore
FONT_BODY  = _detect_font(18)   # Lettere nella griglia
FONT_BTN   = _detect_font(16)   # Tasti tastiera, punteggio
FONT_NORM  = _detect_font(14)   # Bottoni topbar, definizione corrente
FONT_SMALL = _detect_font(12)   # Testo definizioni nel pannello
FONT_TINY  = _detect_font(10)   # Numeri nelle celle

# Log font rilevati per debug
print("Font rilevati / Detected fonts:")
for name, font in [("XL(28)", FONT_XL), ("L(22)", FONT_L),
                    ("M(20)", FONT_M), ("BODY(18)", FONT_BODY),
                    ("BTN(16)", FONT_BTN), ("NORM(14)", FONT_NORM),
                    ("SMALL(12)", FONT_SMALL), ("TINY(10)", FONT_TINY)]:
    print("  {} -> OK".format(name))

# ── Rilevamento enum label long_mode / Label long mode detection ──────
# LVGL 9.x ha cambiato la posizione dell'enum long_mode.
# Possibili percorsi: LONG_WRAP, lv.LABEL_LONG_WRAP, lv.label.LONG_WRAP
def _detect_long_mode(name):
    """Rileva il percorso corretto per l'enum label long_mode."""
    # Tentativo 1: lv.label.LONG.NAME  (LVGL 8.x style)
    try:
        obj = getattr(getattr(lv.label, 'LONG'), name)
        return obj
    except:
        pass
    # Tentativo 2: lv.LABEL_LONG_NAME  (LVGL 9.x flat enum)
    try:
        return getattr(lv, 'LABEL_LONG_{}'.format(name))
    except:
        pass
    # Tentativo 3: lv.label.LONG_NAME
    try:
        return getattr(lv.label, 'LONG_{}'.format(name))
    except:
        pass
    # Tentativo 4: lv.LABEL_LONG_MODE_NAME
    try:
        return getattr(lv, 'LABEL_LONG_MODE_{}'.format(name))
    except:
        pass
    # Tentativo 5: intero (WRAP=0, SCROLL_CIRCULAR=3)
    fallback = {"WRAP": 0, "SCROLL": 1, "DOT": 2, "SCROLL_CIRCULAR": 3, "CLIP": 4}
    return fallback.get(name, 0)

LONG_WRAP            = _detect_long_mode("WRAP")
LONG_SCROLL_CIRCULAR = _detect_long_mode("SCROLL_CIRCULAR")

print("Label long mode: WRAP={}, SCROLL_CIRCULAR={}".format(
    LONG_WRAP, LONG_SCROLL_CIRCULAR))

# ── Costanti display / Display constants ──────────────────────────────
SCREEN_W = 1024
SCREEN_H = 600

# ── Costanti griglia / Grid constants ─────────────────────────────────
GRID_ROWS = 13
GRID_COLS = 13
CELL_SIZE = 30          # pixel per cella
GRID_Y = 46             # margine superiore griglia

# Layout orizzontale: 2/3 sinistra (gioco) + 1/3 destra (definizioni)
LEFT_W = 680            # 2/3 di 1024
RIGHT_W = SCREEN_W - LEFT_W  # = 344 (~1/3)

GRID_W = GRID_COLS * CELL_SIZE   # = 390
GRID_H = GRID_ROWS * CELL_SIZE   # = 390
GRID_X = (LEFT_W - GRID_W) // 2  # griglia centrata nella zona sinistra

# Layout verticale (600px):
#   Topbar:     0  -  44  (44px)
#   Griglia:   46  - 436  (390px)
#   Def.bar:  438  - 466  (28px)
#   Tastiera: 468  - 598  (130px = 3 righe da ~40px)

# ── Colori / Colors ──────────────────────────────────────────────────
COLOR_BG         = lv.color_hex(0x1A1A2E)
COLOR_CELL_BG    = lv.color_hex(0xFFFFFF)
COLOR_CELL_BLACK = lv.color_hex(0x1A1A2E)
COLOR_CELL_SEL   = lv.color_hex(0xFFE082)   # cella selezionata (giallo)
COLOR_CELL_WORD  = lv.color_hex(0xBBDEFB)   # parola corrente (azzurro)
COLOR_CORRECT    = lv.color_hex(0xC8E6C9)   # risposta corretta (verde)
COLOR_WRONG      = lv.color_hex(0xFFCDD2)   # risposta errata (rosso)
COLOR_TEXT       = lv.color_hex(0x212121)
COLOR_NUM        = lv.color_hex(0x1565C0)
COLOR_ACCENT     = lv.color_hex(0x0D47A1)
COLOR_ACCENT2    = lv.color_hex(0xE91E63)
COLOR_PANEL_BG   = lv.color_hex(0x16213E)
COLOR_BTN_BG     = lv.color_hex(0x0F3460)
COLOR_BTN_TEXT   = lv.color_hex(0xFFFFFF)
COLOR_GRID_BORDER= lv.color_hex(0x333333)
COLOR_TITLE      = lv.color_hex(0xE94560)
COLOR_WHITE      = lv.color_hex(0xFFFFFF)
COLOR_CLUE_HL    = lv.color_hex(0x1A237E)

# ── Testi localizzati / Localized text ────────────────────────────────
TEXTS = {
    "it": {
        "title":        "CRUCIVERBA",
        "lang_select":  "Seleziona Lingua",
        "italian":      "Italiano",
        "english":      "English",
        "across":       "ORIZZONTALI",
        "down":         "VERTICALI",
        "new_game":     "Nuovo",
        "check":        "Controlla",
        "reveal":       "Rivela",
        "clear":        "Cancella",
        "score":        "Punteggio",
        "correct":      "Corretto!",
        "wrong":        "Sbagliato!",
        "complete":     "Completo!",
        "well_done":    "Bravo! Cruciverba completato!",
        "clue_label":   "Tocca una casella bianca per iniziare",
        "back":         "Lingua",
        "help":         "?",
        "tut_title":    "COME SI GIOCA",
        "tut_1":        "1. TOCCA una casella BIANCA per selezionarla",
        "tut_2":        "2. Usa la TASTIERA in basso per scrivere la lettera",
        "tut_3":        "3. Il cursore avanza automaticamente nella parola",
        "tut_4":        "4. TOCCA DI NUOVO la stessa casella per cambiare\n   direzione (orizzontale / verticale)",
        "tut_5":        "5. Tocca una DEFINIZIONE a destra per saltare\n   direttamente a quella parola",
        "tut_6":        "6. Premi CONTROLLA per verificare le risposte",
        "tut_7":        "  = casella selezionata   = parola corrente",
        "tut_close":    "HO CAPITO!",
        "dir_across":   "ORIZZONTALE",
        "dir_down":     "VERTICALE",
    },
    "en": {
        "title":        "CROSSWORD",
        "lang_select":  "Select Language",
        "italian":      "Italiano",
        "english":      "English",
        "across":       "ACROSS",
        "down":         "DOWN",
        "new_game":     "New",
        "check":        "Check",
        "reveal":       "Reveal",
        "clear":        "Clear",
        "score":        "Score",
        "correct":      "Correct!",
        "wrong":        "Wrong!",
        "complete":     "Complete!",
        "well_done":    "Well done! Puzzle completed!",
        "clue_label":   "Tap a white cell to begin",
        "back":         "Lang",
        "help":         "?",
        "tut_title":    "HOW TO PLAY",
        "tut_1":        "1. TAP a WHITE cell to select it",
        "tut_2":        "2. Use the KEYBOARD below to type a letter",
        "tut_3":        "3. The cursor moves forward automatically",
        "tut_4":        "4. TAP THE SAME cell AGAIN to switch\n   direction (across / down)",
        "tut_5":        "5. Tap a CLUE on the right panel to jump\n   directly to that word",
        "tut_6":        "6. Press CHECK to verify your answers",
        "tut_7":        "  = selected cell   = current word",
        "tut_close":    "GOT IT!",
        "dir_across":   "ACROSS",
        "dir_down":     "DOWN",
    }
}


# ======================================================================
#  CLASSE PRINCIPALE DEL GIOCO / MAIN GAME CLASS
# ======================================================================
class CrosswordGame:

    def __init__(self):
        self.lang = "it"
        self.grid = None              # CrosswordGrid
        self.user_grid = None         # lettere inserite dall'utente
        self.score = 0
        self.sel_row = -1
        self.sel_col = -1
        self.sel_dir = ACROSS
        self.sel_word_idx = -1        # indice nella lista placed_words
        self.show_tutorial = True     # mostra tutorial al primo avvio

        # Cache per performance
        self.active_cells = set()     # celle attive (pre-calcolate)
        self._prev_sel = (-1, -1)     # posizione selezionata precedente
        self._prev_word_cells = set() # celle parola precedente
        self._dirty = False           # forza full refresh al prossimo update

        # Riferimenti UI
        self.cell_objs = []           # matrice [row][col] di obj LVGL
        self.cell_labels = []         # matrice [row][col] di label
        self.cell_num_labels = []     # matrice [row][col] di label numeri
        self.clue_label = None
        self.dir_label = None         # indicatore direzione (freccia)
        self.score_label = None
        self.across_list = None
        self.down_list = None
        self.game_scr = None          # schermata di gioco (per tutorial)

        # Stili
        self._init_styles()

        # Mostra selezione lingua
        self._show_language_screen()

    # ── Stili LVGL / LVGL Styles ──────────────────────────────────────
    def _init_styles(self):
        # Stile cella bianca
        self.style_cell = lv.style_t()
        self.style_cell.init()
        self.style_cell.set_bg_color(COLOR_CELL_BG)
        self.style_cell.set_bg_opa(lv.OPA.COVER)
        self.style_cell.set_border_color(COLOR_GRID_BORDER)
        self.style_cell.set_border_width(1)
        self.style_cell.set_radius(2)
        self.style_cell.set_pad_all(0)

        # Stile cella nera
        self.style_cell_black = lv.style_t()
        self.style_cell_black.init()
        self.style_cell_black.set_bg_color(COLOR_CELL_BLACK)
        self.style_cell_black.set_bg_opa(lv.OPA.COVER)
        self.style_cell_black.set_border_color(COLOR_GRID_BORDER)
        self.style_cell_black.set_border_width(1)
        self.style_cell_black.set_radius(2)

        # Stile cella selezionata
        self.style_cell_sel = lv.style_t()
        self.style_cell_sel.init()
        self.style_cell_sel.set_bg_color(COLOR_CELL_SEL)
        self.style_cell_sel.set_bg_opa(lv.OPA.COVER)
        self.style_cell_sel.set_border_color(COLOR_ACCENT)
        self.style_cell_sel.set_border_width(2)
        self.style_cell_sel.set_radius(2)

        # Stile parola corrente
        self.style_cell_word = lv.style_t()
        self.style_cell_word.init()
        self.style_cell_word.set_bg_color(COLOR_CELL_WORD)
        self.style_cell_word.set_bg_opa(lv.OPA.COVER)
        self.style_cell_word.set_border_color(COLOR_ACCENT)
        self.style_cell_word.set_border_width(1)
        self.style_cell_word.set_radius(2)

        # Stile corretto
        self.style_cell_ok = lv.style_t()
        self.style_cell_ok.init()
        self.style_cell_ok.set_bg_color(COLOR_CORRECT)
        self.style_cell_ok.set_bg_opa(lv.OPA.COVER)
        self.style_cell_ok.set_border_color(COLOR_GRID_BORDER)
        self.style_cell_ok.set_border_width(1)

        # Stile errato
        self.style_cell_err = lv.style_t()
        self.style_cell_err.init()
        self.style_cell_err.set_bg_color(COLOR_WRONG)
        self.style_cell_err.set_bg_opa(lv.OPA.COVER)
        self.style_cell_err.set_border_color(COLOR_GRID_BORDER)
        self.style_cell_err.set_border_width(1)

        # Stile pannello
        self.style_panel = lv.style_t()
        self.style_panel.init()
        self.style_panel.set_bg_color(COLOR_PANEL_BG)
        self.style_panel.set_bg_opa(lv.OPA.COVER)
        self.style_panel.set_radius(8)
        self.style_panel.set_border_width(0)
        self.style_panel.set_pad_all(6)

        # Stile bottone
        self.style_btn = lv.style_t()
        self.style_btn.init()
        self.style_btn.set_bg_color(COLOR_BTN_BG)
        self.style_btn.set_bg_opa(lv.OPA.COVER)
        self.style_btn.set_radius(6)
        self.style_btn.set_border_width(0)
        self.style_btn.set_pad_hor(12)
        self.style_btn.set_pad_ver(8)

    # ── Testo localizzato / Localized text helper ─────────────────────
    def t(self, key):
        return TEXTS.get(self.lang, TEXTS["en"]).get(key, key)

    # ==================================================================
    #  SCHERMATA SELEZIONE LINGUA / LANGUAGE SELECTION SCREEN
    # ==================================================================
    def _show_language_screen(self):
        scr = lv.obj()
        scr.set_style_bg_color(COLOR_BG, 0)
        scr.set_style_bg_opa(lv.OPA.COVER, 0)

        # Titolo
        title = lv.label(scr)
        title.set_text("CROSSWORD / CRUCIVERBA")
        title.set_style_text_color(COLOR_TITLE, 0)
        title.set_style_text_font(FONT_XL, 0)
        title.align(lv.ALIGN.TOP_MID, 0, 80)

        # Sottotitolo
        sub = lv.label(scr)
        sub.set_text("Select Language / Seleziona Lingua")
        sub.set_style_text_color(COLOR_WHITE, 0)
        sub.set_style_text_font(FONT_BODY, 0)
        sub.align(lv.ALIGN.TOP_MID, 0, 130)

        # ── Bandiera / Bottone Italiano ───────────────────────────────
        btn_it = lv.button(scr)
        btn_it.set_size(280, 80)
        btn_it.align(lv.ALIGN.CENTER, -160, 40)
        btn_it.add_style(self.style_btn, 0)
        btn_it.set_style_bg_color(lv.color_hex(0x009246), 0)

        lbl_it = lv.label(btn_it)
        lbl_it.set_text(lv.SYMBOL.HOME + "  ITALIANO")
        lbl_it.set_style_text_color(COLOR_WHITE, 0)
        lbl_it.set_style_text_font(FONT_L, 0)
        lbl_it.center()

        btn_it.add_event_cb(lambda e: self._on_lang_selected("it"),
                            lv.EVENT.CLICKED, None)

        # ── Bandiera / Bottone Inglese ────────────────────────────────
        btn_en = lv.button(scr)
        btn_en.set_size(280, 80)
        btn_en.align(lv.ALIGN.CENTER, 160, 40)
        btn_en.add_style(self.style_btn, 0)
        btn_en.set_style_bg_color(lv.color_hex(0x00247D), 0)

        lbl_en = lv.label(btn_en)
        lbl_en.set_text(lv.SYMBOL.GPS + "  ENGLISH")
        lbl_en.set_style_text_color(COLOR_WHITE, 0)
        lbl_en.set_style_text_font(FONT_L, 0)
        lbl_en.center()

        btn_en.add_event_cb(lambda e: self._on_lang_selected("en"),
                            lv.EVENT.CLICKED, None)

        # Info versione
        ver = lv.label(scr)
        ver.set_text("MicroPython + LVGL 9.3  |  1024x600")
        ver.set_style_text_color(lv.color_hex(0x555577), 0)
        ver.set_style_text_font(FONT_NORM, 0)
        ver.align(lv.ALIGN.BOTTOM_MID, 0, -20)

        lv.screen_load(scr)

    def _on_lang_selected(self, lang):
        self.lang = lang
        self._start_new_game()

    # ==================================================================
    #  AVVIO NUOVO GIOCO / START NEW GAME
    # ==================================================================
    def _start_new_game(self):
        # Carica database parole / Load word database
        if self.lang == "it":
            import words_it as wdb
        else:
            import words_en as wdb

        word_list = wdb.get_words_by_length(3, GRID_COLS - 1)

        # Genera la griglia
        self.grid = generate_crossword(
            word_list,
            grid_rows=GRID_ROWS,
            grid_cols=GRID_COLS,
            max_words=18
        )

        # Inizializza griglia utente (vuota)
        self.user_grid = [['' for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]
        self.score = 0
        self.sel_row = -1
        self.sel_col = -1
        self.sel_dir = ACROSS
        self.sel_word_idx = -1

        # Pre-calcola cache per performance
        self.active_cells = set()
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                if self.grid.grid[r][c] != '.':
                    self.active_cells.add((r, c))

        # Cache celle per ogni parola (evita ricalcolo ad ogni highlight)
        self._word_cells_cache = []
        for word, clue, wr, wc, wd in self.grid.placed_words:
            cells = set()
            for i in range(len(word)):
                if wd == ACROSS:
                    cells.add((wr, wc + i))
                else:
                    cells.add((wr + i, wc))
            self._word_cells_cache.append(cells)

        self._prev_sel = (-1, -1)
        self._prev_word_cells = set()

        # Seleziona automaticamente la prima parola
        if self.grid.placed_words:
            w, c, r, co, d = self.grid.placed_words[0]
            self.sel_row = r
            self.sel_col = co
            self.sel_dir = d
            self.sel_word_idx = 0

        self._build_game_screen()

    # ==================================================================
    #  COSTRUZIONE SCHERMATA DI GIOCO / BUILD GAME SCREEN
    # ==================================================================
    def _build_game_screen(self):
        scr = lv.obj()
        scr.set_style_bg_color(COLOR_BG, 0)
        scr.set_style_bg_opa(lv.OPA.COVER, 0)
        scr.set_style_pad_all(0, 0)

        # ── Barra superiore / Top bar ─────────────────────────────────
        topbar = lv.obj(scr)
        topbar.set_size(SCREEN_W, 44)
        topbar.set_pos(0, 0)
        topbar.set_style_bg_color(COLOR_PANEL_BG, 0)
        topbar.set_style_bg_opa(lv.OPA.COVER, 0)
        topbar.set_style_border_width(0, 0)
        topbar.set_style_radius(0, 0)
        topbar.set_style_pad_all(4, 0)
        topbar.remove_flag(lv.obj.FLAG.SCROLLABLE)

        title_lbl = lv.label(topbar)
        title_lbl.set_text(self.t("title"))
        title_lbl.set_style_text_color(COLOR_TITLE, 0)
        title_lbl.set_style_text_font(FONT_M, 0)
        title_lbl.align(lv.ALIGN.LEFT_MID, 10, 0)

        self.score_label = lv.label(topbar)
        self.score_label.set_text(self.t("score") + ": 0")
        self.score_label.set_style_text_color(COLOR_WHITE, 0)
        self.score_label.set_style_text_font(FONT_BTN, 0)
        self.score_label.align(lv.ALIGN.CENTER, 0, 0)

        # Bottoni nella topbar
        btn_help = self._make_topbar_btn(topbar, self.t("help"),
                                         self._on_show_tutorial)
        btn_help.set_size(32, 32)
        btn_help.set_style_bg_color(COLOR_ACCENT2, 0)
        btn_help.align(lv.ALIGN.RIGHT_MID, -5, 0)

        btn_back = self._make_topbar_btn(topbar, self.t("back"),
                                         self._on_back)
        btn_back.align(lv.ALIGN.RIGHT_MID, -50, 0)

        btn_reveal = self._make_topbar_btn(topbar, self.t("reveal"),
                                           self._on_reveal_word)
        btn_reveal.align(lv.ALIGN.RIGHT_MID, -110, 0)

        btn_check = self._make_topbar_btn(topbar, self.t("check"),
                                          self._on_check)
        btn_check.align(lv.ALIGN.RIGHT_MID, -185, 0)

        btn_new = self._make_topbar_btn(topbar, self.t("new_game"),
                                        self._on_new_game)
        btn_new.align(lv.ALIGN.RIGHT_MID, -260, 0)

        # ── Griglia / Grid ────────────────────────────────────────────
        self._build_grid(scr)

        # ── Pannello definizioni / Clues panel ────────────────────────
        self._build_clues_panel(scr)

        # ── Definizione corrente + Direzione / Current clue + Direction ──
        clue_bar = lv.obj(scr)
        clue_bar.set_size(LEFT_W - 8, 28)
        clue_bar.set_pos(4, GRID_Y + GRID_H + 2)
        clue_bar.set_style_bg_color(COLOR_PANEL_BG, 0)
        clue_bar.set_style_bg_opa(lv.OPA.COVER, 0)
        clue_bar.set_style_radius(6, 0)
        clue_bar.set_style_border_width(0, 0)
        clue_bar.set_style_pad_all(3, 0)
        clue_bar.remove_flag(lv.obj.FLAG.SCROLLABLE)

        # Indicatore direzione con freccia
        self.dir_label = lv.label(clue_bar)
        self.dir_label.set_text(lv.SYMBOL.RIGHT + " ")
        self.dir_label.set_style_text_color(COLOR_CELL_SEL, 0)
        self.dir_label.set_style_text_font(FONT_BTN, 0)
        self.dir_label.align(lv.ALIGN.LEFT_MID, 2, 0)

        # Definizione corrente (con scroll)
        self.clue_label = lv.label(clue_bar)
        self.clue_label.set_long_mode(LONG_SCROLL_CIRCULAR)
        self.clue_label.set_width(LEFT_W - 60)
        self.clue_label.set_style_text_color(COLOR_WHITE, 0)
        self.clue_label.set_style_text_font(FONT_NORM, 0)
        self.clue_label.align(lv.ALIGN.LEFT_MID, 30, 0)

        # ── Tastiera virtuale / Virtual keyboard ──────────────────────
        self._build_keyboard(scr)

        # Aggiorna evidenziazione (completa alla prima build)
        self._full_highlight()
        self._update_clue_display()

        lv.screen_load(scr)
        self.game_scr = scr

        # Mostra tutorial al primo avvio
        if self.show_tutorial:
            self.show_tutorial = False
            self._show_tutorial()

    def _make_topbar_btn(self, parent, text, callback):
        btn = lv.button(parent)
        btn.set_size(lv.SIZE_CONTENT, 32)
        btn.set_style_bg_color(COLOR_BTN_BG, 0)
        btn.set_style_bg_opa(lv.OPA.COVER, 0)
        btn.set_style_radius(4, 0)
        btn.set_style_pad_hor(10, 0)
        btn.set_style_pad_ver(2, 0)
        btn.set_style_border_width(0, 0)
        lbl = lv.label(btn)
        lbl.set_text(text)
        lbl.set_style_text_color(COLOR_BTN_TEXT, 0)
        lbl.set_style_text_font(FONT_NORM, 0)
        lbl.center()
        btn.add_event_cb(lambda e: callback(), lv.EVENT.CLICKED, None)
        return btn

    # ── Costruzione griglia / Build grid ──────────────────────────────
    def _build_grid(self, parent):
        self.cell_objs = []
        self.cell_labels = []
        self.cell_num_labels = []

        grid_cont = lv.obj(parent)
        grid_cont.set_size(GRID_W + 4, GRID_H + 4)
        grid_cont.set_pos(GRID_X, GRID_Y)
        grid_cont.set_style_bg_color(COLOR_GRID_BORDER, 0)
        grid_cont.set_style_bg_opa(lv.OPA.COVER, 0)
        grid_cont.set_style_radius(4, 0)
        grid_cont.set_style_border_width(0, 0)
        grid_cont.set_style_pad_all(2, 0)
        grid_cont.remove_flag(lv.obj.FLAG.SCROLLABLE)

        for r in range(GRID_ROWS):
            row_objs = []
            row_labels = []
            row_nums = []
            for c in range(GRID_COLS):
                letter, number, active = self.grid.get_cell_info(r, c)

                cell = lv.obj(grid_cont)
                cell.set_size(CELL_SIZE - 2, CELL_SIZE - 2)
                cell.set_pos(c * CELL_SIZE, r * CELL_SIZE)
                cell.set_style_border_width(0, 0)
                cell.set_style_pad_all(0, 0)
                cell.remove_flag(lv.obj.FLAG.SCROLLABLE)

                if active:
                    cell.add_style(self.style_cell, 0)
                    cell.add_flag(lv.obj.FLAG.CLICKABLE)
                    # Cattura click sulla cella
                    cell.add_event_cb(
                        self._make_cell_click_cb(r, c),
                        lv.EVENT.CLICKED, None
                    )
                else:
                    cell.add_style(self.style_cell_black, 0)

                # Label lettera utente
                lbl = lv.label(cell)
                lbl.set_text("")
                lbl.set_style_text_color(COLOR_TEXT, 0)
                lbl.set_style_text_font(FONT_BODY, 0)
                lbl.center()

                # Label numero
                num_lbl = lv.label(cell)
                num_lbl.set_text("")
                num_lbl.set_style_text_color(COLOR_NUM, 0)
                num_lbl.set_style_text_font(FONT_TINY, 0)
                num_lbl.set_pos(2, 1)

                if number > 0:
                    num_lbl.set_text(str(number))

                row_objs.append(cell)
                row_labels.append(lbl)
                row_nums.append(num_lbl)

            self.cell_objs.append(row_objs)
            self.cell_labels.append(row_labels)
            self.cell_num_labels.append(row_nums)

    def _make_cell_click_cb(self, r, c):
        def cb(e):
            self._on_cell_clicked(r, c)
        return cb

    # ── Pannello definizioni / Clues panel ────────────────────────────
    def _build_clues_panel(self, parent):
        panel_x = LEFT_W + 2
        panel_w = RIGHT_W - 6
        panel_h = SCREEN_H - 50

        panel = lv.obj(parent)
        panel.set_size(panel_w, panel_h)
        panel.set_pos(panel_x, 48)
        panel.add_style(self.style_panel, 0)
        panel.set_style_pad_all(6, 0)

        across_clues, down_clues = self.grid.get_clues()

        # ── Titolo Orizzontali ────────────────────────────────────────
        lbl_across = lv.label(panel)
        lbl_across.set_text(self.t("across"))
        lbl_across.set_style_text_color(COLOR_TITLE, 0)
        lbl_across.set_style_text_font(FONT_NORM, 0)
        lbl_across.set_pos(4, 2)

        # Lista definizioni orizzontali
        y_off = 20
        for num, clue, word in across_clues:
            cl = lv.label(panel)
            text = "{}. {}".format(num, clue)
            cl.set_text(text)
            cl.set_long_mode(LONG_WRAP)
            cl.set_width(panel_w - 20)
            cl.set_style_text_color(COLOR_WHITE, 0)
            cl.set_style_text_font(FONT_SMALL, 0)
            cl.set_pos(4, y_off)
            y_off += 18
            # Rendi cliccabile per selezionare la parola
            cl.add_flag(lv.obj.FLAG.CLICKABLE)
            cl.add_event_cb(
                self._make_clue_click_cb(word, ACROSS),
                lv.EVENT.CLICKED, None
            )

        y_off += 8

        # ── Titolo Verticali ──────────────────────────────────────────
        lbl_down = lv.label(panel)
        lbl_down.set_text(self.t("down"))
        lbl_down.set_style_text_color(COLOR_TITLE, 0)
        lbl_down.set_style_text_font(FONT_NORM, 0)
        lbl_down.set_pos(4, y_off)
        y_off += 18

        for num, clue, word in down_clues:
            cl = lv.label(panel)
            text = "{}. {}".format(num, clue)
            cl.set_text(text)
            cl.set_long_mode(LONG_WRAP)
            cl.set_width(panel_w - 20)
            cl.set_style_text_color(COLOR_WHITE, 0)
            cl.set_style_text_font(FONT_SMALL, 0)
            cl.set_pos(4, y_off)
            y_off += 18
            cl.add_flag(lv.obj.FLAG.CLICKABLE)
            cl.add_event_cb(
                self._make_clue_click_cb(word, DOWN),
                lv.EVENT.CLICKED, None
            )

    def _make_clue_click_cb(self, word, direction):
        def cb(e):
            self._select_word_by_name(word, direction)
        return cb

    # ── Tastiera virtuale / Virtual keyboard ──────────────────────────
    def _build_keyboard(self, parent):
        kb_y = GRID_Y + GRID_H + 32     # subito dopo la barra definizione
        kb_h = SCREEN_H - kb_y - 2      # tutto lo spazio restante
        kb_w = LEFT_W - 8               # tutta la zona sinistra

        kb_cont = lv.obj(parent)
        kb_cont.set_size(kb_w, kb_h)
        kb_cont.set_pos(4, kb_y)
        kb_cont.set_style_bg_color(COLOR_PANEL_BG, 0)
        kb_cont.set_style_bg_opa(lv.OPA.COVER, 0)
        kb_cont.set_style_radius(6, 0)
        kb_cont.set_style_border_width(0, 0)
        kb_cont.set_style_pad_all(4, 0)
        kb_cont.remove_flag(lv.obj.FLAG.SCROLLABLE)

        rows = [
            "QWERTYUIOP",
            "ASDFGHJKL",
            "ZXCVBNM"
        ]

        btn_h = max(28, (kb_h - 16) // 3)
        y = 2

        for row_idx, row in enumerate(rows):
            n = len(row)
            btn_w = max(28, (kb_w - 12 - (n - 1) * 2) // n)
            total_w = n * btn_w + (n - 1) * 2
            x_start = (kb_w - total_w) // 2

            x = x_start
            for ch in row:
                btn = lv.button(kb_cont)
                btn.set_size(btn_w, btn_h)
                btn.set_pos(x, y)
                btn.set_style_bg_color(lv.color_hex(0x37474F), 0)
                btn.set_style_bg_opa(lv.OPA.COVER, 0)
                btn.set_style_radius(4, 0)
                btn.set_style_border_width(0, 0)
                btn.set_style_pad_all(0, 0)

                lbl = lv.label(btn)
                lbl.set_text(ch)
                lbl.set_style_text_color(COLOR_WHITE, 0)
                lbl.set_style_text_font(FONT_BTN, 0)
                lbl.center()

                btn.add_event_cb(
                    self._make_key_cb(ch),
                    lv.EVENT.CLICKED, None
                )

                x += btn_w + 2

            # Aggiungi backspace nell'ultima riga
            if row_idx == 2:
                bk_btn = lv.button(kb_cont)
                bk_btn.set_size(btn_w + 20, btn_h)
                bk_btn.set_pos(x + 4, y)
                bk_btn.set_style_bg_color(lv.color_hex(0xBF360C), 0)
                bk_btn.set_style_bg_opa(lv.OPA.COVER, 0)
                bk_btn.set_style_radius(4, 0)
                bk_btn.set_style_border_width(0, 0)

                bk_lbl = lv.label(bk_btn)
                bk_lbl.set_text(lv.SYMBOL.BACKSPACE)
                bk_lbl.set_style_text_color(COLOR_WHITE, 0)
                bk_lbl.center()

                bk_btn.add_event_cb(
                    lambda e: self._on_backspace(),
                    lv.EVENT.CLICKED, None
                )

            y += btn_h + 2

    def _make_key_cb(self, ch):
        def cb(e):
            self._on_key_press(ch)
        return cb

    # ==================================================================
    #  LOGICA DI GIOCO / GAME LOGIC
    # ==================================================================

    def _on_cell_clicked(self, r, c):
        """Gestisce il click su una cella della griglia."""
        if (r, c) not in self.active_cells:
            return

        # Se clicco sulla stessa cella, cambio direzione
        if r == self.sel_row and c == self.sel_col:
            self.sel_dir = DOWN if self.sel_dir == ACROSS else ACROSS

        self.sel_row = r
        self.sel_col = c

        # Trova la parola corrispondente a questa cella e direzione
        self._find_word_at_cell(r, c, self.sel_dir)
        self._update_highlight()
        self._update_clue_display()

    def _find_word_at_cell(self, r, c, preferred_dir):
        """Trova l'indice della parola che contiene la cella (usa cache)."""
        found = -1
        alt = -1

        for i, cells in enumerate(self._word_cells_cache):
            if (r, c) in cells:
                wd = self.grid.placed_words[i][4]
                if wd == preferred_dir:
                    found = i
                else:
                    alt = i

        if found >= 0:
            self.sel_word_idx = found
            self.sel_dir = preferred_dir
        elif alt >= 0:
            self.sel_word_idx = alt
            w, cl, wr, wc, wd = self.grid.placed_words[alt]
            self.sel_dir = wd
        else:
            self.sel_word_idx = -1

    def _select_word_by_name(self, word_text, direction):
        """Seleziona una parola cliccando sulla definizione."""
        for i, (w, c, r, co, d) in enumerate(self.grid.placed_words):
            if w == word_text and d == direction:
                self.sel_word_idx = i
                self.sel_row = r
                self.sel_col = co
                self.sel_dir = d
                self._update_highlight()
                self._update_clue_display()
                break

    def _on_key_press(self, ch):
        """Gestisce la pressione di un tasto della tastiera."""
        r, c = self.sel_row, self.sel_col
        if r < 0 or (r, c) not in self.active_cells:
            return

        # Inserisci la lettera
        self.user_grid[r][c] = ch
        self.cell_labels[r][c].set_text(ch)

        # Avanza alla prossima cella (non aggiorna la definizione)
        self._advance_cursor()
        self._update_highlight()

    def _on_backspace(self):
        """Gestisce la cancellazione."""
        r, c = self.sel_row, self.sel_col
        if r < 0:
            return

        # Se la cella corrente e' vuota, torna indietro
        if self.user_grid[r][c] == '':
            self._retreat_cursor()
            r, c = self.sel_row, self.sel_col

        # Cancella la cella corrente
        if (r, c) in self.active_cells:
            self.user_grid[r][c] = ''
            self.cell_labels[r][c].set_text("")

        self._update_highlight()

    def _advance_cursor(self):
        """Avanza il cursore nella direzione corrente."""
        r, c = self.sel_row, self.sel_col
        if self.sel_dir == ACROSS:
            c += 1
        else:
            r += 1
        if (r, c) in self.active_cells:
            self.sel_row = r
            self.sel_col = c

    def _retreat_cursor(self):
        """Arretra il cursore nella direzione corrente."""
        r, c = self.sel_row, self.sel_col
        if self.sel_dir == ACROSS:
            c -= 1
        else:
            r -= 1
        if (r, c) in self.active_cells:
            self.sel_row = r
            self.sel_col = c

    # ── Aggiornamento evidenziazione OTTIMIZZATO ──────────────────────
    def _update_highlight(self):
        """Aggiorna SOLO le celle che cambiano stato (differenziale)."""
        # Se dirty (dopo check/reveal), fai refresh completo
        if self._dirty:
            self._dirty = False
            self._full_highlight()
            return

        # Calcola nuove celle evidenziate
        new_sel = (self.sel_row, self.sel_col)
        if self.sel_word_idx >= 0:
            new_word_cells = self._word_cells_cache[self.sel_word_idx]
        else:
            new_word_cells = set()

        old_sel = self._prev_sel
        old_word_cells = self._prev_word_cells

        # Celle da aggiornare = quelle che cambiano stato
        # Vecchie che non sono piu' evidenziate -> bianche
        to_clear = (old_word_cells | {old_sel}) - new_word_cells - {new_sel}
        # Nuove celle parola (escludendo la selezionata)
        to_word = (new_word_cells - old_word_cells - {new_sel} - {old_sel})
        # Se la selezione e' cambiata
        sel_changed = (new_sel != old_sel)

        # Aggiorna solo le celle necessarie
        s_cell = self.style_cell
        s_sel = self.style_cell_sel
        s_word = self.style_cell_word

        for (r, c) in to_clear:
            if (r, c) in self.active_cells:
                cell = self.cell_objs[r][c]
                cell.remove_style(s_sel, 0)
                cell.remove_style(s_word, 0)
                cell.add_style(s_cell, 0)

        for (r, c) in to_word:
            if (r, c) in self.active_cells:
                cell = self.cell_objs[r][c]
                cell.remove_style(s_cell, 0)
                cell.remove_style(s_sel, 0)
                cell.add_style(s_word, 0)

        if sel_changed:
            # Ripristina vecchia selezione
            or2, oc = old_sel
            if (or2, oc) in self.active_cells:
                cell = self.cell_objs[or2][oc]
                cell.remove_style(s_sel, 0)
                if (or2, oc) in new_word_cells:
                    cell.add_style(s_word, 0)
                else:
                    cell.add_style(s_cell, 0)

            # Evidenzia nuova selezione
            nr, nc = new_sel
            if (nr, nc) in self.active_cells:
                cell = self.cell_objs[nr][nc]
                cell.remove_style(s_cell, 0)
                cell.remove_style(s_word, 0)
                cell.add_style(s_sel, 0)

        # Salva stato per prossimo aggiornamento differenziale
        self._prev_sel = new_sel
        self._prev_word_cells = new_word_cells

    def _full_highlight(self):
        """Aggiornamento completo (usato solo dopo check/reveal)."""
        word_cells = set()
        if self.sel_word_idx >= 0:
            word_cells = self._word_cells_cache[self.sel_word_idx]

        s_cell = self.style_cell
        s_sel = self.style_cell_sel
        s_word = self.style_cell_word

        for (r, c) in self.active_cells:
            cell = self.cell_objs[r][c]
            cell.remove_style(s_sel, 0)
            cell.remove_style(s_word, 0)
            cell.remove_style(s_cell, 0)
            cell.remove_style(self.style_cell_ok, 0)
            cell.remove_style(self.style_cell_err, 0)

            if r == self.sel_row and c == self.sel_col:
                cell.add_style(s_sel, 0)
            elif (r, c) in word_cells:
                cell.add_style(s_word, 0)
            else:
                cell.add_style(s_cell, 0)

        self._prev_sel = (self.sel_row, self.sel_col)
        self._prev_word_cells = word_cells

    def _update_clue_display(self):
        """Aggiorna la definizione corrente e l'indicatore di direzione."""
        if self.clue_label is None:
            return

        if self.sel_word_idx >= 0:
            w, clue, wr, wc, wd = self.grid.placed_words[self.sel_word_idx]
            num = self.grid.word_numbers.get((wr, wc), 0)
            if wd == ACROSS:
                dir_text = self.t("dir_across")
                arrow = lv.SYMBOL.RIGHT
            else:
                dir_text = self.t("dir_down")
                arrow = lv.SYMBOL.DOWN

            # Aggiorna freccia direzione
            if self.dir_label:
                self.dir_label.set_text(arrow)

            # Formato: "3 ORIZZONTALE: Serve per cucire  (3 lettere)"
            self.clue_label.set_text(
                "{} {}: {}  ({} lettere)".format(num, dir_text, clue, len(w))
            )
        else:
            if self.dir_label:
                self.dir_label.set_text("")
            self.clue_label.set_text(self.t("clue_label"))

    # ── Tutorial / Help overlay ─────────────────────────────────────
    def _on_show_tutorial(self):
        """Mostra il tutorial (anche dal bottone ?)."""
        self._show_tutorial()

    def _show_tutorial(self):
        """Mostra l'overlay con le istruzioni di gioco."""
        scr = lv.screen_active()

        # Overlay scuro
        overlay = lv.obj(scr)
        overlay.set_size(SCREEN_W, SCREEN_H)
        overlay.set_pos(0, 0)
        overlay.set_style_bg_color(lv.color_hex(0x000000), 0)
        overlay.set_style_bg_opa(180, 0)
        overlay.set_style_border_width(0, 0)
        overlay.remove_flag(lv.obj.FLAG.SCROLLABLE)

        # Box centrale
        box = lv.obj(overlay)
        box.set_size(520, 420)
        box.center()
        box.set_style_bg_color(lv.color_hex(0x0A1628), 0)
        box.set_style_bg_opa(lv.OPA.COVER, 0)
        box.set_style_radius(12, 0)
        box.set_style_border_color(COLOR_ACCENT, 0)
        box.set_style_border_width(2, 0)
        box.set_style_pad_all(20, 0)
        box.remove_flag(lv.obj.FLAG.SCROLLABLE)

        # Titolo
        t = lv.label(box)
        t.set_text(self.t("tut_title"))
        t.set_style_text_color(COLOR_TITLE, 0)
        t.set_style_text_font(FONT_L, 0)
        t.align(lv.ALIGN.TOP_MID, 0, 0)

        # Istruzioni
        y = 40
        for key in ["tut_1", "tut_2", "tut_3", "tut_4", "tut_5", "tut_6"]:
            lbl = lv.label(box)
            lbl.set_text(self.t(key))
            lbl.set_style_text_color(COLOR_WHITE, 0)
            lbl.set_style_text_font(FONT_NORM, 0)
            lbl.set_long_mode(LONG_WRAP)
            lbl.set_width(470)
            lbl.set_pos(10, y)
            y += 44

        # Legenda colori
        y += 5
        # Quadrato giallo (selezionata)
        sq1 = lv.obj(box)
        sq1.set_size(20, 20)
        sq1.set_pos(10, y)
        sq1.set_style_bg_color(COLOR_CELL_SEL, 0)
        sq1.set_style_bg_opa(lv.OPA.COVER, 0)
        sq1.set_style_radius(3, 0)
        sq1.set_style_border_color(COLOR_ACCENT, 0)
        sq1.set_style_border_width(2, 0)

        leg1 = lv.label(box)
        leg1.set_text("= " + (
            "casella selezionata" if self.lang == "it" else "selected cell"))
        leg1.set_style_text_color(COLOR_CELL_SEL, 0)
        leg1.set_style_text_font(FONT_NORM, 0)
        leg1.set_pos(36, y + 1)

        # Quadrato azzurro (parola corrente)
        sq2 = lv.obj(box)
        sq2.set_size(20, 20)
        sq2.set_pos(250, y)
        sq2.set_style_bg_color(COLOR_CELL_WORD, 0)
        sq2.set_style_bg_opa(lv.OPA.COVER, 0)
        sq2.set_style_radius(3, 0)
        sq2.set_style_border_color(COLOR_ACCENT, 0)
        sq2.set_style_border_width(1, 0)

        leg2 = lv.label(box)
        leg2.set_text("= " + (
            "parola corrente" if self.lang == "it" else "current word"))
        leg2.set_style_text_color(COLOR_CELL_WORD, 0)
        leg2.set_style_text_font(FONT_NORM, 0)
        leg2.set_pos(276, y + 1)

        # Bottone chiudi
        btn = lv.button(box)
        btn.set_size(200, 46)
        btn.align(lv.ALIGN.BOTTOM_MID, 0, -5)
        btn.set_style_bg_color(lv.color_hex(0x2E7D32), 0)
        btn.set_style_bg_opa(lv.OPA.COVER, 0)
        btn.set_style_radius(8, 0)
        btn.set_style_border_width(0, 0)
        bl = lv.label(btn)
        bl.set_text(self.t("tut_close"))
        bl.set_style_text_color(COLOR_WHITE, 0)
        bl.set_style_text_font(FONT_BTN, 0)
        bl.center()

        def close_tut(e):
            overlay.delete()
        btn.add_event_cb(close_tut, lv.EVENT.CLICKED, None)

    # ── Controllo / Check ─────────────────────────────────────────────
    def _on_check(self):
        """Controlla le parole inserite."""
        all_correct = True
        words_correct = 0

        for idx, (word, clue, wr, wc, wd) in enumerate(self.grid.placed_words):
            word_ok = True
            for i in range(len(word)):
                if wd == ACROSS:
                    r, c = wr, wc + i
                else:
                    r, c = wr + i, wc

                user_ch = self.user_grid[r][c]
                if user_ch != word[i]:
                    word_ok = False
                    all_correct = False
                    if user_ch != '':
                        # Segna cella errata brevemente
                        self.cell_objs[r][c].remove_style(self.style_cell, 0)
                        self.cell_objs[r][c].remove_style(self.style_cell_word, 0)
                        self.cell_objs[r][c].remove_style(self.style_cell_sel, 0)
                        self.cell_objs[r][c].add_style(self.style_cell_err, 0)

            if word_ok:
                words_correct += 1
                # Segna parola corretta
                for i in range(len(word)):
                    if wd == ACROSS:
                        r, c = wr, wc + i
                    else:
                        r, c = wr + i, wc
                    self.cell_objs[r][c].remove_style(self.style_cell, 0)
                    self.cell_objs[r][c].remove_style(self.style_cell_word, 0)
                    self.cell_objs[r][c].remove_style(self.style_cell_sel, 0)
                    self.cell_objs[r][c].add_style(self.style_cell_ok, 0)

        self.score = words_correct * 10
        self.score_label.set_text("{}: {}".format(self.t("score"), self.score))

        # Prossimo click fara' full refresh per pulire ok/err
        self._dirty = True

        if all_correct and self._is_grid_full():
            self._show_completion_message()

    def _is_grid_full(self):
        """Verifica se tutte le celle sono state riempite."""
        for word, clue, wr, wc, wd in self.grid.placed_words:
            for i in range(len(word)):
                if wd == ACROSS:
                    r, c = wr, wc + i
                else:
                    r, c = wr + i, wc
                if self.user_grid[r][c] == '':
                    return False
        return True

    def _on_reveal_word(self):
        """Rivela la parola corrente."""
        if self.sel_word_idx < 0:
            return

        w, cl, wr, wc, wd = self.grid.placed_words[self.sel_word_idx]

        for i in range(len(w)):
            if wd == ACROSS:
                r, c = wr, wc + i
            else:
                r, c = wr + i, wc

            self.user_grid[r][c] = w[i]
            self.cell_labels[r][c].set_text(w[i])

        # Penalita punteggio
        self.score = max(0, self.score - 5)
        self.score_label.set_text("{}: {}".format(self.t("score"), self.score))
        self._update_highlight()

    def _on_new_game(self):
        """Inizia un nuovo gioco."""
        self._start_new_game()

    def _on_back(self):
        """Torna alla schermata di selezione lingua."""
        self._show_language_screen()

    def _show_completion_message(self):
        """Mostra messaggio di completamento."""
        scr = lv.screen_active()

        # Overlay semi-trasparente
        overlay = lv.obj(scr)
        overlay.set_size(SCREEN_W, SCREEN_H)
        overlay.set_pos(0, 0)
        overlay.set_style_bg_color(lv.color_hex(0x000000), 0)
        overlay.set_style_bg_opa(150, 0)  # ~60% opacita
        overlay.set_style_border_width(0, 0)
        overlay.remove_flag(lv.obj.FLAG.SCROLLABLE)

        # Box centrale
        box = lv.obj(overlay)
        box.set_size(380, 200)
        box.center()
        box.set_style_bg_color(COLOR_PANEL_BG, 0)
        box.set_style_bg_opa(lv.OPA.COVER, 0)
        box.set_style_radius(12, 0)
        box.set_style_border_color(COLOR_TITLE, 0)
        box.set_style_border_width(2, 0)
        box.set_style_pad_all(20, 0)
        box.remove_flag(lv.obj.FLAG.SCROLLABLE)

        # Titolo
        t = lv.label(box)
        t.set_text(self.t("complete"))
        t.set_style_text_color(COLOR_TITLE, 0)
        t.set_style_text_font(FONT_L, 0)
        t.align(lv.ALIGN.TOP_MID, 0, 10)

        # Messaggio
        msg = lv.label(box)
        msg.set_text(self.t("well_done") +
                     "\n{}: {}".format(self.t("score"), self.score))
        msg.set_style_text_color(COLOR_WHITE, 0)
        msg.set_style_text_font(FONT_BTN, 0)
        msg.align(lv.ALIGN.CENTER, 0, 5)

        # Bottone chiudi
        btn = lv.button(box)
        btn.set_size(120, 40)
        btn.align(lv.ALIGN.BOTTOM_MID, 0, -5)
        btn.set_style_bg_color(COLOR_ACCENT, 0)
        btn.set_style_radius(6, 0)
        bl = lv.label(btn)
        bl.set_text("OK")
        bl.set_style_text_color(COLOR_WHITE, 0)
        bl.set_style_text_font(FONT_BTN, 0)
        bl.center()

        def close_overlay(e):
            overlay.delete()

        btn.add_event_cb(close_overlay, lv.EVENT.CLICKED, None)


# ======================================================================
#  PUNTO DI INGRESSO / ENTRY POINT
# ======================================================================
# Nota: Il display e il driver di input devono essere inizializzati
# PRIMA di eseguire questo modulo. Tipicamente nel boot.py o in un
# modulo di inizializzazione hardware specifico per la vostra board.
#
# Esempio di inizializzazione (da adattare alla vostra board):
#
#   import lvgl as lv
#   lv.init()
#
#   # Inizializza display driver (esempio per ILI9488 SPI)
#   from ili9XXX import ili9488
#   disp = ili9488(miso=12, mosi=13, clk=14, cs=15, dc=21,
#                  rst=22, width=1024, height=600, rot=0)
#
#   # Inizializza input driver (esempio touch)
#   from ft6x36 import ft6x36
#   touch = ft6x36(i2c_bus=0)
#
# Dopo l'inizializzazione HW, eseguire:
#   import main
# ======================================================================

def start():
    """Avvia il gioco del cruciverba."""
    game = CrosswordGame()
    return game


# Auto-start quando importato come modulo principale
try:
    game = start()
except Exception as e:
    print("Errore avvio gioco / Game start error:", e)
    print("Assicurarsi che LVGL e i driver display/touch siano inizializzati.")
    print("Make sure LVGL and display/touch drivers are initialized.")
