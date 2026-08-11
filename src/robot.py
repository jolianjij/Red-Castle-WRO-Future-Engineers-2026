#!/usr/bin/env python3
"""
robot.py - shared hardware + vision library for the WRO 2026 car.

Both open_challenge.py and obstacle_challenge.py import this so the pin map,
motor safety, camera settings and colour thresholds live in ONE place.

Runtime layout: keep robot.py, camera.py, colors.json (+ optional
servo_center.txt) all together in ~/wro2026 on the Pi.

Sign conventions (IMPORTANT):
  steering angle : 0 = straight, +right, -left   (clamped +-45)
  motor speed    : -100..100, + = forward
  wall metric    : left_wall / right_wall = fraction (0..1) of that half of the
                   ROI that is 'black' (a wall). Bigger = wall is closer.
"""
import json
import os
import time

import cv2
import numpy as np
import RPi.GPIO as GPIO

from camera import open_camera   # locked focus / exposure / AWB / 180 flip / full FOV

# ==========================================================================
# HARDWARE
# ==========================================================================
SERVO_PIN = 13
MOTOR_IN1 = 23          # PWM here = forward (IN2 low)
MOTOR_IN2 = 24          # PWM here = reverse (IN1 low)
SERVO_HZ = 50
MOTOR_HZ = 1000
STOP_FLIP_DELAY = 0.3   # s to coast before reversing (protect the regulator)
STEER_MAX = 8           # deg (max steering deviation; kept low - no differential, avoids wheel scrub)

# center trim: written by servo_center.py; 0 if not calibrated yet
SERVO_CENTER_TRIM = 0.0
if os.path.exists("servo_center.txt"):
    try:
        SERVO_CENTER_TRIM = float(open("servo_center.txt").read().strip())
    except Exception:
        pass

_servo_pwm = None
_m1 = None
_m2 = None
_last_dir = 0


def setup_hardware():
    global _servo_pwm, _m1, _m2
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for p in (SERVO_PIN, MOTOR_IN1, MOTOR_IN2):
        GPIO.setup(p, GPIO.OUT)
    _servo_pwm = GPIO.PWM(SERVO_PIN, SERVO_HZ); _servo_pwm.start(0)
    _m1 = GPIO.PWM(MOTOR_IN1, MOTOR_HZ); _m1.start(0)
    _m2 = GPIO.PWM(MOTOR_IN2, MOTOR_HZ); _m2.start(0)


def servo(angle):
    """0 = straight (after trim), + right, - left, clamped +-STEER_MAX."""
    angle = max(-STEER_MAX, min(STEER_MAX, angle))
    a = angle + SERVO_CENTER_TRIM + 90.0
    a = max(45.0, min(135.0, a))
    duty = 2.5 + (a / 180.0) * 10.0
    _servo_pwm.ChangeDutyCycle(duty)
    # note: we do NOT sleep here - the control loop runs continuously


def motor(speed):
    """-100..100. Never flips fwd<->rev directly (back-EMF kills the regulator)."""
    global _last_dir
    speed = max(-100, min(100, speed))
    new_dir = 1 if speed > 0 else (-1 if speed < 0 else 0)
    if new_dir != 0 and _last_dir != 0 and new_dir != _last_dir:
        _m1.ChangeDutyCycle(0); _m2.ChangeDutyCycle(0)
        time.sleep(STOP_FLIP_DELAY)
    mag = abs(speed)
    if speed > 0:
        _m1.ChangeDutyCycle(mag); _m2.ChangeDutyCycle(0)
    elif speed < 0:
        _m1.ChangeDutyCycle(0); _m2.ChangeDutyCycle(mag)
    else:
        _m1.ChangeDutyCycle(0); _m2.ChangeDutyCycle(0)
    if new_dir != 0:
        _last_dir = new_dir


def shutdown():
    try:
        motor(0); servo(0); time.sleep(0.1)
    finally:
        GPIO.cleanup()


# ==========================================================================
# VISION
# ==========================================================================
# Processing ROI: camera gives 640x480 (upright). We take the bottom part
# (the mat) and resize to a small buffer. PROC_H rows, PROC_W cols.
ROI_TOP = 160          # crop away the top (background clutter) - rows above this ignored
PROC_W, PROC_H = 320, 160

# fraction of a half-ROI that must be 'black' to call it wall-touching-close
WALL_TARGET = 0.14     # desired outer-wall fill when nicely centered   (TUNE)
WALL_EMERGENCY = 0.34  # wall this close -> hard steer away             (TUNE)

# line detection: a line is 'present' when its pixel fraction in the ROI exceeds
LINE_FRACTION = 0.055  # of the whole ROI                              (TUNE)
LINE_DEBOUNCE = 10     # cycles to wait before counting the same line again

# pillars
PILLAR_MIN_AREA = 120  # px in the PROC buffer                          (TUNE)
PILLAR_SIDE_MARGIN = 0.18   # red -> aim pillar to x=0.18W, green -> 0.82W

# parking gate (magenta)
PARK_STOP_AREA = 9000  # magenta contour area at which we are parked     (TUNE)

_K = np.ones((3, 3), np.uint8)

# ---- colours ----
_DEFAULT_COLORS = {
    "black":   [0, 179, 0, 255, 0, 70],
    "blue":    [90, 135, 60, 255, 70, 200],
    "orange":  [0, 30, 60, 255, 125, 240],
    "green":   [45, 90, 120, 255, 60, 240],
    "red":     [170, 10, 120, 255, 60, 240],
    "magenta": [130, 145, 177, 255, 93, 255],
}
if os.path.exists("colors.json"):
    COLORS = json.load(open("colors.json"))
    for k, v in _DEFAULT_COLORS.items():
        COLORS.setdefault(k, v)
else:
    COLORS = dict(_DEFAULT_COLORS)


def mask(hsv, name):
    lo_h, hi_h, lo_s, hi_s, lo_v, hi_v = COLORS[name]
    if lo_h <= hi_h:
        return cv2.inRange(hsv, (lo_h, lo_s, lo_v), (hi_h, hi_s, hi_v))
    m1 = cv2.inRange(hsv, (0, lo_s, lo_v), (hi_h, hi_s, hi_v))       # red wrap
    m2 = cv2.inRange(hsv, (lo_h, lo_s, lo_v), (179, hi_s, hi_v))
    return cv2.bitwise_or(m1, m2)


def read_hsv(cam):
    """Grab a frame, crop the mat ROI, return (proc_bgr, hsv)."""
    frame = cam.capture_array()              # 640x480 RGB888, upright
    roi = frame[ROI_TOP:480, :, :]
    proc = cv2.resize(roi, (PROC_W, PROC_H))
    hsv = cv2.cvtColor(proc, cv2.COLOR_BGR2HSV)
    return proc, hsv


def wall_readings(hsv):
    """Return (left_wall, right_wall) as black-fraction of each ROI half."""
    m = mask(hsv, "black")
    half = PROC_W // 2
    area = half * PROC_H
    left = int(np.count_nonzero(m[:, :half])) / area
    right = int(np.count_nonzero(m[:, half:])) / area
    return left, right


def line_counts(hsv):
    """Return (blue_fraction, orange_fraction) over the ROI."""
    area = PROC_W * PROC_H
    b = int(np.count_nonzero(mask(hsv, "blue"))) / area
    o = int(np.count_nonzero(mask(hsv, "orange"))) / area
    return b, o


def find_pillars(hsv):
    """Return the NEAREST valid pillar as (color, cx, cy_base, area) or None.
    Valid = area>=PILLAR_MIN_AREA and taller than wide. Nearest = lowest base."""
    best = None
    for color in ("red", "green"):
        m = mask(hsv, color)
        m = cv2.dilate(cv2.erode(m, _K), _K)
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in cnts:
            a = cv2.contourArea(c)
            if a < PILLAR_MIN_AREA:
                continue
            x, y, w, h = cv2.boundingRect(c)
            if h <= w:                       # keep vertical shapes only
                continue
            cx = x + w // 2
            cy_base = y + h                  # bottom of the pillar = closest point
            if best is None or cy_base > best[2]:
                best = (color, cx, cy_base, int(a))
    return best


def magenta_area(hsv):
    """Largest magenta (parking-gate) contour area, 0 if none."""
    m = mask(hsv, "magenta")
    m = cv2.dilate(cv2.erode(m, _K), _K)
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return 0, PROC_W // 2
    c = max(cnts, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(c)
    return int(cv2.contourArea(c)), x + w // 2


# ==========================================================================
# LINE / LAP TRACKING (hysteresis, faithful to the proven previous code)
# ==========================================================================
class LapTracker:
    """Sets driving direction from the first line seen and counts quadrants.
    direction:  +1 = orange first (clockwise),  -1 = blue first (ccw).
    12 quadrants = 3 laps."""

    def __init__(self):
        self.direction = 0
        self.quadrant = 0
        self.cycle = 0
        self._blue_det = False
        self._orange_det = False
        self._blue_next = 0
        self._orange_next = 0
        self.blue_state = 0     # 0 none, 1 present, 2 falling edge (just ended)
        self.orange_state = 0

    def _edge(self, present, detected, next_ok, state_attr):
        pass  # (inlined below for clarity)

    def update(self, blue_frac, orange_frac):
        self.cycle += 1

        # blue
        if blue_frac > LINE_FRACTION:
            self.blue_state = 1
            if self.cycle >= self._blue_next:
                self._blue_det = True
        else:
            self.blue_state = 0
            if self._blue_det:
                self.blue_state = 2
                self._blue_next = self.cycle + LINE_DEBOUNCE
            self._blue_det = False

        # orange
        if orange_frac > LINE_FRACTION:
            self.orange_state = 1
            if self.cycle >= self._orange_next:
                self._orange_det = True
        else:
            self.orange_state = 0
            if self._orange_det:
                self.orange_state = 2
                self._orange_next = self.cycle + LINE_DEBOUNCE
            self._orange_det = False

        # first line sets direction
        if self.direction == 0:
            if self.orange_state != 0:
                self.direction = 1
            elif self.blue_state != 0:
                self.direction = -1

        # count a quadrant on the driving-direction line's falling edge
        if self.direction >= 0 and self.orange_state == 2:
            self.quadrant += 1
        elif self.direction < 0 and self.blue_state == 2:
            self.quadrant += 1


# ==========================================================================
# STEERING
# ==========================================================================
class WallFollower:
    """PD wall-following that keeps the car CENTERED between the two side walls.
       error = left_wall - right_wall  (>0 => left wall closer => steer right).
       Centering keeps it off BOTH walls (fixes the inner-wall hugging).
       Hard-steers away if either wall gets dangerously close."""

    def __init__(self, kp=60.0, kd=25.0):
        self.kp = kp
        self.kd = kd
        self._prev = 0.0

    def steer(self, left, right, direction=0):
        # emergency: whichever wall is very close wins
        if left > WALL_EMERGENCY:
            self._prev = 0.0
            return STEER_MAX            # left close -> hard right
        if right > WALL_EMERGENCY:
            self._prev = 0.0
            return -STEER_MAX           # right close -> hard left

        err = left - right              # center between the two side walls
        out = self.kp * err + self.kd * (err - self._prev)
        self._prev = err
        return max(-STEER_MAX, min(STEER_MAX, out))


def pillar_steer(color, cx, cy_base, kp=90.0):
    """Steer to pass red on the right / green on the left.
       red  -> push pillar toward the LEFT edge  (car goes right)
       green-> push pillar toward the RIGHT edge (car goes left)."""
    if color == "red":
        target_x = PILLAR_SIDE_MARGIN * PROC_W
    else:
        target_x = (1.0 - PILLAR_SIDE_MARGIN) * PROC_W
    err = (cx - target_x) / PROC_W            # >0 -> steer right
    prox = cy_base / PROC_H                    # closer pillar -> stronger reaction
    out = kp * err * (0.4 + 0.6 * prox)
    return max(-STEER_MAX, min(STEER_MAX, out))


def cruise_speed(base, steer):
    """Slow down in proportion to steering effort (fast on straights)."""
    return base * (1.0 - 0.5 * min(1.0, abs(steer) / STEER_MAX))
