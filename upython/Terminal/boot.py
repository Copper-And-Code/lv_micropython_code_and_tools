# boot.py — Minimal boot for STM32H743 Terminal
# Display init is handled by 'import display_driver' in main.py.
# This file only does pre-display setup (mount SD, QSPI, etc.)
# Place in /flash/boot.py if you want auto-start.

import os
import gc

# ── Mount SD card (optional) ──
try:
    import machine
    sd = machine.SDCard(slot=1)
    os.mount(sd, '/sd')
    print('[boot] SD card: mounted')
except Exception as e:
    print('[boot] SD card: not available ({})'.format(e))

# ── Verify QSPI (usually auto-mounted by firmware) ──
try:
    os.listdir('/qspi')
    print('[boot] QSPI: mounted')
except OSError:
    print('[boot] QSPI: not available')

gc.collect()
print('[boot] Free RAM: {} KB'.format(gc.mem_free() // 1024))
