#!/usr/bin/env python3
"""
preview.py - live camera window on the Pi desktop (view it over VNC).

Shows the real camera feed (180-flipped, manual focus). Click the window and
press 'q' to quit. Change LENS_POS to test focus for far cubes.

Run on the Pi desktop / VNC:
    cd ~/wro2026 && source .venv/bin/activate && python tools/preview.py
"""
import cv2
from picamera2 import Picamera2
from libcamera import Transform, controls

LENS_POS = 2.0   # focus in dioptres: ~0.33 m -> 3.0 (near), ~0.5 m -> 2.0, farther -> 1.5

p = Picamera2()
p.configure(p.create_preview_configuration(
    main={"size": (960, 540), "format": "RGB888"},
    transform=Transform(hflip=1, vflip=1)))
p.set_controls({"AfMode": controls.AfModeEnum.Manual, "LensPosition": LENS_POS})
p.start()

print("Live preview - click the window and press 'q' to quit")
try:
    while True:
        frame = p.capture_array()
        cv2.imshow("WRO camera (press q to quit)", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
finally:
    p.close()
    cv2.destroyAllWindows()
