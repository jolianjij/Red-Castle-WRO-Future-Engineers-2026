#!/usr/bin/env python3
"""
mask_debug.py - see EVERY mask the car uses, on one picture.

    python tools/mask_debug.py              # one shot -> mask_debug.png
    python tools/mask_debug.py 20           # average the counts over 20 frames
    python tools/mask_debug.py --live       # re-shoot every second until Ctrl-C

It uses obstacle_challenge.py's OWN capture, crop, colour tests and wall mask,
so what you see is what the car sees - not a second implementation that can
quietly disagree with it.

The picture is a grid of panels, each 320x120, the same size as the frame the
car actually works on:

    camera view          what the lens gives after the crop
    WALL                 what the steering treats as a wall
    blue / orange        the lines that count quadrants
    red / green          the pillars
    purple               the parking walls

Under each panel: the pixel count and what fraction of the frame it is. The
same numbers are printed, so you can read them over SSH without the picture.

Nothing moves. The motor is never touched.
"""
import sys
import os
import time
import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
os.chdir(os.path.join(HERE, ".."))
import obstacle_challenge as O          # noqa: E402  - has every colour

W, H = 320, 120
TOTAL = W * H

live = "--live" in sys.argv
N = next((int(a) for a in sys.argv[1:] if a.isdigit()), 1)


def masks_of(hsv):
    """Every mask, built with obstacle_challenge's own thresholds."""
    h = hsv[:, :, 0].astype(np.int16)
    s = hsv[:, :, 1].astype(np.int16)
    v = hsv[:, :, 2].astype(np.int16)
    return [
        ("WALL", O.wall_mask(h, s, v), (200, 200, 200)),
        ("blue line", ((s > O.BLUE_SAT_MIN) & (v > O.BLUE_VAL_MIN) &
                       (v < O.BLUE_VAL_MAX) & (h > O.BLUE_HUE_MIN) &
                       (h < O.BLUE_HUE_MAX)), (255, 80, 0)),
        ("orange line", ((s > O.ORANGE_SAT_MIN) & (v > O.ORANGE_VAL_MIN) &
                         (v < O.ORANGE_VAL_MAX) & (h >= O.ORANGE_HUE_MIN) &
                         (h <= O.ORANGE_HUE_MAX)), (0, 140, 255)),
        ("red pillar", ((s > O.RED_SAT_MIN) & (v > O.RED_VAL_MIN) &
                        (v < O.RED_VAL_MAX) &
                        ((h < O.RED_HUE_LO) | (h > O.RED_HUE_HI))),
         (0, 0, 255)),
        ("green pillar", ((s > O.GREEN_SAT_MIN) & (v > O.GREEN_VAL_MIN) &
                          (v < O.GREEN_VAL_MAX) & (h > O.GREEN_HUE_MIN) &
                          (h < O.GREEN_HUE_MAX)), (0, 255, 0)),
        ("purple park", ((s > O.PURPLE_SAT_MIN) & (v > O.PURPLE_VAL_MIN) &
                         (v < O.PURPLE_VAL_MAX) & (h >= O.PURPLE_HUE_MIN) &
                         (h <= O.PURPLE_HUE_MAX)), (255, 0, 255)),
    ]


def label(panel, text, sub):
    cv2.rectangle(panel, (0, 0), (W, 13), (0, 0, 0), -1)
    cv2.putText(panel, text, (3, 10), cv2.FONT_HERSHEY_SIMPLEX, 0.32,
                (255, 255, 255), 1, cv2.LINE_AA)
    cv2.rectangle(panel, (0, H - 13), (W, H), (0, 0, 0), -1)
    cv2.putText(panel, sub, (3, H - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.32,
                (200, 255, 200), 1, cv2.LINE_AA)
    cv2.rectangle(panel, (0, 0), (W - 1, H - 1), (60, 60, 60), 1)
    return panel


def shoot(cam):
    frames = []
    for _ in range(max(1, N)):
        raw = O.capture_array(cam)
        O.raw_frame[:] = raw
        fr = np.empty((H, W, 3), np.uint8)
        O.process_frame(O.raw_frame, fr)
        frames.append(fr)
    view = frames[-1]
    hsv = cv2.cvtColor(view, cv2.COLOR_BGR2HSV)

    # counts averaged over every frame, mask picture from the last one
    named = masks_of(hsv)
    sums = {n: 0 for n, _, _ in named}
    for fr in frames:
        for n, m, _ in masks_of(cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)):
            sums[n] += int(m.sum())

    panels = [label(view.copy(), "camera view",
                    "crop_top=%d  %dx%d" % (O.CROP_TOP, W, H))]
    print()
    print("=" * 62)
    print("  MASK DEBUG   %d frame%s   crop_top=%d"
          % (len(frames), "s" if len(frames) > 1 else "", O.CROP_TOP))
    print("=" * 62)
    print("  %-14s %8s %8s   %s" % ("mask", "pixels", "% frame", "note"))
    for name, m, colour in named:
        avg = sums[name] / float(len(frames))
        pct = 100.0 * avg / TOTAL
        panel = np.zeros((H, W, 3), np.uint8)
        panel[m] = colour
        # halves matter for the wall, so mark the centre line
        cv2.line(panel, (W // 2, 13), (W // 2, H - 13), (70, 70, 70), 1)
        note = ""
        if name == "WALL":
            l = int(m[:, :W // 2].sum()) / 12800.0
            r = int(m[:, W // 2:].sum()) / 12800.0
            note = "L=%.3f R=%.3f  (targets CW %.3f / CCW %.3f)" % (
                l, r, O.WALL_CENTRED, O.WALL_CENTRED)
        elif name == "blue line":
            note = "fires above %d" % O.blue_line_threshould
        elif name == "orange line":
            note = "fires above %d" % O.orange_line_threshould
        elif name == "red pillar":
            note = "a sign above %d px" % O.RED_MIN_AREA
        elif name == "green pillar":
            note = "a sign above %d px" % O.GREEN_MIN_AREA
        print("  %-14s %8.0f %7.2f%%   %s" % (name, avg, pct, note))
        panels.append(label(panel, name, "%d px  %.2f%%" % (avg, pct)))

    while len(panels) % 2:
        panels.append(np.zeros((H, W, 3), np.uint8))
    rows = [np.hstack(panels[i:i + 2]) for i in range(0, len(panels), 2)]
    sheet = np.vstack(rows)
    cv2.imwrite("mask_debug.png", sheet)
    print()
    print("  Saved mask_debug.png  (%dx%d)" % (sheet.shape[1], sheet.shape[0]))
    print("=" * 62)


cam = O.Setup_Camera()
time.sleep(0.6)
try:
    if live:
        print("live mode - Ctrl-C to stop")
        while True:
            shoot(cam)
            time.sleep(1.0)
    else:
        shoot(cam)
finally:
    cam.close()
