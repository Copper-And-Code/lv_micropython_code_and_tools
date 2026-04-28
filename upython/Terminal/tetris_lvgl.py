# ============================================================
#  TETRIS  –  MicroPython + LVGL 9.3
#  Target: STM32H743 · 32 MB SDRAM · LCD 1024×600 · Touch
# ============================================================
#  Metà sinistra: campo di gioco 10×20
#  Metà destra:   anteprima, punteggio, comandi (touch d-pad)
# ============================================================

# ---------- random compatibile MicroPython ----------
try:
    import urandom as _rnd
except ImportError:
    import random as _rnd

def _rand7():
    """Restituisce 0‥6 (7 pezzi)."""
    return _rnd.getrandbits(8) % 7

# =====================================================
#  COSTANTI
# =====================================================
COLS, ROWS = 10, 20
CELL        = 27                       # pixel per cella
BOARD_W     = COLS * CELL              # 270
BOARD_H     = ROWS * CELL             # 540

SCR_W, SCR_H = 1024, 600
LEFT_W       = SCR_W // 2             # 512
BOARD_X      = (LEFT_W - BOARD_W) // 2
BOARD_Y      = (SCR_H - BOARD_H) // 2

RPANEL_CX    = LEFT_W + LEFT_W // 2   # 768  centro pannello dx
PREV_CELL    = 26
PREV_N       = 4

# ---- colori (hex) ----
C_BG       = 0x0F0E17
C_EMPTY    = 0x1E1E30
C_GRID     = 0x2A2A44
C_BORDER   = 0x6A3CBC
C_TEXT     = 0xFFF5D6
C_TEXT_DIM = 0x8888AA
C_BTN_BG   = 0x2D2B55
C_BTN_PR   = 0x6A3CBC
C_GAMEOVER = 0xFF2255

# colori dei 7 tetramini  I  O  T  S  Z  J  L
PIECE_COL = [
    0x00D4FF, 0xFFDD00, 0xBB44FF,
    0x00CC66, 0xFF3333, 0x3366FF, 0xFF8811,
]

# =====================================================
#  FORME  –  ogni pezzo ha N rotazioni,
#            ogni rotazione è una lista di (riga, colonna)
# =====================================================
SHAPES = [
    # 0 = I
    [[(0,0),(0,1),(0,2),(0,3)],
     [(0,0),(1,0),(2,0),(3,0)]],
    # 1 = O
    [[(0,0),(0,1),(1,0),(1,1)]],
    # 2 = T
    [[(0,0),(0,1),(0,2),(1,1)],
     [(0,0),(1,0),(1,1),(2,0)],
     [(0,1),(1,0),(1,1),(1,2)],
     [(0,1),(1,0),(1,1),(2,1)]],
    # 3 = S
    [[(0,1),(0,2),(1,0),(1,1)],
     [(0,0),(1,0),(1,1),(2,1)]],
    # 4 = Z
    [[(0,0),(0,1),(1,1),(1,2)],
     [(0,1),(1,0),(1,1),(2,0)]],
    # 5 = J
    [[(0,0),(1,0),(1,1),(1,2)],
     [(0,0),(0,1),(1,0),(2,0)],
     [(0,0),(0,1),(0,2),(1,2)],
     [(0,1),(1,1),(2,0),(2,1)]],
    # 6 = L
    [[(0,2),(1,0),(1,1),(1,2)],
     [(0,0),(1,0),(2,0),(2,1)],
     [(0,0),(0,1),(0,2),(1,0)],
     [(0,0),(0,1),(1,1),(2,1)]],
]

PIECE_NAMES = ['I','O','T','S','Z','J','L']

# =====================================================
#  FONT helper  –  usa ciò che è compilato nel firmware
# =====================================================
def _font(size):
    for s in (size, 28, 24, 20, 18, 16, 14):
        try:
            return getattr(lv, 'font_montserrat_%d' % s)
        except Exception:
            pass
    return lv.font_default()

FONT_TITLE = _font(36)
FONT_BIG   = _font(28)
FONT_MED   = _font(20)
FONT_SMALL = _font(16)

# =====================================================
#  CLASSE  Tetris
# =====================================================
class Tetris:

    # -------------------------------------------------
    def __init__(self):
        # stato logico
        self.board   = [[0]*COLS for _ in range(ROWS)]  # 0=vuoto, 1‥7=colore
        self.score   = 0
        self.lines   = 0
        self.level   = 1
        self.piece   = 0       # indice pezzo corrente
        self.rot     = 0       # rotazione corrente
        self.px      = 0       # colonna del pezzo (top-left)
        self.py      = 0       # riga   del pezzo (top-left)
        self.nxt     = _rand7()
        self.paused  = False
        self.over    = False
        # display cache (per aggiornare solo celle cambiate)
        self.disp_board = [[-1]*COLS for _ in range(ROWS)]
        self.disp_prev  = [[-1]*PREV_N for _ in range(PREV_N)]
        # build UI
        self._build_ui()
        # primo pezzo
        self._spawn()
        self._draw_board()
        self._draw_preview()
        # timer di gioco
        self.timer = lv.timer_create(self._on_tick, 800, None)

    # =================================================
    #  UI
    # =================================================
    def _build_ui(self):
        screen.set_style_bg_color(lv.color_hex(C_BG), 0)

        # ---------- CAMPO DI GIOCO (sinistra) ----------
        self.board_cont = lv.obj(screen)
        self.board_cont.set_size(BOARD_W + 4, BOARD_H + 4)
        self.board_cont.set_pos(BOARD_X - 2, BOARD_Y - 2)
        self.board_cont.set_style_bg_color(lv.color_hex(C_GRID), 0)
        self.board_cont.set_style_border_color(lv.color_hex(C_BORDER), 0)
        self.board_cont.set_style_border_width(2, 0)
        self.board_cont.set_style_radius(4, 0)
        self.board_cont.set_style_pad_all(0, 0)
        self.board_cont.remove_flag(lv.obj.FLAG.SCROLLABLE)

        # celle
        self.cells = []
        for r in range(ROWS):
            row = []
            for c in range(COLS):
                o = lv.obj(self.board_cont)
                o.set_size(CELL - 2, CELL - 2)
                o.set_pos(c * CELL + 2, r * CELL + 2)
                o.set_style_radius(3, 0)
                o.set_style_border_width(0, 0)
                o.set_style_bg_color(lv.color_hex(C_EMPTY), 0)
                o.set_style_bg_opa(lv.OPA.COVER, 0)
                o.remove_flag(lv.obj.FLAG.SCROLLABLE | lv.obj.FLAG.CLICKABLE)
                row.append(o)
            self.cells.append(row)

        # ---------- PANNELLO DESTRO ----------
        rp = lv.obj(screen)
        rp.set_size(LEFT_W, SCR_H)
        rp.set_pos(LEFT_W, 0)
        rp.set_style_bg_opa(lv.OPA.TRANSP, 0)
        rp.set_style_border_width(0, 0)
        rp.set_style_pad_all(0, 0)
        rp.remove_flag(lv.obj.FLAG.SCROLLABLE)
        self.rpanel = rp
        cx = LEFT_W // 2   # centro locale

        # TITOLO
        t = lv.label(rp)
        t.set_text("TETRIS")
        t.set_style_text_color(lv.color_hex(C_BORDER), 0)
        t.set_style_text_font(FONT_TITLE, 0)
        t.align(lv.ALIGN.TOP_MID, 0, 10)

        # Prossimo / Next
        lb = lv.label(rp)
        lb.set_text("Prossimo / Next")
        lb.set_style_text_color(lv.color_hex(C_TEXT_DIM), 0)
        lb.set_style_text_font(FONT_SMALL, 0)
        lb.align(lv.ALIGN.TOP_MID, 0, 60)

        # contenitore anteprima
        pw = PREV_N * PREV_CELL + 4
        pc = lv.obj(rp)
        pc.set_size(pw, pw)
        pc.set_style_bg_color(lv.color_hex(C_GRID), 0)
        pc.set_style_border_color(lv.color_hex(C_BORDER), 0)
        pc.set_style_border_width(2, 0)
        pc.set_style_radius(4, 0)
        pc.set_style_pad_all(0, 0)
        pc.remove_flag(lv.obj.FLAG.SCROLLABLE)
        pc.align(lv.ALIGN.TOP_MID, 0, 82)
        self.prev_cells = []
        for r in range(PREV_N):
            row = []
            for c in range(PREV_N):
                o = lv.obj(pc)
                o.set_size(PREV_CELL - 2, PREV_CELL - 2)
                o.set_pos(c * PREV_CELL + 2, r * PREV_CELL + 2)
                o.set_style_radius(3, 0)
                o.set_style_border_width(0, 0)
                o.set_style_bg_color(lv.color_hex(C_EMPTY), 0)
                o.set_style_bg_opa(lv.OPA.COVER, 0)
                o.remove_flag(lv.obj.FLAG.SCROLLABLE | lv.obj.FLAG.CLICKABLE)
                row.append(o)
            self.prev_cells.append(row)

        # Punteggio / Score
        y0 = 200
        self._make_label(rp, "Punteggio / Score", C_TEXT_DIM, FONT_SMALL, 0, y0)
        self.lbl_score = self._make_label(rp, "0", C_TEXT, FONT_BIG, 0, y0 + 22)

        # Linee / Lines
        y0 = 270
        self._make_label(rp, "Linee / Lines", C_TEXT_DIM, FONT_SMALL, 0, y0)
        self.lbl_lines = self._make_label(rp, "0", C_TEXT, FONT_BIG, 0, y0 + 22)

        # Livello / Level
        y0 = 340
        self._make_label(rp, "Livello / Level", C_TEXT_DIM, FONT_SMALL, 0, y0)
        self.lbl_level = self._make_label(rp, "1", C_TEXT, FONT_BIG, 0, y0 + 22)

        # Game Over label (nascosta)
        self.lbl_over = lv.label(rp)
        self.lbl_over.set_text("GAME OVER")
        self.lbl_over.set_style_text_color(lv.color_hex(C_GAMEOVER), 0)
        self.lbl_over.set_style_text_font(FONT_TITLE, 0)
        self.lbl_over.align(lv.ALIGN.TOP_MID, 0, 395)
        self.lbl_over.add_flag(lv.obj.FLAG.HIDDEN)

        # ---------- D-PAD ----------
        BS = 68   # dimensione tasto
        GAP = 4
        dpad_y = 460
        dpad_cx = cx

        # su  = ruota / rotate
        self.btn_up = self._make_btn(rp, lv.SYMBOL.UP,
            dpad_cx - BS//2, dpad_y, BS, BS, self._on_rotate)
        # sinistra
        self.btn_left = self._make_btn(rp, lv.SYMBOL.LEFT,
            dpad_cx - BS - BS//2 - GAP, dpad_y + BS + GAP, BS, BS, self._on_left)
        # giù (soft drop)
        self.btn_down = self._make_btn(rp, lv.SYMBOL.DOWN,
            dpad_cx - BS//2, dpad_y + BS + GAP, BS, BS, self._on_down)
        # destra
        self.btn_right = self._make_btn(rp, lv.SYMBOL.RIGHT,
            dpad_cx + BS//2 + GAP, dpad_y + BS + GAP, BS, BS, self._on_right)

        # Pausa / Nuovo  (sotto il d-pad)
        bw = 100
        bh = 42
        by = dpad_y + 2*(BS + GAP) + 10
        self.btn_pause = self._make_btn(rp, "Pausa", cx - bw - 8, by, bw, bh, self._on_pause)
        self.btn_new   = self._make_btn(rp, "Nuovo", cx + 8,       by, bw, bh, self._on_new)

    # helpers UI
    @staticmethod
    def _make_label(parent, txt, color, font, x_ofs, y_ofs):
        lb = lv.label(parent)
        lb.set_text(txt)
        lb.set_style_text_color(lv.color_hex(color), 0)
        lb.set_style_text_font(font, 0)
        lb.align(lv.ALIGN.TOP_MID, x_ofs, y_ofs)
        return lb

    @staticmethod
    def _make_btn(parent, text, x, y, w, h, cb):
        btn = lv.button(parent)
        btn.set_size(w, h)
        btn.set_pos(x, y)
        btn.set_style_bg_color(lv.color_hex(C_BTN_BG), 0)
        btn.set_style_bg_color(lv.color_hex(C_BTN_PR), lv.STATE.PRESSED)
        btn.set_style_radius(8, 0)
        btn.set_style_border_width(0, 0)
        btn.set_style_shadow_width(0, 0)
        lb = lv.label(btn)
        lb.set_text(text)
        lb.set_style_text_color(lv.color_hex(C_TEXT), 0)
        lb.set_style_text_font(FONT_MED, 0)
        lb.center()
        btn.add_event_cb(cb, lv.EVENT.CLICKED, None)
        return btn

    # =================================================
    #  LOGICA DI GIOCO
    # =================================================
    def _cells_of(self, piece, rot, py, px):
        """Coordinate assolute (r,c) delle 4 celle del pezzo."""
        return [(py + dr, px + dc) for dr, dc in SHAPES[piece][rot]]

    def _fits(self, piece, rot, py, px):
        for r, c in self._cells_of(piece, rot, py, px):
            if r < 0 or r >= ROWS or c < 0 or c >= COLS:
                return False
            if self.board[r][c]:
                return False
        return True

    def _spawn(self):
        self.piece = self.nxt
        self.nxt   = _rand7()
        self.rot   = 0
        self.px    = (COLS - 4) // 2   # centrato
        self.py    = 0
        if not self._fits(self.piece, self.rot, self.py, self.px):
            self.over = True
            self.timer.pause()
            self.lbl_over.remove_flag(lv.obj.FLAG.HIDDEN)

    def _lock(self):
        """Fissa il pezzo corrente sulla griglia."""
        col_idx = self.piece + 1  # 1‥7
        for r, c in self._cells_of(self.piece, self.rot, self.py, self.px):
            if 0 <= r < ROWS and 0 <= c < COLS:
                self.board[r][c] = col_idx

    def _clear_lines(self):
        """Rimuove le righe complete e restituisce il numero rimosso."""
        cleared = 0
        r = ROWS - 1
        while r >= 0:
            if all(self.board[r]):
                del self.board[r]
                self.board.insert(0, [0]*COLS)
                cleared += 1
            else:
                r -= 1
        return cleared

    def _update_score(self, cleared):
        bonus = [0, 100, 300, 500, 800]
        self.score += bonus[min(cleared, 4)] * self.level
        self.lines += cleared
        new_level = self.lines // 10 + 1
        if new_level != self.level:
            self.level = new_level
            speed = max(100, 800 - (self.level - 1) * 70)
            self.timer.set_period(speed)
        self.lbl_score.set_text(str(self.score))
        self.lbl_lines.set_text(str(self.lines))
        self.lbl_level.set_text(str(self.level))

    # ---------- movimenti ----------
    def _move(self, dr, dc):
        if self.over or self.paused:
            return
        ny, nx = self.py + dr, self.px + dc
        if self._fits(self.piece, self.rot, ny, nx):
            self.py, self.px = ny, nx
            self._draw_board()
            return True
        return False

    def _rotate(self):
        if self.over or self.paused:
            return
        nrot = (self.rot + 1) % len(SHAPES[self.piece])
        # prova rotazione diretta, poi con wall kick ±1
        for dx in (0, -1, 1, -2, 2):
            if self._fits(self.piece, nrot, self.py, self.px + dx):
                self.rot = nrot
                self.px += dx
                self._draw_board()
                return
        # rotazione impossibile: non fare nulla

    def _drop_one(self):
        """Scende di una riga; se non può, fissa il pezzo."""
        if not self._move(1, 0):
            self._lock()
            cleared = self._clear_lines()
            if cleared:
                self._update_score(cleared)
            self._spawn()
            self._draw_board()
            self._draw_preview()

    # =================================================
    #  RENDERING
    # =================================================
    def _draw_board(self):
        """Aggiorna solo le celle cambiate."""
        # crea snapshot con pezzo corrente sovrapposto
        snap = [row[:] for row in self.board]
        if not self.over:
            # ombra (ghost piece) – opzionale, la saltiamo per semplicità
            ci = self.piece + 1
            for r, c in self._cells_of(self.piece, self.rot, self.py, self.px):
                if 0 <= r < ROWS and 0 <= c < COLS:
                    snap[r][c] = ci

        for r in range(ROWS):
            for c in range(COLS):
                v = snap[r][c]
                if v != self.disp_board[r][c]:
                    self.disp_board[r][c] = v
                    if v == 0:
                        self.cells[r][c].set_style_bg_color(
                            lv.color_hex(C_EMPTY), 0)
                    else:
                        self.cells[r][c].set_style_bg_color(
                            lv.color_hex(PIECE_COL[v - 1]), 0)

    def _draw_preview(self):
        """Disegna l'anteprima del prossimo pezzo."""
        filled = set(SHAPES[self.nxt][0])
        for r in range(PREV_N):
            for c in range(PREV_N):
                v = (self.nxt + 1) if (r, c) in filled else 0
                if v != self.disp_prev[r][c]:
                    self.disp_prev[r][c] = v
                    if v == 0:
                        self.prev_cells[r][c].set_style_bg_color(
                            lv.color_hex(C_EMPTY), 0)
                    else:
                        self.prev_cells[r][c].set_style_bg_color(
                            lv.color_hex(PIECE_COL[v - 1]), 0)

    # =================================================
    #  CALLBACKS
    # =================================================
    def _on_tick(self, timer):
        if not self.over and not self.paused:
            self._drop_one()

    def _on_left(self, event):
        self._move(0, -1)

    def _on_right(self, event):
        self._move(0, 1)

    def _on_down(self, event):
        self._drop_one()

    def _on_rotate(self, event):
        self._rotate()

    def _on_pause(self, event):
        if self.over:
            return
        self.paused = not self.paused
        if self.paused:
            self.timer.pause()
            # aggiorna testo bottone
            self.btn_pause.get_child(0).set_text("Riprendi")
        else:
            self.timer.resume()
            self.btn_pause.get_child(0).set_text("Pausa")

    def _on_new(self, event):
        """Nuova partita / New game."""
        self.board = [[0]*COLS for _ in range(ROWS)]
        self.score = 0
        self.lines = 0
        self.level = 1
        self.over  = False
        self.paused = False
        self.disp_board = [[-1]*COLS for _ in range(ROWS)]
        self.disp_prev  = [[-1]*PREV_N for _ in range(PREV_N)]
        self.lbl_score.set_text("0")
        self.lbl_lines.set_text("0")
        self.lbl_level.set_text("1")
        self.lbl_over.add_flag(lv.obj.FLAG.HIDDEN)
        self.btn_pause.get_child(0).set_text("Pausa")
        self.timer.set_period(800)
        self.timer.resume()
        self.nxt = _rand7()
        self._spawn()
        self._draw_board()
        self._draw_preview()


# =====================================================
#  AVVIO
# =====================================================
#  Il tuo firmware deve aver già inizializzato:
#    - il display driver (es. LTDC / DSI)
#    - il driver touch (es. GT911 / FT5x06)
#    - lv.init(), lv_display, lv_indev, tick
#
#  Basta fare:   import tetris_lvgl
#  oppure:       exec(open('tetris_lvgl.py').read())
# =====================================================

game = Tetris()
