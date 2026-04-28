"""
boot_simon.py — Example bootstrap for Simon Game
══════════════════════════════════════════════════
Adapt the display / touch driver section to YOUR hardware.

This example shows two common setups:
  A) Generic ILI9488 / ILI9341 + FT6336 / GT911 (SPI + I2C)
  B) ESP32-S3 with RGB parallel display (e.g. Elecrow, Sunton, etc.)

Uncomment / edit the section that matches your board, then
copy both this file and simon_game.py to the device.
"""

import lvgl as lv
import time
import display_driver

# ─────────────────────────────────────────────────────────────────
# 1.  Initialise LVGL
# ─────────────────────────────────────────────────────────────────
lv.init()

# ─────────────────────────────────────────────────────────────────
# 2.  Display & touch driver  — *** EDIT FOR YOUR HARDWARE ***
# ─────────────────────────────────────────────────────────────────

# ┌───────────────────────────────────────────────────────────────┐
# │  OPTION A — SPI display (ILI9488 / ST7796) + I2C touch       │
# │  Common on many 3.5″–5″ TFT modules.                         │
# └───────────────────────────────────────────────────────────────┘
"""
from machine import SPI, Pin, I2C
import ili9XXX
import ft6x36

# SPI display
spi = SPI(1, baudrate=40_000_000, sck=Pin(18), mosi=Pin(23), miso=Pin(19))
disp = ili9XXX.Ili9488(
    spi=spi, dc=Pin(27), cs=Pin(14), rst=Pin(33),
    width=480, height=320, rot=0x60,          # landscape
)

# I2C touch
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400_000)
touch = ft6x36.Ft6x36(i2c)
"""

# ┌───────────────────────────────────────────────────────────────┐
# │  OPTION B — RGB parallel display (ESP32-S3 boards)            │
# │  Elecrow 7″ (1024×600), Sunton 4.3″ (800×480), etc.          │
# └───────────────────────────────────────────────────────────────┘
"""
import lcd_bus
import ili9XXX  # or st7796, gc9a01, etc.
import gt911    # or ft6x36, cst816s …

# Adapt pin numbers, timings, resolution to your board's schematic.
bus = lcd_bus.RGBBus(
    hsync=46, vsync=3, de=5, pclk=7,
    data0=14, data1=38, data2=18, data3=17, data4=10,
    data5=39, data6=0,  data7=45, data8=48, data9=47,
    data10=21, data11=1, data12=2, data13=42, data14=41, data15=40,
    freq=16_000_000,
    hsync_front_porch=40, hsync_pulse_width=48, hsync_back_porch=40,
    vsync_front_porch=1,  vsync_pulse_width=31, vsync_back_porch=13,
    width=1024, height=600,
)

import rgb_display
disp = rgb_display.RGBDisplay(bus, width=1024, height=600)

i2c = I2C(0, scl=Pin(9), sda=Pin(8), freq=400_000)
touch = gt911.Gt911(i2c)
"""

# ┌───────────────────────────────────────────────────────────────┐
# │  OPTION C — SDL / Unix port (for desktop testing)             │
# └───────────────────────────────────────────────────────────────┘
"""
import sdl_display
import sdl_pointer

disp = sdl_display.SdlDisplay(width=1024, height=600)
touch = sdl_pointer.SdlPointer()
"""

# ─────────────────────────────────────────────────────────────────
# 3.  Launch the game
# ─────────────────────────────────────────────────────────────────
import simon_game
simon_game.start()

# If your framework doesn't have its own event loop, add one:
# while True:
#     lv.timer_handler()
#     time.sleep_ms(5)
