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
CRUISE = 100            # base forward speed (%)                         (TUNE)
FINISH_EXTRA_CYCLES = 60  # keep going a bit after the 12th quadrant, then stop
MAX_RUNTIME_S = 60      # SAFETY: hard stop after this many seconds       (TUNE)
DEBUG = True            # print a status line every 15 cycles


def main():
    R.setup_hardware()
    R.servo(0)
    cam = R.open_camera()

    laps = R.LapTracker()
    follower = R.WallFollower()

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
            blue, orange = R.line_counts(hsv)
            laps.update(blue, orange, left, right)

            # single dispatch point - honours NAV_METHOD ("gap" or "density")
            steer, mode = R.navigate(hsv, left, right, laps, follower)
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

            # 3 laps done -> coast a moment then stop
            if laps.quadrant >= 12 and finish_at is None:
                finish_at = n + FINISH_EXTRA_CYCLES
            if finish_at is not None and n >= finish_at:
                reason = "3 laps complete"
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
