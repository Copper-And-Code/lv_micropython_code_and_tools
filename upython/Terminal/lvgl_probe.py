# lvgl_probe.py — LVGL API Probe v3
# Run on target:  import lvgl_probe

import lvgl as lv
import display_driver    # <-- YOUR display init

import time
time.sleep_ms(100)       # Let LVGL process first frame

print("=== LVGL API Probe v3 ===\n")

# ── 1. Display ──
scr = lv.screen_active()
print("[1] lv.screen_active():", scr, type(scr))
if scr is None:
    print("    FATAL: No active screen even after display_driver!")
    raise SystemExit

# ── 2. Basic obj ──
parent = lv.obj(scr)
print("[2] lv.obj(scr): OK")

# ── 3. Spangroup ──
print("\n--- SPANGROUP ---")
sg = None
try:
    sg = lv.spangroup(parent)
    print("[3a] lv.spangroup():", sg, type(sg))
except Exception as e:
    print("[3a] lv.spangroup(): EXCEPTION -", e)

if sg is not None:
    print("[3b] methods:", sorted([m for m in dir(sg) if not m.startswith('_')]))
    # Try span creation
    for name in ['new_span', 'get_new_span', 'add_span']:
        if hasattr(sg, name):
            print("     sg.{}: EXISTS".format(name))
    try:
        sg.delete()
    except:
        pass
else:
    print("[3b] spangroup is None — disabled in build")

# ── 4. Label ──
print("\n--- LABEL ---")
lbl = lv.label(parent)
print("[4a] lv.label(): OK, type =", type(lbl))
print("[4b] methods:", sorted([m for m in dir(lbl) if not m.startswith('_')]))
print("[4c] set_recolor:", hasattr(lbl, 'set_recolor'))

# Try recolor
if hasattr(lbl, 'set_recolor'):
    try:
        lbl.set_recolor(True)
        lbl.set_text("#ff0000 Red# Normal")
        print("[4d] recolor: OK")
    except Exception as e:
        print("[4d] recolor: FAIL -", e)

# Long mode
try:
    lbl.set_long_mode(lv.label.LONG.CLIP)
    print("[4e] LONG.CLIP: OK")
except:
    try:
        lbl.set_long_mode(lv.label.LONG_CLIP)
        print("[4e] LONG_CLIP (alt): OK")
    except:
        print("[4e] set_long_mode: FAIL")

lbl.delete()

# ── 5. Font ──
print("\n--- FONT ---")
for fn in ['font_unscii_8', 'font_unscii_16', 'font_montserrat_14']:
    print("[5] lv.{}: {}".format(fn, 'YES' if hasattr(lv, fn) else 'no'))

# ── 6. Style test ──
print("\n--- STYLE TEST ---")
try:
    t = lv.label(parent)
    t.set_style_text_font(lv.font_unscii_8, 0)
    t.set_style_text_color(lv.color_hex(0xFF0000), 0)
    t.set_style_bg_color(lv.color_hex(0x000000), 0)
    t.set_style_bg_opa(lv.OPA.COVER, 0)
    t.set_text("Test OK")
    print("[6] label styling: ALL OK")
    t.delete()
except Exception as e:
    print("[6] label styling: FAIL -", e)

# ── 7. Timer ──
print("\n--- TIMER ---")
try:
    tmr = lv.timer_create(lambda t: None, 1000, None)
    print("[7] lv.timer_create: OK")
    tmr.delete()
except Exception as e:
    print("[7] lv.timer_create: FAIL -", e)

# ── 8. Screen size ──
print("\n--- DISPLAY ---")
try:
    d = lv.display_get_default()
    w = d.get_horizontal_resolution()
    h = d.get_vertical_resolution()
    print("[8] Display: {}x{}".format(w, h))
except:
    try:
        w = lv.disp_get_hor_res(None)
        h = lv.disp_get_ver_res(None)
        print("[8] Display: {}x{}".format(w, h))
    except:
        print("[8] Could not get display resolution")

parent.delete()
print("\n=== Probe complete ===")
