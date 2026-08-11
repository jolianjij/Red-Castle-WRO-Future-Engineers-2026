#!/usr/bin/env python3
"""
color_tuner.py - Interactive HSV tuner for the WRO 2026 car.

Tune each colour ONE AT A TIME (black, blue, orange, green, red, magenta),
see the live mask, then save every range to colors.json for the main code.

HSV is computed with cv2.COLOR_BGR2HSV on the RGB888 frame - the SAME way the
challenge code does it - so tuned values transfer directly. Frames are rotated
180 because the camera is mounted upside-down.

Needs a display (run on the Pi desktop or over VNC, not headless SSH).

Controls
--------
  Left-click the image  : smart-sample - auto-fills the 6 sliders from that spot
  trackbars             : fine-tune H/S/V low & high by hand
  n  or  SPACE          : save current colour, go to NEXT colour
  b                     : go to previous colour
  r                     : reset current colour to its default seed
  s                     : save all colours to colors.json now
  q  or  ESC            : save all + quit
"""

import json
import os
import time

import cv2
import numpy as np
from picamera2 import Picamera2

OUTPUT_FILE = "colors.json"
WINDOW = "color tuner"
FLIP_180 = True   # camera mounted upside-down

COLORS = ["black", "blue", "orange", "green", "red", "magenta"]

# Seeds from the challenge thresholds. [h_low,h_high,s_low,s_high,v_low,v_high]
# Red has h_low > h_high on purpose -> wrap-around range.
DEFAULTS = {
    "black":   [0,   179,   0, 255,   0,  70],
    "blue":    [90,  135,  60, 255,  70, 200],
    "orange":  [0,    30,  60, 255, 125, 240],
    "green":   [45,   90, 120, 255,  60, 240],
    "red":     [170,  10, 120, 255,  60, 240],
    "magenta": [130, 145, 177, 255,  93, 255],
}

colors = {}
current = 0
last_click_hsv = None
_updating = False

TRACKBARS = ["H low", "H high", "S low", "S high", "V low", "V high"]
TB_MAX = [179, 179, 255, 255, 255, 255]


def load_colors():
    global colors
    colors = {c: list(DEFAULTS[c]) for c in COLORS}
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE) as f:
                saved = json.load(f)
            for c in COLORS:
                if c in saved:
                    colors[c] = [int(v) for v in saved[c]]
            print(f"loaded existing {OUTPUT_FILE}")
        except Exception as e:
            print(f"could not read {OUTPUT_FILE} ({e}); using defaults")


def save_colors():
    with open(OUTPUT_FILE, "w") as f:
        json.dump(colors, f, indent=2)
    print(f"saved -> {os.path.abspath(OUTPUT_FILE)}")


def _on_trackbar(_):
    if _updating:
        return
    colors[COLORS[current]] = [cv2.getTrackbarPos(t, WINDOW) for t in TRACKBARS]


def push_sliders_from_state():
    global _updating
    _updating = True
    for t, v in zip(TRACKBARS, colors[COLORS[current]]):
        cv2.setTrackbarPos(t, WINDOW, int(v))
    _updating = False


def build_mask(hsv, rng):
    h_lo, h_hi, s_lo, s_hi, v_lo, v_hi = rng
    if h_lo <= h_hi:
        return cv2.inRange(hsv, (h_lo, s_lo, v_lo), (h_hi, s_hi, v_hi))
    m1 = cv2.inRange(hsv, (0,    s_lo, v_lo), (h_hi, s_hi, v_hi))
    m2 = cv2.inRange(hsv, (h_lo, s_lo, v_lo), (179,  s_hi, v_hi))
    return cv2.bitwise_or(m1, m2)


def smart_sample(hsv, x, y):
    global last_click_hsv
    r = 4
    y0, y1 = max(0, y - r), min(hsv.shape[0], y + r + 1)
    x0, x1 = max(0, x - r), min(hsv.shape[1], x + r + 1)
    patch = hsv[y0:y1, x0:x1].reshape(-1, 3).astype(int)
    hue, sat, val = patch[:, 0], patch[:, 1], patch[:, 2]
    last_click_hsv = (int(np.median(hue)), int(np.median(sat)), int(np.median(val)))

    if hue.max() - hue.min() > 90:
        h_lo = int(hue[hue > 90].min()) - 8
        h_hi = int(hue[hue < 90].max()) + 8
    else:
        h_lo = int(hue.min()) - 8
        h_hi = int(hue.max()) + 8
    h_lo = max(0, min(179, h_lo))
    h_hi = max(0, min(179, h_hi))
    s_lo = max(0, int(sat.min()) - 40)
    v_lo = max(0, int(val.min()) - 40)
    v_hi = min(255, int(val.max()) + 40)

    if COLORS[current] == "black":
        colors[COLORS[current]] = [0, 179, 0, 255, 0, min(90, int(val.max()) + 20)]
    else:
        colors[COLORS[current]] = [h_lo, h_hi, s_lo, 255, v_lo, v_hi]
    push_sliders_from_state()


def on_mouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN and param is not None and param[0] is not None:
        smart_sample(param[0], x, y)


def main():
    global current
    load_colors()

    cam = Picamera2()
    cam.configure(cam.create_preview_configuration(
        main={"format": "RGB888", "size": (640, 480)}))
    cam.start()
    time.sleep(1.0)

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    for t, mx in zip(TRACKBARS, TB_MAX):
        cv2.createTrackbar(t, WINDOW, 0, mx, _on_trackbar)
    push_sliders_from_state()

    hsv_holder = [None]
    cv2.setMouseCallback(WINDOW, on_mouse, hsv_holder)

    print(__doc__)
    while True:
        frame = cam.capture_array()                     # RGB888
        if FLIP_180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)   # camera upside-down
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)    # matches main code
        hsv_holder[0] = hsv

        rng = colors[COLORS[current]]
        mask = build_mask(hsv, rng)
        result = cv2.bitwise_and(frame, frame, mask=mask)
        mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        combo = np.hstack([frame, mask_bgr, result])

        name = COLORS[current]
        wrap = " (WRAP)" if rng[0] > rng[1] else ""
        cv2.putText(combo, f"[{current+1}/{len(COLORS)}] {name}{wrap}  px={int(mask.sum()//255)}",
                    (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(combo, f"H{rng[0]}-{rng[1]} S{rng[2]}-{rng[3]} V{rng[4]}-{rng[5]}",
                    (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        if last_click_hsv:
            cv2.putText(combo, f"click HSV {last_click_hsv}",
                        (10, 74), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)
        cv2.putText(combo, "click=sample  n/space=next  b=back  r=reset  s=save  q=quit",
                    (10, combo.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

        cv2.imshow(WINDOW, combo)
        key = cv2.waitKey(30) & 0xFF

        if key in (ord('n'), ord(' ')):
            colors[COLORS[current]] = [cv2.getTrackbarPos(t, WINDOW) for t in TRACKBARS]
            current = (current + 1) % len(COLORS)
            push_sliders_from_state()
        elif key == ord('b'):
            colors[COLORS[current]] = [cv2.getTrackbarPos(t, WINDOW) for t in TRACKBARS]
            current = (current - 1) % len(COLORS)
            push_sliders_from_state()
        elif key == ord('r'):
            colors[COLORS[current]] = list(DEFAULTS[COLORS[current]])
            push_sliders_from_state()
        elif key == ord('s'):
            colors[COLORS[current]] = [cv2.getTrackbarPos(t, WINDOW) for t in TRACKBARS]
            save_colors()
        elif key in (ord('q'), 27):
            colors[COLORS[current]] = [cv2.getTrackbarPos(t, WINDOW) for t in TRACKBARS]
            save_colors()
            break

    cam.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
