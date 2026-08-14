#!/usr/bin/env python3
"""
open_challenge.py - WRO 2026 Future Engineers, OPEN challenge.

Logic (clean, per frame):
  1. read camera -> wall densities (left/right) + line fractions (blue/orange)
  2. LapTracker: first line sets driving direction; count 12 quadrants = 3 laps
  3. WallFollower: PD steering to stay CENTERED between the two walls
  4. speed eases off in turns; after 3 laps (+ a short coast) -> stop

Logging: every cycle is written to logs/open_<timestamp>.csv so the run can be
reviewed afterwards (wall readings, lines, direction, quadrant, steer, speed).

Run on the Pi:  cd ~/wro2026 && source .venv/bin/activate && python open_challenge.py
"""
import csv
import os
import time

import robot as R

# ==========================================================================
# TUNABLES - everything you might want to change lives here.
# Anything NOT in this block is shared with the Obstacle Challenge and lives
# in config.py, so changing it there changes both runs.
# ==========================================================================

# --- speed ---
CRUISE           = 100     # base speed %. Falls automatically with steering
                           # (see R.cruise_speed), so this is the straight-line
                           # figure, not the average.

# --- direction ---
FORCE_DIRECTION  = 0       # 0 = detect from the corner lines (normal).
                           # +1 forces CW, -1 forces CCW. Only set this if the
                           # judges tell you the run direction.

# --- how far from the outer wall to drive ---
LANE_DISTANCE_CM = 40.0    # hold this far from the OUTER wall on the straights.
# density = 0.1032 at 40 cm, slope 0.00501 per cm closer (measured on this car)
LANE_TARGET      = 0.1032 - (LANE_DISTANCE_CM - 40.0) * 0.00501

# --- corner lines (direction + lap counting) ---
# These two are the reason a CW run could be read as CCW: one shared threshold
# is unfair to orange, which is far fainter than blue on this camera. They live
# in config.py because the Obstacle Challenge needs exactly the same values.
#     R.LINE_FRACTION_ORANGE   lower bar - orange is hard to see
#     R.LINE_FRACTION_BLUE     higher bar - blue over-triggers on background
#     R.LINE_DIR_MIN_RATIO     how decisively one must beat the other to lock
LINE_ROWS_OVERRIDE = None  # None = use config's LINE_ROWS (bottom 45% of ROI)

# --- run control ---
STOP_AFTER_QUADRANT = None # None = use config's value (11). 12 corners = 3 laps.
MAX_RUNTIME_S    = 150     # SAFETY net only. 3 laps measured ~5 s/quadrant
                           # = ~60 s, so this is headroom, not a lap limit.
FINISH_EXTRA_CYCLES = 60   # keep going a bit after the last quadrant, then stop
DEBUG            = True    # print a status line every DEBUG_EVERY cycles
DEBUG_EVERY      = 15
# ==========================================================================

if LINE_ROWS_OVERRIDE is not None:
    R.LINE_ROWS = LINE_ROWS_OVERRIDE
if STOP_AFTER_QUADRANT is not None:
    R.STOP_AFTER_QUADRANT = STOP_AFTER_QUADRANT


def main():
    R.setup_hardware()
    R.servo(0)
    cam = R.open_camera()

    laps = R.LapTracker()
    if FORCE_DIRECTION:
        laps.direction = FORCE_DIRECTION
    follower = R.WallFollower()
    outer = R.OuterWallFollower(target=LANE_TARGET)   # when NAV_METHOD=="outer"
    turner = R.TurnSequencer()         # scripted line-triggered corner turn

    # --- logging ---
    os.makedirs("logs", exist_ok=True)
    logpath = time.strftime("logs/open_%Y%m%d_%H%M%S.csv")
    logf = open(logpath, "w", newline="")
    log = csv.writer(logf)
    log.writerow(["t_ms", "cycle", "dir", "quad", "corner", "mode",
                  "left", "right", "blue", "orange", "steer", "speed"])
    print(f"config: NAV_METHOD={R.NAV_METHOD} CRUISE={CRUISE} "
          f"STEER_MAX={R.STEER_MAX} trim={R.SERVO_CENTER_TRIM}")
    print(f"  direction : {'FORCED ' + ('CW' if FORCE_DIRECTION > 0 else 'CCW')}"
          if FORCE_DIRECTION else "  direction : auto from corner lines")
    print(f"  lane      : {LANE_DISTANCE_CM:.0f} cm from the outer wall "
          f"(density {LANE_TARGET:.4f})")
    print(f"  lines     : orange>{R.LINE_FRACTION_ORANGE:.3f}  "
          f"blue>{R.LINE_FRACTION_BLUE:.3f}  ratio>{R.LINE_DIR_MIN_RATIO:.2f}")
    print(f"  stop      : after quadrant {R.STOP_AFTER_QUADRANT}")
    print(f"colors loaded: {list(R.COLORS.keys())}")
    print(f"logging -> {logpath}")

    input("Open Challenge ready. Press Enter to START...")
    t0 = time.time()
    R.motor(CRUISE)

    finish_at = None
    n = 0
    reason = "?"
    try:
        while True:
            n += 1
            proc, hsv = R.read_hsv(cam)
            left, right = R.wall_readings(hsv)
            front = R.front_reading(hsv)
            blue, orange = R.line_counts(hsv)
            q_before = laps.quadrant
            laps.update(blue, orange, left, right, front)
            if laps.quadrant > q_before and R.NAV_METHOD == "outer":
                turner.trigger(laps.direction)

            # single dispatch point - honours NAV_METHOD ("gap" or "density")
            # a counted quadrant means we just crossed the corner line ->
            # fire the scripted turn (only used by NAV_METHOD == "outer")
            # geometry backup: a wall this close ahead forces a turn even if the
            # corner line was missed entirely
            steer, mode = R.navigate(hsv, left, right, laps, follower, outer,
                                     turner, front > R.FRONT_TURN_BACKUP, front)
            speed = R.cruise_speed(CRUISE, steer)
            R.servo(steer)
            R.motor(speed)

            t_ms = int((time.time() - t0) * 1000)
            log.writerow([t_ms, n, laps.direction, laps.quadrant, int(laps.in_corner), mode,
                          f"{left:.3f}", f"{right:.3f}", f"{blue:.3f}", f"{orange:.3f}",
                          f"{steer:.1f}", f"{speed:.0f}"])

            if DEBUG and DEBUG_EVERY and n % DEBUG_EVERY == 0:
                logf.flush()
                print(f"t={t_ms:5d}ms dir={laps.direction:+d} quad={laps.quadrant:2d} "
                      f"{mode:12s} L={left:.2f} R={right:.2f} steer={steer:+.0f}")

            # finish: STOP_AFTER_QUADRANT counted AND the lap timer expired
            if laps.ready_to_finish():
                reason = f"{laps.quadrant} quadrants + lap timer expired"
                break
            # safety timeout
            if time.time() - t0 > MAX_RUNTIME_S:
                reason = "SAFETY timeout"
                break

        R.motor(0)
        R.servo(0)
        dt = time.time() - t0
        summary = (f"FINISHED ({reason}): quadrants={laps.quadrant} "
                   f"cycles={n} time={dt:.1f}s avg={1000*dt/max(n,1):.1f}ms/cycle")
        print(summary)
        print("  fusion: " + laps.summary())
        log.writerow(["#", laps.summary()])
        log.writerow([])
        log.writerow(["#", summary])
    except KeyboardInterrupt:
        print("interrupted by user")
        log.writerow(["#", "interrupted by user"])
    finally:
        R.motor(0)
        R.servo(0)
        logf.flush()
        logf.close()
        R.shutdown()
        cam.close()
        print(f"log saved: {logpath}")


if __name__ == "__main__":
    main()
