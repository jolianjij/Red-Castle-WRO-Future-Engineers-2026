#!/usr/bin/env python3
"""
legacy_open.py - LAST YEAR'S Open Challenge code, ported to this year's hardware.

This is a faithful port of the team's 2025 OpenChallenge.py (itself a Python port
of KyivRoboMagic's C++). The CONTROL LOGIC AND ALL ITS CONSTANTS ARE UNCHANGED:

    ROI            bottom half of 480 rows, every 2nd pixel -> 120 x 320
    wall metric    pixels with value < 70, counted per half, divided by 160*80
    steering       CW : dir = (left_wall  - 0.5) * 75
                   CCW: dir = (0.5 - right_wall) * 75
    servo          angle += 60, clamped to +-55
    lines          blue 90<h<135 s>60 90<v<240 ; orange 15<=h<=45 s>30 60<v<240
                   threshold 1500 px, 10-cycle debounce
    laps           first line sets direction; count on the falling edge

WHAT IS DIFFERENT (hardware only):
  * pins            servo GPIO13, motor GPIO24/23   (was 17, 27/22)
  * no NeoPixel / no button
  * camera          our OV5647 via camera.py, so the WHITE BALANCE IS CORRECTED.
                    Last year's code assumed a colour-accurate image; ours had a
                    magenta cast until it was calibrated, which would have broken
                    the blue/orange line thresholds below.
  * no 180 rotation here - camera.py already flips in hardware
  * the per-pixel Python loops are vectorised with numpy (identical maths, but
    ~50x faster, so the control loop actually runs at camera rate)

Run:  cd ~/wro2026 && source .venv/bin/activate && python legacy_open.py
"""
import csv
import os
import sys
import time

import cv2
import numpy as np
import RPi.GPIO as GPIO

from camera import open_camera

# ---------------- hardware (THIS year's wiring) ----------------
SERVO_PIN = 13
MOTOR_IN1 = 24          # PWM here = forward
MOTOR_IN2 = 23
SERVO_HZ = 50
MOTOR_HZ = 1000

SERVO_CENTER_TRIM = 0.0
if os.path.exists("servo_center.txt"):
    try:
        SERVO_CENTER_TRIM = float(open("servo_center.txt").read().strip())
    except Exception:
        pass

# ---------------- last year's constants, untouched ----------------
LINE_CYCLE_DELAY = 10
BLUE_THRESHOLD = 1500
ORANGE_THRESHOLD = 1500
WALL_TARGET = 0.5           # their reference
WALL_GAIN = 75.0            # their gain
SERVO_CENTER = 60           # their servo() used angle += 60
SERVO_DEVIATION = 55        # and clamped +-55
STOP_AFTER_QUADRANT = 12    # their file had 2 for testing; a real run is 12
SPEED = 100                 # they ran motor(100)
MAX_RUNTIME_S = 150

servo_pwm = m1 = m2 = None


def setup_gpio():
    global servo_pwm, m1, m2
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for p in (SERVO_PIN, MOTOR_IN1, MOTOR_IN2):
        GPIO.setup(p, GPIO.OUT)
    servo_pwm = GPIO.PWM(SERVO_PIN, SERVO_HZ); servo_pwm.start(0)
    m1 = GPIO.PWM(MOTOR_IN1, MOTOR_HZ); m1.start(0)
    m2 = GPIO.PWM(MOTOR_IN2, MOTOR_HZ); m2.start(0)


def servo(angle):
    """Their mapping: angle += 60, clamp +-55, duty 2.5..12.5."""
    a = angle + SERVO_CENTER + SERVO_CENTER_TRIM
    lo, hi = SERVO_CENTER - SERVO_DEVIATION, SERVO_CENTER + SERVO_DEVIATION
    a = max(lo, min(hi, a))
    duty = 2.5 + (a / 180.0) * 10.0
    servo_pwm.ChangeDutyCycle(duty)


def motor(speed):
    speed = max(-100, min(100, speed))
    if speed > 0:
        m1.ChangeDutyCycle(speed); m2.ChangeDutyCycle(0)
    elif speed < 0:
        m1.ChangeDutyCycle(0); m2.ChangeDutyCycle(-speed)
    else:
        m1.ChangeDutyCycle(0); m2.ChangeDutyCycle(0)


# ---------------- vision (their maths, vectorised) ----------------
def process(frame_bgr):
    """Return (left_wall, right_wall, blue_px, orange_px) exactly as last year."""
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0].astype(np.int16)
    s = hsv[:, :, 1].astype(np.int16)
    v = hsv[:, :, 2].astype(np.int16)

    blue = np.count_nonzero((s > 60) & (v > 90) & (v < 240) & (h > 90) & (h < 135))
    orange = np.count_nonzero((s > 30) & (v > 60) & (v < 240) & (h >= 15) & (h <= 45))

    dark = v < 70
    left = int(np.count_nonzero(dark[:, :160])) / (160.0 * 80.0)
    right = int(np.count_nonzero(dark[:, 160:])) / (160.0 * 80.0)
    return left, right, int(blue), int(orange)


class LineState:
    """Their update_lines(): 0 absent, 1 present, 2 falling edge, 10-cycle guard."""

    def __init__(self):
        self.blue = self.orange = 0
        self._bd = self._od = False
        self._bn = self._on = 0

    def update(self, cycle, blue_px, orange_px):
        if blue_px > BLUE_THRESHOLD:
            self.blue = 1
            if cycle >= self._bn:
                self._bd = True
        else:
            self.blue = 0
            if self._bd:
                self.blue = 2
                self._bn = cycle + LINE_CYCLE_DELAY
            self._bd = False

        if orange_px > ORANGE_THRESHOLD:
            self.orange = 1
            if cycle >= self._on:
                self._od = True
        else:
            self.orange = 0
            if self._od:
                self.orange = 2
                self._on = cycle + LINE_CYCLE_DELAY
            self._od = False


def main():
    setup_gpio()
    servo(0)
    cam = open_camera()

    lines = LineState()
    direction = 0
    quadrant = 0
    cycle_count = 0

    os.makedirs("logs", exist_ok=True)
    path = time.strftime("logs/legacy_%Y%m%d_%H%M%S.csv")
    lf = open(path, "w", newline="")
    log = csv.writer(lf)
    log.writerow(["t_ms", "cycle", "dir", "quad", "left", "right",
                  "blue_px", "orange_px", "dir_cmd"])

    print("LEGACY (last year) open challenge - their logic, this year's hardware")
    print(f"  target={WALL_TARGET} gain={WALL_GAIN} servo center={SERVO_CENTER} "
          f"dev=+-{SERVO_DEVIATION} trim={SERVO_CENTER_TRIM}")
    print(f"  logging -> {path}")
    input("Press Enter to START...")

    t0 = time.time()
    motor(SPEED)
    reason = "?"
    try:
        while True:
            cycle_count += 1
            raw = cam.capture_array()                 # 640x480, already upright
            frame = raw[240:480:2, 0:640:2]           # their ROI -> 120x320
            left, right, blue_px, orange_px = process(frame)
            lines.update(cycle_count, blue_px, orange_px)

            if lines.blue != 0 and direction == 0:
                direction = -1
            if lines.orange != 0 and direction == 0:
                direction = 1

            if direction >= 0:
                if lines.orange == 2:
                    quadrant += 1
                    print(f"  quadrant {quadrant} (orange)")
            else:
                if lines.blue == 2:
                    quadrant += 1
                    print(f"  quadrant {quadrant} (blue)")

            if direction == 1:
                d = (left - WALL_TARGET) * WALL_GAIN
            elif direction == -1:
                d = (WALL_TARGET - right) * WALL_GAIN
            else:
                d = 0.0
                if left > WALL_TARGET:
                    d = (left - WALL_TARGET) * WALL_GAIN
                if right > WALL_TARGET:
                    d = (WALL_TARGET - right) * WALL_GAIN

            servo(d)
            t_ms = int((time.time() - t0) * 1000)
            log.writerow([t_ms, cycle_count, direction, quadrant,
                          f"{left:.4f}", f"{right:.4f}", blue_px, orange_px,
                          f"{d:.1f}"])

            if cycle_count % 20 == 0:
                lf.flush()
                print(f"  t={t_ms/1000:5.1f}s dir={direction:+d} q={quadrant:2d} "
                      f"L={left:.3f} R={right:.3f} blue={blue_px:5d} "
                      f"orange={orange_px:5d} dir_cmd={d:+6.1f}")

            if quadrant >= STOP_AFTER_QUADRANT:
                reason = "laps complete"
                break
            if time.time() - t0 > MAX_RUNTIME_S:
                reason = "timeout"
                break

        motor(0); servo(0)
        dt = time.time() - t0
        print(f"FINISHED ({reason}) quadrants={quadrant} cycles={cycle_count} "
              f"time={dt:.1f}s {1000*dt/max(cycle_count,1):.1f} ms/cycle")
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
        GPIO.cleanup()
        cam.close()
        print(f"log saved: {path}")


if __name__ == "__main__":
    main()
