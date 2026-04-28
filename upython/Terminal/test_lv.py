# test_lv.py -- Bare minimum LVGL diagnostic
# Run: runlv test_lv.py
# Prints debug to SERIAL (not shell terminal)

import sys

# Force print to real serial (bypass shell)
def dbg(msg):
    sys.stdout.write('[DBG] ' + msg + '\n')

dbg('test_lv started')
dbg('screen type: ' + str(type(screen)))
dbg('display: {}x{}'.format(DISPLAY_W, DISPLAY_H))

# Create label directly on screen
dbg('creating label...')
lbl = lv.label(screen)
dbg('label created: ' + str(lbl))

lbl.set_text('TEST OK')
dbg('text set')

lbl.set_style_text_color(lv.color_hex(0xFF0000), 0)
dbg('color set')

lbl.set_pos(100, 100)
dbg('pos set')

lv.task_handler()
dbg('task_handler done')

dbg('entering loop, press q...')
for i in range(300):  # 10 seconds timeout
    k = get_key()
    if k:
        dbg('key: ' + repr(k))
    if k == 'q':
        dbg('quit!')
        break
    lv.task_handler()
    sleep_ms(33)

dbg('loop ended')
