#!/usr/bin/env python3
"""
hsv_pick.py - point the car at an object, get HSV bounds you can paste in.

FOR THE VENUE. The other tools CHECK bounds you already have; this one PROPOSES
new ones from whatever the object actually measures under the venue's light.

    python tools/hsv_pick.py green          # name is just a label
    python tools/hsv_pick.py orange --frames 10
    python tools/hsv_pick.py red --wrap     # for red, whose hue wraps past 0

Park so the object FILLS as much of the view as you can and nothing else
coloured is in frame. It finds the most saturated large blob, measures it, and
proposes bounds with margin - then re-counts with those bounds and tells you how
much of the rest of the frame they let in. That second number is the one that
matters: bounds that catch the object are easy, bounds that catch the object and
NOT the mat are the job.

Nothing moves. The motor is never touched.
"""
import sys
import os
import time

import numpy as np
import cv2

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, ".."))
os.chdir(os.path.join(_HERE, ".."))
import open_challenge as OPEN          # noqa: E402  its main() is guarded

# the mat is the thing we must stay out of. MEASURED on this field:
#   mat  H 70-79   S p50 93  p99 146   V p50 135
SEED_SAT = 130          # a blob this saturated is an object, not the mat
SEED_MIN_AREA = 150     # ignore speckle when hunting for the object


def main(argv):
    name = "colour"
    frames = 8
    wrap = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--frames":
            i += 1; frames = int(argv[i])
        elif a == "--wrap":
            wrap = True
        elif not a.startswith("-"):
            name = a
        i += 1

    picam2 = OPEN.Setup_Camera()
    time.sleep(0.6)

    hs, ss, vs = [], [], []
    last = None
    for _ in range(frames):
        raw = OPEN.capture_array(picam2)
        OPEN.raw_frame[:] = raw
        frame = np.empty((120, 320, 3), dtype=np.uint8)
        OPEN.process_frame(OPEN.raw_frame, frame)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        H = hsv[:, :, 0].astype(np.int16)
        S = hsv[:, :, 1].astype(np.int16)
        V = hsv[:, :, 2].astype(np.int16)

        seed = (S > SEED_SAT).astype(np.uint8)
        n, lab, st, _ = cv2.connectedComponentsWithStats(seed, 8)
        if n <= 1:
            continue
        k = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        if st[k, cv2.CC_STAT_AREA] < SEED_MIN_AREA:
            continue
        m = lab == k
        hs.append(H[m]); ss.append(S[m]); vs.append(V[m])
        last = (frame, hsv, m)

    print()
    print("=" * 70)
    print("  HSV PICK   '%s'   %d frames%s"
          % (name, frames, "   (hue wraps)" if wrap else ""))
    print("=" * 70)

    if last is None:
        print()
        print("  NOTHING FOUND. No blob was more saturated than S>%d and bigger"
              % SEED_SAT)
        print("  than %d px. Either the object is not in view, or it is so dark"
              % SEED_MIN_AREA)
        print("  that its saturation collapsed. Move closer and try again.")
        print("=" * 70)
        return 1

    frame, hsv, m = last
    H = np.concatenate(hs); S = np.concatenate(ss); V = np.concatenate(vs)
    print()
    print("  the object, %d px over %d frames:" % (H.size, len(hs)))
    for lbl, A in (("H", H), ("S", S), ("V", V)):
        q = np.percentile(A, [1, 5, 50, 95, 99])
        print("      %s  p01=%3d  p05=%3d  p50=%3d  p95=%3d  p99=%3d"
              % (lbl, q[0], q[1], q[2], q[3], q[4]))

    # everything that is NOT the object, in the last frame - the background
    Hb = hsv[:, :, 0].astype(np.int16)[~m]
    Sb = hsv[:, :, 1].astype(np.int16)[~m]
    print()
    print("  the background in the same frame, %d px:" % Hb.size)
    print("      H  p50=%3d           S  p50=%3d p95=%3d p99=%3d"
          % (np.percentile(Hb, 50), np.percentile(Sb, 50),
             np.percentile(Sb, 95), np.percentile(Sb, 99)))

    # ---- propose ----
    h_lo, h_hi = int(np.percentile(H, 1)) - 5, int(np.percentile(H, 99)) + 5
    if wrap:
        # a wrapping colour straddles 0; report the two arms the code expects
        near0 = H[H < 90]; near180 = H[H >= 90]
        hi_arm = int(np.percentile(near0, 99)) + 5 if near0.size else 15
        lo_arm = int(np.percentile(near180, 1)) - 5 if near180.size else 175
        h_lo, h_hi = max(0, lo_arm), min(179, hi_arm)
    else:
        h_lo, h_hi = max(0, h_lo), min(179, h_hi)

    # saturation floor: below the object but clearly ABOVE the background
    s_obj_low = int(np.percentile(S, 1))
    s_bg_high = int(np.percentile(Sb, 99))
    s_floor = int((s_obj_low + s_bg_high) / 2) if s_bg_high < s_obj_low else s_obj_low - 10
    s_floor = max(0, min(254, s_floor))

    # brightness floor: WELL below the object - this is the bound that has
    # broken every colour on this car, so it gets real margin
    v_floor = max(0, int(np.percentile(V, 1) * 0.6))

    print()
    print("  " + "-" * 66)
    print("  PROPOSED - paste these in")
    print("  " + "-" * 66)
    if wrap:
        print("      %s_HUE_LO, %s_HUE_HI = %d, %d       # h < LO  or  h > HI"
              % (name.upper(), name.upper(), h_hi, h_lo))
    else:
        print("      %s_HUE_MIN, %s_HUE_MAX = %d, %d"
              % (name.upper(), name.upper(), h_lo, h_hi))
    print("      %s_SAT_MIN = %d" % (name.upper(), s_floor))
    print("      %s_VAL_MIN, %s_VAL_MAX = %d, 255"
          % (name.upper(), name.upper(), v_floor))

    # ---- check them ----
    Hf = hsv[:, :, 0].astype(np.int16)
    Sf = hsv[:, :, 1].astype(np.int16)
    Vf = hsv[:, :, 2].astype(np.int16)
    if wrap:
        hue_ok = (Hf <= h_hi) | (Hf >= h_lo)
    else:
        hue_ok = (Hf >= h_lo) & (Hf <= h_hi)
    got = hue_ok & (Sf > s_floor) & (Vf > v_floor)
    on_obj = int(np.count_nonzero(got & m))
    off_obj = int(np.count_nonzero(got & ~m))
    obj_total = int(np.count_nonzero(m))
    print()
    print("  checked on this frame:")
    print("      of the object   : %d of %d px kept   (%.0f%%)"
          % (on_obj, obj_total, 100.0 * on_obj / max(1, obj_total)))
    print("      of everything else: %d px let in" % off_obj)
    if off_obj > obj_total * 0.15:
        print("      !! that is a lot of background. Raise the SAT floor until")
        print("         it drops - saturation is what separates object from mat.")
    else:
        print("      that is clean separation.")

    vis = frame.copy()
    vis[got] = (0, 255, 255)
    cv2.imwrite("hsv_pick_%s.png" % name, np.vstack([frame, vis]))
    print()
    print("  Saved hsv_pick_%s.png  (yellow = what the proposed bounds catch)" % name)
    print()
    print("  NOW CHECK THE OTHER WAY: move the object OUT of view and run")
    print("      python tools/color_count.py <the six numbers above>")
    print("  A threshold is only safe when you know BOTH readings.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
