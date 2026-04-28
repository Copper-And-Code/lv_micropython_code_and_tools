"""
===============================================================
  ELECTRIC VEHICLE DASHBOARD — MicroPython + LVGL 9.3
  Target: STM32H743 | 32 MB SDRAM | 1024 x 600 LCD + CTP
  Realistic highway simulation with random accel/brake events
===============================================================
"""

import lvgl as lv
import math
import display_driver

# ─── TinyRandom (no 'random' module on bare-metal) ──────────
_rng_state = 987654321

def _rng_next():
    global _rng_state
    _rng_state ^= (_rng_state << 13) & 0xFFFFFFFF
    _rng_state ^= (_rng_state >> 17)
    _rng_state ^= (_rng_state << 5) & 0xFFFFFFFF
    _rng_state &= 0xFFFFFFFF
    return _rng_state

def rand_int(lo, hi):
    """Return random integer in [lo, hi]"""
    return lo + (_rng_next() % (hi - lo + 1))

def rand_float(lo, hi):
    """Return random float in [lo, hi]"""
    return lo + (_rng_next() % 10000) / 10000.0 * (hi - lo)


# ─── SCREEN & RESOLUTION ────────────────────────────────────
SCR_W = 1024
SCR_H = 600

# ─── FONT DETECTION ─────────────────────────────────────────
def _try_font(names):
    for n in names:
        try:
            return getattr(lv, n)
        except Exception:
            pass
    return lv.font_montserrat_14

FONT_XXL = _try_font(["font_montserrat_48", "font_montserrat_44",
                       "font_montserrat_40", "font_montserrat_36"])
FONT_XL  = _try_font(["font_montserrat_36", "font_montserrat_32",
                       "font_montserrat_28"])
FONT_LG  = _try_font(["font_montserrat_24", "font_montserrat_22",
                       "font_montserrat_20"])
FONT_MD  = _try_font(["font_montserrat_18", "font_montserrat_16"])
FONT_SM  = _try_font(["font_montserrat_14"])
FONT_XS  = _try_font(["font_montserrat_12", "font_montserrat_10",
                       "font_montserrat_14"])

# ─── COLOR PALETTE ───────────────────────────────────────────
C_BG       = lv.color_hex(0x080810)
C_PANEL    = lv.color_hex(0x10101C)
C_RING_BG  = lv.color_hex(0x1A1A2E)
C_GRAY     = lv.color_hex(0x3A3A5C)
C_WHITE    = lv.color_hex(0xE8E8F0)
C_BRIGHT   = lv.color_hex(0xFFFFFF)
C_CYAN     = lv.color_hex(0x00E5FF)
C_GREEN    = lv.color_hex(0x00E676)
C_LIME     = lv.color_hex(0x76FF03)
C_YELLOW   = lv.color_hex(0xFFD740)
C_ORANGE   = lv.color_hex(0xFF6D00)
C_RED      = lv.color_hex(0xFF1744)
C_BLUE     = lv.color_hex(0x448AFF)
C_TEAL     = lv.color_hex(0x00BFA5)
C_PURPLE   = lv.color_hex(0xB388FF)
C_DIM      = lv.color_hex(0x50506A)
C_REGEN    = lv.color_hex(0x00C853)
C_CONSUME  = lv.color_hex(0xFF6E40)


# ═════════════════════════════════════════════════════════════
#   DRIVING SIMULATION — STATE MACHINE
# ═════════════════════════════════════════════════════════════
#
#  States: CRUISE / ACCELERATE / BRAKE / COAST
#  Each state has a random duration and intensity.
#  Transitions happen when the state timer expires.

ST_CRUISE     = 0
ST_ACCELERATE = 1
ST_BRAKE      = 2
ST_COAST      = 3

class DriveSim:
    def __init__(self):
        self.speed        = 0.0
        self.target_speed = 120.0
        self.accel        = 0.0
        self.state        = ST_ACCELERATE
        self.state_timer  = 0.0
        self.rpm          = 0.0
        self.power_kw     = 0.0
        self.prev_speed   = 0.0

        self.battery_pct  = 94.0
        self.range_km     = 347.0
        self.motor_temp   = 38.0
        self.bat_temp     = 27.0
        self.odo_km       = 12873.4
        self.trip_km      = 0.0
        self.v_max        = 0.0
        self.spd_accum    = 0.0
        self.spd_samples  = 0

        self.blink_cnt    = 0
        self.clock_s      = 14 * 3600 + 32 * 60

        # Initial ramp-up from standstill
        self._pick_state(ST_ACCELERATE)
        self.target_speed = 130.0
        self.accel = rand_float(15.0, 25.0)
        self.state_timer = 12.0

    def _pick_state(self, force=None):
        """Choose next driving state with random duration and intensity"""
        if force is not None:
            self.state = force
        else:
            r = rand_int(0, 99)
            if self.speed < 30:
                self.state = ST_ACCELERATE
            elif r < 40:
                self.state = ST_CRUISE
            elif r < 65:
                self.state = ST_ACCELERATE
            elif r < 88:
                self.state = ST_BRAKE
            else:
                self.state = ST_COAST

        if self.state == ST_CRUISE:
            self.target_speed = self.speed + rand_float(-5.0, 5.0)
            self.accel = 0.0
            self.state_timer = rand_float(4.0, 15.0)

        elif self.state == ST_ACCELERATE:
            intensity = rand_int(0, 2)
            if intensity == 0:
                self.accel = rand_float(3.0, 8.0)
                self.target_speed = self.speed + rand_float(5.0, 15.0)
                self.state_timer = rand_float(2.0, 5.0)
            elif intensity == 1:
                self.accel = rand_float(8.0, 18.0)
                self.target_speed = self.speed + rand_float(15.0, 40.0)
                self.state_timer = rand_float(3.0, 7.0)
            else:
                self.accel = rand_float(18.0, 35.0)
                self.target_speed = self.speed + rand_float(30.0, 60.0)
                self.state_timer = rand_float(2.0, 5.0)
            if self.target_speed > 210.0:
                self.target_speed = rand_float(180.0, 210.0)

        elif self.state == ST_BRAKE:
            intensity = rand_int(0, 2)
            if intensity == 0:
                self.accel = rand_float(-5.0, -12.0)
                self.target_speed = self.speed - rand_float(10.0, 25.0)
                self.state_timer = rand_float(2.0, 5.0)
            elif intensity == 1:
                self.accel = rand_float(-12.0, -25.0)
                self.target_speed = self.speed - rand_float(20.0, 50.0)
                self.state_timer = rand_float(2.0, 6.0)
            else:
                self.accel = rand_float(-25.0, -50.0)
                self.target_speed = self.speed - rand_float(40.0, 80.0)
                self.state_timer = rand_float(1.5, 3.5)
            if self.target_speed < 40.0:
                self.target_speed = rand_float(40.0, 70.0)

        elif self.state == ST_COAST:
            self.accel = rand_float(-2.0, -5.0)
            self.target_speed = self.speed - rand_float(5.0, 15.0)
            self.state_timer = rand_float(3.0, 8.0)
            if self.target_speed < 60.0:
                self.target_speed = 60.0

    def update(self, dt):
        """Advance simulation by dt seconds"""
        self.prev_speed = self.speed

        self.state_timer -= dt
        if self.state_timer <= 0:
            self._pick_state()

        if self.state == ST_CRUISE:
            noise = math.sin(self.spd_samples * 0.3) * 1.5
            diff = (self.target_speed + noise) - self.speed
            self.speed += diff * 2.0 * dt
        else:
            self.speed += self.accel * dt
            if self.state == ST_ACCELERATE and self.speed >= self.target_speed:
                self.speed = self.target_speed
                self._pick_state(ST_CRUISE)
            elif self.state in (ST_BRAKE, ST_COAST) and self.speed <= self.target_speed:
                self.speed = self.target_speed
                self._pick_state(ST_CRUISE)

        if self.speed < 0.0:
            self.speed = 0.0
        if self.speed > 220.0:
            self.speed = 220.0

        # RPM — EV single-gear reducer ratio
        rpm_base = self.speed * 52.0
        rpm_noise = math.sin(self.spd_samples * 0.7) * 150.0
        self.rpm = rpm_base + rpm_noise
        if self.rpm < 0:
            self.rpm = 0
        if self.rpm > 14000:
            self.rpm = 14000

        # Power (kW)
        speed_delta = self.speed - self.prev_speed
        accel_now = speed_delta / dt if dt > 0 else 0.0
        drag_kw = 0.0008 * self.speed * self.speed
        accel_kw = accel_now * 1.8
        self.power_kw = drag_kw + accel_kw
        if self.power_kw < -60.0:
            self.power_kw = -60.0
        if self.power_kw > 250.0:
            self.power_kw = 250.0

        # Battery drain
        kwh_tick = abs(self.power_kw) * dt / 3600.0
        pack_kwh = 78.0
        if self.power_kw > 0:
            self.battery_pct -= (kwh_tick / pack_kwh) * 100.0
        else:
            self.battery_pct += (kwh_tick * 0.85 / pack_kwh) * 100.0
        if self.battery_pct < 0:
            self.battery_pct = 0
        if self.battery_pct > 100:
            self.battery_pct = 100
        self.range_km = self.battery_pct / 100.0 * 380.0

        # Temperatures
        tgt_mt = 40.0 + self.power_kw * 0.15
        self.motor_temp += (tgt_mt - self.motor_temp) * 0.002
        tgt_bt = 28.0 + self.power_kw * 0.03
        self.bat_temp += (tgt_bt - self.bat_temp) * 0.001

        # Odometer and trip
        km_tick = self.speed * dt / 3600.0
        self.odo_km += km_tick
        self.trip_km += km_tick

        # Statistics
        if self.speed > self.v_max:
            self.v_max = self.speed
        self.spd_accum += self.speed
        self.spd_samples += 1

        # Clock (10x real-time)
        self.clock_s += dt * 10
        if self.clock_s >= 86400:
            self.clock_s -= 86400

        self.blink_cnt += 1


SIM = DriveSim()


# ═════════════════════════════════════════════════════════════
#   SCREEN SETUP
# ═════════════════════════════════════════════════════════════
scr = lv.screen_active()
if scr is None:
    scr = lv.obj()
    lv.screen_load(scr)

scr.set_style_bg_color(C_BG, 0)
scr.remove_flag(lv.obj.FLAG.SCROLLABLE)


# ═════════════════════════════════════════════════════════════
#   HELPER FUNCTIONS
# ═════════════════════════════════════════════════════════════
def make_transparent(obj, part=0):
    """Set background fully transparent, remove border"""
    obj.set_style_bg_opa(lv.OPA.TRANSP, part)
    obj.set_style_border_width(0, part)

def create_container(parent, x, y, w, h):
    """Create an invisible container at given position"""
    c = lv.obj(parent)
    c.set_size(w, h)
    c.set_pos(x, y)
    make_transparent(c)
    c.set_style_pad_all(0, 0)
    c.remove_flag(lv.obj.FLAG.SCROLLABLE)
    c.remove_flag(lv.obj.FLAG.CLICKABLE)
    return c

def create_label(parent, text, font, color, align=lv.ALIGN.CENTER, ox=0, oy=0):
    """Create and position a styled label"""
    lb = lv.label(parent)
    lb.set_text(text)
    lb.set_style_text_color(color, 0)
    lb.set_style_text_font(font, 0)
    lb.align(align, ox, oy)
    return lb

def value_to_angle(val, vmin, vmax, sweep=270, start=135):
    """Convert a value to LVGL arc angle (CW from east)"""
    ratio = (val - vmin) / max((vmax - vmin), 1)
    if ratio < 0.0:
        ratio = 0.0
    if ratio > 1.0:
        ratio = 1.0
    return start + ratio * sweep

def angle_to_xy(angle_deg, radius, cx, cy):
    """Screen coordinates from LVGL angle"""
    rad = math.radians(angle_deg)
    return int(cx + radius * math.cos(rad)), int(cy + radius * math.sin(rad))

def speed_color(spd):
    if spd < 100:   return C_GREEN
    elif spd < 140: return C_CYAN
    elif spd < 180: return C_YELLOW
    elif spd < 220: return C_ORANGE
    return C_RED

def rpm_color(rpm):
    if rpm < 5000:   return C_TEAL
    elif rpm < 8000: return C_CYAN
    elif rpm < 11000:return C_YELLOW
    return C_RED

def power_color(kw):
    if kw < 0:     return C_REGEN
    elif kw < 40:  return C_GREEN
    elif kw < 80:  return C_YELLOW
    elif kw < 150: return C_ORANGE
    return C_RED

def battery_color(pct):
    if pct > 50:   return C_GREEN
    elif pct > 25: return C_YELLOW
    elif pct > 10: return C_ORANGE
    return C_RED


# ═════════════════════════════════════════════════════════════
#   ARC-BASED GAUGE BUILDER
# ═════════════════════════════════════════════════════════════
def build_arc_gauge(parent, cx, cy, diameter, arc_w,
                    vmin, vmax, color, title_str, unit_str,
                    tick_step=None):
    """
    Build a 270-degree arc gauge (open at bottom).
    Returns a dict of widgets for dynamic updates.
    """
    r = diameter // 2
    cont = create_container(parent, cx - r, cy - r, diameter, diameter)

    # Decorative outer thin ring
    deco = lv.arc(cont)
    deco.set_size(diameter - 2, diameter - 2)
    deco.align(lv.ALIGN.CENTER, 0, 0)
    deco.set_bg_angles(0, 270)
    deco.set_rotation(135)
    deco.set_range(vmin, vmax)
    deco.set_value(vmax)
    deco.remove_flag(lv.obj.FLAG.CLICKABLE)
    deco.set_style_arc_width(2, lv.PART.MAIN)
    deco.set_style_arc_color(C_RING_BG, lv.PART.MAIN)
    deco.set_style_arc_opa(lv.OPA._60, lv.PART.MAIN)
    deco.set_style_arc_width(2, lv.PART.INDICATOR)
    deco.set_style_arc_color(C_GRAY, lv.PART.INDICATOR)
    deco.set_style_arc_opa(lv.OPA._40, lv.PART.INDICATOR)
    deco.set_style_bg_opa(lv.OPA.TRANSP, lv.PART.KNOB)
    deco.set_style_pad_all(0, lv.PART.KNOB)

    # Main track arc
    arc_track = lv.arc(cont)
    tr_sz = diameter - 20
    arc_track.set_size(tr_sz, tr_sz)
    arc_track.align(lv.ALIGN.CENTER, 0, 0)
    arc_track.set_bg_angles(0, 270)
    arc_track.set_rotation(135)
    arc_track.set_range(vmin, vmax)
    arc_track.set_value(vmin)
    arc_track.set_mode(lv.arc.MODE.NORMAL)
    arc_track.remove_flag(lv.obj.FLAG.CLICKABLE)
    arc_track.set_style_arc_width(arc_w, lv.PART.MAIN)
    arc_track.set_style_arc_color(C_RING_BG, lv.PART.MAIN)
    arc_track.set_style_arc_rounded(False, lv.PART.MAIN)
    arc_track.set_style_arc_width(arc_w, lv.PART.INDICATOR)
    arc_track.set_style_arc_color(color, lv.PART.INDICATOR)
    arc_track.set_style_arc_rounded(True, lv.PART.INDICATOR)
    arc_track.set_style_bg_opa(lv.OPA.TRANSP, lv.PART.KNOB)
    arc_track.set_style_pad_all(0, lv.PART.KNOB)

    # Inner glow arc
    arc_glow = lv.arc(cont)
    gl_sz = tr_sz - arc_w * 2 - 6
    arc_glow.set_size(gl_sz, gl_sz)
    arc_glow.align(lv.ALIGN.CENTER, 0, 0)
    arc_glow.set_bg_angles(0, 270)
    arc_glow.set_rotation(135)
    arc_glow.set_range(vmin, vmax)
    arc_glow.set_value(vmin)
    arc_glow.set_mode(lv.arc.MODE.NORMAL)
    arc_glow.remove_flag(lv.obj.FLAG.CLICKABLE)
    arc_glow.set_style_arc_width(3, lv.PART.MAIN)
    arc_glow.set_style_arc_opa(lv.OPA.TRANSP, lv.PART.MAIN)
    arc_glow.set_style_arc_width(3, lv.PART.INDICATOR)
    arc_glow.set_style_arc_color(color, lv.PART.INDICATOR)
    arc_glow.set_style_arc_opa(lv.OPA._40, lv.PART.INDICATOR)
    arc_glow.set_style_arc_rounded(True, lv.PART.INDICATOR)
    arc_glow.set_style_bg_opa(lv.OPA.TRANSP, lv.PART.KNOB)
    arc_glow.set_style_pad_all(0, lv.PART.KNOB)

    # Needle dot
    dot = lv.obj(cont)
    dot_sz = max(10, arc_w - 4)
    dot.set_size(dot_sz, dot_sz)
    dot.set_style_radius(dot_sz // 2, 0)
    dot.set_style_bg_color(C_BRIGHT, 0)
    dot.set_style_bg_opa(lv.OPA.COVER, 0)
    dot.set_style_border_width(0, 0)
    dot.set_style_shadow_width(12, 0)
    dot.set_style_shadow_color(color, 0)
    dot.set_style_shadow_opa(lv.OPA._70, 0)
    dot.remove_flag(lv.obj.FLAG.SCROLLABLE | lv.obj.FLAG.CLICKABLE)
    dx, dy = angle_to_xy(135, (tr_sz / 2 - arc_w / 2), r, r)
    dot.set_pos(dx - dot_sz // 2, dy - dot_sz // 2)

    # Tick labels
    if tick_step:
        tick_r = tr_sz / 2 + 12
        for v in range(vmin, vmax + 1, tick_step):
            ang = value_to_angle(v, vmin, vmax)
            tx, ty = angle_to_xy(ang, tick_r, r, r)
            lb = lv.label(cont)
            lb.set_text(str(v))
            lb.set_style_text_color(C_DIM, 0)
            lb.set_style_text_font(FONT_XS, 0)
            lb.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
            lb.align(lv.ALIGN.TOP_LEFT, 0, 0)
            lb.set_pos(tx - 16, ty - 8)

    # Title above center
    create_label(cont, title_str, FONT_SM, C_GRAY, lv.ALIGN.CENTER, 0, -r // 3 - 5)

    # Big value display
    lbl_val = create_label(cont, "0", FONT_XXL, C_BRIGHT, lv.ALIGN.CENTER, 0, 10)

    # Unit below value
    create_label(cont, unit_str, FONT_MD, C_DIM, lv.ALIGN.CENTER, 0, r // 3 + 10)

    return {
        "arc": arc_track, "glow": arc_glow, "dot": dot,
        "lbl_val": lbl_val,
        "vmin": vmin, "vmax": vmax,
        "tr_sz": tr_sz, "arc_w": arc_w,
        "dot_sz": dot_sz, "cx": r, "cy": r,
    }


def gauge_set(g, value, color=None):
    """Update gauge value and optionally change color"""
    v = value
    if v < g["vmin"]:
        v = g["vmin"]
    if v > g["vmax"]:
        v = g["vmax"]
    vi = int(v)

    g["arc"].set_value(vi)
    g["glow"].set_value(vi)
    g["lbl_val"].set_text(str(vi))

    if color:
        g["arc"].set_style_arc_color(color, lv.PART.INDICATOR)
        g["glow"].set_style_arc_color(color, lv.PART.INDICATOR)
        g["dot"].set_style_shadow_color(color, 0)

    ang = value_to_angle(v, g["vmin"], g["vmax"])
    nr = g["tr_sz"] / 2 - g["arc_w"] / 2
    nx, ny = angle_to_xy(ang, nr, g["cx"], g["cy"])
    ds = g["dot_sz"]
    g["dot"].set_pos(nx - ds // 2, ny - ds // 2)


# ═════════════════════════════════════════════════════════════
#   BUILD DASHBOARD LAYOUT
# ═════════════════════════════════════════════════════════════

# Speedometer (left-center, large)
spd_gauge = build_arc_gauge(
    scr, cx=290, cy=250, diameter=400, arc_w=22,
    vmin=0, vmax=260, color=C_CYAN,
    title_str="SPEED", unit_str="km/h",
    tick_step=40
)

# Tachometer (right-center)
rpm_gauge = build_arc_gauge(
    scr, cx=734, cy=250, diameter=340, arc_w=18,
    vmin=0, vmax=14000, color=C_TEAL,
    title_str="MOTOR", unit_str="RPM",
    tick_step=2000
)


# ═════════════════════════════════════════════════════════════
#   BATTERY PANEL (left strip)
# ═════════════════════════════════════════════════════════════
bat_panel = create_container(scr, 10, 60, 100, 360)

create_label(bat_panel, lv.SYMBOL.BATTERY_FULL, FONT_LG, C_GREEN,
             lv.ALIGN.TOP_MID, 0, 0)

lbl_bat_pct = create_label(bat_panel, "94%", FONT_LG, C_GREEN,
                           lv.ALIGN.TOP_MID, 0, 32)

bat_bar = lv.bar(bat_panel)
bat_bar.set_size(30, 200)
bat_bar.align(lv.ALIGN.TOP_MID, 0, 70)
bat_bar.set_range(0, 100)
bat_bar.set_value(94, False)
bat_bar.set_style_bg_color(C_RING_BG, lv.PART.MAIN)
bat_bar.set_style_bg_opa(lv.OPA.COVER, lv.PART.MAIN)
bat_bar.set_style_radius(6, lv.PART.MAIN)
bat_bar.set_style_bg_color(C_GREEN, lv.PART.INDICATOR)
bat_bar.set_style_bg_opa(lv.OPA.COVER, lv.PART.INDICATOR)
bat_bar.set_style_radius(6, lv.PART.INDICATOR)

create_label(bat_panel, "RANGE", FONT_XS, C_DIM, lv.ALIGN.TOP_MID, 0, 282)
lbl_range = create_label(bat_panel, "347 km", FONT_MD, C_WHITE,
                         lv.ALIGN.TOP_MID, 0, 298)


# ═════════════════════════════════════════════════════════════
#   POWER BAR (center-bottom)
# ═════════════════════════════════════════════════════════════
pwr_panel = create_container(scr, 170, 470, 684, 55)

create_label(pwr_panel, "REGEN", FONT_XS, C_REGEN, lv.ALIGN.LEFT_MID, 2, -14)
create_label(pwr_panel, "POWER", FONT_XS, C_DIM, lv.ALIGN.CENTER, 0, -14)
create_label(pwr_panel, "MAX", FONT_XS, C_CONSUME, lv.ALIGN.RIGHT_MID, -10, -14)

pwr_bar = lv.bar(pwr_panel)
pwr_bar.set_size(660, 16)
pwr_bar.align(lv.ALIGN.CENTER, 0, 8)
pwr_bar.set_range(0, 310)
pwr_bar.set_value(60, False)
pwr_bar.set_style_bg_color(C_RING_BG, lv.PART.MAIN)
pwr_bar.set_style_bg_opa(lv.OPA.COVER, lv.PART.MAIN)
pwr_bar.set_style_radius(8, lv.PART.MAIN)
pwr_bar.set_style_bg_color(C_GREEN, lv.PART.INDICATOR)
pwr_bar.set_style_bg_opa(lv.OPA.COVER, lv.PART.INDICATOR)
pwr_bar.set_style_radius(8, lv.PART.INDICATOR)

zero_mark = lv.obj(pwr_panel)
zero_mark.set_size(2, 22)
zero_mark.set_pos(int(60 / 310 * 660) + 12, 3)
zero_mark.set_style_bg_color(C_WHITE, 0)
zero_mark.set_style_bg_opa(lv.OPA._60, 0)
zero_mark.set_style_border_width(0, 0)

lbl_power = create_label(pwr_panel, "0 kW", FONT_SM, C_WHITE,
                         lv.ALIGN.CENTER, 0, 28)


# ═════════════════════════════════════════════════════════════
#   DRIVING STATE INDICATOR (between gauges)
# ═════════════════════════════════════════════════════════════
state_panel = create_container(scr, 460, 160, 104, 70)
lbl_state_icon = create_label(state_panel, lv.SYMBOL.RIGHT, FONT_XL,
                              C_GREEN, lv.ALIGN.TOP_MID, 0, 0)
lbl_state_txt = create_label(state_panel, "CRUISE", FONT_XS, C_DIM,
                             lv.ALIGN.BOTTOM_MID, 0, 0)


# ═════════════════════════════════════════════════════════════
#   INFO PANEL (right strip)
# ═════════════════════════════════════════════════════════════
info_right = create_container(scr, 920, 60, 98, 360)

create_label(info_right, "MOTOR", FONT_XS, C_DIM, lv.ALIGN.TOP_MID, 0, 0)
lbl_motor_t = create_label(info_right, "38\xb0C", FONT_MD,
                           C_WHITE, lv.ALIGN.TOP_MID, 0, 16)

create_label(info_right, "BATT", FONT_XS, C_DIM, lv.ALIGN.TOP_MID, 0, 55)
lbl_bat_t = create_label(info_right, "27\xb0C", FONT_MD,
                         C_WHITE, lv.ALIGN.TOP_MID, 0, 71)

create_label(info_right, "EFFICIENCY", FONT_XS, C_DIM, lv.ALIGN.TOP_MID, 0, 110)
lbl_eff = create_label(info_right, "16.2", FONT_MD, C_GREEN,
                       lv.ALIGN.TOP_MID, 0, 126)
create_label(info_right, "kWh/100km", FONT_XS, C_DIM, lv.ALIGN.TOP_MID, 0, 148)

create_label(info_right, "ODO", FONT_XS, C_DIM, lv.ALIGN.TOP_MID, 0, 185)
lbl_odo = create_label(info_right, "12873 km", FONT_MD, C_WHITE,
                       lv.ALIGN.TOP_MID, 0, 201)

create_label(info_right, "V MAX", FONT_XS, C_DIM, lv.ALIGN.TOP_MID, 0, 240)
lbl_vmax = create_label(info_right, "0", FONT_MD, C_YELLOW,
                        lv.ALIGN.TOP_MID, 0, 256)


# ═════════════════════════════════════════════════════════════
#   STATUS BAR (bottom)
# ═════════════════════════════════════════════════════════════
status_bar = create_container(scr, 0, 545, SCR_W, 55)
status_bar.set_style_bg_color(C_PANEL, 0)
status_bar.set_style_bg_opa(lv.OPA.COVER, 0)
status_bar.set_style_border_width(0, 0)

lbl_turn_l = create_label(status_bar, lv.SYMBOL.LEFT, FONT_LG, C_RING_BG,
                          lv.ALIGN.LEFT_MID, 30, 0)
lbl_turn_r = create_label(status_bar, lv.SYMBOL.RIGHT, FONT_LG, C_RING_BG,
                          lv.ALIGN.RIGHT_MID, -30, 0)

gear_letters = ["P", "R", "N", "D"]
gear_labels = {}
gx = 200
for g in gear_letters:
    col = C_BRIGHT if g == "D" else C_GRAY
    lb = create_label(status_bar, g, FONT_LG, col, lv.ALIGN.LEFT_MID, gx, 0)
    gear_labels[g] = lb
    gx += 50

create_label(status_bar, lv.SYMBOL.EYE_OPEN, FONT_MD, C_CYAN,
             lv.ALIGN.CENTER, -80, 0)

lbl_clock = create_label(status_bar, "14:32", FONT_LG, C_WHITE,
                         lv.ALIGN.CENTER, 0, 0)

lbl_ext_temp = create_label(status_bar, "22\xb0C", FONT_MD, C_WHITE,
                            lv.ALIGN.CENTER, 80, 0)

lbl_drive_mode = create_label(status_bar, "COMFORT", FONT_SM, C_CYAN,
                              lv.ALIGN.RIGHT_MID, -200, 0)

create_label(status_bar, lv.SYMBOL.WIFI, FONT_SM, C_DIM,
             lv.ALIGN.RIGHT_MID, -100, 0)


# ═════════════════════════════════════════════════════════════
#   HEADER BAR (top)
# ═════════════════════════════════════════════════════════════
header = create_container(scr, 0, 0, SCR_W, 50)
header.set_style_bg_color(C_PANEL, 0)
header.set_style_bg_opa(lv.OPA._80, 0)

create_label(header, "EV DASHBOARD", FONT_SM, C_DIM,
             lv.ALIGN.LEFT_MID, 15, 0)

lbl_trip = create_label(header, "TRIP A: 0.0 km", FONT_SM, C_DIM,
                        lv.ALIGN.CENTER, 0, 0)

lbl_avg_speed = create_label(header, "AVG: 0 km/h", FONT_SM, C_DIM,
                             lv.ALIGN.RIGHT_MID, -15, 0)


# ═════════════════════════════════════════════════════════════
#   MAIN UPDATE CALLBACK (~25 fps)
# ═════════════════════════════════════════════════════════════
DT = 0.04

def main_update(timer):
    """Main simulation and UI refresh callback"""

    SIM.update(DT)

    # Speedometer
    gauge_set(spd_gauge, SIM.speed, speed_color(SIM.speed))

    # Tachometer
    gauge_set(rpm_gauge, SIM.rpm, rpm_color(SIM.rpm))

    # Battery
    bp = int(SIM.battery_pct)
    bc = battery_color(bp)
    bat_bar.set_value(bp, False)
    bat_bar.set_style_bg_color(bc, lv.PART.INDICATOR)
    lbl_bat_pct.set_text("{}%".format(bp))
    lbl_bat_pct.set_style_text_color(bc, 0)
    lbl_range.set_text("{} km".format(int(SIM.range_km)))

    # Power bar
    bar_val = int(SIM.power_kw + 60)
    if bar_val < 0:
        bar_val = 0
    if bar_val > 310:
        bar_val = 310
    pwr_bar.set_value(bar_val, False)
    pc = power_color(SIM.power_kw)
    pwr_bar.set_style_bg_color(pc, lv.PART.INDICATOR)
    if SIM.power_kw < -2:
        pwr_txt = "REGEN {:.0f} kW".format(abs(SIM.power_kw))
    else:
        pwr_txt = "{:.0f} kW".format(SIM.power_kw)
    lbl_power.set_text(pwr_txt)
    lbl_power.set_style_text_color(pc, 0)

    # Driving state indicator
    if SIM.state == ST_ACCELERATE:
        lbl_state_icon.set_text(lv.SYMBOL.UP)
        lbl_state_icon.set_style_text_color(C_GREEN, 0)
        lbl_state_txt.set_text("ACCEL")
    elif SIM.state == ST_BRAKE:
        lbl_state_icon.set_text(lv.SYMBOL.DOWN)
        lbl_state_icon.set_style_text_color(C_RED, 0)
        lbl_state_txt.set_text("BRAKE")
    elif SIM.state == ST_COAST:
        lbl_state_icon.set_text(lv.SYMBOL.MINUS)
        lbl_state_icon.set_style_text_color(C_YELLOW, 0)
        lbl_state_txt.set_text("COAST")
    else:
        lbl_state_icon.set_text(lv.SYMBOL.RIGHT)
        lbl_state_icon.set_style_text_color(C_CYAN, 0)
        lbl_state_txt.set_text("CRUISE")

    # Temperatures
    lbl_motor_t.set_text("{:.0f}\xb0C".format(SIM.motor_temp))
    if SIM.motor_temp < 70:
        mt_col = C_WHITE
    elif SIM.motor_temp < 90:
        mt_col = C_YELLOW
    else:
        mt_col = C_RED
    lbl_motor_t.set_style_text_color(mt_col, 0)

    lbl_bat_t.set_text("{:.0f}\xb0C".format(SIM.bat_temp))
    if SIM.bat_temp < 40:
        bt_col = C_WHITE
    elif SIM.bat_temp < 50:
        bt_col = C_YELLOW
    else:
        bt_col = C_RED
    lbl_bat_t.set_style_text_color(bt_col, 0)

    # Efficiency
    if SIM.speed > 5:
        eff = SIM.power_kw / SIM.speed * 100
        if eff < 0:
            eff = 0
        lbl_eff.set_text("{:.1f}".format(eff))
        lbl_eff.set_style_text_color(C_GREEN if eff < 18 else C_YELLOW, 0)

    # Odometer
    lbl_odo.set_text("{:.0f} km".format(SIM.odo_km))

    # V max
    lbl_vmax.set_text("{:.0f}".format(SIM.v_max))

    # Trip and average speed
    lbl_trip.set_text("TRIP A: {:.1f} km".format(SIM.trip_km))
    if SIM.spd_samples > 0:
        avg = SIM.spd_accum / SIM.spd_samples
        lbl_avg_speed.set_text("AVG: {:.0f} km/h".format(avg))

    # Clock
    hrs = int(SIM.clock_s // 3600)
    mins = int((SIM.clock_s % 3600) // 60)
    lbl_clock.set_text("{:02d}:{:02d}".format(hrs, mins))

    # Turn signal blinkers
    blink_on = (SIM.blink_cnt % 50) < 25

    if SIM.state == ST_ACCELERATE and SIM.speed > 100:
        lbl_turn_r.set_style_text_color(C_ORANGE if blink_on else C_RING_BG, 0)
    else:
        lbl_turn_r.set_style_text_color(C_RING_BG, 0)

    if SIM.state == ST_CRUISE and SIM.prev_speed > SIM.speed + 0.5 and SIM.speed > 100:
        lbl_turn_l.set_style_text_color(C_ORANGE if blink_on else C_RING_BG, 0)
    else:
        lbl_turn_l.set_style_text_color(C_RING_BG, 0)


# ═════════════════════════════════════════════════════════════
#   START
# ═════════════════════════════════════════════════════════════
_main_timer = lv.timer_create(main_update, 40, None)

print("=== EV Dashboard started ===")
print("Display: 1024x600 | Realistic highway simulation active")
