# hello_lv.py -- Minimal LVGL test app
# Run from shell: runlv hello_lv.py
# Press q to quit.

# Create labels directly on screen (same approach as testlv)
lbl = lv.label(screen)
lbl.set_text('Hello from LVGL!\n\nDisplay: {}x{}\n\nPress q to quit'.format(
    DISPLAY_W, DISPLAY_H))
lbl.set_style_text_color(lv.color_hex(0x00FF00), 0)
try:
    lbl.set_style_text_font(lv.font_unscii_16, 0)
except:
    pass
lbl.center()
lbl.move_foreground()

clbl = lv.label(screen)
clbl.set_pos(10, 10)
clbl.set_style_text_color(lv.color_hex(0xFFFF00), 0)
try:
    clbl.set_style_text_font(lv.font_unscii_16, 0)
except:
    pass
clbl.move_foreground()

lv.task_handler()

count = 0
while True:
    k = get_key()
    if k == 'q':
        break
    count += 1
    if count % 30 == 0:
        clbl.set_text('Frame: {}'.format(count))
    lv.task_handler()
    sleep_ms(33)
