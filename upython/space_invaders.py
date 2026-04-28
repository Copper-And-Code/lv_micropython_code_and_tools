"""
=============================================================
  GALAGA - Arcade Game
  MicroPython + LVGL 9.3 | STM32H743
  Display: 1024 x 600 | Touch capacitivo
  Controlli via terminale:
      a = Sinistra
      d = Destra
      [spazio] = Fuoco
      s = Start / Restart
      q = Quit
  Eseguire:  import galaga
=============================================================
"""

import lvgl as lv
import sys
import time
import display_driver

# ── Timing ────────────────────────────────────────────────
try:
    import utime
    _ms = utime.ticks_ms
    _diff = utime.ticks_diff
    _sleep = utime.sleep_ms
except ImportError:
    _ms = lambda: int(time.time() * 1000)
    _diff = lambda a, b: a - b
    _sleep = lambda ms: time.sleep(ms / 1000.0)

# ── Input via USB_VCP (bypass REPL) ──────────────────────
_vcp = None
_use_vcp = False

try:
    import pyb
    _vcp = pyb.USB_VCP()
    _vcp.setinterrupt(-1)    # disabilita Ctrl+C sulla VCP
    _use_vcp = True
    print("[GALAGA] Input: pyb.USB_VCP (raw mode)")
except ImportError:
    print("[GALAGA] pyb non disponibile, provo sys.stdin")
    try:
        import select as _sel
        _poll_obj = _sel.poll()
        _poll_obj.register(sys.stdin, _sel.POLLIN)
    except Exception:
        _poll_obj = None
        print("[GALAGA] ATTENZIONE: nessun input non-bloccante!")

def _read_chars():
    """Legge tutti i caratteri disponibili senza bloccare."""
    buf = ''
    if _use_vcp:
        while _vcp.any():
            c = _vcp.recv(1, timeout=0)
            if c:
                buf += c.decode('ascii', 'ignore')
    else:
        if _poll_obj:
            while _poll_obj.poll(0):
                buf += sys.stdin.read(1)
    return buf

# ── Random ────────────────────────────────────────────────
try:
    from urandom import getrandbits, randint
except ImportError:
    from random import getrandbits, randint

# ── Costanti di gioco ─────────────────────────────────────
SCR_W       = 1024
SCR_H       = 600

PLAYER_W    = 44
PLAYER_H    = 28
PLAYER_Y    = SCR_H - 60
PLAYER_SPD  = 10
NOSE_W      = 8
NOSE_H      = 14

BULLET_W    = 4
BULLET_H    = 14
BULLET_SPD  = 12
MAX_P_BULL  = 6
FIRE_CD     = 5

ENEMY_W     = 32
ENEMY_H     = 22
ENEMY_COLS  = 10
ENEMY_ROWS  = 5
ENEMY_GAP_X = 22
ENEMY_GAP_Y = 18
ENEMY_DROP  = 18
ENEMY_BULL_SPD = 7
MAX_E_BULL  = 8

FORM_W      = ENEMY_COLS * ENEMY_W + (ENEMY_COLS - 1) * ENEMY_GAP_X
FORM_X0     = (SCR_W - FORM_W) // 2
FORM_Y0     = 74

TICK_MS     = 33          # ~30 fps

# Colori
C_BG        = 0x000510
C_STAR      = 0x555577
C_PLAYER    = 0x00E040
C_NOSE      = 0x80FF80
C_P_BULLET  = 0xFFFF00
C_E_BULLET  = 0xFF4444
C_EXPLOSION = 0xFFAA00
C_TEXT      = 0xFFFFFF
C_TITLE     = 0x00CCFF
C_SCORE     = 0xFFFF44

ENEM_COLORS = [0x00DDDD, 0x00DDDD, 0xDD44FF, 0xDD44FF, 0xFF2020]
ENEM_POINTS = [50, 50, 100, 100, 150]

NUM_STARS   = 40

# ── Helpers LVGL ──────────────────────────────────────────
def _box(parent, x, y, w, h, color):
    o = lv.obj(parent)
    o.set_size(w, h)
    o.set_pos(x, y)
    o.set_style_bg_color(lv.color_hex(color), 0)
    o.set_style_bg_opa(lv.OPA.COVER, 0)
    o.set_style_border_width(0, 0)
    o.set_style_radius(0, 0)
    o.set_style_pad_all(0, 0)
    o.remove_flag(lv.obj.FLAG.SCROLLABLE)
    o.remove_flag(lv.obj.FLAG.CLICKABLE)
    return o

def _label(parent, text, color, x, y, font=None):
    lb = lv.label(parent)
    lb.set_text(text)
    lb.set_style_text_color(lv.color_hex(color), 0)
    if font:
        lb.set_style_text_font(font, 0)
    lb.set_pos(x, y)
    return lb

# ══════════════════════════════════════════════════════════
#  Classe Galaga
# ══════════════════════════════════════════════════════════
class Galaga:

    def __init__(self):
        self.state = 'TITLE'
        self.score = 0
        self.high_score = 0
        self.lives = 3
        self.level = 1
        self.container = None

        self.p_bullets = []
        self.e_bullets = []
        self.enemies   = []
        self.explosions = []

        self.form_x = 0
        self.form_y = 0
        self.form_dir = 1
        self.form_spd = 1.5
        self.move_tick = 0
        self.move_interval = 2

        self.px = SCR_W // 2 - PLAYER_W // 2
        self.fire_cd = 0
        self.player_obj = None
        self.nose_obj = None

        self.lbl_score = None
        self.lbl_hi    = None
        self.lbl_lives = None
        self.lbl_level = None

        self.e_fire_timer = 0
        self.e_fire_interval = 55

        self.invuln = 0

        self._flash_msg = None
        self._flash_timer = 0

        # Contatori di "hold" per il movimento continuo
        self._left_hold = 0
        self._right_hold = 0
        self._hold_frames = 4

        self._setup_screen()
        self._show_title()

    # ── Schermo ───────────────────────────────────────────
    def _setup_screen(self):
        self.scr = lv.screen_active()
        self.scr.set_style_bg_color(lv.color_hex(C_BG), 0)
        self.scr.set_style_bg_opa(lv.OPA.COVER, 0)
        self.scr.remove_flag(lv.obj.FLAG.SCROLLABLE)

    def _clear(self):
        self.p_bullets.clear()
        self.e_bullets.clear()
        self.enemies.clear()
        self.explosions.clear()
        if self.container:
            self.container.delete()
            self.container = None
        self.player_obj = None
        self.nose_obj = None
        self.lbl_score = None
        self.lbl_hi = None
        self.lbl_lives = None
        self.lbl_level = None
        self._flash_msg = None

    def _make_container(self):
        c = lv.obj(self.scr)
        c.set_size(SCR_W, SCR_H)
        c.set_pos(0, 0)
        c.set_style_bg_opa(lv.OPA.TRANSP, 0)
        c.set_style_border_width(0, 0)
        c.set_style_pad_all(0, 0)
        c.remove_flag(lv.obj.FLAG.SCROLLABLE)
        c.remove_flag(lv.obj.FLAG.CLICKABLE)
        self.container = c
        return c

    def _create_stars(self, parent):
        for _ in range(NUM_STARS):
            sx = randint(0, SCR_W - 3)
            sy = randint(0, SCR_H - 3)
            sz = 2 if getrandbits(1) else 1
            bright = 0x334466 if sz == 1 else C_STAR
            _box(parent, sx, sy, sz, sz, bright)

    # ══════════════════════════════════════════════════════
    #  TITLE SCREEN
    # ══════════════════════════════════════════════════════
    def _show_title(self):
        self._clear()
        self.state = 'TITLE'
        c = self._make_container()
        self._create_stars(c)

        try:
            big = lv.font_montserrat_40
        except Exception:
            try:
                big = lv.font_montserrat_28
            except Exception:
                big = lv.font_montserrat_14

        _label(c, "G A L A G A", C_TITLE,
               SCR_W // 2 - 160, SCR_H // 2 - 90, big)

        try:
            med = lv.font_montserrat_20
        except Exception:
            med = lv.font_montserrat_14

        _label(c, "a = Sinistra   d = Destra   [spazio] = Fuoco",
               C_TEXT, SCR_W // 2 - 250, SCR_H // 2, med)
        _label(c, "s = Start     q = Quit",
               C_TEXT, SCR_W // 2 - 140, SCR_H // 2 + 35, med)

        if self.high_score > 0:
            _label(c, "HIGH SCORE: {:,}".format(self.high_score),
                   C_SCORE, SCR_W // 2 - 120, SCR_H // 2 + 90, med)

        _box(c, SCR_W // 2 - PLAYER_W // 2, SCR_H // 2 + 140,
             PLAYER_W, PLAYER_H, C_PLAYER)
        _box(c, SCR_W // 2 - NOSE_W // 2, SCR_H // 2 + 140 - NOSE_H + 4,
             NOSE_W, NOSE_H, C_NOSE)

    # ══════════════════════════════════════════════════════
    #  GAME OVER
    # ══════════════════════════════════════════════════════
    def _show_game_over(self):
        self._clear()
        self.state = 'GAMEOVER'
        c = self._make_container()
        self._create_stars(c)

        try:
            big = lv.font_montserrat_40
        except Exception:
            try:
                big = lv.font_montserrat_28
            except Exception:
                big = lv.font_montserrat_14
        try:
            med = lv.font_montserrat_20
        except Exception:
            med = lv.font_montserrat_14

        _label(c, "GAME  OVER", 0xFF2020,
               SCR_W // 2 - 150, SCR_H // 2 - 80, big)
        _label(c, "Score: {:,}".format(self.score),
               C_SCORE, SCR_W // 2 - 90, SCR_H // 2, med)
        _label(c, "High Score: {:,}".format(self.high_score),
               C_TEXT, SCR_W // 2 - 110, SCR_H // 2 + 40, med)
        _label(c, "Premi 's' per rigiocare",
               C_TEXT, SCR_W // 2 - 140, SCR_H // 2 + 100, med)

        print("[GALAGA] GAME OVER  Score:", self.score)

    # ══════════════════════════════════════════════════════
    #  START / NEW LEVEL
    # ══════════════════════════════════════════════════════
    def _start_game(self):
        self._clear()
        self.state = 'PLAYING'
        self.score = 0
        self.lives = 3
        self.level = 1
        self._init_level()

    def _init_level(self):
        self._clear()
        self.state = 'PLAYING'
        c = self._make_container()
        self._create_stars(c)

        self.form_x = 0
        self.form_y = 0
        self.form_dir = 1
        self.form_spd = 1.5 + (self.level - 1) * 0.3
        self.move_tick = 0
        self.move_interval = max(1, 3 - (self.level - 1) // 3)
        self.e_fire_interval = max(15, 55 - (self.level - 1) * 6)
        self.e_fire_timer = 0
        self.fire_cd = 0
        self.invuln = 0

        self.px = SCR_W // 2 - PLAYER_W // 2

        self.player_obj = _box(c, int(self.px), PLAYER_Y,
                               PLAYER_W, PLAYER_H, C_PLAYER)
        self.nose_obj   = _box(c, int(self.px) + PLAYER_W // 2 - NOSE_W // 2,
                               PLAYER_Y - NOSE_H + 4,
                               NOSE_W, NOSE_H, C_NOSE)

        self._create_enemies(c)

        try:
            hf = lv.font_montserrat_20
        except Exception:
            hf = lv.font_montserrat_14

        self.lbl_score = _label(c, "SCORE: 0", C_SCORE, 20, 10, hf)
        self.lbl_hi    = _label(c, "HI: {:,}".format(self.high_score),
                                C_TEXT, SCR_W // 2 - 60, 10, hf)
        self.lbl_lives = _label(c, self._lives_txt(),
                                C_PLAYER, SCR_W - 200, 10, hf)
        self.lbl_level = _label(c, "LV {}".format(self.level),
                                C_TITLE, SCR_W - 80, 10, hf)

        self._flash_msg = _label(c, "LEVEL {}".format(self.level),
                                 C_TITLE, SCR_W // 2 - 60,
                                 SCR_H // 2 - 20, hf)
        self._flash_timer = 40

        print("[GALAGA] Level", self.level, " GO!")

    def _lives_txt(self):
        return "LIVES: " + ('<' * self.lives)

    def _create_enemies(self, parent):
        self.enemies.clear()
        for row in range(ENEMY_ROWS):
            color = ENEM_COLORS[row]
            pts   = ENEM_POINTS[row]
            for col in range(ENEMY_COLS):
                ix = FORM_X0 + col * (ENEMY_W + ENEMY_GAP_X)
                iy = FORM_Y0 + row * (ENEMY_H + ENEMY_GAP_Y)
                obj = _box(parent, ix, iy, ENEMY_W, ENEMY_H, color)
                _box(obj, 4, 4, ENEMY_W - 8, ENEMY_H - 8,
                     (color & 0xFEFEFE) >> 1)
                self.enemies.append({
                    'ix': ix, 'iy': iy,
                    'x': ix, 'y': iy,
                    'obj': obj,
                    'alive': True,
                    'pts': pts,
                    'row': row, 'col': col,
                    'color': color,
                })

    # ══════════════════════════════════════════════════════
    #  GAME TICK
    # ══════════════════════════════════════════════════════
    def tick(self, inp):
        """Chiamato dal main loop con i caratteri letti."""

        # ── TITLE / GAMEOVER ──────────────────────────────
        if self.state in ('TITLE', 'GAMEOVER'):
            if 's' in inp:
                self._start_game()
            elif 'q' in inp:
                self.state = 'QUIT'
            return

        if self.state != 'PLAYING':
            return

        # ── Flash messaggio livello ───────────────────────
        if self._flash_timer > 0:
            self._flash_timer -= 1
            if self._flash_timer == 0 and self._flash_msg:
                self._flash_msg.delete()
                self._flash_msg = None

        # ── Input con hold ────────────────────────────────
        fire = False
        for ch in inp:
            if ch == 'a':
                self._left_hold = self._hold_frames
            elif ch == 'd':
                self._right_hold = self._hold_frames
            elif ch == ' ':
                fire = True
            elif ch == 'q':
                self.state = 'QUIT'
                return

        move = 0
        if self._left_hold > 0:
            move -= 1
            self._left_hold -= 1
        if self._right_hold > 0:
            move += 1
            self._right_hold -= 1

        # ── Player movement ───────────────────────────────
        if move != 0:
            self.px += move * PLAYER_SPD
            if self.px < 4:
                self.px = 4
            elif self.px > SCR_W - PLAYER_W - 4:
                self.px = SCR_W - PLAYER_W - 4
            self.player_obj.set_pos(int(self.px), PLAYER_Y)
            self.nose_obj.set_pos(int(self.px) + PLAYER_W // 2 - NOSE_W // 2,
                                  PLAYER_Y - NOSE_H + 4)

        # ── Player fire ───────────────────────────────────
        if self.fire_cd > 0:
            self.fire_cd -= 1
        if fire and self.fire_cd == 0 and len(self.p_bullets) < MAX_P_BULL:
            bx = int(self.px) + PLAYER_W // 2 - BULLET_W // 2
            by = PLAYER_Y - BULLET_H
            obj = _box(self.container, bx, by,
                       BULLET_W, BULLET_H, C_P_BULLET)
            self.p_bullets.append({'x': bx, 'y': by, 'obj': obj})
            self.fire_cd = FIRE_CD

        # ── Update player bullets ─────────────────────────
        alive_pb = []
        for b in self.p_bullets:
            b['y'] -= BULLET_SPD
            if b['y'] < -BULLET_H:
                b['obj'].delete()
            else:
                b['obj'].set_pos(int(b['x']), int(b['y']))
                alive_pb.append(b)
        self.p_bullets = alive_pb

        # ── Update enemy bullets ──────────────────────────
        alive_eb = []
        for b in self.e_bullets:
            b['y'] += ENEMY_BULL_SPD
            if b['y'] > SCR_H + 10:
                b['obj'].delete()
            else:
                b['obj'].set_pos(int(b['x']), int(b['y']))
                alive_eb.append(b)
        self.e_bullets = alive_eb

        # ── Enemy movement ────────────────────────────────
        self.move_tick += 1
        if self.move_tick >= self.move_interval:
            self.move_tick = 0
            self.form_x += self.form_dir * self.form_spd

            edge = False
            for e in self.enemies:
                if not e['alive']:
                    continue
                ax = e['ix'] + self.form_x
                if ax <= 8 or ax + ENEMY_W >= SCR_W - 8:
                    edge = True
                    break
            if edge:
                self.form_dir *= -1
                self.form_y += ENEMY_DROP
                self.form_x += self.form_dir * self.form_spd * 2

            for e in self.enemies:
                if not e['alive']:
                    continue
                e['x'] = e['ix'] + self.form_x
                e['y'] = e['iy'] + self.form_y
                e['obj'].set_pos(int(e['x']), int(e['y']))

                if e['y'] + ENEMY_H >= PLAYER_Y:
                    self._player_dead()
                    return

        # ── Enemy fire ────────────────────────────────────
        self.e_fire_timer += 1
        if self.e_fire_timer >= self.e_fire_interval:
            self.e_fire_timer = 0
            self._enemy_shoot()

        # ── Collisions: player bullets -> enemies ─────────
        new_pb = []
        for b in self.p_bullets:
            hit = False
            for e in self.enemies:
                if not e['alive']:
                    continue
                if self._collide(b['x'], b['y'], BULLET_W, BULLET_H,
                                 e['x'], e['y'], ENEMY_W, ENEMY_H):
                    e['alive'] = False
                    e['obj'].delete()
                    self.score += e['pts']
                    self._spawn_explosion(e['x'], e['y'])
                    b['obj'].delete()
                    hit = True
                    break
            if not hit:
                new_pb.append(b)
        self.p_bullets = new_pb

        # ── Collisions: enemy bullets -> player ───────────
        if self.invuln > 0:
            self.invuln -= 1
            if self.invuln % 4 < 2:
                self.player_obj.set_style_bg_opa(lv.OPA._50, 0)
            else:
                self.player_obj.set_style_bg_opa(lv.OPA.COVER, 0)
        else:
            self.player_obj.set_style_bg_opa(lv.OPA.COVER, 0)
            for b in self.e_bullets:
                if self._collide(b['x'], b['y'], BULLET_W, BULLET_H,
                                 self.px, PLAYER_Y, PLAYER_W, PLAYER_H):
                    b['obj'].delete()
                    self.e_bullets.remove(b)
                    self._player_hit()
                    return

        # ── Explosions ────────────────────────────────────
        alive_exp = []
        for ex in self.explosions:
            ex['ttl'] -= 1
            if ex['ttl'] <= 0:
                ex['obj'].delete()
            else:
                sz = ex['sz'] + 2
                ex['sz'] = sz
                ex['obj'].set_size(sz, sz)
                if ex['ttl'] < 4:
                    ex['obj'].set_style_bg_opa(lv.OPA._50, 0)
                alive_exp.append(ex)
        self.explosions = alive_exp

        # ── HUD ───────────────────────────────────────────
        if self.lbl_score:
            self.lbl_score.set_text("SCORE: {:,}".format(self.score))
        if self.lbl_lives:
            self.lbl_lives.set_text(self._lives_txt())

        # ── All enemies dead? ─────────────────────────────
        if all(not e['alive'] for e in self.enemies):
            self.level += 1
            if self.score > self.high_score:
                self.high_score = self.score
            self._init_level()

    # ── Enemy shoot ───────────────────────────────────────
    def _enemy_shoot(self):
        if len(self.e_bullets) >= MAX_E_BULL:
            return
        alive = [e for e in self.enemies if e['alive']]
        if not alive:
            return

        bottom = {}
        for e in alive:
            col = e['col']
            if col not in bottom or e['y'] > bottom[col]['y']:
                bottom[col] = e

        shooters = list(bottom.values())
        if not shooters:
            return

        n_shots = min(len(shooters), 1 + self.level // 3)
        for _ in range(n_shots):
            if len(self.e_bullets) >= MAX_E_BULL:
                break
            idx = randint(0, len(shooters) - 1)
            e = shooters[idx]
            bx = int(e['x']) + ENEMY_W // 2 - BULLET_W // 2
            by = int(e['y']) + ENEMY_H
            obj = _box(self.container, bx, by,
                       BULLET_W + 2, BULLET_H, C_E_BULLET)
            self.e_bullets.append({'x': bx, 'y': by, 'obj': obj})

    def _spawn_explosion(self, x, y):
        sz = 10
        obj = _box(self.container, int(x) - 2, int(y) - 2,
                   sz, sz, C_EXPLOSION)
        obj.set_style_radius(4, 0)
        self.explosions.append({'obj': obj, 'ttl': 8, 'sz': sz})

    def _player_hit(self):
        self.lives -= 1
        self._spawn_explosion(self.px + PLAYER_W // 2 - 5,
                              PLAYER_Y - 5)
        if self.lives <= 0:
            self._player_dead()
        else:
            self.invuln = 45
            print("[GALAGA] Colpito! Vite rimaste:", self.lives)

    def _player_dead(self):
        if self.score > self.high_score:
            self.high_score = self.score
        self._show_game_over()

    @staticmethod
    def _collide(x1, y1, w1, h1, x2, y2, w2, h2):
        return (x1 < x2 + w2 and x1 + w1 > x2 and
                y1 < y2 + h2 and y1 + h1 > y2)

    def cleanup(self):
        self._clear()
        lb = lv.label(self.scr)
        lb.set_text("GALAGA - Sessione terminata")
        lb.set_style_text_color(lv.color_hex(C_TEXT), 0)
        lb.center()


# ══════════════════════════════════════════════════════════
#  MAIN LOOP  (bypassa completamente la REPL)
# ══════════════════════════════════════════════════════════
def run():
    """Avvia il gioco con main loop dedicato.
    
    Il loop prende il controllo completo:
    - legge input direttamente da USB_VCP (niente echo)
    - chiama game.tick() per la logica
    - chiama lv.timer_handler() per il rendering LVGL
    - mantiene ~30fps con sleep preciso
    """

    print("=" * 50)
    print("  GALAGA per MicroPython + LVGL 9.3")
    print("  Controlli:")
    print("    a = Sinistra")
    print("    d = Destra")
    print("  [spazio] = Fuoco")
    print("    s = Start / Restart")
    print("    q = Quit")
    print("=" * 50)
    print()
    print("[GALAGA] Premi 's' per iniziare!")
    print()

    game = Galaga()

    while game.state != 'QUIT':
        t0 = _ms()

        # 1) Leggi input raw (no echo, no REPL)
        chars = _read_chars()

        # 2) Logica di gioco
        game.tick(chars)

        # 3) Aggiorna LVGL (rendering + timer interni)
        try:
            lv.timer_handler()
        except Exception:
            try:
                lv.task_handler()
            except Exception:
                pass

        # 4) Mantieni ~30fps
        elapsed = _diff(_ms(), t0)
        wait = TICK_MS - elapsed
        if wait > 0:
            _sleep(wait)

    # Cleanup
    game.cleanup()
    print("[GALAGA] Quit. Per rilanciare: galaga.run()")

    # Ripristina Ctrl+C sulla VCP
    if _use_vcp:
        try:
            _vcp.setinterrupt(3)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════
#  Auto-start al primo import
# ══════════════════════════════════════════════════════════
run()
