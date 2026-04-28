###############################################################################
#  LVGL 9.3 — AUTO-DEMO  (self-running showcase)
#  ─────────────────────────────────────────────────────────────────────────────
#  Target  : STM32H743  ·  32 MB SDRAM  ·  1024×600 LCD  ·  Capacitive Touch
#  Stack   : MicroPython + LVGL 9.3 (bindings already ported)
#
#  This version automatically cycles through every tab, pressing buttons,
#  moving sliders, typing text, changing selections — in an infinite loop.
#  Touch is still active: the user can interact at any time.
###############################################################################

# ═════════════════════════════════════════════════════════════════════════════
#  SETTINGS
# ═════════════════════════════════════════════════════════════════════════════
LANG = "en"                       # <<< "en" | "it"
AUTO_DEMO = True                  # <<< Set False to disable auto-demo

import lvgl as lv
import math
import display_driver

# ═════════════════════════════════════════════════════════════════════════════
#  TRANSLATION STRINGS
# ═════════════════════════════════════════════════════════════════════════════
_S = {
    "tab_home":       {"en": "Home",            "it": "Home"},
    "tab_buttons":    {"en": "Buttons & Input", "it": "Pulsanti & Input"},
    "tab_data":       {"en": "Data Display",    "it": "Dati & Grafici"},
    "tab_selection":  {"en": "Selection",        "it": "Selezione"},
    "tab_text":       {"en": "Text Input",      "it": "Testo"},
    "tab_anim":       {"en": "Animations",      "it": "Animazioni"},
    "tab_styles":     {"en": "Styles",          "it": "Stili"},

    "welcome_title":  {"en": "LVGL 9.3 on STM32H743",
                       "it": "LVGL 9.3 su STM32H743"},
    "welcome_sub":    {"en": "AUTO-DEMO — Comprehensive Widget Showcase\n1024 x 600 · 32 MB SDRAM · Capacitive Touch",
                       "it": "AUTO-DEMO — Vetrina Completa dei Widget\n1024 x 600 · 32 MB SDRAM · Touch Capacitivo"},
    "home_info":      {"en": "This demo runs automatically.\nTouch is still active — feel free to interact!\n\n"
                             "• Buttons & Input — interactive controls\n"
                             "• Data Display — charts, bars, gauges\n"
                             "• Selection — dropdowns, rollers, tables\n"
                             "• Text Input — textarea & keyboard\n"
                             "• Animations — real-time motion & timers\n"
                             "• Styles — colors, gradients, rounded cards",
                       "it": "Questa demo gira automaticamente.\nIl touch è attivo — puoi interagire!\n\n"
                             "• Pulsanti & Input — controlli interattivi\n"
                             "• Dati & Grafici — grafici, barre, indicatori\n"
                             "• Selezione — dropdown, roller, tabelle\n"
                             "• Testo — area di testo e tastiera\n"
                             "• Animazioni — movimento e timer\n"
                             "• Stili — colori, gradienti, card"},

    "btn_normal":     {"en": "Click me!",       "it": "Cliccami!"},
    "btn_toggle":     {"en": "Toggle",          "it": "Attiva/Disattiva"},
    "btn_disabled":   {"en": "Disabled",        "it": "Disabilitato"},
    "click_count":    {"en": "Clicks: {}",      "it": "Click: {}"},
    "switch_label":   {"en": "Enable feature",  "it": "Attiva funzione"},
    "switch_on":      {"en": "ON",              "it": "ATTIVO"},
    "switch_off":     {"en": "OFF",             "it": "SPENTO"},
    "cb1":            {"en": "Option A",        "it": "Opzione A"},
    "cb2":            {"en": "Option B",        "it": "Opzione B"},
    "cb3":            {"en": "Option C",        "it": "Opzione C"},
    "slider_label":   {"en": "Brightness: {}%", "it": "Luminosità: {}%"},

    "chart_line":     {"en": "Temperature (°C)", "it": "Temperatura (°C)"},
    "chart_bar":      {"en": "Monthly Sales",    "it": "Vendite Mensili"},
    "progress":       {"en": "Progress: {}%",    "it": "Progresso: {}%"},
    "arc_gauge":      {"en": "CPU Load",         "it": "Carico CPU"},
    "led_title":      {"en": "Status LEDs",      "it": "LED di Stato"},
    "led_names":      {"en": ["Power", "Network", "Error"],
                       "it": ["Alimentaz.", "Rete", "Errore"]},

    "dd_label":       {"en": "Choose a city:",     "it": "Scegli una città:"},
    "dd_options":     {"en": "London\nParis\nBerlin\nRome\nMadrid\nTokyo",
                       "it": "Londra\nParigi\nBerlino\nRoma\nMadrid\nTokyo"},
    "dd_selected":    {"en": "Selected: {}",       "it": "Selezionato: {}"},
    "roller_label":   {"en": "Pick a month:",      "it": "Scegli un mese:"},
    "roller_opts":    {"en": "January\nFebruary\nMarch\nApril\nMay\nJune\n"
                             "July\nAugust\nSeptember\nOctober\nNovember\nDecember",
                       "it": "Gennaio\nFebbraio\nMarzo\nAprile\nMaggio\nGiugno\n"
                             "Luglio\nAgosto\nSettembre\nOttobre\nNovembre\nDicembre"},
    "table_title":    {"en": "Sensor Data",        "it": "Dati Sensori"},
    "table_hdr":      {"en": ["Sensor", "Value", "Unit", "Status"],
                       "it": ["Sensore", "Valore", "Unità", "Stato"]},
    "list_title":     {"en": "Settings",           "it": "Impostazioni"},
    "list_items":     {"en": ["Wi-Fi", "Bluetooth", "Display", "Sound", "About"],
                       "it": ["Wi-Fi", "Bluetooth", "Display", "Audio", "Info"]},

    "ta_placeholder": {"en": "Type something here ...",
                       "it": "Scrivi qualcosa qui ..."},
    "ta_title":       {"en": "On-screen keyboard demo",
                       "it": "Demo tastiera a schermo"},

    "anim_title":     {"en": "Live Animations",    "it": "Animazioni Live"},
    "anim_bar":       {"en": "Animated bar",       "it": "Barra animata"},
    "anim_arc":       {"en": "Spinning arc",       "it": "Arco rotante"},
    "anim_pos":       {"en": "Bouncing box",       "it": "Scatola rimbalzante"},

    "styles_title":   {"en": "Style Showcase",     "it": "Vetrina Stili"},
    "card_titles":    {"en": ["Gradient Card", "Outlined Card", "Shadow Card",
                              "Rounded Card", "Accent Card", "Flat Card"],
                       "it": ["Card Gradiente", "Card Bordo", "Card Ombra",
                              "Card Arrotondata", "Card Accento", "Card Piatta"]},
}

def T(key):
    entry = _S.get(key, None)
    if entry is None:
        return key
    return entry.get(LANG, entry.get("en", key))

# ═════════════════════════════════════════════════════════════════════════════
#  COLOURS
# ═════════════════════════════════════════════════════════════════════════════
COLOR_BG_DARK    = lv.color_hex(0x1E1E2E)
COLOR_BG_CARD    = lv.color_hex(0x2A2A3C)
COLOR_PRIMARY    = lv.color_hex(0x5B9BD5)
COLOR_ACCENT     = lv.color_hex(0x70C1B3)
COLOR_WARN       = lv.color_hex(0xF4A261)
COLOR_ERROR      = lv.color_hex(0xE76F51)
COLOR_TEXT       = lv.color_hex(0xECECEC)
COLOR_TEXT_DIM   = lv.color_hex(0x8888AA)
COLOR_GREEN      = lv.color_hex(0x2ECC71)
COLOR_WHITE      = lv.color_hex(0xFFFFFF)

# ═════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═════════════════════════════════════════════════════════════════════════════
def make_card(parent, w=lv.SIZE_CONTENT, h=lv.SIZE_CONTENT):
    card = lv.obj(parent)
    card.set_size(w, h)
    card.set_style_bg_color(COLOR_BG_CARD, 0)
    card.set_style_bg_opa(lv.OPA.COVER, 0)
    card.set_style_radius(12, 0)
    card.set_style_border_width(0, 0)
    card.set_style_pad_all(14, 0)
    card.set_style_shadow_width(20, 0)
    card.set_style_shadow_opa(lv.OPA._20, 0)
    card.set_style_shadow_color(lv.color_hex(0x000000), 0)
    return card

def section_label(parent, text):
    lbl = lv.label(parent)
    lbl.set_text(text)
    lbl.set_style_text_color(COLOR_TEXT_DIM, 0)
    return lbl

def setup_tab_bg(tab):
    tab.set_style_bg_color(COLOR_BG_DARK, 0)
    tab.set_style_bg_opa(lv.OPA.COVER, 0)
    tab.set_style_pad_all(12, 0)
    tab.set_style_pad_gap(12, 0)

def hsv_to_rgb(h, s, v):
    s_f = s / 100.0
    v_f = v / 100.0
    c = v_f * s_f
    x = c * (1 - abs((h / 60.0) % 2 - 1))
    m = v_f - c
    if   h < 60:  r, g, b = c, x, 0
    elif h < 120: r, g, b = x, c, 0
    elif h < 180: r, g, b = 0, c, x
    elif h < 240: r, g, b = 0, x, c
    elif h < 300: r, g, b = x, 0, c
    else:         r, g, b = c, 0, x
    return int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)

# ═════════════════════════════════════════════════════════════════════════════
#  TAB 1 — HOME
# ═════════════════════════════════════════════════════════════════════════════
def build_home(tab):
    setup_tab_bg(tab)
    tab.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    tab.set_flex_align(lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)

    title = lv.label(tab)
    title.set_text(T("welcome_title"))
    title.set_style_text_color(COLOR_PRIMARY, 0)
    try:
        title.set_style_text_font(lv.font_montserrat_28, 0)
    except Exception:
        pass

    sub = lv.label(tab)
    sub.set_text(T("welcome_sub"))
    sub.set_style_text_color(COLOR_TEXT, 0)
    sub.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
    try:
        sub.set_style_text_font(lv.font_montserrat_18, 0)
    except Exception:
        pass

    line = lv.obj(tab)
    line.set_size(400, 3)
    line.set_style_bg_color(COLOR_PRIMARY, 0)
    line.set_style_bg_opa(lv.OPA.COVER, 0)
    line.set_style_radius(1, 0)
    line.set_style_border_width(0, 0)
    line.remove_flag(lv.obj.FLAG.SCROLLABLE)

    card = make_card(tab, 700, lv.SIZE_CONTENT)
    card.set_style_pad_all(24, 0)
    info = lv.label(card)
    info.set_text(T("home_info"))
    info.set_style_text_color(COLOR_TEXT, 0)
    info.set_long_mode(lv.label.LONG_MODE.WRAP)
    info.set_width(660)
    return {}

# ═════════════════════════════════════════════════════════════════════════════
#  TAB 2 — BUTTONS & INPUT  (returns widget refs for auto-demo)
# ═════════════════════════════════════════════════════════════════════════════
def build_buttons(tab):
    setup_tab_bg(tab)
    tab.set_flex_flow(lv.FLEX_FLOW.ROW_WRAP)
    tab.set_flex_align(lv.FLEX_ALIGN.SPACE_EVENLY, lv.FLEX_ALIGN.START,
                       lv.FLEX_ALIGN.START)

    # Buttons card
    card_btn = make_card(tab, 460, 220)
    card_btn.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    card_btn.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START,
                            lv.FLEX_ALIGN.START)
    card_btn.set_style_pad_gap(10, 0)
    section_label(card_btn, "BUTTONS")

    row = lv.obj(card_btn)
    row.set_size(lv.pct(100), lv.SIZE_CONTENT)
    row.set_flex_flow(lv.FLEX_FLOW.ROW)
    row.set_style_pad_gap(12, 0)
    row.set_style_bg_opa(lv.OPA.TRANSP, 0)
    row.set_style_border_width(0, 0)
    row.set_style_pad_all(0, 0)
    row.remove_flag(lv.obj.FLAG.SCROLLABLE)

    counter_lbl = lv.label(card_btn)
    counter_lbl.set_text(T("click_count").format(0))
    counter_lbl.set_style_text_color(COLOR_TEXT, 0)
    click_count = [0]

    btn = lv.button(row)
    btn_lbl = lv.label(btn)
    btn_lbl.set_text(T("btn_normal"))
    btn.set_style_bg_color(COLOR_PRIMARY, 0)
    btn.set_style_radius(8, 0)
    def on_click(e):
        click_count[0] += 1
        counter_lbl.set_text(T("click_count").format(click_count[0]))
    btn.add_event_cb(on_click, lv.EVENT.CLICKED, None)

    btn_tog = lv.button(row)
    btn_tog.add_flag(lv.obj.FLAG.CHECKABLE)
    lbl_tog = lv.label(btn_tog)
    lbl_tog.set_text(T("btn_toggle"))
    btn_tog.set_style_bg_color(lv.color_hex(0x555577), 0)
    btn_tog.set_style_bg_color(COLOR_GREEN, lv.STATE.CHECKED)
    btn_tog.set_style_radius(8, 0)

    btn_dis = lv.button(row)
    lbl_dis = lv.label(btn_dis)
    lbl_dis.set_text(T("btn_disabled"))
    btn_dis.add_state(lv.STATE.DISABLED)
    btn_dis.set_style_bg_color(lv.color_hex(0x444466), 0)
    btn_dis.set_style_bg_opa(lv.OPA._60, lv.STATE.DISABLED)
    btn_dis.set_style_radius(8, 0)

    # Switch card
    card_sw = make_card(tab, 460, 220)
    card_sw.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    card_sw.set_style_pad_gap(10, 0)
    section_label(card_sw, "SWITCH & CHECKBOX")

    sw_row = lv.obj(card_sw)
    sw_row.set_size(lv.pct(100), lv.SIZE_CONTENT)
    sw_row.set_flex_flow(lv.FLEX_FLOW.ROW)
    sw_row.set_style_bg_opa(lv.OPA.TRANSP, 0)
    sw_row.set_style_border_width(0, 0)
    sw_row.set_style_pad_all(0, 0)
    sw_row.set_style_pad_gap(12, 0)
    sw_row.remove_flag(lv.obj.FLAG.SCROLLABLE)

    sw = lv.switch(sw_row)
    sw.set_style_bg_color(lv.color_hex(0x555577), 0)
    sw.set_style_bg_color(COLOR_GREEN, lv.PART.INDICATOR | lv.STATE.CHECKED)

    sw_lbl = lv.label(sw_row)
    sw_lbl.set_text(T("switch_label") + "  [ " + T("switch_off") + " ]")
    sw_lbl.set_style_text_color(COLOR_TEXT, 0)

    def on_sw(e):
        obj = e.get_target_obj()
        is_on = obj.has_state(lv.STATE.CHECKED)
        state_txt = T("switch_on") if is_on else T("switch_off")
        sw_lbl.set_text(T("switch_label") + "  [ " + state_txt + " ]")
    sw.add_event_cb(on_sw, lv.EVENT.VALUE_CHANGED, None)

    checkboxes = []
    for txt_key in ("cb1", "cb2", "cb3"):
        cb = lv.checkbox(card_sw)
        cb.set_text(T(txt_key))
        cb.set_style_text_color(COLOR_TEXT, 0)
        checkboxes.append(cb)

    # Slider card
    card_sl = make_card(tab, 940, 130)
    card_sl.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    card_sl.set_style_pad_gap(8, 0)

    sl_lbl = lv.label(card_sl)
    sl_lbl.set_text(T("slider_label").format(50))
    sl_lbl.set_style_text_color(COLOR_TEXT, 0)

    slider = lv.slider(card_sl)
    slider.set_width(880)
    slider.set_range(0, 100)
    slider.set_value(50, False)
    slider.set_style_bg_color(lv.color_hex(0x444466), 0)
    slider.set_style_bg_color(COLOR_PRIMARY, lv.PART.INDICATOR)
    slider.set_style_bg_color(COLOR_WHITE, lv.PART.KNOB)

    def on_slider(e):
        val = slider.get_value()
        sl_lbl.set_text(T("slider_label").format(val))
    slider.add_event_cb(on_slider, lv.EVENT.VALUE_CHANGED, None)

    return {"btn": btn, "btn_tog": btn_tog, "sw": sw, "sw_lbl": sw_lbl,
            "checkboxes": checkboxes, "slider": slider, "sl_lbl": sl_lbl,
            "click_count": click_count, "counter_lbl": counter_lbl}

# ═════════════════════════════════════════════════════════════════════════════
#  TAB 3 — DATA DISPLAY
# ═════════════════════════════════════════════════════════════════════════════
def build_data(tab):
    setup_tab_bg(tab)
    tab.set_flex_flow(lv.FLEX_FLOW.ROW_WRAP)
    tab.set_flex_align(lv.FLEX_ALIGN.SPACE_EVENLY, lv.FLEX_ALIGN.START,
                       lv.FLEX_ALIGN.START)

    # Line chart
    card_line = make_card(tab, 460, 260)
    card_line.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    card_line.set_style_pad_gap(4, 0)
    section_label(card_line, T("chart_line"))

    chart_l = lv.chart(card_line)
    chart_l.set_size(420, 190)
    chart_l.set_type(lv.chart.TYPE.LINE)
    chart_l.set_point_count(12)
    chart_l.set_axis_range(lv.chart.AXIS.PRIMARY_Y, -10, 40)
    chart_l.set_div_line_count(5, 7)
    chart_l.set_style_bg_color(lv.color_hex(0x1A1A2E), 0)
    chart_l.set_style_border_color(lv.color_hex(0x333355), 0)
    chart_l.set_style_line_color(lv.color_hex(0x333355), lv.PART.MAIN)
    chart_l.set_style_radius(8, 0)

    ser_temp = chart_l.add_series(COLOR_WARN, lv.chart.AXIS.PRIMARY_Y)
    for v in [2, 4, 8, 14, 19, 24, 28, 27, 22, 15, 9, 3]:
        chart_l.set_next_value(ser_temp, v)

    ser_temp2 = chart_l.add_series(COLOR_PRIMARY, lv.chart.AXIS.PRIMARY_Y)
    for v in [-2, 0, 5, 10, 15, 20, 24, 23, 18, 11, 5, -1]:
        chart_l.set_next_value(ser_temp2, v)
    chart_l.refresh()

    # Bar chart
    card_bar = make_card(tab, 460, 260)
    card_bar.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    card_bar.set_style_pad_gap(4, 0)
    section_label(card_bar, T("chart_bar"))

    chart_b = lv.chart(card_bar)
    chart_b.set_size(420, 190)
    chart_b.set_type(lv.chart.TYPE.BAR)
    chart_b.set_point_count(6)
    chart_b.set_axis_range(lv.chart.AXIS.PRIMARY_Y, 0, 120)
    chart_b.set_div_line_count(4, 0)
    chart_b.set_style_bg_color(lv.color_hex(0x1A1A2E), 0)
    chart_b.set_style_border_color(lv.color_hex(0x333355), 0)
    chart_b.set_style_radius(8, 0)

    ser_sales = chart_b.add_series(COLOR_ACCENT, lv.chart.AXIS.PRIMARY_Y)
    for v in [45, 72, 58, 90, 110, 85]:
        chart_b.set_next_value(ser_sales, v)
    ser_sales2 = chart_b.add_series(COLOR_PRIMARY, lv.chart.AXIS.PRIMARY_Y)
    for v in [38, 60, 50, 80, 95, 70]:
        chart_b.set_next_value(ser_sales2, v)
    chart_b.refresh()

    # Progress bars
    card_prog = make_card(tab, 460, 200)
    card_prog.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    card_prog.set_style_pad_gap(8, 0)
    section_label(card_prog, T("progress").format(""))

    prog_lbl = lv.label(card_prog)
    prog_lbl.set_text(T("progress").format(0))
    prog_lbl.set_style_text_color(COLOR_TEXT, 0)

    bar = lv.bar(card_prog)
    bar.set_size(420, 22)
    bar.set_range(0, 100)
    bar.set_value(0, False)
    bar.set_style_bg_color(lv.color_hex(0x333355), 0)
    bar.set_style_bg_color(COLOR_PRIMARY, lv.PART.INDICATOR)
    bar.set_style_radius(6, 0)
    bar.set_style_radius(6, lv.PART.INDICATOR)

    bar2 = lv.bar(card_prog)
    bar2.set_size(420, 22)
    bar2.set_range(0, 100)
    bar2.set_value(0, False)
    bar2.set_style_bg_color(lv.color_hex(0x333355), 0)
    bar2.set_style_bg_color(COLOR_GREEN, lv.PART.INDICATOR)
    bar2.set_style_radius(6, 0)
    bar2.set_style_radius(6, lv.PART.INDICATOR)

    prog_state = [0]
    def prog_timer_cb(timer):
        prog_state[0] = (prog_state[0] + 1) % 101
        v = prog_state[0]
        bar.set_value(v, True)
        bar2.set_value((v * 7 + 30) % 101, True)
        prog_lbl.set_text(T("progress").format(v))
    lv.timer_create(prog_timer_cb, 80, None)

    # Arc gauge + LEDs
    card_gauge = make_card(tab, 460, 200)
    card_gauge.set_flex_flow(lv.FLEX_FLOW.ROW)
    card_gauge.set_flex_align(lv.FLEX_ALIGN.SPACE_EVENLY, lv.FLEX_ALIGN.CENTER,
                              lv.FLEX_ALIGN.CENTER)

    gauge_cont = lv.obj(card_gauge)
    gauge_cont.set_size(180, 170)
    gauge_cont.set_style_bg_opa(lv.OPA.TRANSP, 0)
    gauge_cont.set_style_border_width(0, 0)
    gauge_cont.remove_flag(lv.obj.FLAG.SCROLLABLE)

    arc_g = lv.arc(gauge_cont)
    arc_g.set_size(150, 150)
    arc_g.set_range(0, 100)
    arc_g.set_value(0)
    arc_g.set_bg_angles(135, 45)
    arc_g.set_rotation(0)
    arc_g.remove_flag(lv.obj.FLAG.CLICKABLE)
    arc_g.set_style_arc_color(lv.color_hex(0x333355), 0)
    arc_g.set_style_arc_color(COLOR_ACCENT, lv.PART.INDICATOR)
    arc_g.set_style_arc_width(14, 0)
    arc_g.set_style_arc_width(14, lv.PART.INDICATOR)
    arc_g.remove_style(None, lv.PART.KNOB)
    arc_g.align(lv.ALIGN.CENTER, 0, -8)

    arc_lbl = lv.label(gauge_cont)
    arc_lbl.set_text("0%")
    arc_lbl.set_style_text_color(COLOR_TEXT, 0)
    arc_lbl.align(lv.ALIGN.CENTER, 0, 20)

    cpu_lbl = lv.label(gauge_cont)
    cpu_lbl.set_text(T("arc_gauge"))
    cpu_lbl.set_style_text_color(COLOR_TEXT_DIM, 0)
    cpu_lbl.align(lv.ALIGN.CENTER, 0, 45)

    arc_state = [0, 1]
    def arc_timer_cb(timer):
        arc_state[0] += arc_state[1] * 2
        if arc_state[0] >= 95:
            arc_state[1] = -1
        elif arc_state[0] <= 5:
            arc_state[1] = 1
        arc_g.set_value(arc_state[0])
        arc_lbl.set_text("{}%".format(arc_state[0]))
    lv.timer_create(arc_timer_cb, 120, None)

    led_cont = lv.obj(card_gauge)
    led_cont.set_size(200, 170)
    led_cont.set_style_bg_opa(lv.OPA.TRANSP, 0)
    led_cont.set_style_border_width(0, 0)
    led_cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    led_cont.set_flex_align(lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.START,
                            lv.FLEX_ALIGN.CENTER)
    led_cont.set_style_pad_gap(10, 0)

    section_label(led_cont, T("led_title"))
    led_names = T("led_names")
    led_colors = [COLOR_GREEN, COLOR_PRIMARY, COLOR_ERROR]
    leds = []
    for i in range(3):
        r = lv.obj(led_cont)
        r.set_size(lv.pct(100), lv.SIZE_CONTENT)
        r.set_flex_flow(lv.FLEX_FLOW.ROW)
        r.set_style_bg_opa(lv.OPA.TRANSP, 0)
        r.set_style_border_width(0, 0)
        r.set_style_pad_all(0, 0)
        r.set_style_pad_gap(10, 0)
        r.remove_flag(lv.obj.FLAG.SCROLLABLE)
        led = lv.led(r)
        led.set_size(24, 24)
        led.set_color(led_colors[i])
        if i == 0:
            led.on()
        elif i == 2:
            led.off()
        else:
            led.on()
        leds.append(led)
        ll = lv.label(r)
        ll.set_text(led_names[i])
        ll.set_style_text_color(COLOR_TEXT, 0)

    led_blink = [0]
    def led_blink_cb(timer):
        led_blink[0] = (led_blink[0] + 1) % 20
        if led_blink[0] < 10:
            leds[1].set_brightness(255)
        else:
            leds[1].set_brightness(80)
    lv.timer_create(led_blink_cb, 100, None)
    return {}

# ═════════════════════════════════════════════════════════════════════════════
#  TAB 4 — SELECTION
# ═════════════════════════════════════════════════════════════════════════════
def build_selection(tab):
    setup_tab_bg(tab)
    tab.set_flex_flow(lv.FLEX_FLOW.ROW_WRAP)
    tab.set_flex_align(lv.FLEX_ALIGN.SPACE_EVENLY, lv.FLEX_ALIGN.START,
                       lv.FLEX_ALIGN.START)

    # Dropdown
    card_dd = make_card(tab, 300, 250)
    card_dd.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    card_dd.set_style_pad_gap(10, 0)
    section_label(card_dd, T("dd_label"))

    dd = lv.dropdown(card_dd)
    dd.set_options(T("dd_options"))
    dd.set_width(250)
    dd.set_style_bg_color(lv.color_hex(0x333355), 0)
    dd.set_style_text_color(COLOR_TEXT, 0)

    dd_sel_lbl = lv.label(card_dd)
    dd_sel_lbl.set_text(T("dd_selected").format("---"))
    dd_sel_lbl.set_style_text_color(COLOR_TEXT, 0)

    def on_dd(e):
        buf = bytearray(64)
        dd.get_selected_str(buf, len(buf))
        name = buf.decode("utf-8").rstrip("\x00")
        dd_sel_lbl.set_text(T("dd_selected").format(name))
    dd.add_event_cb(on_dd, lv.EVENT.VALUE_CHANGED, None)

    # Roller
    card_rl = make_card(tab, 300, 250)
    card_rl.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    card_rl.set_style_pad_gap(10, 0)
    section_label(card_rl, T("roller_label"))

    roller = lv.roller(card_rl)
    roller.set_options(T("roller_opts"), lv.roller.MODE.NORMAL)
    roller.set_visible_row_count(4)
    roller.set_width(250)
    roller.set_style_bg_color(lv.color_hex(0x333355), 0)
    roller.set_style_text_color(COLOR_TEXT_DIM, 0)
    roller.set_style_bg_color(COLOR_PRIMARY, lv.PART.SELECTED)
    roller.set_style_text_color(COLOR_WHITE, lv.PART.SELECTED)

    # Table
    card_tbl = make_card(tab, 460, 250)
    card_tbl.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    card_tbl.set_style_pad_gap(6, 0)
    section_label(card_tbl, T("table_title"))

    tbl = lv.table(card_tbl)
    tbl.set_column_count(4)
    tbl.set_column_width(0, 110)
    tbl.set_column_width(1, 80)
    tbl.set_column_width(2, 60)
    tbl.set_column_width(3, 80)
    hdrs = T("table_hdr")
    for c in range(4):
        tbl.set_cell_value(0, c, hdrs[c])
    sensor_data = [
        ["Temp",      "23.5",  "°C",  "OK"],
        ["Humidity",  "61",    "%",   "OK"],
        ["Pressure",  "1013",  "hPa", "OK"],
        ["CO2",       "820",   "ppm", "WARN"],
        ["Light",     "340",   "lux", "OK"],
    ]
    for r, row in enumerate(sensor_data):
        for c, val in enumerate(row):
            tbl.set_cell_value(r + 1, c, val)
    tbl.set_style_bg_color(lv.color_hex(0x222240), 0)
    tbl.set_style_border_color(lv.color_hex(0x444466), 0)
    tbl.set_style_text_color(COLOR_TEXT, 0)
    tbl.set_style_bg_color(COLOR_PRIMARY, lv.PART.ITEMS | lv.STATE.PRESSED)

    # List
    card_lst = make_card(tab, 160, 250)
    card_lst.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    card_lst.set_style_pad_gap(4, 0)
    section_label(card_lst, T("list_title"))
    lst = lv.list(card_lst)
    lst.set_size(140, 180)
    lst.set_style_bg_color(lv.color_hex(0x222240), 0)
    lst.set_style_border_width(0, 0)
    lst.set_style_radius(8, 0)
    icons = [lv.SYMBOL.WIFI, lv.SYMBOL.BLUETOOTH, lv.SYMBOL.IMAGE,
             lv.SYMBOL.AUDIO, lv.SYMBOL.LIST]
    for i, item_text in enumerate(T("list_items")):
        b = lst.add_button(icons[i], item_text)
        b.set_style_bg_color(lv.color_hex(0x2A2A3C), 0)
        b.set_style_text_color(COLOR_TEXT, 0)
        b.set_style_bg_color(COLOR_PRIMARY, lv.STATE.PRESSED)

    return {"dd": dd, "dd_sel_lbl": dd_sel_lbl, "roller": roller}

# ═════════════════════════════════════════════════════════════════════════════
#  TAB 5 — TEXT INPUT
# ═════════════════════════════════════════════════════════════════════════════
def build_text(tab):
    setup_tab_bg(tab)
    tab.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    tab.set_style_pad_gap(10, 0)

    title = lv.label(tab)
    title.set_text(T("ta_title"))
    title.set_style_text_color(COLOR_TEXT, 0)

    ta = lv.textarea(tab)
    ta.set_size(980, 150)
    ta.set_placeholder_text(T("ta_placeholder"))
    ta.set_style_bg_color(lv.color_hex(0x222240), 0)
    ta.set_style_text_color(COLOR_TEXT, 0)
    ta.set_style_border_color(COLOR_PRIMARY, lv.STATE.FOCUSED)
    ta.set_style_border_width(2, 0)
    ta.set_style_radius(8, 0)

    kb = lv.keyboard(tab)
    kb.set_size(980, 280)
    kb.set_textarea(ta)
    kb.set_style_bg_color(lv.color_hex(0x2A2A3C), 0)
    kb.set_style_text_color(COLOR_TEXT, lv.PART.ITEMS)
    kb.set_style_bg_color(lv.color_hex(0x3A3A5C), lv.PART.ITEMS)

    def on_ta_focus(e):
        kb.set_textarea(ta)
    ta.add_event_cb(on_ta_focus, lv.EVENT.FOCUSED, None)

    return {"ta": ta, "kb": kb}

# ═════════════════════════════════════════════════════════════════════════════
#  TAB 6 — ANIMATIONS
# ═════════════════════════════════════════════════════════════════════════════
def build_anim(tab):
    setup_tab_bg(tab)
    tab.set_flex_flow(lv.FLEX_FLOW.ROW_WRAP)
    tab.set_flex_align(lv.FLEX_ALIGN.SPACE_EVENLY, lv.FLEX_ALIGN.START,
                       lv.FLEX_ALIGN.START)

    # Animated bar
    card_bar = make_card(tab, 300, 220)
    card_bar.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    card_bar.set_style_pad_gap(10, 0)
    section_label(card_bar, T("anim_bar"))

    abar = lv.bar(card_bar)
    abar.set_size(260, 20)
    abar.set_range(0, 100)
    abar.set_style_bg_color(lv.color_hex(0x333355), 0)
    abar.set_style_bg_color(COLOR_WARN, lv.PART.INDICATOR)
    abar.set_style_radius(10, 0)
    abar.set_style_radius(10, lv.PART.INDICATOR)

    abar_lbl = lv.label(card_bar)
    abar_lbl.set_text("0%")
    abar_lbl.set_style_text_color(COLOR_TEXT, 0)

    abar_state = [0, 3]
    def abar_cb(timer):
        abar_state[0] += abar_state[1]
        if abar_state[0] >= 100:
            abar_state[1] = -3
        elif abar_state[0] <= 0:
            abar_state[1] = 3
        abar.set_value(abar_state[0], True)
        abar_lbl.set_text("{}%".format(abar_state[0]))
    lv.timer_create(abar_cb, 50, None)

    # Spinning arc
    card_arc = make_card(tab, 300, 220)
    card_arc.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    card_arc.set_flex_align(lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER,
                            lv.FLEX_ALIGN.CENTER)
    card_arc.set_style_pad_gap(6, 0)
    section_label(card_arc, T("anim_arc"))

    spin_arc = lv.arc(card_arc)
    spin_arc.set_size(130, 130)
    spin_arc.set_bg_angles(0, 360)
    spin_arc.set_angles(0, 90)
    spin_arc.remove_flag(lv.obj.FLAG.CLICKABLE)
    spin_arc.set_style_arc_color(lv.color_hex(0x333355), 0)
    spin_arc.set_style_arc_color(COLOR_PRIMARY, lv.PART.INDICATOR)
    spin_arc.set_style_arc_width(10, 0)
    spin_arc.set_style_arc_width(10, lv.PART.INDICATOR)
    spin_arc.remove_style(None, lv.PART.KNOB)

    spin_angle = [0]
    def spin_cb(timer):
        spin_angle[0] = (spin_angle[0] + 6) % 360
        a = spin_angle[0]
        spin_arc.set_angles(a, a + 90)
    lv.timer_create(spin_cb, 25, None)

    # Bouncing box
    card_bounce = make_card(tab, 300, 220)
    card_bounce.remove_flag(lv.obj.FLAG.SCROLLABLE)
    section_label(card_bounce, T("anim_pos"))

    box = lv.obj(card_bounce)
    box.set_size(40, 40)
    box.set_style_bg_color(COLOR_ACCENT, 0)
    box.set_style_radius(8, 0)
    box.set_style_border_width(0, 0)
    box.remove_flag(lv.obj.FLAG.SCROLLABLE)

    bounce_state = [20, 20, 3, 2]
    def bounce_cb(timer):
        bx, by, dx, dy = bounce_state
        bx += dx
        by += dy
        if bx < 0 or bx > 220:
            dx = -dx
        if by < 30 or by > 140:
            dy = -dy
        bounce_state[0] = bx
        bounce_state[1] = by
        bounce_state[2] = dx
        bounce_state[3] = dy
        box.set_pos(bx, by)
    lv.timer_create(bounce_cb, 20, None)

    # Color cycle
    card_cycle = make_card(tab, 460, 220)
    card_cycle.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    card_cycle.set_flex_align(lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER,
                              lv.FLEX_ALIGN.CENTER)
    card_cycle.set_style_pad_gap(10, 0)
    section_label(card_cycle, "Color Cycle" if LANG == "en" else "Ciclo Colori")

    cbox_row = lv.obj(card_cycle)
    cbox_row.set_size(420, 80)
    cbox_row.set_flex_flow(lv.FLEX_FLOW.ROW)
    cbox_row.set_flex_align(lv.FLEX_ALIGN.SPACE_EVENLY, lv.FLEX_ALIGN.CENTER,
                            lv.FLEX_ALIGN.CENTER)
    cbox_row.set_style_bg_opa(lv.OPA.TRANSP, 0)
    cbox_row.set_style_border_width(0, 0)
    cbox_row.remove_flag(lv.obj.FLAG.SCROLLABLE)

    cboxes = []
    for i in range(8):
        cb = lv.obj(cbox_row)
        cb.set_size(40, 40)
        cb.set_style_radius(20, 0)
        cb.set_style_border_width(0, 0)
        cb.set_style_bg_opa(lv.OPA.COVER, 0)
        cb.remove_flag(lv.obj.FLAG.SCROLLABLE)
        cboxes.append(cb)

    cycle_phase = [0]
    def cycle_cb(timer):
        cycle_phase[0] = (cycle_phase[0] + 1) % 360
        for i, cb in enumerate(cboxes):
            hue = (cycle_phase[0] + i * 45) % 360
            r, g, b = hsv_to_rgb(hue, 85, 95)
            cb.set_style_bg_color(lv.color_make(r, g, b), 0)
    lv.timer_create(cycle_cb, 40, None)
    return {}

# ═════════════════════════════════════════════════════════════════════════════
#  TAB 7 — STYLES
# ═════════════════════════════════════════════════════════════════════════════
def build_styles(tab):
    setup_tab_bg(tab)
    tab.set_flex_flow(lv.FLEX_FLOW.ROW_WRAP)
    tab.set_flex_align(lv.FLEX_ALIGN.SPACE_EVENLY, lv.FLEX_ALIGN.START,
                       lv.FLEX_ALIGN.START)
    titles = T("card_titles")

    c0 = lv.obj(tab)
    c0.set_size(290, 200)
    c0.set_style_bg_color(COLOR_PRIMARY, 0)
    c0.set_style_bg_grad_color(COLOR_ACCENT, 0)
    c0.set_style_bg_grad_dir(lv.GRAD_DIR.VER, 0)
    c0.set_style_bg_opa(lv.OPA.COVER, 0)
    c0.set_style_radius(16, 0)
    c0.set_style_border_width(0, 0)
    c0.set_style_pad_all(20, 0)
    c0.remove_flag(lv.obj.FLAG.SCROLLABLE)
    l0 = lv.label(c0); l0.set_text(titles[0]); l0.set_style_text_color(COLOR_WHITE, 0)

    c1 = lv.obj(tab)
    c1.set_size(290, 200)
    c1.set_style_bg_color(COLOR_BG_DARK, 0)
    c1.set_style_bg_opa(lv.OPA.COVER, 0)
    c1.set_style_border_width(3, 0)
    c1.set_style_border_color(COLOR_PRIMARY, 0)
    c1.set_style_radius(16, 0)
    c1.set_style_pad_all(20, 0)
    c1.remove_flag(lv.obj.FLAG.SCROLLABLE)
    l1 = lv.label(c1); l1.set_text(titles[1]); l1.set_style_text_color(COLOR_PRIMARY, 0)

    c2 = lv.obj(tab)
    c2.set_size(290, 200)
    c2.set_style_bg_color(COLOR_BG_CARD, 0)
    c2.set_style_bg_opa(lv.OPA.COVER, 0)
    c2.set_style_radius(16, 0)
    c2.set_style_border_width(0, 0)
    c2.set_style_shadow_width(40, 0)
    c2.set_style_shadow_color(lv.color_hex(0x000000), 0)
    c2.set_style_shadow_opa(lv.OPA._40, 0)
    c2.set_style_shadow_offset_y(8, 0)
    c2.set_style_pad_all(20, 0)
    c2.remove_flag(lv.obj.FLAG.SCROLLABLE)
    l2 = lv.label(c2); l2.set_text(titles[2]); l2.set_style_text_color(COLOR_TEXT, 0)

    c3 = lv.obj(tab)
    c3.set_size(290, 200)
    c3.set_style_bg_color(lv.color_hex(0x3A3A5C), 0)
    c3.set_style_bg_opa(lv.OPA.COVER, 0)
    c3.set_style_radius(100, 0)
    c3.set_style_border_width(0, 0)
    c3.set_style_pad_all(20, 0)
    c3.remove_flag(lv.obj.FLAG.SCROLLABLE)
    l3 = lv.label(c3); l3.set_text(titles[3]); l3.align(lv.ALIGN.CENTER, 0, 0)
    l3.set_style_text_color(COLOR_TEXT, 0)

    c4 = lv.obj(tab)
    c4.set_size(290, 200)
    c4.set_style_bg_color(COLOR_WARN, 0)
    c4.set_style_bg_opa(lv.OPA.COVER, 0)
    c4.set_style_radius(16, 0)
    c4.set_style_border_width(0, 0)
    c4.set_style_pad_all(20, 0)
    c4.remove_flag(lv.obj.FLAG.SCROLLABLE)
    l4 = lv.label(c4); l4.set_text(titles[4]); l4.set_style_text_color(COLOR_BG_DARK, 0)

    c5 = lv.obj(tab)
    c5.set_size(290, 200)
    c5.set_style_bg_color(lv.color_hex(0x222240), 0)
    c5.set_style_bg_opa(lv.OPA.COVER, 0)
    c5.set_style_radius(4, 0)
    c5.set_style_border_width(1, 0)
    c5.set_style_border_color(lv.color_hex(0x444466), 0)
    c5.set_style_pad_all(20, 0)
    c5.remove_flag(lv.obj.FLAG.SCROLLABLE)
    l5 = lv.label(c5); l5.set_text(titles[5]); l5.set_style_text_color(COLOR_TEXT_DIM, 0)

    # Interactive playground
    card_play = make_card(tab, 600, 200)
    card_play.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    card_play.set_style_pad_gap(8, 0)
    section_label(card_play, "Radius & Opacity" if LANG == "en" else "Raggio & Opacita")

    preview = lv.obj(card_play)
    preview.set_size(120, 80)
    preview.set_style_bg_color(COLOR_PRIMARY, 0)
    preview.set_style_bg_opa(lv.OPA.COVER, 0)
    preview.set_style_border_width(0, 0)
    preview.set_style_radius(0, 0)
    preview.remove_flag(lv.obj.FLAG.SCROLLABLE)
    preview.set_style_shadow_width(12, 0)
    preview.set_style_shadow_color(COLOR_PRIMARY, 0)
    preview.set_style_shadow_opa(lv.OPA._30, 0)

    row_r = lv.obj(card_play)
    row_r.set_size(560, 40)
    row_r.set_flex_flow(lv.FLEX_FLOW.ROW)
    row_r.set_style_bg_opa(lv.OPA.TRANSP, 0)
    row_r.set_style_border_width(0, 0)
    row_r.set_style_pad_all(0, 0)
    row_r.set_style_pad_gap(10, 0)
    row_r.remove_flag(lv.obj.FLAG.SCROLLABLE)

    rl = lv.label(row_r)
    rl.set_text("Radius: 0")
    rl.set_style_text_color(COLOR_TEXT, 0)
    rl.set_width(120)

    sl_r = lv.slider(row_r)
    sl_r.set_width(400)
    sl_r.set_range(0, 60)
    sl_r.set_value(0, False)
    sl_r.set_style_bg_color(lv.color_hex(0x444466), 0)
    sl_r.set_style_bg_color(COLOR_PRIMARY, lv.PART.INDICATOR)
    sl_r.set_style_bg_color(COLOR_WHITE, lv.PART.KNOB)

    def on_radius(e):
        v = sl_r.get_value()
        preview.set_style_radius(v, 0)
        rl.set_text("Radius: {}".format(v))
    sl_r.add_event_cb(on_radius, lv.EVENT.VALUE_CHANGED, None)

    row_o = lv.obj(card_play)
    row_o.set_size(560, 40)
    row_o.set_flex_flow(lv.FLEX_FLOW.ROW)
    row_o.set_style_bg_opa(lv.OPA.TRANSP, 0)
    row_o.set_style_border_width(0, 0)
    row_o.set_style_pad_all(0, 0)
    row_o.set_style_pad_gap(10, 0)
    row_o.remove_flag(lv.obj.FLAG.SCROLLABLE)

    ol = lv.label(row_o)
    ol.set_text("Opacity: 100%")
    ol.set_style_text_color(COLOR_TEXT, 0)
    ol.set_width(120)

    sl_o = lv.slider(row_o)
    sl_o.set_width(400)
    sl_o.set_range(0, 255)
    sl_o.set_value(255, False)
    sl_o.set_style_bg_color(lv.color_hex(0x444466), 0)
    sl_o.set_style_bg_color(COLOR_PRIMARY, lv.PART.INDICATOR)
    sl_o.set_style_bg_color(COLOR_WHITE, lv.PART.KNOB)

    def on_opa(e):
        v = sl_o.get_value()
        preview.set_style_bg_opa(v, 0)
        ol.set_text("Opacity: {}%".format(v * 100 // 255))
    sl_o.add_event_cb(on_opa, lv.EVENT.VALUE_CHANGED, None)

    return {"sl_r": sl_r, "sl_o": sl_o, "preview": preview,
            "rl": rl, "ol": ol}


# ═════════════════════════════════════════════════════════════════════════════
#  AUTO-DEMO SEQUENCER
# ═════════════════════════════════════════════════════════════════════════════
#  Each "step" is (tab_index, action_function).
#  The sequencer switches to the tab, waits a beat, then runs the action
#  over several sub-ticks. When done it advances to the next step.
# ═════════════════════════════════════════════════════════════════════════════

def build_auto_demo(tv, w):
    """
    tv : tabview object
    w  : dict of all widget refs returned by build_* functions
    """
    STEP_MS = 6           # ms per sub-tick
    DWELL_TICKS = 4       # ticks to stay on a tab before switching (~2.4 s)

    # ── The demo text typed char-by-char ─────────────────────────────────────
    demo_text = "Hello LVGL 9.3!" if LANG == "en" else "Ciao LVGL 9.3!"

    # ── State ────────────────────────────────────────────────────────────────
    state = {
        "phase": 0,        # which phase of the whole sequence
        "tick": 0,         # sub-tick within current phase
        "slider_dir": 1,   # for slider sweep
        "char_idx": 0,     # for typing
        "cycle": 0,        # full cycle count
    }

    # ── Phases ───────────────────────────────────────────────────────────────
    # (tab_index, duration_in_ticks, description)
    phases = [
        (0,  50,  "home"),
        (1, 50,  "buttons"),
        (2,  15,  "data"),
        (3,  30,  "selection"),
        (4,  60,  "text"),
        (5,  20,  "anim"),
        (6,  20,  "styles"),
    ]

    def do_tick(timer):
        p = state["phase"]
        t = state["tick"]

        tab_idx, duration, name = phases[p]

        # ── Switch tab on tick 0 ─────────────────────────────────────────────
        if t == 0:
            try:
                tv.set_active(tab_idx, True)
            except Exception:
                try:
                    tv.set_act(tab_idx, True)
                except Exception:
                    pass

        # ── Tab-specific actions ─────────────────────────────────────────────

        # TAB 0 — Home: just display
        # (no actions, the welcome screen speaks for itself)

        # TAB 1 — Buttons & Input
        if p == 1:
            btns = w.get("buttons", {})
            if t == 10:
                # Click the button
                b = btns.get("btn")
                if b:
                    b.send_event(lv.EVENT.PRESSED, None)
            elif t == 15:
                b = btns.get("btn")
                if b:
                    b.send_event(lv.EVENT.CLICKED, None)
                    b.send_event(lv.EVENT.RELEASED, None)
            elif t == 25:
                b = btns.get("btn")
                if b:
                    b.send_event(lv.EVENT.PRESSED, None)
            elif t == 30:
                b = btns.get("btn")
                if b:
                    b.send_event(lv.EVENT.CLICKED, None)
                    b.send_event(lv.EVENT.RELEASED, None)
            elif t == 40:
                b = btns.get("btn")
                if b:
                    b.send_event(lv.EVENT.PRESSED, None)
            elif t == 45:
                b = btns.get("btn")
                if b:
                    b.send_event(lv.EVENT.CLICKED, None)
                    b.send_event(lv.EVENT.RELEASED, None)
            elif t == 55:
                # Toggle button
                bt = btns.get("btn_tog")
                if bt:
                    if bt.has_state(lv.STATE.CHECKED):
                        bt.remove_state(lv.STATE.CHECKED)
                    else:
                        bt.add_state(lv.STATE.CHECKED)
            elif t == 65:
                # Switch
                s = btns.get("sw")
                if s:
                    if s.has_state(lv.STATE.CHECKED):
                        s.remove_state(lv.STATE.CHECKED)
                    else:
                        s.add_state(lv.STATE.CHECKED)
                    s.send_event(lv.EVENT.VALUE_CHANGED, None)
            elif t == 70 or t == 75 or t == 80:
                # Checkboxes one by one
                cbs = btns.get("checkboxes", [])
                idx = (t - 70) // 5
                if idx < len(cbs):
                    cb = cbs[idx]
                    if cb.has_state(lv.STATE.CHECKED):
                        cb.remove_state(lv.STATE.CHECKED)
                    else:
                        cb.add_state(lv.STATE.CHECKED)
            elif 85 <= t <= 99:
                # Sweep the slider
                sl = btns.get("slider")
                sl_lbl = btns.get("sl_lbl")
                if sl:
                    cur = sl.get_value()
                    d = state["slider_dir"]
                    nv = cur + d * 7
                    if nv >= 100:
                        nv = 100
                        state["slider_dir"] = -1
                    elif nv <= 0:
                        nv = 0
                        state["slider_dir"] = 1
                    sl.set_value(nv, True)
                    if sl_lbl:
                        sl_lbl.set_text(T("slider_label").format(nv))

        # TAB 2 — Data: auto-animated, just dwell

        # TAB 3 — Selection
        elif p == 3:
            sel = w.get("selection", {})
            if t == 15 or t == 30 or t == 45 or t == 60:
                dd = sel.get("dd")
                dd_lbl = sel.get("dd_sel_lbl")
                if dd:
                    cur = dd.get_selected()
                    dd.set_selected((cur + 1) % 6)
                    dd.send_event(lv.EVENT.VALUE_CHANGED, None)
            if t == 20 or t == 35 or t == 50 or t == 65:
                rl = sel.get("roller")
                if rl:
                    cur = rl.get_selected()
                    rl.set_selected((cur + 1) % 12, True)

        # TAB 4 — Text: type demo text char by char
        elif p == 4:
            txt = w.get("text", {})
            ta = txt.get("ta")
            if ta:
                if t == 5:
                    ta.set_text("")        # clear
                    state["char_idx"] = 0
                elif 10 <= t < 10 + len(demo_text) * 3:
                    # Type one char every 3 ticks
                    if (t - 10) % 3 == 0:
                        ci = state["char_idx"]
                        if ci < len(demo_text):
                            ta.add_char(ord(demo_text[ci]))
                            state["char_idx"] = ci + 1
                elif t == 10 + len(demo_text) * 3 + 10:
                    # Pause, then clear for next cycle
                    ta.set_text("")

        # TAB 5 — Animations: self-running, just dwell

        # TAB 6 — Styles: sweep radius & opacity sliders
        elif p == 6:
            sty = w.get("styles", {})
            sl_r = sty.get("sl_r")
            sl_o = sty.get("sl_o")
            preview = sty.get("preview")
            rl_lbl = sty.get("rl")
            ol_lbl = sty.get("ol")
            if sl_r and 10 <= t <= 40:
                v = int((t - 10) * 60 / 30)
                sl_r.set_value(v, True)
                if preview:
                    preview.set_style_radius(v, 0)
                if rl_lbl:
                    rl_lbl.set_text("Radius: {}".format(v))
            if sl_o and 45 <= t <= 75:
                v = 255 - int((t - 45) * 200 / 30)
                sl_o.set_value(v, True)
                if preview:
                    preview.set_style_bg_opa(v, 0)
                if ol_lbl:
                    ol_lbl.set_text("Opacity: {}%".format(v * 100 // 255))

        # ── Advance ──────────────────────────────────────────────────────────
        state["tick"] = t + 1
        if state["tick"] >= duration:
            state["tick"] = 0
            state["phase"] = (p + 1) % len(phases)
            if state["phase"] == 0:
                state["cycle"] += 1
                state["slider_dir"] = 1
                # Reset some widgets for clean next cycle
                btns = w.get("buttons", {})
                sl = btns.get("slider")
                if sl:
                    sl.set_value(50, False)
                sty = w.get("styles", {})
                sr = sty.get("sl_r")
                so = sty.get("sl_o")
                pr = sty.get("preview")
                if sr:
                    sr.set_value(0, False)
                if so:
                    so.set_value(255, False)
                if pr:
                    pr.set_style_radius(0, 0)
                    pr.set_style_bg_opa(lv.OPA.COVER, 0)

    lv.timer_create(do_tick, STEP_MS, None)
    print("[AUTO-DEMO] sequencer started — cycle every ~35 s")


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════════════════════
def main():
    scr = lv.screen_active()
    scr.set_style_bg_color(COLOR_BG_DARK, 0)

    tv = lv.tabview(scr)
    try:
        tv.set_tab_bar_position(lv.DIR.TOP)
        tv.set_tab_bar_size(48)
    except Exception:
        pass

    tv.set_size(1024, 600)
    tv.set_pos(0, 0)

    t1 = tv.add_tab(T("tab_home"))
    t2 = tv.add_tab(T("tab_buttons"))
    t3 = tv.add_tab(T("tab_data"))
    t4 = tv.add_tab(T("tab_selection"))
    t5 = tv.add_tab(T("tab_text"))
    t6 = tv.add_tab(T("tab_anim"))
    t7 = tv.add_tab(T("tab_styles"))

    # Style tab bar
    tab_bar = None
    try:
        tab_bar = tv.get_tab_bar()
    except Exception:
        pass
    if tab_bar is None:
        try:
            tab_bar = tv.get_child(0)
        except Exception:
            pass
    if tab_bar is not None:
        try:
            tab_bar.set_style_bg_color(lv.color_hex(0x16162A), 0)
            tab_bar.set_style_pad_left(6, 0)
            tab_bar.set_style_pad_right(6, 0)
            cnt = tab_bar.get_child_count()
            for i in range(cnt):
                btn = tab_bar.get_child(i)
                if btn is None:
                    continue
                btn.set_style_text_color(COLOR_TEXT_DIM, 0)
                btn.set_style_text_color(COLOR_WHITE, lv.STATE.CHECKED)
                btn.set_style_bg_color(lv.color_hex(0x16162A), 0)
                btn.set_style_bg_color(COLOR_PRIMARY, lv.STATE.CHECKED)
                btn.set_style_bg_opa(lv.OPA._40, lv.STATE.CHECKED)
                btn.set_style_radius(6, 0)
        except Exception as ex:
            print("[WARN] tab button styling skipped:", ex)

    # Build all tabs and collect widget references
    w = {}
    w["home"]      = build_home(t1)
    w["buttons"]   = build_buttons(t2)
    w["data"]      = build_data(t3)
    w["selection"] = build_selection(t4)
    w["text"]      = build_text(t5)
    w["anim"]      = build_anim(t6)
    w["styles"]    = build_styles(t7)

    print("[LVGL DEMO] built — lang={}, screen=1024x600".format(LANG))

    # Start auto-demo if enabled
    if AUTO_DEMO:
        build_auto_demo(tv, w)

# ─── Run ─────────────────────────────────────────────────────────────────────
main()
