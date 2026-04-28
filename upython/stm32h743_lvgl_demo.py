import lvgl as lv
import display_driver

# ==========================================
# 1. CONFIGURAZIONE LINGUA E TRADUZIONI
# ==========================================
# Imposta 'en' per Inglese o 'it' per Italiano
LANG = 'en' 

testi = {
    'en': {
        'tab_basic': 'Basic Controls',
        'tab_visual': 'Visuals & Charts',
        'tab_input': 'Text Input',
        'btn_text': 'Click Me!',
        'btn_clicked': 'Clicked!',
        'slider_text': 'Slider Value: {}',
        'switch_text': 'Enable Feature',
        'arc_text': 'Power',
        'chart_title': 'Performance Data',
        'kb_placeholder': 'Tap here to type using the capacitive screen...'
    },
    'it': {
        'tab_basic': 'Controlli Base',
        'tab_visual': 'Grafici e Visual',
        'tab_input': 'Inserimento Testo',
        'btn_text': 'Cliccami!',
        'btn_clicked': 'Cliccato!',
        'slider_text': 'Valore Slider: {}',
        'switch_text': 'Abilita Funzione',
        'arc_text': 'Potenza',
        'chart_title': 'Dati Prestazioni',
        'kb_placeholder': 'Tocca qui per scrivere col touch capacitivo...'
    }
}

t = testi[LANG]

# ==========================================
# 2. DEFINIZIONE DELLA DEMO
# ==========================================
def create_demo():
    # In LVGL 9, si usa screen_active()
    scr = lv.screen_active()
    
    # Imposta un colore di sfondo neutro
    scr.set_style_bg_color(lv.palette_main(lv.PALETTE.GREY), 0)
    scr.set_style_bg_opa(lv.OPA.COVER, 0)

    # Crea un TabView principale per gestire i 1024x600 in sezioni logiche
    tv = lv.tabview(scr)
    tv.set_size(1024, 600)
    tv.center()

    # Aggiunge le schede (Tabs)
    tab1 = tv.add_tab(t['tab_basic'])
    tab2 = tv.add_tab(t['tab_visual'])
    tab3 = tv.add_tab(t['tab_input'])

    # ------------------------------------------
    # TAB 1: Controlli Base (Layout Flexbox)
    # ------------------------------------------
    tab1.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    tab1.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
    tab1.set_style_pad_all(30, 0)

    # Switch con etichetta
    switch_cont = lv.obj(tab1)
    switch_cont.set_size(400, 80)
    switch_cont.set_flex_flow(lv.FLEX_FLOW.ROW)
    switch_cont.set_flex_align(lv.FLEX_ALIGN.SPACE_BETWEEN, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
    switch_cont.set_style_border_width(0, 0) # Rimuovi bordo container
    
    sw_label = lv.label(switch_cont)
    sw_label.set_text(t['switch_text'])
    sw = lv.switch(switch_cont)
    
    # Pulsante Interattivo (In LVGL 9 è lv.button e non più lv.btn)
    btn = lv.button(tab1)
    btn.set_size(250, 80)
    btn_label = lv.label(btn)
    btn_label.set_text(t['btn_text'])
    btn_label.center()

    def btn_event_cb(e):
        if e.get_code() == lv.EVENT.CLICKED:
            btn_label.set_text(t['btn_clicked'])
            # Animazione di feedback visivo
            btn.set_style_bg_color(btn, lv.palette_main(lv.PALETTE.GREEN), 0)

    btn.add_event_cb(btn_event_cb, lv.EVENT.ALL, None)

    # Slider
    slider = lv.slider(tab1)
    slider.set_width(400)
    slider_label = lv.label(tab1)
    slider_label.set_text(t['slider_text'].format(slider.get_value()))

    def slider_event_cb(e):
        slider_obj = e.get_target()
        slider_label.set_text(t['slider_text'].format(slider_obj.get_value()))

    slider.add_event_cb(slider_event_cb, lv.EVENT.VALUE_CHANGED, None)

    # ------------------------------------------
    # TAB 2: Visuals (Arco e Grafico Lineare)
    # ------------------------------------------
    tab2.set_flex_flow(lv.FLEX_FLOW.ROW)
    tab2.set_flex_align(lv.FLEX_ALIGN.SPACE_EVENLY, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)

    # Widget Arco
    arc = lv.arc(tab2)
    arc.set_size(300, 300)
    arc.set_rotation(270)
    arc.set_bg_angles(0, 360)
    arc.set_value(75)
    
    arc_label = lv.label(arc)
    arc_label.set_text(f"{t['arc_text']}\n75%")
    arc_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
    arc_label.center()

    def arc_event_cb(e):
        arc_obj = e.get_target()
        arc_label.set_text(f"{t['arc_text']}\n{arc_obj.get_value()}%")

    arc.add_event_cb(arc_event_cb, lv.EVENT.VALUE_CHANGED, None)

    # Widget Grafico (Chart)
    chart_cont = lv.obj(tab2)
    chart_cont.set_size(500, 400)
    
    chart_title = lv.label(chart_cont)
    chart_title.set_text(t['chart_title'])
    chart_title.align(lv.ALIGN.TOP_MID, 0, 0)

    chart = lv.chart(chart_cont)
    chart.set_size(450, 300)
    chart.align(lv.ALIGN.BOTTOM_MID, 0, 0)
    chart.set_type(lv.chart.TYPE.LINE)
    
    # Serie di dati (API v9 per la palette e gli assi)
    ser1 = chart.add_series(lv.palette_main(lv.PALETTE.RED), lv.chart.AXIS.PRIMARY_Y)
    ser2 = chart.add_series(lv.palette_main(lv.PALETTE.BLUE), lv.chart.AXIS.SECONDARY_Y)
    
    # Popolamento dati fittizi
    dati_rossi = [10, 20, 45, 80, 50, 40, 60, 90, 80, 100]
    dati_blu = [90, 80, 70, 60, 40, 30, 45, 20, 10, 0]
    
    for val in dati_rossi:
        chart.set_next_value(ser1, val)
    for val in dati_blu:
        chart.set_next_value(ser2, val)

    # ------------------------------------------
    # TAB 3: Input Tastiera Capacitiva
    # ------------------------------------------
    # Area di testo in alto
    ta = lv.textarea(tab3)
    ta.set_size(700, 120)
    ta.align(lv.ALIGN.TOP_MID, 0, 40)
    ta.set_placeholder_text(t['kb_placeholder'])
    
    # Tastiera virtuale ancorata in basso (perfetta per 1024x600)
    kb = lv.keyboard(tab3)
    kb.set_size(900, 300)
    kb.align(lv.ALIGN.BOTTOM_MID, 0, -20)
    # Associa la tastiera all'area di testo
    kb.set_textarea(ta)

# Lancia la demo
create_demo()
