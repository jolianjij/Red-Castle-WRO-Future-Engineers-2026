#!/usr/bin/env python3
"""
cam_capture.py - field capture / focus & exposure testing for the IMX708 Wide.

Usage:
    python cam_capture.py [name] [width] [height] [lens]
      name   output basename           (default: cap)
      width  main width                (default: 2304  = full FOV)
      height main height               (default: 1296)
      lens   manual focus in dioptres  (default: -1 = autofocus)
             ~0.5 m -> 2.0, ~0.33 m -> 3.0, ~0.22 m -> 4.5

Saves <name>.jpg (180-flipped to match the upside-down mount) and prints the
lens/exposure/gain the camera used.
"""
import sys
import time

import cv2
from picamera2 import Picamera2
from libcamera import Transform, controls

name = sys.argv[1] if len(sys.argv) > 1 else "cap"
w = int(sys.argv[2]) if len(sys.argv) > 2 else 2304
h = int(sys.argv[3]) if len(sys.argv) > 3 else 1296
lens = float(sys.argv[4]) if len(sys.argv) > 4 else -1.0

p = Picamera2()
cfg = p.create_still_configuration(main={"size": (w, h), "format": "RGB888"},
                                   transform=Transform(hflip=1, vflip=1))
p.configure(cfg)
p.start()
time.sleep(1.0)

if lens >= 0:
    p.set_controls({"AfMode": controls.AfModeEnum.Manual, "LensPosition": lens})
    time.sleep(1.2)
else:
    p.set_controls({"AfMode": controls.AfModeEnum.Auto})
    try:
        p.autofocus_cycle()
    except Exception as e:
        print("AF err:", e)

time.sleep(0.6)
md = p.capture_metadata()
frame = p.capture_array()
p.close()

cv2.imwrite(name + ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
print("saved", name + ".jpg", frame.shape)
print("LensPosition:", md.get("LensPosition"), "Exposure(us):", md.get("ExposureTime"),
      "Gain:", md.get("AnalogueGain"), "Lux:", md.get("Lux"))
