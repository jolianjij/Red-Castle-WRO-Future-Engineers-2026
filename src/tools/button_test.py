#!/usr/bin/env python3
"""
button_test.py - check the start/stop button is wired and configured right.

Run this ONCE after wiring the button, before trusting it in a real run:

    cd ~/wro2026 && source .venv/bin/activate && python tools/button_test.py

It first reports which way the button is wired, then counts presses. If the
reading is inverted (it says PRESSED when you are not touching it), flip
BUTTON_PULL_UP in config.py and run this again.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import RPi.GPIO as GPIO      # noqa: E402
import robot as R            # noqa: E402

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(R.BUTTON_PIN, GPIO.IN,
           pull_up_down=GPIO.PUD_UP if R.BUTTON_PULL_UP else GPIO.PUD_DOWN)

print(f"button on GPIO{R.BUTTON_PIN}, "
      f"BUTTON_PULL_UP = {R.BUTTON_PULL_UP} "
      f"({'wired to GND' if R.BUTTON_PULL_UP else 'wired to 3V3'})")
print("\nDo not touch the button for a moment...")
time.sleep(1.5)

raw = GPIO.input(R.BUTTON_PIN)
idle_down = (raw == 0) if R.BUTTON_PULL_UP else (raw == 1)
print(f"  idle level = {'HIGH' if raw else 'LOW'}  ->  "
      f"reads as {'PRESSED' if idle_down else 'released'}")

if idle_down:
    print("\n  *** WRONG. It thinks the button is held while you are not")
    print(f"      touching it. Set BUTTON_PULL_UP = {not R.BUTTON_PULL_UP} in")
    print("      config.py and run this again.")
    print("      (If it still reads pressed, check the wiring itself.)")
    GPIO.cleanup()
    sys.exit(1)

print("  correct - idle reads as released\n")

button = R.Button()
button._ignore_until = 0.0
print("Now press the button a few times. Ctrl+C when you are done.")
print("Each press should print exactly ONE line.\n")

presses = 0
try:
    while True:
        if button.stop_pressed():
            presses += 1
            print(f"  press {presses}")
        time.sleep(0.005)
except KeyboardInterrupt:
    print(f"\n{presses} presses counted.")
    print("If that matches how many times you actually pressed, the button is"
          " good.\nIf it counted extra, raise BUTTON_DEBOUNCE_S in config.py.")
finally:
    GPIO.cleanup()
