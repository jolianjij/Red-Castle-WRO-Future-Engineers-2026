#!/usr/bin/env python3
"""
pure_open.py - the single-wall control law and NOTHING else. A diagnostic build.

No emergency override. No gap follower. No turn sequencer. No lap counting.
No steering trim. Just the one control law, so we can see whether it works:

    CW  : steer = (left_wall  - TARGET) * GAIN
    CCW : steer = (TARGET - right_wall) * GAIN

Corners are handled IMPLICITLY, with no dedicated corner code at all: approaching
a corner, the wall ahead raises the outer-wall density, which drives the steering
into the turn - and the sign comes out right in both directions.

It saves an annotated frame whenever the steering exceeds SAVE_ANGLE, so we can
look at exactly what the camera saw at the moments that matter.

Run:  cd ~/wro2026 && source .venv/bin/activate && python pure_open.py
"""
import csv
import os
import time

import cv2
import numpy as np
import RPi.GPIO as GPIO

from camera import open_camera

# ---------------- hardware ----------------
SERVO_PIN, MOTOR_IN1, MOTOR_IN2 = 13, 24, 23
SERVO_HZ, MOTOR_HZ = 50, 1000

# ---------------- the only tunables that matter ----------------
DIRECTION = 1        # +1 = CW (follow LEFT wall), -1 = CCW (follow RIGHT wall)
TARGET = 0.150       # desired outer-wall density. MEASURED REFERENCE POINTS:
                     #   0.114 = centred in the corridor (~45 cm from each wall)
                     #   0.150 = ~39 cm from the outer wall   <-- default
                     #   0.204 = ~29 cm  (too close: leaves only ~13 cm before
                     #                    the walls fill the frame)
GAIN = 160.0         # deg per unit density (slope is 0.00575 density/cm, so
                     # 160 gives ~9.2 deg for 10 cm of error)
STEER_LIMIT = 20     # deg
SPEED = 45           # % - slow for diagnosis; raise once the law is proven
RUN_SECONDS = 25

SAVE_ANGLE = 12      # save a frame whenever |steer| exceeds this
SAVE_EVERY = 40      # ...and one routine frame every N cycles anyway
MAX_SAVES = 40

SERVO_TRIM = 0.0
if os.path.exists("servo_center.txt"):
    try:
        SERVO_TRIM = float(open("servo_center.txt").read().strip())
    except Exception:
        pass

servo_pwm = m1 = m2 = None


def setup():
    global servo_pwm, m1, m2
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for p in (SERVO_PIN, MOTOR_IN1, MOTOR_IN2):
        GPIO.setup(p, GPIO.OUT)
    servo_pwm = GPIO.PWM(SERVO_PIN, SERVO_HZ); servo_pwm.start(0)
    m1 = GPIO.PWM(MOTOR_IN1, MOTOR_HZ); m1.start(0)
    m2 = GPIO.PWM(MOTOR_IN2, MOTOR_HZ); m2.start(0)


def servo(angle):
    a = max(-STEER_LIMIT, min(STEER_LIMIT, angle)) + SERVO_TRIM + 90.0
    a = max(45.0, min(135.0, a))
    servo_pwm.ChangeDutyCycle(2.5 + (a / 180.0) * 10.0)


def motor(sp):
    sp = max(0, min(100, sp))
    m1.ChangeDutyCycle(sp); m2.ChangeDutyCycle(0)


def walls(hsv):
    """left, right = fraction of each half that is dark (a wall)."""
    dark = hsv[:, :, 2] < 70
    h = dark.shape[1] // 2
    area = float(h * dark.shape[0])
    return int(np.count_nonzero(dark[:, :h])) / area, \
           int(np.count_nonzero(dark[:, h:])) / area


def main():
    setup(); servo(0)
    cam = open_camera()
    os.makedirs("frames", exist_ok=True)
    for f in os.listdir("frames"):
        os.remove(os.path.join("frames", f))

    path = time.strftime("logs/pure_%Y%m%d_%H%M%S.csv")
    os.makedirs("logs", exist_ok=True)
    lf = open(path, "w", newline=""); log = csv.writer(lf)
    log.writerow(["t_ms", "cycle", "left", "right", "err", "steer", "frame"])

    side = "LEFT" if DIRECTION > 0 else "RIGHT"
    print(f"PURE {'CW' if DIRECTION>0 else 'CCW'}  - follow the {side} wall")
    print(f"  TARGET={TARGET}  GAIN={GAIN}  LIMIT=+-{STEER_LIMIT}  SPEED={SPEED}%")
    print(f"  trim={SERVO_TRIM}   log={path}   frames -> frames/")
    input("Press Enter to START...")

    t0 = time.time(); n = 0; saves = 0
    try:
        motor(SPEED)
        while time.time() - t0 < RUN_SECONDS:
            n += 1
            frame = cam.capture_array()
            roi = frame[160:480, :, :]
            proc = cv2.resize(roi, (320, 160))
            hsv = cv2.cvtColor(proc, cv2.COLOR_BGR2HSV)
            l, r = walls(hsv)

            err = (l - TARGET) if DIRECTION > 0 else (TARGET - r)
            steer = max(-STEER_LIMIT, min(STEER_LIMIT, err * GAIN))
            servo(steer)

            t_ms = int((time.time() - t0) * 1000)
            name = ""
            if saves < MAX_SAVES and (abs(steer) >= SAVE_ANGLE or n % SAVE_EVERY == 0):
                name = f"frames/{n:05d}_s{steer:+05.1f}_L{l:.3f}_R{r:.3f}.png"
                vis = proc.copy()
                vis[hsv[:, :, 2] < 70] = (0, 0, 255)          # red = counted as wall
                cv2.line(vis, (160, 0), (160, 160), (0, 255, 255), 1)
                cv2.putText(vis, f"L{l:.3f} R{r:.3f} s{steer:+.1f}", (4, 12),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 255), 1)
                cv2.imwrite(name, np.vstack([proc, vis]))
                saves += 1
            log.writerow([t_ms, n, f"{l:.4f}", f"{r:.4f}", f"{err:+.4f}",
                          f"{steer:+.1f}", name])
            if n % 15 == 0:
                lf.flush()
                print(f"  t={t_ms/1000:5.1f}s L={l:.3f} R={r:.3f} "
                      f"err={err:+.4f} steer={steer:+6.1f}")
        print("run complete")
    except KeyboardInterrupt:
        print("interrupted")
    finally:
        motor(0); servo(0)
        lf.flush(); lf.close()
        for p in (m1, m2, servo_pwm):
            try:
                p.stop()
            except Exception:
                pass
        GPIO.cleanup(); cam.close()
        print(f"log: {path}   frames saved: {saves}")


if __name__ == "__main__":
    main()
