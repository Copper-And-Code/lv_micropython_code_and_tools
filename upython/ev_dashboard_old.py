"""
===============================================================
  ELECTRIC VEHICLE DASHBOARD - MicroPython + LVGL 9.3
  Target: STM32H743 | 32 MB SDRAM | 1024 x 600 LCD + Touch
  Simulates highway driving with speed/RPM correlation
===============================================================
"""

import lvgl as lv
import math
import display_driver

# ─── SCREEN & RESOLUTION ────────────────────────────────────
SCR_W = 1024
SCR_H = 600

# ─── FONT DETECTION ─────────────────────────────────────────
# Adatta automaticamente ai font compilati nel tuo firmware
def _try_font(names):
    for n in names:
        try:
            return getattr(lv, n)
        except Exception:
            pass
    return lv.font_montserrat_14

FONT_XXL  = _try_font(["font_montserrat_48", "font_montserrat_44",
                        "font_montserrat_40", "font_montserrat_36"])
FONT_XL   = _try_font(["font_montserrat_36", "font_montserrat_32",
                        "font_montserrat_28"])
FONT_LG   = _try_font(["font_montserrat_24", "font_montserrat_22",
                        "font_montserrat_20"])
FONT_MD   = _try_font(["font_montserrat_18", "font_montserrat_16"])
FONT_SM   = _try_font(["font_montserrat_14"])
FONT_XS   = _try_font(["font_montserrat_12", "font_montserrat_10",
                        "font_montserrat_14"])

# ─── PALETTE ─────────────────────────────────────────────────
C_BG         = lv.color_hex(0x080810)
C_PANEL      = lv.color_hex(0x10101C)
C_RING_BG    = lv.color_hex(0x1A1A2E)
C_GRAY       = lv.color_hex(0x3A3A5C)
C_WHITE      = lv.color_hex(0xE8E8F0)
C_BRIGHT     = lv.color_hex(0xFFFFFF)
C_CYAN       = lv.color_hex(0x00E5FF)
C_GREEN      = lv.color_hex(0x00E676)
C_LIME       = lv.color_hex(0x76FF03)
C_YELLOW     = lv.color_hex(0xFFD740)
C_ORANGE     = lv.color_hex(0xFF6D00)
C_RED        = lv.color_hex(0xFF1744)
C_BLUE       = lv.color_hex(0x448AFF)
C_TEAL       = lv.color_hex(0x00BFA5)
C_PURPLE     = lv.color_hex(0xB388FF)
C_DIM        = lv.color_hex(0x50506A)
C_REGEN      = lv.color_hex(0x00C853)
C_CONSUME    = lv.color_hex(0xFF6E40)

# ─── SIMULATION STATE ───────────────────────────────────────
class SimState:
    def __init__(self):
        self.t           = 0.0
        self.speed       = 0.0
        self.prev_speed  = 0.0
        self.rpm         = 0.0
        self.power_kw    = 0.0
        self.battery_pct = 94.0
        self.range_km    = 347.0
        self.motor_temp  = 42.0
        self.bat_temp    = 29.0
        self.odo_km      = 12873.4
        self.gear        = "D"
        self.blinker_on  = False
        self.blink_cnt   = 0

S = SimState()

# ─── SCREEN SETUP ───────────────────────────────────────────
# Strategia: prova display_get_default -> get_screen_active,
# poi screen_active(), infine crea un nuovo screen.
scr = None

# Metodo 1: via display object (LVGL 9.x standard)
try:
    disp = lv.display_get_default()
    if disp is not None:
        for attr in ["get_screen_active", "get_scr_act", "screen_active"]:
            if hasattr(disp, attr):
                scr = getattr(disp, attr)()
                if scr is not None:
                    break
except Exception:
    pass

# Metodo 2: funzione globale
if scr is None:
    try:
        scr = lv.screen_active()
    except Exception:
        pass

# Metodo 3: crea un nuovo screen e caricalo
if scr is None:
    scr = lv.obj()
    lv.screen_load(scr)

scr.set_style_bg_color(C_BG, 0)
scr.remove_flag(lv.obj.FLAG.SCROLLABLE)

# ─── HELPERS ─────────────────────────────────────────────────
def _opa(obj, part=0):
    """Rende trasparente lo sfondo e rimuove bordi"""
    obj.set_style_bg_opa(lv.OPA.TRANSP, part)
    obj.set_style_border_width(0, part)

def _container(parent, x, y, w, h):
    c = lv.obj(parent)
    c.set_size(w, h)
    c.set_pos(x, y)
    _opa(c)
    c.set_style_pad_all(0, 0)
    c.remove_flag(lv.obj.FLAG.SCROLLABLE)
    c.remove_flag(lv.obj.FLAG.CLICKABLE)
    return c

def _label(parent, text, font, color, align=lv.ALIGN.CENTER, ox=0, oy=0):
    lb = lv.label(parent)
    lb.set_text(text)
    lb.set_style_text_color(color, 0)
    lb.set_style_text_font(font, 0)
    lb.align(align, ox, oy)
    return lb

def _value_to_angle(val, vmin, vmax, sweep=270, start=135):
    """Converte un valore in angolo LVGL (CW da est)"""
    ratio = (val - vmin) / max((vmax - vmin), 1)
    ratio = max(0.0, min(1.0, ratio))
    return start + ratio * sweep

def _angle_xy(angle_deg, radius, cx, cy):
    """Coordinate su schermo dato angolo LVGL"""
    rad = math.radians(angle_deg)
    return int(cx + radius * math.cos(rad)), int(cy + radius * math.sin(rad))

def _speed_color(spd):
    if spd < 100:    return C_GREEN
    elif spd < 140:  return C_CYAN
    elif spd < 180:  return C_YELLOW
    elif spd < 220:  return C_ORANGE
    else:            return C_RED

def _rpm_color(rpm):
    if rpm < 5000:   return C_TEAL
    elif rpm < 8000: return C_CYAN
    elif rpm < 11000:return C_YELLOW
    else:            return C_RED

def _power_color(kw):
    if kw < 0:       return C_REGEN
    elif kw < 40:    return C_GREEN
    elif kw < 80:    return C_YELLOW
    elif kw < 150:   return C_ORANGE
    else:            return C_RED

def _bat_color(pct):
    if pct > 50:   return C_GREEN
    elif pct > 25: return C_YELLOW
    elif pct > 10: return C_ORANGE
    else:          return C_RED


# ═════════════════════════════════════════════════════════════
#   ARC-BASED GAUGE BUILDER
# ═════════════════════════════════════════════════════════════
def build_arc_gauge(parent, cx, cy, diameter, arc_w,
                    vmin, vmax, color, title_str, unit_str,
                    tick_step=None, tick_labels=True):
    """
    Crea un gauge circolare con arco 270° aperto in basso.
    Ritorna dict di widgets per aggiornamento dinamico.
    """
    r = diameter // 2
    cont = _container(parent, cx - r, cy - r, diameter, diameter)

    # --- Zone decorative (archi sottili colorati) ---
    # Outer thin ring for decoration
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

    # --- Background arc (track) ---
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
    # Track style
    arc_track.set_style_arc_width(arc_w, lv.PART.MAIN)
    arc_track.set_style_arc_color(C_RING_BG, lv.PART.MAIN)
    arc_track.set_style_arc_rounded(False, lv.PART.MAIN)
    # Indicator style
    arc_track.set_style_arc_width(arc_w, lv.PART.INDICATOR)
    arc_track.set_style_arc_color(color, lv.PART.INDICATOR)
    arc_track.set_style_arc_rounded(True, lv.PART.INDICATOR)
    # No knob
    arc_track.set_style_bg_opa(lv.OPA.TRANSP, lv.PART.KNOB)
    arc_track.set_style_pad_all(0, lv.PART.KNOB)

    # --- Inner thin glow arc (follows indicator for depth) ---
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

    # --- Needle dot ---
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
    # Initial position (min value)
    dx, dy = _angle_xy(135, (tr_sz / 2 - arc_w / 2), r, r)
    dot.set_pos(dx - dot_sz // 2, dy - dot_sz // 2)

    # --- Tick marks (labels attorno all'arco) ---
    tick_labels_list = []
    if tick_step:
        tick_r = tr_sz / 2 + 12          # raggio per label tick
        minor_r = tr_sz / 2 + 4          # raggio per tacca minore
        for v in range(vmin, vmax + 1, tick_step):
            ang = _value_to_angle(v, vmin, vmax)
            tx, ty = _angle_xy(ang, tick_r, r, r)
            lb = lv.label(cont)
            lb.set_text(str(v))
            lb.set_style_text_color(C_DIM, 0)
            lb.set_style_text_font(FONT_XS, 0)
            lb.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
            # Centra il label sulla posizione calcolata
            lb.align(lv.ALIGN.TOP_LEFT, 0, 0)
            lb.set_pos(tx - 16, ty - 8)
            tick_labels_list.append(lb)

    # --- Title (sopra centro) ---
    _label(cont, title_str, FONT_SM, C_GRAY, lv.ALIGN.CENTER, 0, -r // 3 - 5)

    # --- Big value ---
    lbl_val = _label(cont, "0", FONT_XXL, C_BRIGHT, lv.ALIGN.CENTER, 0, 10)

    # --- Unit (sotto il valore) ---
    _label(cont, unit_str, FONT_MD, C_DIM, lv.ALIGN.CENTER, 0, r // 3 + 10)

    return {
        "arc": arc_track, "glow": arc_glow, "dot": dot,
        "lbl_val": lbl_val, "ticks": tick_labels_list,
        "vmin": vmin, "vmax": vmax,
        "tr_sz": tr_sz, "arc_w": arc_w,
        "dot_sz": dot_sz, "cx": r, "cy": r,
    }


def gauge_set(g, value, color=None):
    """Aggiorna il gauge con nuovo valore e colore opzionale"""
    v = max(g["vmin"], min(g["vmax"], value))
    vi = int(v)

    g["arc"].set_value(vi)
    g["glow"].set_value(vi)
    g["lbl_val"].set_text(str(vi))

    if color:
        g["arc"].set_style_arc_color(color, lv.PART.INDICATOR)
        g["glow"].set_style_arc_color(color, lv.PART.INDICATOR)
        g["dot"].set_style_shadow_color(color, 0)

    # Aggiorna posizione dot
    ang = _value_to_angle(v, g["vmin"], g["vmax"])
    nr = g["tr_sz"] / 2 - g["arc_w"] / 2
    nx, ny = _angle_xy(ang, nr, g["cx"], g["cy"])
    ds = g["dot_sz"]
    g["dot"].set_pos(nx - ds // 2, ny - ds // 2)


# ═════════════════════════════════════════════════════════════
#   COSTRUZIONE CRUSCOTTO
# ═════════════════════════════════════════════════════════════

# --- Speedometer (sinistra-centro) ---
spd_gauge = build_arc_gauge(
    scr, cx=290, cy=250, diameter=400, arc_w=22,
    vmin=0, vmax=260, color=C_CYAN,
    title_str="VELOCITA'", unit_str="km/h",
    tick_step=40
)

# --- Tachometer / RPM (destra-centro) ---
rpm_gauge = build_arc_gauge(
    scr, cx=734, cy=250, diameter=340, arc_w=18,
    vmin=0, vmax=14000, color=C_TEAL,
    title_str="MOTORE", unit_str="RPM",
    tick_step=2000
)


# ═════════════════════════════════════════════════════════════
#   PANNELLO BATTERIA (sinistra)
# ═════════════════════════════════════════════════════════════
bat_panel = _container(scr, 10, 60, 100, 360)

_label(bat_panel, lv.SYMBOL.BATTERY_FULL, FONT_LG, C_GREEN,
       lv.ALIGN.TOP_MID, 0, 0)

lbl_bat_pct = _label(bat_panel, "94%", FONT_LG, C_GREEN,
                     lv.ALIGN.TOP_MID, 0, 32)

# Barra verticale batteria
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

# Range label
_label(bat_panel, "RANGE", FONT_XS, C_DIM, lv.ALIGN.TOP_MID, 0, 282)
lbl_range = _label(bat_panel, "347 km", FONT_MD, C_WHITE,
                   lv.ALIGN.TOP_MID, 0, 298)


# ═════════════════════════════════════════════════════════════
#   PANNELLO POTENZA (centro-basso)
# ═════════════════════════════════════════════════════════════
pwr_panel = _container(scr, 170, 470, 684, 55)

_label(pwr_panel, "REGEN", FONT_XS, C_REGEN, lv.ALIGN.LEFT_MID, 2, -14)
_label(pwr_panel, "POTENZA", FONT_XS, C_DIM, lv.ALIGN.CENTER, 0, -14)
_label(pwr_panel, "MAX", FONT_XS, C_CONSUME, lv.ALIGN.RIGHT_MID, -10, -14)

# Bar potenza (range: -60 a +250 kW, normalizzato 0-310)
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

# Zero-point marker (dove 0kW = pos 60 nella barra 0-310)
zero_mark = lv.obj(pwr_panel)
zero_mark.set_size(2, 22)
zero_px = int(60 / 310 * 660) + (170 + 684 // 2 - 330) - 170 + 12
zero_mark.set_pos(int(60 / 310 * 660) + 12, 3)
zero_mark.set_style_bg_color(C_WHITE, 0)
zero_mark.set_style_bg_opa(lv.OPA._60, 0)
zero_mark.set_style_border_width(0, 0)

lbl_power = _label(pwr_panel, "0 kW", FONT_SM, C_WHITE,
                   lv.ALIGN.CENTER, 0, 28)


# ═════════════════════════════════════════════════════════════
#   PANNELLO INFO DESTRA (temperature, odometro)
# ═════════════════════════════════════════════════════════════
info_right = _container(scr, 920, 60, 98, 360)

# Motor temperature
_label(info_right, "MOTORE", FONT_XS, C_DIM, lv.ALIGN.TOP_MID, 0, 0)
lbl_motor_t = _label(info_right, "42" + chr(0x00B0) + "C", FONT_MD,
                     C_WHITE, lv.ALIGN.TOP_MID, 0, 16)

# Battery temperature
_label(info_right, "BATT", FONT_XS, C_DIM, lv.ALIGN.TOP_MID, 0, 55)
lbl_bat_t = _label(info_right, "29" + chr(0x00B0) + "C", FONT_MD,
                   C_WHITE, lv.ALIGN.TOP_MID, 0, 71)

# Efficienza
_label(info_right, "EFFICIENZA", FONT_XS, C_DIM, lv.ALIGN.TOP_MID, 0, 110)
lbl_eff = _label(info_right, "16.2", FONT_MD, C_GREEN,
                 lv.ALIGN.TOP_MID, 0, 126)
_label(info_right, "kWh/100km", FONT_XS, C_DIM, lv.ALIGN.TOP_MID, 0, 148)

# Odometro
_label(info_right, "ODO", FONT_XS, C_DIM, lv.ALIGN.TOP_MID, 0, 185)
lbl_odo = _label(info_right, "12873 km", FONT_MD, C_WHITE,
                 lv.ALIGN.TOP_MID, 0, 201)

# V max in sessione
_label(info_right, "V MAX", FONT_XS, C_DIM, lv.ALIGN.TOP_MID, 0, 240)
lbl_vmax = _label(info_right, "0", FONT_MD, C_YELLOW,
                  lv.ALIGN.TOP_MID, 0, 256)


# ═════════════════════════════════════════════════════════════
#   BARRA DI STATO INFERIORE
# ═════════════════════════════════════════════════════════════
status_bar = _container(scr, 0, 545, SCR_W, 55)
status_bar.set_style_bg_color(C_PANEL, 0)
status_bar.set_style_bg_opa(lv.OPA.COVER, 0)
status_bar.set_style_border_width(0, 0)

# Freccia sinistra
lbl_turn_l = _label(status_bar, lv.SYMBOL.LEFT, FONT_LG, C_RING_BG,
                    lv.ALIGN.LEFT_MID, 30, 0)

# Gear selector
gear_letters = ["P", "R", "N", "D"]
gear_labels = {}
gx = 200
for g in gear_letters:
    col = C_BRIGHT if g == "D" else C_GRAY
    lb = _label(status_bar, g, FONT_LG, col, lv.ALIGN.LEFT_MID, gx, 0)
    gear_labels[g] = lb
    gx += 50

# Headlights icon
lbl_lights = _label(status_bar, lv.SYMBOL.EYE_OPEN, FONT_MD, C_CYAN,
                    lv.ALIGN.CENTER, -80, 0)

# Orologio
lbl_clock = _label(status_bar, "14:32", FONT_LG, C_WHITE,
                   lv.ALIGN.CENTER, 0, 0)

# Temperatura esterna
lbl_ext_temp = _label(status_bar, "22" + chr(0x00B0) + "C", FONT_MD,
                      C_WHITE, lv.ALIGN.CENTER, 80, 0)

# Modalita' guida
lbl_drive_mode = _label(status_bar, "COMFORT", FONT_SM, C_CYAN,
                        lv.ALIGN.RIGHT_MID, -200, 0)

# Freccia destra
lbl_turn_r = _label(status_bar, lv.SYMBOL.RIGHT, FONT_LG, C_RING_BG,
                    lv.ALIGN.RIGHT_MID, -30, 0)

# Icona WiFi / connettivita
_label(status_bar, lv.SYMBOL.WIFI, FONT_SM, C_DIM,
       lv.ALIGN.RIGHT_MID, -100, 0)


# ═════════════════════════════════════════════════════════════
#   INDICATORI SUPERIORI (header)
# ═════════════════════════════════════════════════════════════
header = _container(scr, 0, 0, SCR_W, 50)
header.set_style_bg_color(C_PANEL, 0)
header.set_style_bg_opa(lv.OPA._80, 0)

_label(header, "EV DASHBOARD", FONT_SM, C_DIM,
       lv.ALIGN.LEFT_MID, 15, 0)

lbl_trip = _label(header, "TRIP A: 0.0 km", FONT_SM, C_DIM,
                  lv.ALIGN.CENTER, 0, 0)

lbl_avg_speed = _label(header, "Media: 0 km/h", FONT_SM, C_DIM,
                       lv.ALIGN.RIGHT_MID, -15, 0)


# ═════════════════════════════════════════════════════════════
#   SIMULAZIONE GUIDA AUTOSTRADALE
# ═════════════════════════════════════════════════════════════

# Tracking per statistiche
v_max_session = 0.0
trip_dist     = 0.0
speed_accum   = 0.0
speed_samples = 0
DT            = 0.04   # ~25 fps (40 ms timer)
clock_seconds = 14 * 3600 + 32 * 60  # parte da 14:32

def sim_highway_speed(t):
    """
    Genera un profilo di velocita' autostradale realistico.
    Combina onde sinusoidali a diverse frequenze per simulare:
    - Andatura costante ~120 km/h
    - Variazioni graduali (sorpassi, rallentamenti)
    - Micro-variazioni (pedale non perfettamente fermo)
    """
    base = 118.0
    # Onda lenta: cambi di andatura (sorpassi, tratti diversi)
    slow    = 16.0 * math.sin(t * 0.12)
    # Onda media: piccole accelerazioni/frenate
    medium  = 9.0  * math.sin(t * 0.37 + 1.2)
    # Onda veloce: micro-variazioni pedale
    fast    = 4.0  * math.sin(t * 1.1 + 0.7)
    # Onda molto lenta: rallentamenti zona lavori / code
    ultra   = 20.0 * math.sin(t * 0.04 + 2.5)
    # Effetto "cruise": a volte velocita' molto stabile
    cruise  = 5.0  * math.sin(t * 0.22) * math.sin(t * 0.07)

    spd = base + slow + medium + fast + ultra + cruise

    # Clamp realistico
    if spd < 60:
        spd = 60 + abs(math.sin(t * 0.5)) * 10
    if spd > 195:
        spd = 195 - abs(math.sin(t * 0.3)) * 5

    return spd


def sim_update(timer):
    """Callback del timer principale - aggiorna tutta la simulazione"""
    global v_max_session, trip_dist, speed_accum, speed_samples
    global clock_seconds

    S.t += DT

    # ── Velocita' ──
    S.prev_speed = S.speed
    S.speed = sim_highway_speed(S.t)

    # ── RPM (rapporto tipico EV: riduttore ~9:1, ruote ~0.33m) ──
    #    RPM approssimativo: speed_kmh * 48-55
    rpm_ratio = 50.0 + 3.0 * math.sin(S.t * 0.8)
    S.rpm = S.speed * rpm_ratio
    if S.rpm > 14000:
        S.rpm = 14000

    # ── Potenza (kW) ──
    accel = (S.speed - S.prev_speed) / DT  # km/h per secondo
    # Consumo base proporzionale al quadrato della velocita' (drag)
    drag_kw = 0.0008 * S.speed * S.speed
    # Componente accelerazione
    accel_kw = accel * 1.8
    S.power_kw = drag_kw + accel_kw
    if S.power_kw < -60:
        S.power_kw = -60
    if S.power_kw > 250:
        S.power_kw = 250

    # ── Batteria (scarica lenta, ~18 kWh/100km) ──
    km_this_tick = S.speed * DT / 3600.0
    kwh_used = abs(S.power_kw) * DT / 3600.0
    if S.power_kw > 0:
        S.battery_pct -= kwh_used / 0.78  # ~78 kWh pack
    else:
        S.battery_pct += kwh_used * 0.85 / 0.78  # regen 85% eff

    S.battery_pct = max(0, min(100, S.battery_pct))
    S.range_km = S.battery_pct / 100 * 380  # ~380 km al 100%

    # ── Temperature ──
    target_mt = 40 + S.power_kw * 0.15
    S.motor_temp += (target_mt - S.motor_temp) * 0.002
    S.bat_temp += (28 + S.power_kw * 0.03 - S.bat_temp) * 0.001

    # ── Odometro & Trip ──
    S.odo_km += km_this_tick
    trip_dist += km_this_tick

    # ── Statistiche ──
    if S.speed > v_max_session:
        v_max_session = S.speed
    speed_accum += S.speed
    speed_samples += 1

    # ── Orologio (simula 10x velocita' reale) ──
    clock_seconds += DT * 10
    if clock_seconds >= 86400:
        clock_seconds -= 86400
    hrs = int(clock_seconds // 3600)
    mins = int((clock_seconds % 3600) // 60)

    # ── Frecce (lampeggio periodico) ──
    S.blink_cnt += 1
    blink_phase = (S.blink_cnt % 50) < 25
    # Simula freccia destra ogni ~200 tick (sorpasso)
    do_blink_r = (S.blink_cnt % 400) < 100

    # ══════════════════════════════════════════════════════
    #   AGGIORNAMENTO WIDGET
    # ══════════════════════════════════════════════════════

    # Speedometer
    gauge_set(spd_gauge, S.speed, _speed_color(S.speed))

    # RPM
    gauge_set(rpm_gauge, S.rpm, _rpm_color(S.rpm))

    # Batteria
    bp = int(S.battery_pct)
    bat_bar.set_value(bp, False)
    bc = _bat_color(bp)
    bat_bar.set_style_bg_color(bc, lv.PART.INDICATOR)
    lbl_bat_pct.set_text("{}%".format(bp))
    lbl_bat_pct.set_style_text_color(bc, 0)
    lbl_range.set_text("{} km".format(int(S.range_km)))

    # Potenza
    # Mappa: -60kW → 0, 0kW → 60, +250kW → 310
    bar_val = int(S.power_kw + 60)
    bar_val = max(0, min(310, bar_val))
    pwr_bar.set_value(bar_val, False)
    pc = _power_color(S.power_kw)
    pwr_bar.set_style_bg_color(pc, lv.PART.INDICATOR)
    pwr_txt = "{:.0f} kW".format(S.power_kw)
    if S.power_kw < -2:
        pwr_txt = "REGEN {:.0f} kW".format(abs(S.power_kw))
    lbl_power.set_text(pwr_txt)
    lbl_power.set_style_text_color(pc, 0)

    # Temperature
    lbl_motor_t.set_text("{:.0f}".format(S.motor_temp) + chr(0x00B0) + "C")
    mt_col = C_WHITE if S.motor_temp < 70 else (C_YELLOW if S.motor_temp < 90 else C_RED)
    lbl_motor_t.set_style_text_color(mt_col, 0)

    lbl_bat_t.set_text("{:.0f}".format(S.bat_temp) + chr(0x00B0) + "C")
    bt_col = C_WHITE if S.bat_temp < 40 else (C_YELLOW if S.bat_temp < 50 else C_RED)
    lbl_bat_t.set_style_text_color(bt_col, 0)

    # Efficienza (kWh/100km, media mobile)
    if S.speed > 5:
        eff = S.power_kw / S.speed * 100
        lbl_eff.set_text("{:.1f}".format(max(0, eff)))
        lbl_eff.set_style_text_color(C_GREEN if eff < 18 else C_YELLOW, 0)

    # Odometro
    lbl_odo.set_text("{:.0f} km".format(S.odo_km))

    # V max
    lbl_vmax.set_text("{:.0f}".format(v_max_session))

    # Trip & media
    lbl_trip.set_text("TRIP A: {:.1f} km".format(trip_dist))
    if speed_samples > 0:
        avg = speed_accum / speed_samples
        lbl_avg_speed.set_text("Media: {:.0f} km/h".format(avg))

    # Orologio
    lbl_clock.set_text("{:02d}:{:02d}".format(hrs, mins))

    # Frecce
    if do_blink_r and blink_phase:
        lbl_turn_r.set_style_text_color(C_ORANGE, 0)
    else:
        lbl_turn_r.set_style_text_color(C_RING_BG, 0)

    # Freccia sinistra ogni tanto
    do_blink_l = ((S.blink_cnt + 200) % 600) < 80
    if do_blink_l and blink_phase:
        lbl_turn_l.set_style_text_color(C_ORANGE, 0)
    else:
        lbl_turn_l.set_style_text_color(C_RING_BG, 0)


# ═════════════════════════════════════════════════════════════
#   AVVIO TIMER DI SIMULAZIONE (~25 fps)
# ═════════════════════════════════════════════════════════════
_timer = lv.timer_create(sim_update, 40, None)

print("=== EV Dashboard avviato ===")
print("Display: 1024 x 600 | Simulazione autostradale attiva")
