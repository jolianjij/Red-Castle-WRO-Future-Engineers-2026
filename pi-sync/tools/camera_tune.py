#!/usr/bin/env python3
"""
camera_tune.py - tune the CAMERA (not the colours) for the best colour detection.

Colour tuning fails when the image itself is bad: too dark = colours lose
saturation and red/orange collapse together; too bright = they wash out; high
gain = noise; wrong white balance = every hue shifted.

This tool tunes the picture, then color_tuner.py tunes the thresholds on top.
Run this FIRST, then re-run color_tuner.py.

Biggest lever: SATURATION. Pushing it to ~1.3-1.6 separates red / orange /
green / magenta far more cleanly in HSV, at no CPU cost (the ISP does it).

Saves -> camera_settings.json, which camera.py loads automatically.

Needs the Pi desktop / VNC (it opens a window).

Controls
--------
  trackbars : Exposure(us), Gain, Saturation, Contrast, ColourGain R, ColourGain B
  h         : cycle the preview  RGB -> Hue -> Saturation -> Value
  s         : SAVE to camera_settings.json
  q / ESC   : quit (saves too)
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
from picamera2 import Picamera2
from libcamera import Transform

OUT = "camera_settings.json"
WIN = "camera tune"

DEFAULTS = {
    "ExposureTime": 12000,
    "AnalogueGain": 8.0,
    "Saturation": 1.4,
    "Contrast": 1.1,
    "ColourGainR": 1.6,
    "ColourGainB": 1.6,
}

s = dict(DEFAULTS)
if os.path.exists(OUT):
    try:
        s.update(json.load(open(OUT)))
        print(f"loaded existing {OUT}")
    except Exception as e:
        print("could not read", OUT, e)

cam = Picamera2()
cam.configure(cam.create_preview_configuration(
    main={"size": (640, 480), "format": "RGB888"},
    transform=Transform(hflip=1, vflip=1)))
cam.start()
time.sleep(1.0)

cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
cv2.createTrackbar("Exposure x100us", WIN, int(s["ExposureTime"] / 100), 400, lambda v: None)
cv2.createTrackbar("Gain x10",        WIN, int(s["AnalogueGain"] * 10), 160, lambda v: None)
cv2.createTrackbar("Saturation x10",  WIN, int(s["Saturation"] * 10), 30, lambda v: None)
cv2.createTrackbar("Contrast x10",    WIN, int(s["Contrast"] * 10), 30, lambda v: None)
cv2.createTrackbar("GainR x10",       WIN, int(s["ColourGainR"] * 10), 60, lambda v: None)
cv2.createTrackbar("GainB x10",       WIN, int(s["ColourGainB"] * 10), 60, lambda v: None)

view = 0
VIEWS = ["RGB", "HUE", "SAT", "VAL"]
print(__doc__)

try:
    while True:
        s["ExposureTime"] = max(100, cv2.getTrackbarPos("Exposure x100us", WIN) * 100)
        s["AnalogueGain"] = max(1.0, cv2.getTrackbarPos("Gain x10", WIN) / 10.0)
        s["Saturation"] = cv2.getTrackbarPos("Saturation x10", WIN) / 10.0
        s["Contrast"] = cv2.getTrackbarPos("Contrast x10", WIN) / 10.0
        s["ColourGainR"] = max(0.1, cv2.getTrackbarPos("GainR x10", WIN) / 10.0)
        s["ColourGainB"] = max(0.1, cv2.getTrackbarPos("GainB x10", WIN) / 10.0)

        cam.set_controls({
            "AeEnable": False, "AwbEnable": False,
            "ExposureTime": int(s["ExposureTime"]),
            "AnalogueGain": float(s["AnalogueGain"]),
            "Saturation": float(s["Saturation"]),
            "Contrast": float(s["Contrast"]),
            "ColourGains": (float(s["ColourGainR"]), float(s["ColourGainB"])),
        })

        frame = cam.capture_array()
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        if view == 0:
            show = frame.copy()
        elif view == 1:
            show = cv2.applyColorMap(hsv[:, :, 0] * 255 // 179, cv2.COLORMAP_HSV)
        elif view == 2:
            show = cv2.cvtColor(hsv[:, :, 1], cv2.COLOR_GRAY2BGR)
        else:
            show = cv2.cvtColor(hsv[:, :, 2], cv2.COLOR_GRAY2BGR)

        # quality read-outs: mean saturation (higher = easier colour work) and
        # how much of the frame is blown out / crushed
        sat_mean = float(hsv[:, :, 1].mean())
        v = hsv[:, :, 2]
        blown = float((v > 250).mean() * 100)
        dark = float((v < 12).mean() * 100)
        cv2.putText(show, f"view={VIEWS[view]}  exp={int(s['ExposureTime'])}us "
                          f"gain={s['AnalogueGain']:.1f} sat={s['Saturation']:.1f}",
                    (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
        cv2.putText(show, f"mean_sat={sat_mean:5.1f} (higher=better)  "
                          f"blown={blown:.1f}%  dark={dark:.1f}%",
                    (8, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
        cv2.putText(show, "h=view  s=save  q=quit",
                    (8, show.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        cv2.imshow(WIN, show)
        k = cv2.waitKey(30) & 0xFF
        if k == ord('h'):
            view = (view + 1) % len(VIEWS)
        elif k == ord('s'):
            json.dump(s, open(OUT, "w"), indent=2)
            print("saved ->", os.path.abspath(OUT))
        elif k in (ord('q'), 27):
            json.dump(s, open(OUT, "w"), indent=2)
            print("saved ->", os.path.abspath(OUT))
            break
finally:
    cam.close()
    cv2.destroyAllWindows()
