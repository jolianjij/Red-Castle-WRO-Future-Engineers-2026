"""Show exactly what is being classified as WALL, and whether shadow is to blame."""
import sys, time, cv2, numpy as np, robot as R
label = sys.argv[1] if len(sys.argv) > 1 else "spot"
cam = R.open_camera(); time.sleep(0.7)
proc, hsv = R.read_hsv(cam); cam.close()

V = hsv[:, :, 2].astype(int)
m = R.mask(hsv, "black") > 0
l, r = R.wall_readings(hsv)
thr = R.COLORS["black"][5]

print("[%s]  left=%.4f  right=%.4f   (wall = value < %d)" % (label, l, r, thr))
print("  brightness in frame: min=%d  median=%d  max=%d" % (V.min(), np.median(V), V.max()))

# a TRUE wall is a tall solid dark region; a shadow is a broad shallow one.
base = R.wall_base_rows(hsv)          # needs FREE_MIN_RUN consecutive dark rows
runmask = np.zeros_like(m)
for x in range(R.PROC_W):
    if base[x] > 0:
        runmask[:base[x] + 1, x] = True
solid = int((m & runmask).sum())
loose = int((m & ~runmask).sum())
print("  dark px in a TALL RUN (real wall) : %5d" % solid)
print("  dark px NOT in a run (shadow?)    : %5d  <-- these inflate the density" % loose)
if solid + loose:
    print("  -> %.0f%% of what we call 'wall' is not part of a solid vertical wall"
          % (100.0 * loose / (solid + loose)))

# histogram of the darker end, to see if shadow sits just under the threshold
print("\n  brightness histogram (dark end):")
for lo in range(0, 140, 20):
    n = int(((V >= lo) & (V < lo + 20)).sum())
    if n:
        tag = "  <= counted as WALL" if lo + 20 <= thr else ("  <= STRADDLES threshold" if lo < thr else "")
        print("    V %3d-%3d : %6d px%s" % (lo, lo + 19, n, tag))

vis = proc.copy()
vis[m & runmask] = (0, 255, 0)      # green = solid wall
vis[m & ~runmask] = (0, 0, 255)     # red   = dark but not a wall -> suspect shadow
cv2.imwrite("shadow_%s.png" % label, np.vstack([proc, vis]))
print("\n  saved shadow_%s.png  (green = real wall, RED = suspected shadow)" % label)
