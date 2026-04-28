"""
Diagnostico LVGL 9.x MicroPython
Esegui sulla board e incolla l'output qui.
"""
import lvgl as lv

print("=" * 50)
print("LVGL BINDING DIAGNOSTIC")
print("=" * 50)

# 1) Come ottenere lo schermo attivo
print("\n--- SCREEN ACCESS ---")
for name in ["screen_active", "scr_act", "active_screen",
             "get_screen_active", "current_screen"]:
    print(f"  lv.{name}: {hasattr(lv, name)}")

# Display object
print("\n--- DISPLAY ---")
for name in ["disp_get_default", "display"]:
    print(f"  lv.{name}: {hasattr(lv, name)}")

try:
    d = lv.disp_get_default()
    print(f"  disp_get_default() -> {d}")
    print(f"  dir(disp): {[x for x in dir(d) if 'scr' in x or 'screen' in x]}")
except:
    pass

try:
    d = lv.display.get_default()
    print(f"  display.get_default() -> {d}")
    print(f"  dir(display): {[x for x in dir(d) if 'scr' in x or 'screen' in x]}")
except:
    pass

# 2) Enum OPA
print("\n--- OPA ---")
print(f"  hasattr(lv, 'OPA'): {hasattr(lv, 'OPA')}")
try:
    print(f"  dir(lv.OPA): {dir(lv.OPA)}")
except:
    pass
for name in ["OPA_TRANSP", "OPA_COVER", "OPA_50"]:
    print(f"  lv.{name}: {hasattr(lv, name)}")

# 3) Enum FLAG
print("\n--- FLAGS ---")
try:
    print(f"  lv.obj.FLAG exists: {hasattr(lv.obj, 'FLAG')}")
    print(f"  dir(FLAG): {[x for x in dir(lv.obj.FLAG) if not x.startswith('_')]}")
except:
    print("  lv.obj.FLAG not found")

# 4) Arc API
print("\n--- ARC ---")
try:
    a = lv.arc.__dict__
    print(f"  arc attrs with 'MODE': {[x for x in dir(lv.arc) if 'MODE' in x.upper()]}")
except:
    pass

# 5) SYMBOL
print("\n--- SYMBOLS ---")
print(f"  hasattr(lv, 'SYMBOL'): {hasattr(lv, 'SYMBOL')}")
try:
    print(f"  BATTERY: {[x for x in dir(lv.SYMBOL) if 'BATT' in x.upper()]}")
    print(f"  ARROWS:  {[x for x in dir(lv.SYMBOL) if 'LEFT' in x.upper() or 'RIGHT' in x.upper()]}")
except:
    pass

# 6) FONT
print("\n--- FONTS ---")
fonts = [x for x in dir(lv) if 'font' in x.lower() or 'FONT' in x]
print(f"  Available: {fonts}")

# 7) Timer
print("\n--- TIMER ---")
for name in ["timer_create", "timer"]:
    print(f"  lv.{name}: {hasattr(lv, name)}")

# 8) ANIM
print("\n--- ANIM ---")
for name in ["ANIM_OFF", "ANIM_ON", "ANIM"]:
    print(f"  lv.{name}: {hasattr(lv, name)}")

# 9) Top-level dir (cerchiamo cose utili)
print("\n--- TOP LEVEL (filtered) ---")
top = [x for x in dir(lv) if not x.startswith('_')
       and any(k in x.lower() for k in ['scr','screen','disp','display',
                                          'load','opa','anim','flag'])]
print(f"  {top}")

print("\n" + "=" * 50)
print("FINE DIAGNOSTICO")
print("=" * 50)
