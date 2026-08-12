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

# ---- tunables ----
CRUISE = 100           # max speed
FINISH_EXTRA_CYCLES = 60  # keep going a bit after the 12th quadrant, then stop
MAX_RUNTIME_S = 150     # SAFETY net only. 3 laps measured ~5s/quadrant = ~60s,
                        # so this is generous headroom, not a lap limit.
DEBUG = True            # print a status line every 15 cycles


def main():
    R.setup_hardware()
    R.servo(0)
    cam = R.open_camera()

    laps = R.LapTracker()
    follower = R.WallFollower()
    outer = R.OuterWallFollower()      # used when NAV_METHOD == "outer"
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

            if DEBUG and n % 15 == 0:
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
