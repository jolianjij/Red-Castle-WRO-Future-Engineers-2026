#!/usr/bin/env python3
"""
freespace_test.py - VALIDATE the free-space / follow-the-gap perception (method B)
                    WITHOUT driving the car. Nothing moves. Safe to run anywhere.

It captures a frame, finds the mat->wall boundary in every column, builds the
free-space profile, picks the widest gap, and writes an annotated picture so you
can SEE whether the perception is trustworthy before we build control on it.

What to look for in freespace_test.png:
  GREEN line   = detected mat/wall boundary. It must hug the bottom of the walls.
                 If it jumps onto the mat's dotted lines -> raise FREE_MIN_RUN.
  CYAN band    = the widest gap (where the car thinks the road is).
  YELLOW line  = the steering target. On a straight it should sit near the middle;
                 approaching a corner it should swing to the open side.
  Printed text = steering angle it WOULD command (nothing is actually driven).

Usage (from ~/wro2026):
    python tools/freespace_test.py             # one frame
    python tools/freespace_test.py 20          # 20 frames, ~2/s (walk the car around)
    python tools/freespace_test.py 1 10        # one frame, FREE_MIN_RUN=10
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import cv2
import numpy as np
import robot as R

frames = int(sys.argv[1]) if len(sys.argv) > 1 else 1
min_run = int(sys.argv[2]) if len(sys.argv) > 2 else None

cam = R.open_camera()
time.sleep(0.6)
print(f"FREE_MIN_RUN={min_run or R.FREE_MIN_RUN}  GAP_OPEN_FRAC={R.GAP_OPEN_FRAC}")
print("nothing is driven - this is perception only\n")

try:
    for i in range(frames):
        proc, hsv = R.read_hsv(cam)
        base = R.wall_base_rows(hsv, min_run)
        free = R.freespace_profile(hsv, min_run)
        gap = R.find_gap(free)
        left, right = R.wall_readings(hsv)
        front = R.front_reading(hsv)

        vis = proc.copy()
        # boundary (green) - where the code thinks each wall starts
        for x in range(R.PROC_W):
            y = int(base[x])
            if 0 < y < R.PROC_H:
                vis[y, x] = (0, 255, 0)
                if y + 1 < R.PROC_H:
                    vis[y + 1, x] = (0, 255, 0)

        if gap is not None:
            cx, width, best = gap
            steer = R.gap_steer(cx)
            half = int(width // 2)
            x0, x1 = max(0, int(cx) - half), min(R.PROC_W - 1, int(cx) + half)
            band = vis[:, x0:x1].astype(np.int32)          # cyan tint on the gap
            band[:, :, 1] += 45
            band[:, :, 0] += 45
            vis[:, x0:x1] = np.clip(band, 0, 255).astype(np.uint8)
            cv2.line(vis, (int(cx), 0), (int(cx), R.PROC_H), (0, 255, 255), 1)
            msg = f"gap@{cx:5.1f} w={width:3d} steer={steer:+5.1f}"
        else:
            steer = 0.0
            msg = "NO GAP - blocked"

        info = (f"[{i+1}/{frames}] {msg} | L={left:.2f} R={right:.2f} "
                f"front={front:.2f} maxfree={free.max():.0f}/{R.PROC_H}")
        print(info)

        # scale up + a profile strip underneath so it is readable
        big = cv2.resize(vis, (R.PROC_W * 2, R.PROC_H * 2), interpolation=cv2.INTER_NEAREST)
        strip = np.zeros((80, R.PROC_W * 2, 3), np.uint8)
        for x in range(R.PROC_W):
            h = int(free[x] / R.PROC_H * 78)
            cv2.line(strip, (x * 2, 79), (x * 2, 79 - h), (200, 200, 60), 2)
        thr_y = 79 - int(R.GAP_OPEN_FRAC * 78)
        cv2.line(strip, (0, thr_y), (R.PROC_W * 2, thr_y), (0, 0, 255), 1)
        out = np.vstack([big, strip])
        cv2.putText(out, msg, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        cv2.imwrite("freespace_test.png", out)
        if frames > 1:
            cv2.imwrite(f"freespace_{i:03d}.png", out)
            time.sleep(0.5)
finally:
    cam.close()
    print("\nsaved -> freespace_test.png  (open it, or I can pull it over SSH)")
