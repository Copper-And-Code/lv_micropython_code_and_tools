# tetris.py -- Tetris for MicroPython+LVGL (optimized)
# Run: runlv tetris.py
# Controls: a=left d=right w=rotate s=drop q=quit

import random

# ── Config ────────────────────────────────────────────────────────

COLS = 10
ROWS = 20
CELL = min(DISPLAY_W // (COLS + 8), DISPLAY_H // (ROWS + 2))

BOARD_X = 8
BOARD_Y = (DISPLAY_H - ROWS * CELL) // 2

COLORS = [
    0x000000,  # 0 = empty
    0x00FFFF,  # 1 = I
    0xFFFF00,  # 2 = O
    0xAA00FF,  # 3 = T
    0x00FF00,  # 4 = S
    0xFF0000,  # 5 = Z
    0x0000FF,  # 6 = J
    0xFF8800,  # 7 = L
]

SHAPES = [
    [[(0,0),(0,1),(0,2),(0,3)], [(0,0),(1,0),(2,0),(3,0)]],
    [[(0,0),(0,1),(1,0),(1,1)]],
    [[(0,0),(0,1),(0,2),(1,1)], [(0,0),(1,0),(2,0),(1,1)],
     [(0,1),(1,0),(1,1),(1,2)], [(0,0),(1,0),(2,0),(1,-1)]],
    [[(0,1),(0,2),(1,0),(1,1)], [(0,0),(1,0),(1,1),(2,1)]],
    [[(0,0),(0,1),(1,1),(1,2)], [(0,1),(1,0),(1,1),(2,0)]],
    [[(0,0),(1,0),(1,1),(1,2)], [(0,0),(0,1),(1,0),(2,0)],
     [(0,0),(0,1),(0,2),(1,2)], [(0,0),(1,0),(2,0),(2,-1)]],
    [[(0,2),(1,0),(1,1),(1,2)], [(0,0),(1,0),(2,0),(2,1)],
     [(0,0),(0,1),(0,2),(1,0)], [(0,0),(0,1),(1,1),(2,1)]],
]

# ── State ─────────────────────────────────────────────────────────

board = [[0] * COLS for _ in range(ROWS)]
score = 0
game_over = False
piece_type = 0
piece_rot = 0
piece_r = 0
piece_c = 0

# Previous display state for dirty tracking
prev_display = [[0] * COLS for _ in range(ROWS)]

# ── LVGL Setup ────────────────────────────────────────────────────

# Board border
border = lv.obj(screen)
border.set_pos(BOARD_X - 2, BOARD_Y - 2)
border.set_size(COLS * CELL + 4, ROWS * CELL + 4)
border.set_style_bg_opa(lv.OPA.TRANSP, 0)
border.set_style_border_color(lv.color_hex(0x444444), 0)
border.set_style_border_width(2, 0)
border.set_style_radius(0, 0)
border.remove_flag(lv.obj.FLAG.SCROLLABLE)
border.move_foreground()

# Pre-create cell grid
cells = []
for r in range(ROWS):
    row = []
    for c in range(COLS):
        cell = lv.obj(screen)
        cell.set_pos(BOARD_X + c * CELL, BOARD_Y + r * CELL)
        cell.set_size(CELL - 1, CELL - 1)
        cell.set_style_radius(1, 0)
        cell.set_style_border_width(0, 0)
        cell.set_style_bg_color(lv.color_hex(0x000000), 0)
        cell.set_style_bg_opa(lv.OPA.COVER, 0)
        cell.set_style_pad_all(0, 0)
        cell.remove_flag(lv.obj.FLAG.SCROLLABLE | lv.obj.FLAG.CLICKABLE)
        cell.move_foreground()
        row.append(cell)
    cells.append(row)
    # Feed watchdog every 5 rows
    if (r + 1) % 5 == 0:
        lv.task_handler()

# Pre-compute LVGL color objects
lv_colors = [lv.color_hex(c) for c in COLORS]

# Labels
score_lbl = lv.label(screen)
score_lbl.set_pos(BOARD_X + COLS * CELL + 20, BOARD_Y)
score_lbl.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
try:
    score_lbl.set_style_text_font(lv.font_unscii_16, 0)
except:
    pass
score_lbl.set_text('Score: 0')
score_lbl.move_foreground()

ctrl_lbl = lv.label(screen)
ctrl_lbl.set_pos(BOARD_X + COLS * CELL + 20, BOARD_Y + 40)
ctrl_lbl.set_style_text_color(lv.color_hex(0x666666), 0)
try:
    ctrl_lbl.set_style_text_font(lv.font_unscii_16, 0)
except:
    pass
ctrl_lbl.set_text('a=left\nd=right\nw=rotate\ns=drop\nq=quit')
ctrl_lbl.move_foreground()

go_lbl = lv.label(screen)
go_lbl.set_pos(BOARD_X + 10, BOARD_Y + ROWS * CELL // 2 - 10)
go_lbl.set_style_text_color(lv.color_hex(0xFF0000), 0)
try:
    go_lbl.set_style_text_font(lv.font_unscii_16, 0)
except:
    pass
go_lbl.set_text('')
go_lbl.move_foreground()

lv.task_handler()

# ── Logic ─────────────────────────────────────────────────────────

def get_shape():
    return SHAPES[piece_type][piece_rot % len(SHAPES[piece_type])]

def valid_pos(r, c, rot):
    shape = SHAPES[piece_type][rot % len(SHAPES[piece_type])]
    for dr, dc in shape:
        nr, nc = r + dr, c + dc
        if nr < 0 or nr >= ROWS or nc < 0 or nc >= COLS:
            return False
        if board[nr][nc] != 0:
            return False
    return True

def spawn_piece():
    global piece_type, piece_rot, piece_r, piece_c, game_over
    piece_type = random.randint(0, len(SHAPES) - 1)
    piece_rot = 0
    piece_r = 0
    piece_c = COLS // 2 - 1
    if not valid_pos(piece_r, piece_c, piece_rot):
        game_over = True

def lock_piece():
    global score
    shape = get_shape()
    color_idx = piece_type + 1
    for dr, dc in shape:
        board[piece_r + dr][piece_c + dc] = color_idx
    lines = 0
    r = ROWS - 1
    while r >= 0:
        if all(board[r][c] != 0 for c in range(COLS)):
            del board[r]
            board.insert(0, [0] * COLS)
            lines += 1
        else:
            r -= 1
    if lines > 0:
        score += [0, 100, 300, 500, 800][min(lines, 4)]
        score_lbl.set_text('Score: {}'.format(score))

def draw_board():
    """Update ONLY cells that changed since last frame."""
    # Build current display with piece overlay
    shape = get_shape() if not game_over else []
    ci = piece_type + 1

    changed = 0
    for r in range(ROWS):
        for c in range(COLS):
            val = board[r][c]
            # Overlay piece
            if not game_over:
                for dr, dc in shape:
                    if piece_r + dr == r and piece_c + dc == c:
                        val = ci
                        break
            # Only update if changed
            if val != prev_display[r][c]:
                cells[r][c].set_style_bg_color(lv_colors[val], 0)
                prev_display[r][c] = val
                changed += 1

# ── Main Loop ─────────────────────────────────────────────────────

spawn_piece()
drop_counter = 0
DROP_SPEED = 12
FRAME_MS = 50

running = True
while running:
    key = get_key()
    if key == 'q':
        running = False
        break
    elif not game_over:
        if key == 'a':
            if valid_pos(piece_r, piece_c - 1, piece_rot):
                piece_c -= 1
        elif key == 'd':
            if valid_pos(piece_r, piece_c + 1, piece_rot):
                piece_c += 1
        elif key == 'w':
            new_rot = (piece_rot + 1) % len(SHAPES[piece_type])
            if valid_pos(piece_r, piece_c, new_rot):
                piece_rot = new_rot
        elif key == 's':
            while valid_pos(piece_r + 1, piece_c, piece_rot):
                piece_r += 1
            lock_piece()
            spawn_piece()
            drop_counter = 0

    if not game_over:
        drop_counter += 1
        if drop_counter >= DROP_SPEED:
            drop_counter = 0
            if valid_pos(piece_r + 1, piece_c, piece_rot):
                piece_r += 1
            else:
                lock_piece()
                spawn_piece()

    if game_over:
        go_lbl.set_text('GAME OVER!\nScore: {}\nq=quit'.format(score))

    draw_board()
    lv.task_handler()
    sleep_ms(FRAME_MS)
