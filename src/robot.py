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

from camera import open_camera   # locked exposure / AWB / 180 flip / full FOV
from config import *             # ALL tunable numbers live in config.py

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
    if INVERT_STEERING:
        angle = -angle
    angle = max(-STEER_MAX, min(STEER_MAX, angle))
    a = angle + SERVO_CENTER_TRIM + 90.0
    a = max(45.0, min(135.0, a))
    duty = SERVO_MIN_DUTY + (a / 180.0) * (SERVO_MAX_DUTY - SERVO_MIN_DUTY)
    _servo_pwm.ChangeDutyCycle(duty)
    # note: we do NOT sleep here - the control loop runs continuously


def motor(speed):
    """-100..100. Never flips fwd<->rev directly (back-EMF kills the regulator)."""
    global _last_dir
    if INVERT_MOTOR:
        speed = -speed
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
    """Stop everything cleanly.

    The PWM objects must be stopped and dropped BEFORE GPIO.cleanup(); otherwise
    rpi-lgpio garbage-collects them afterwards and PWM.__del__ throws
    'unsupported operand type(s) for &: NoneType and int'. Harmless, but noisy.
    """
    global _servo_pwm, _m1, _m2
    try:
        motor(0); servo(0); time.sleep(0.1)
        for p in (_m1, _m2, _servo_pwm):
            if p is not None:
                try:
                    p.stop()
                except Exception:
                    pass
        _servo_pwm = _m1 = _m2 = None
    finally:
        GPIO.cleanup()


# ==========================================================================
# VISION   (all thresholds come from config.py)
# ==========================================================================
_K = np.ones((3, 3), np.uint8)

# ---- colours ----
_DEFAULT_COLORS = {
    "black":   [0, 179, 0, 255, 0, 70],
    "blue":    [90, 135, 60, 255, 70, 200],
    "orange":  [3, 22, 50, 165, 70, 255],   # MEASURED hue~5-8, S~90.  S ceiling
                                            # 165 is what keeps red out of orange.
    "green":   [45, 90, 120, 255, 60, 240],
    "red":     [170, 5, 150, 255, 60, 255], # MEASURED hue~178, S~252. High S
                                            # floor separates it from the line.
    "magenta": [130, 145, 177, 255, 93, 255],
}
if os.path.exists("colors.json"):
    COLORS = json.load(open("colors.json"))
    for k, v in _DEFAULT_COLORS.items():
        COLORS.setdefault(k, v)
else:
    COLORS = dict(_DEFAULT_COLORS)


def mask(hsv, name, clean=True):
    """Binary mask for a tuned colour. clean=True removes speckle (open) and
    fills small holes (close) - this is what makes far/blurry objects survive."""
    lo_h, hi_h, lo_s, hi_s, lo_v, hi_v = COLORS[name]
    if lo_h <= hi_h:
        m = cv2.inRange(hsv, (lo_h, lo_s, lo_v), (hi_h, hi_s, hi_v))
    else:                                                            # red wrap
        m1 = cv2.inRange(hsv, (0, lo_s, lo_v), (hi_h, hi_s, hi_v))
        m2 = cv2.inRange(hsv, (lo_h, lo_s, lo_v), (179, hi_s, hi_v))
        m = cv2.bitwise_or(m1, m2)
    if clean:
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, _K)    # kill isolated noise px
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, _K)   # reconnect broken blobs
    return m


def read_hsv(cam):
    """Grab a frame, crop the mat ROI, return (proc_bgr, hsv).
    A median blur is applied first - the short exposure + high gain makes the
    image noisy, and noise breaks both the colour masks and the wall scan."""
    frame = cam.capture_array()              # 640x480 RGB888, upright
    roi = frame[ROI_TOP:CAM_H, :, :]
    proc = cv2.resize(roi, (PROC_W, PROC_H))
    if BLUR_KSIZE and BLUR_KSIZE > 1:
        proc = cv2.medianBlur(proc, BLUR_KSIZE)
    hsv = cv2.cvtColor(proc, cv2.COLOR_BGR2HSV)
    return proc, hsv


# --------------------------------------------------------------------------
# FREE-SPACE / FOLLOW-THE-GAP  (method "B")
# --------------------------------------------------------------------------
def wall_base_rows(hsv, min_run=None):
    """For every column, the image row where the mat meets the wall.

    Scans each column from the BOTTOM up and returns the lowest row that starts
    a run of >= min_run consecutive wall pixels. Requiring a RUN is what stops
    the mat's dotted lines / printed marks being mistaken for a wall.
    Returns 0 for a column with no wall at all (open to the horizon).
    """
    if min_run is None:
        min_run = FREE_MIN_RUN
    m = mask(hsv, "black") > 0
    H, W = m.shape
    cs = np.cumsum(m.astype(np.int32), axis=0)
    win = np.zeros((H, W), dtype=np.int32)
    # win[y] = number of wall pixels in rows (y-min_run+1 .. y)
    win[min_run - 1:] = cs[min_run - 1:] - np.vstack(
        [np.zeros((1, W), np.int32), cs[:H - min_run]])
    full = win >= min_run
    has = full.any(axis=0)
    # lowest (largest y) row that completes a full run = the wall's base edge
    ys = np.where(has, H - 1 - np.argmax(full[::-1], axis=0), 0)
    return ys.astype(np.int32)


def freespace_profile(hsv, min_run=None):
    """free[x] in 0..PROC_H. BIG = open road ahead in that direction,
    SMALL = a wall is close. This is the camera's 'pseudo-LiDAR' scan."""
    base = wall_base_rows(hsv, min_run)
    free = (PROC_H - base).astype(np.float32)
    if FREE_SMOOTH > 1:
        k = np.ones(FREE_SMOOTH, np.float32) / FREE_SMOOTH
        free = np.convolve(free, k, mode="same")
    return free


def find_gap(free):
    """Widest contiguous run of 'open' columns.
    Returns (center_x, width, best_free) or None if nothing is drivable."""
    thr = GAP_OPEN_FRAC * PROC_H
    lo, hi = FREE_EDGE_IGNORE, len(free) - FREE_EDGE_IGNORE
    open_cols = free >= thr
    best_len, best_start, start = 0, 0, None
    for x in range(lo, hi):
        if open_cols[x]:
            if start is None:
                start = x
        elif start is not None:
            if x - start > best_len:
                best_len, best_start = x - start, start
            start = None
    if start is not None and hi - start > best_len:
        best_len, best_start = hi - start, start
    if best_len < GAP_MIN_WIDTH:
        return None
    return best_start + best_len / 2.0, best_len, float(free[lo:hi].max())


def gap_steer(center_x):
    """Steer toward the centre of the widest gap."""
    err = (center_x - PROC_W / 2.0) / (PROC_W / 2.0)     # -1 .. +1
    return max(-STEER_MAX, min(STEER_MAX, GAP_KP * err))


def wall_readings(hsv):
    """Return (left_wall, right_wall) as black-fraction of each ROI half."""
    m = mask(hsv, "black")
    half = PROC_W // 2
    area = half * PROC_H
    left = int(np.count_nonzero(m[:, :half])) / area
    right = int(np.count_nonzero(m[:, half:])) / area
    return left, right


def front_reading(hsv):
    """Black fill fraction straight AHEAD (centre columns, upper rows).
    High = a wall is close in front = we are at a corner."""
    m = mask(hsv, "black")
    c0 = int(PROC_W * (1 - FRONT_COLS) / 2)
    c1 = PROC_W - c0
    r1 = int(PROC_H * FRONT_ROWS)
    band = m[:r1, c0:c1]
    return int(np.count_nonzero(band)) / max(1, band.size)


def line_counts(hsv):
    """Return (blue_fraction, orange_fraction) in the LINE BAND only.

    The band is the bottom LINE_ROWS of the ROI - the mat. Corner lines are
    painted on the mat, so a line cannot appear above it; anything blue/orange
    higher up is wall or background and must not be able to trigger a lap count.
    """
    r0 = int(PROC_H * (1.0 - LINE_ROWS))
    band = hsv[r0:, :, :]
    area = band.shape[0] * band.shape[1]
    b = int(np.count_nonzero(mask(band, "blue"))) / area
    o = int(np.count_nonzero(mask(band, "orange"))) / area
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
    """Counts corners (quadrants) from WALL GEOMETRY - no colour needed.

    Why: the coloured corner lines proved unreliable on this camera (orange never
    detected, blue peaked below threshold), so direction/laps never worked. A
    corner is instead detected when a wall appears AHEAD (left+right dark fraction
    both high) - that happens once per corner, 12 corners = 3 laps.

    Turn direction is decided at the FIRST corner by which side has more free
    space, then LOCKED for the whole run (the track never changes direction), so
    the car can't flip direction mid-run.

    Colour lines are still tracked (if tuned) purely as a cross-check.
    """

    def __init__(self):
        self.direction = FORCE_DIRECTION   # 0 = auto-detect, else forced in config
        self.quadrant = 0
        self.cycle = 0
        self.in_corner = False
        self.front = 0.0
        self._next_ok = 0
        # TIME-based guards (frame-rate independent - the reliable ones)
        self._last_count_t = 0.0           # lap timer reference
        self.last_gap_s = 0.0              # seconds between the last two corners
        # colour line edge detection
        self.blue_state = 0
        self.orange_state = 0
        self._blue_det = False
        self._orange_det = False
        self._blue_next_t = 0.0    # wall-clock lockout, NOT cycles
        self._orange_next_t = 0.0
        # ---- SENSOR FUSION bookkeeping (visible in the log) ----
        self.direction_source = "none"     # what locked the direction
        self.direction_confirmed = False   # geometry AND lines agreed
        self.corner_source = ""            # "geom", "line", or "geom+line"
        self.line_hint = 0                 # what the colour lines say  (+1/-1/0)
        self.geom_hint = 0                 # what the wall geometry says (+1/-1/0)
        self.disagreements = 0             # times the two signals conflicted
        self.corners_geom = 0              # corners first seen by geometry
        self.corners_line = 0              # corners first seen by a line
        self.blue_reads = 0                # times the blue line was READ (locked)
        self.orange_reads = 0              # times the orange line was READ

    def _line_edges(self, blue_frac, orange_frac):
        """Turn a noisy colour fraction into ONE reading per physical crossing.

        state 0 = absent, 1 = present, 2 = falling edge (the crossing is over).
        After a falling edge the colour is LOCKED OUT for LINE_LOCKOUT_S seconds,
        so a mask that flickers above/below threshold can only ever be read once
        per crossing. The lockout is in SECONDS so it does not change with frame
        rate.
        """
        now = time.monotonic()

        # ---- blue ----
        if blue_frac > LINE_FRACTION:
            self.blue_state = 1
            if now >= self._blue_next_t:      # not locked out -> arm it
                self._blue_det = True
        else:
            self.blue_state = 0
            if self._blue_det:                # armed and now gone = one crossing
                self.blue_state = 2
                self._blue_next_t = now + LINE_LOCKOUT_S
                self.blue_reads += 1
            self._blue_det = False

        # ---- orange ----
        if orange_frac > LINE_FRACTION:
            self.orange_state = 1
            if now >= self._orange_next_t:
                self._orange_det = True
        else:
            self.orange_state = 0
            if self._orange_det:
                self.orange_state = 2
                self._orange_next_t = now + LINE_LOCKOUT_S
                self.orange_reads += 1
            self._orange_det = False

    def update(self, blue_frac, orange_frac, left=0.0, right=0.0, front=None):
        """One frame of lap logic.

        PHASE 1 - direction (happens once, at the FIRST line seen):
            decided by the BIGGER line (orange = CW, blue = CCW) with the wall
            geometry as a second opinion. Once set it is FIXED for the whole run.

        PHASE 2 - lap counting (only after the direction is known):
            a quadrant needs BOTH
              (a) a line crossing (blue OR orange), and
              (b) the lap timer to have expired.
            Counting restarts the timer, so one crossing can only ever add one.

        Corner detection for STEERING is separate and comes from wall geometry,
        because the car must turn whether or not a line is visible.
        """
        self.cycle += 1
        self._line_edges(blue_frac, orange_frac)
        self.front = front if front is not None else (left + right)
        now = time.monotonic()

        # ---------------- PHASE 1: fix the direction, once ----------------
        if self.direction == 0:
            line_seen = (blue_frac > LINE_FRACTION) or (orange_frac > LINE_FRACTION)
            if line_seen:
                # condition 1 - the BIGGER line wins
                bigger = 1 if orange_frac > blue_frac else -1      # +1 CW, -1 CCW
                self.line_hint = bigger
                # condition 2 - wall geometry, only when one side is clearly open
                if abs(left - right) >= GEOM_DIR_MIN_DIFF:
                    self.geom_hint = -1 if left < right else 1
                self._lock_direction(bigger, "bigger line "
                                     f"({'orange' if bigger > 0 else 'blue'} "
                                     f"{max(blue_frac, orange_frac):.3f})")
                if self.geom_hint:
                    if self.geom_hint == self.direction:
                        self.direction_confirmed = True
                        print("[lap] direction CONFIRMED by wall geometry")
                    else:
                        self.disagreements += 1
                        print("[lap] NOTE: geometry suggested the opposite; "
                              "keeping the line decision")
                # the lap timer starts running from the moment direction is fixed
                self._last_count_t = now

        # ---------------- corner detection for STEERING (geometry) ----------
        if front is not None:
            enter, exit_ = FRONT_ENTER, FRONT_EXIT
        else:
            enter, exit_ = CORNER_TOTAL, CORNER_TOTAL * 0.75
        if not self.in_corner:
            if self.front > enter:
                self.in_corner = True
        elif self.front < exit_:
            self.in_corner = False

        # ---------------- PHASE 2: count laps from the LINES + timer --------
        if self.direction != 0:
            crossed = (self.blue_state == 2) or (self.orange_state == 2)
            elapsed = now - self._last_count_t
            if crossed and elapsed >= LAP_COUNT_LOCKOUT_S:
                self.quadrant += 1
                self.corners_line += 1
                self.corner_source = "line"
                self.last_gap_s = elapsed
                self._last_count_t = now          # <-- timer RESTARTS here
                which = "orange" if self.orange_state == 2 else "blue"
                print(f"[lap] quadrant {self.quadrant}/{QUADRANTS_PER_RUN} "
                      f"on {which} line (+{elapsed:.1f}s)")
            elif crossed:
                print(f"[lap] line crossing IGNORED - timer has "
                      f"{LAP_COUNT_LOCKOUT_S - elapsed:.1f}s left")

    def _lock_direction(self, d, why):
        """Direction is decided ONCE and never changes - this is what stops the
        car flipping from counter-clockwise to clockwise mid-run."""
        if self.direction == 0 and d != 0:
            self.direction = d
            self.direction_source = why
            print(f"[lap] direction locked {'CW' if d > 0 else 'CCW'} ({why})")

    def summary(self):
        """One-line fusion report for the end of a run."""
        return (f"direction={'CW' if self.direction > 0 else 'CCW' if self.direction else '?'}"
                f" via {self.direction_source}"
                f"{' (CONFIRMED by both)' if self.direction_confirmed else ''}"
                f" | corners={self.quadrant} (geom {self.corners_geom}, line {self.corners_line})"
                f" | line reads: blue={self.blue_reads} orange={self.orange_reads}"
                f" | disagreements={self.disagreements}")

    def ready_to_finish(self):
        """True once STOP_AFTER_QUADRANT quadrants are counted AND the lap timer
        has run out - i.e. the car has driven on past the last counted line."""
        if self.quadrant < STOP_AFTER_QUADRANT:
            return False
        return (time.monotonic() - self._last_count_t) >= LAP_COUNT_LOCKOUT_S

    def stalled(self):
        """True if no quadrant has been counted for suspiciously long."""
        if not self._last_count_t:
            return False
        return (time.monotonic() - self._last_count_t) > CORNER_MAX_INTERVAL_S

    def turn_bias(self):
        """Steering bias to apply while inside a corner (deg)."""
        return self.direction * STEER_MAX


# ==========================================================================
# STEERING
# ==========================================================================
class WallFollower:
    """PD wall-following that keeps the car CENTERED between the two side walls.
       error = left_wall - right_wall  (>0 => left wall closer => steer right).
       Centering keeps it off BOTH walls (fixes the inner-wall hugging).
       Hard-steers away if either wall gets dangerously close."""

    def __init__(self, kp=45.0, kd=18.0):
        self.kp = kp
        self.kd = kd
        self._prev = 0.0
        self._out = 0.0             # previous output, for slew limiting

    def steer(self, left, right, direction=0):
        err = left - right          # >0 => left wall closer => steer right

        # deadband: ignore tiny imbalances so the car runs straight instead of
        # twitching left/right (this was the main cause of the jittery, risky run)
        if abs(err) < CENTER_DEADBAND:
            err = 0.0

        out = self.kp * err + self.kd * (err - self._prev)
        self._prev = err

        # emergency is PROPORTIONAL, not instant full lock: the closer the wall,
        # the stronger the push away - blended on top of the PD output
        if left > WALL_EMERGENCY:
            out += STEER_MAX * min(1.0, (left - WALL_EMERGENCY) / 0.15)
        if right > WALL_EMERGENCY:
            out -= STEER_MAX * min(1.0, (right - WALL_EMERGENCY) / 0.15)

        out = max(-STEER_MAX, min(STEER_MAX, out))

        # slew limit: no instant lock-to-lock snaps (protects the servo + traction)
        max_step = STEER_MAX * 0.35
        out = max(self._out - max_step, min(self._out + max_step, out))
        self._out = out
        return out


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
    return max(MIN_SPEED, base * (1.0 - SPEED_CORNER_CUT * min(1.0, abs(steer) / STEER_MAX)))


# --------------------------------------------------------------------------
# NAVIGATION DISPATCH
# One place decides how the car steers, so both challenges behave identically
# and NAV_METHOD in config.py actually switches the strategy.
# --------------------------------------------------------------------------
def _apply_bias(steer):
    """Add the drift trim and re-clamp. Applied to every driving command."""
    return max(-STEER_MAX, min(STEER_MAX, steer + STEER_BIAS))


def navigate(hsv, left, right, laps, follower):
    """Return (steer_deg, mode_string) for this frame.

    Priority:
      1. in a corner        -> commit to the locked turn direction
      2. NAV_METHOD == gap  -> follow-the-gap on the free-space profile
                               (falls back to the density controller if the way
                               ahead is blocked or no gap is drivable)
      3. otherwise          -> PD wall-density controller (proven fallback)
    """
    # ---- PRIORITY 1: WALL EMERGENCY - applies in EVERY mode, no exceptions ----
    # This used to live only inside the density controller, so in "gap" mode the
    # car had NO wall avoidance at all and drove along touching the inner wall.
    if left > WALL_EMERGENCY or right > WALL_EMERGENCY:
        push = 0.0
        if left > WALL_EMERGENCY:
            push += STEER_MAX * min(1.0, (left - WALL_EMERGENCY) / 0.12)
        if right > WALL_EMERGENCY:
            push -= STEER_MAX * min(1.0, (right - WALL_EMERGENCY) / 0.12)
        return _apply_bias(push), "emergency"

    if laps.in_corner:
        bias = laps.turn_bias()
        if bias == 0.0:
            # direction is not fixed yet (no line crossed). Do NOT go straight
            # into the wall - turn toward whichever side has more free space.
            bias = STEER_MAX * (-1.0 if left < right else 1.0)
            return _apply_bias(bias), "corner-nodir"
        return _apply_bias(bias), "corner"

    if NAV_METHOD == "gap":
        free = freespace_profile(hsv)
        gap = find_gap(free)
        if gap is not None and free.max() >= GAP_BLOCKED_FRAC * PROC_H:
            cx, width, best = gap
            return _apply_bias(gap_steer(cx)), "gap"
        # blocked or nothing drivable -> commit to the known turn direction
        if laps.direction != 0:
            return _apply_bias(laps.turn_bias()), "blocked"
        return _apply_bias(follower.steer(left, right, laps.direction)), "blocked-nodir"

    return _apply_bias(follower.steer(left, right, laps.direction)), "wall"
