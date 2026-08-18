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
import collections
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
    GPIO.setup(BUTTON_PIN, GPIO.IN,
               pull_up_down=GPIO.PUD_UP if BUTTON_PULL_UP else GPIO.PUD_DOWN)
    _servo_pwm = GPIO.PWM(SERVO_PIN, SERVO_HZ); _servo_pwm.start(0)
    _m1 = GPIO.PWM(MOTOR_IN1, MOTOR_HZ); _m1.start(0)
    _m2 = GPIO.PWM(MOTOR_IN2, MOTOR_HZ); _m2.start(0)


class Button:
    """The one push button on BUTTON_PIN: starts the run, then stops it.

    Two jobs, one button:
        wait_for_start()  blocks until you press AND release. Nothing moves
                          before this returns, which is what the rules want.
        stop_pressed()    poll once per loop. True on a NEW press -> stop.

    Both are EDGE triggered (they react to the moment of pressing, not to the
    button being held), and debounced, so one physical press is one event. A
    hold-off after the start press means letting go of it cannot be mistaken
    for the stop press.
    """

    def __init__(self):
        self._last_raw = self.is_down()
        self._stable = self._last_raw
        self._was_down = self._last_raw
        self._changed_t = 0.0
        self._ignore_until = 0.0

    def is_down(self):
        """True while the button is physically held."""
        level = GPIO.input(BUTTON_PIN)
        return (level == 0) if BUTTON_PULL_UP else (level == 1)

    def _debounced(self):
        """The button state, ignoring contact bounce."""
        now = time.monotonic()
        raw = self.is_down()
        if raw != self._last_raw:
            self._last_raw = raw
            self._changed_t = now
        elif (now - self._changed_t) >= BUTTON_DEBOUNCE_S:
            self._stable = raw
        return self._stable

    def wait_for_start(self, what="run"):
        """Block until pressed and released. Falls back to Enter if the button
        is disabled in config (BUTTON_REQUIRED = False)."""
        if not BUTTON_REQUIRED:
            input(f"{what} ready (button disabled). Press Enter to START...")
            return
        if self.is_down():
            print("  ! button reads PRESSED before you touched it - check "
                  "BUTTON_PULL_UP in config.py (tools/button_test.py helps)")
        print(f"{what} ready. PRESS THE BUTTON to start "
              f"(press again at any time to stop)...")
        while not self._debounced():          # wait for the press
            time.sleep(0.01)
        while self._debounced():              # ...and for the release
            time.sleep(0.01)
        self._ignore_until = time.monotonic() + BUTTON_HOLDOFF_S
        print("  GO")

    def stop_pressed(self):
        """True ONCE, on a new press. Poll this every loop for the e-stop."""
        if not BUTTON_REQUIRED:
            return False
        down = self._debounced()
        was, self._was_down = self._was_down, down
        if time.monotonic() < self._ignore_until:
            return False          # still letting go of the START press
        return down and not was   # the rising edge is the stop


def servo(angle, limit=None):
    """0 = straight (after trim), + right, - left.

    Clamped to STEER_MAX by default. `limit` raises that ceiling for ONE call,
    up to the linkage's real mechanical limit (STEER_MECH_MAX) - used by the
    corner kick, which deliberately asks for more lock than normal driving.
    """
    if INVERT_STEERING:
        angle = -angle
    lim = STEER_MAX if limit is None else min(abs(limit), STEER_MECH_MAX)
    angle = max(-lim, min(lim, angle))
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
_esc = {"dir": 0}   # latched escape direction for emergency-both

# ---- colours ----
_DEFAULT_COLORS = {
    "black":   [0, 179, 0, 255, 0, 70],
    "blue":    [90, 135, 60, 255, 70, 200],
    "orange":  [2, 13, 72, 170, 70, 255],   # MEASURED: the LINE is H5-8 S86-94,
                                            # but the MAT ITSELF is H17-19 S42-53
                                            # (a warm cream). H<=13 and S>=72 are
                                            # what separate the line from the mat;
                                            # S<=170 keeps the red pillar out.
    "green":   [60, 95, 140, 255, 30, 170], # MEASURED H81-86 S152. The floor is 60,
                                            # not 30: the RED pillar's fringe reaches
                                            # H=30, and a 30 floor matched 74 px of it
                                            # as "green" - enough to pass MIN_AREA.
    "red":     [178, 12, 170, 255, 45, 255], # MEASURED. The wrap starts at 178,
                                            # ABOVE the magenta parking wall which
                                            # sits at H171-177: at 174 red claimed a
                                            # 119x20 slab of that WALL as a "sign".
    "magenta": [158, 177, 90, 255, 40, 255],# MEASURED on the PARKING WALL up close,
                                            # not the block at distance: S165-229,
                                            # V47-85. The old S<=168 / V>=90 excluded
                                            # the whole shadowed body and matched only
                                            # its lit top edge - 290 px instead of 29k.
}
if os.path.exists("colors.json"):
    COLORS = json.load(open("colors.json"))
    for k, v in _DEFAULT_COLORS.items():
        COLORS.setdefault(k, v)
else:
    COLORS = dict(_DEFAULT_COLORS)

# ---- the WALL DETECTOR's own thresholds ----
# NOTE: the wall detector does NOT use COLORS["black"] - it uses the three
# numbers below (see wall_mask). COLORS["black"] survives only for the
# shadow_check diagnostic. Tuning "black" therefore does NOT retune the walls;
# tools/tune_walls.py does, by writing wall_settings.json here.
if os.path.exists("wall_settings.json"):
    _ws = json.load(open("wall_settings.json"))
    WALL_V_HARD = int(_ws.get("WALL_V_HARD", WALL_V_HARD))
    WALL_V_SOFT = int(_ws.get("WALL_V_SOFT", WALL_V_SOFT))
    WALL_S_MAX = int(_ws.get("WALL_S_MAX", WALL_S_MAX))
    print(f"[wall] wall_settings.json: V_HARD={WALL_V_HARD} "
          f"V_SOFT={WALL_V_SOFT} S_MAX={WALL_S_MAX}")


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


_WK = None


def wall_mask(hsv):
    """Pixels that are genuinely a WALL - not a coloured line, not a mat marking.

    wall = (V < WALL_V_HARD)              very dark: definitely wall
           or (V < WALL_V_SOFT and S < WALL_S_MAX)   dark AND desaturated
    then a morphological open to drop the small printed dots.

    The two-case test matters: HSV saturation is unreliable when V is tiny, so a
    black wall can read S>200 from noise. Testing saturation alone rejects real
    walls; testing brightness alone accepts the blue/orange lines.
    """
    global _WK
    if _WK is None:
        _WK = np.ones((WALL_OPEN_K, WALL_OPEN_K), np.uint8)
    S = hsv[:, :, 1]
    V = hsv[:, :, 2]
    m = ((V < WALL_V_HARD) | ((V < WALL_V_SOFT) & (S < WALL_S_MAX)))
    if MAGENTA_IS_WALL:
        # the magenta parking walls are solid obstacles too - treat them as wall
        m = m | (mask(hsv, "magenta", clean=False) > 0)
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, _WK)
    return m > 0


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
def wall_readings(hsv):
    """Return (left_wall, right_wall) as black-fraction of each ROI half."""
    m = wall_mask(hsv)
    half = PROC_W // 2
    area = half * PROC_H
    left = int(np.count_nonzero(m[:, :half])) / area
    right = int(np.count_nonzero(m[:, half:])) / area
    return left, right


def front_reading(hsv):
    """Black fill fraction straight AHEAD (centre columns, upper rows).
    High = a wall is close in front = we are at a corner."""
    m = wall_mask(hsv)
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


# Everything the car can see in one frame.
#   proc         the BGR image itself (for saving annotated frames)
#   hsv          the same frame in HSV (for any extra colour work)
#   left, right  fraction of that half of the image that is wall. BIGGER =
#                CLOSER, because a nearer wall fills more of the picture.
#   front        the same measure straight ahead - high means a corner
#   blue, orange fraction of the bottom band that is each corner line
View = collections.namedtuple("View", "proc hsv left right front blue orange")


def park_readings(hsv):
    """How boxed-in each side is, for the parking-lot exit.

    Returns (magenta_left, magenta_right, wall_left, wall_right) as fractions of
    each half of the image. The parking lot's walls are MAGENTA; the track's
    outer wall behind it is BLACK. Both are reported separately so the exit
    decision can use magenta alone if the black wall turns out to swamp it.
    """
    mag = mask(hsv, "magenta") > 0
    wal = wall_mask(hsv)
    half = hsv.shape[1] // 2
    area = float(hsv.shape[0] * half)
    return (float(np.count_nonzero(mag[:, :half])) / area,
            float(np.count_nonzero(mag[:, half:])) / area,
            float(np.count_nonzero(wal[:, :half])) / area,
            float(np.count_nonzero(wal[:, half:])) / area)


def look(cam):
    """Take one frame and measure everything from it.

    This is the car's entire sense of the world, in one call, so a challenge
    loop starts with a single readable line:   view = R.look(cam)
    """
    proc, hsv = read_hsv(cam)
    left, right = wall_readings(hsv)
    blue, orange = line_counts(hsv)
    return View(proc, hsv, left, right, front_reading(hsv), blue, orange)


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

        # ---- blue ----  (its OWN, higher, threshold - blue over-triggers)
        if blue_frac > LINE_FRACTION_BLUE:
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

        # ---- orange ----  (its OWN, lower, threshold - orange is faint)
        if orange_frac > LINE_FRACTION_ORANGE:
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
            # CONFIDENCE, not raw pixels: each colour is scored against ITS OWN
            # threshold, so "faint orange that cleared its bar" can beat "lots of
            # blue that barely cleared its higher bar". Comparing raw fractions
            # is what let stray blue call a CW run CCW.
            o_conf = orange_frac / LINE_FRACTION_ORANGE
            b_conf = blue_frac / LINE_FRACTION_BLUE
            win, lose = max(o_conf, b_conf), min(o_conf, b_conf)
            bigger = 1 if o_conf > b_conf else -1                   # +1 CW, -1 CCW
            # both lines convincing at once = ambiguous. Wait for a clearer frame
            # rather than lock a direction that can never be undone.
            ambiguous = (lose > 0.0 and win < lose * LINE_DIR_MIN_RATIO)
            if win > 1.0:
                self.line_hint = bigger
            if win > 1.0 and ambiguous:
                print(f"[lap] direction AMBIGUOUS (orange {o_conf:.2f}x vs "
                      f"blue {b_conf:.2f}x of their own thresholds) - waiting")
            elif win > 1.0:
                # condition 2 - wall geometry, only when one side is clearly open
                if abs(left - right) >= GEOM_DIR_MIN_DIFF:
                    self.geom_hint = -1 if left < right else 1
                self._lock_direction(bigger,
                                     f"{'orange' if bigger > 0 else 'blue'} line at "
                                     f"{win:.2f}x its threshold")
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

    def set_direction(self, d, why="set externally"):
        """Fix the direction from OUTSIDE - a config override, or the parking lot.

        ALWAYS use this instead of assigning .direction directly. Assigning the
        attribute skips the line below, leaving the lap timer at 0.0 - and since
        `elapsed = now - 0.0` is then the machine's entire uptime, the timer
        looks permanently expired and the very FIRST line crossing is counted
        with no debounce at all. A car starting beside a line would begin the
        run one quadrant ahead and stop a corner early.
        """
        self._lock_direction(d, why)
        self._last_count_t = time.monotonic()

    def summary(self):
        """One-line fusion report for the end of a run."""
        return (f"direction={'CW' if self.direction > 0 else 'CCW' if self.direction else '?'}"
                f" via {self.direction_source}"
                f"{' (CONFIRMED by both)' if self.direction_confirmed else ''}"
                f" | corners={self.quadrant} (geom {self.corners_geom}, line {self.corners_line})"
                f" | line reads: blue={self.blue_reads} orange={self.orange_reads}"
                f" | disagreements={self.disagreements}")

    def ready_to_finish(self, coast_s=None):
        """True once STOP_AFTER_QUADRANT quadrants are counted AND the car has
        driven on for `coast_s` seconds past that last corner.

        The coast is a SEPARATE number from the lap debounce, even though it
        defaulted to it before. They mean different things - one stops a line
        being counted twice, the other decides where on the track the car comes
        to rest - and tying them together meant you could not change where it
        stopped without also changing how corners were counted.
        """
        if self.quadrant < STOP_AFTER_QUADRANT:
            return False
        wait = LAP_COUNT_LOCKOUT_S if coast_s is None else coast_s
        return (time.monotonic() - self._last_count_t) >= wait

    def stalled(self):
        """True if no quadrant has been counted for suspiciously long."""
        if not self._last_count_t:
            return False
        return (time.monotonic() - self._last_count_t) > CORNER_MAX_INTERVAL_S

    def turn_bias(self):
        """Steering bias to apply while inside a corner (deg)."""
        return self.direction * STEER_MAX


class ParkingExit:
    """Leave the parking lot, and let the way out decide the lap direction.

    THE IDEA
    The car starts inside the magenta parking lot. Whichever side is boxed in is
    the side it cannot leave by, so the free side is the way out - and the way
    out is also the direction the lap will run. One measurement answers both
    questions, before the car has moved at all.

        more obstruction on the LEFT   ->  leave to the RIGHT  ->  CW  (+1)
        more obstruction on the RIGHT  ->  leave to the LEFT   ->  CCW (-1)

    Because +1 already means "steer right" everywhere else in this code, the
    exit steering is simply direction * angle - the same number answers both.

    THREE PHASES
        settle  the car is stationary, so several frames are averaged. This is
                the one moment in the run with no motion blur; spend it.
        drive   hold the exit lock for a fixed time, open loop.
        done    hand back to normal driving with the direction already locked.

    If it cannot see enough parking lot it gives up rather than guessing, and
    leaves the direction to the corner lines as before. That matters: a wrong
    direction locked at frame one would ruin the entire run.
    """

    def __init__(self, angle=30.0, time_s=1.6, speed=45, settle_frames=8,
                 min_magenta=0.010, use_wall=True, enabled=True, invert=False):
        self.angle = angle
        self.time_s = time_s
        self.speed = speed
        self.settle_frames = settle_frames
        self.min_magenta = min_magenta
        self.use_wall = use_wall
        self.enabled = enabled
        self.invert = invert      # flip the whole mapping if a venue proves it
                                  # backwards. The measurement is trustworthy;
                                  # whether "blocked left" means CW depends on
                                  # the track's physical layout, not on us.
        self.direction = 0
        self.done = not enabled
        self.reason = "disabled" if not enabled else ""
        self._seen = 0
        self._acc = [0.0, 0.0, 0.0, 0.0]
        self._until = 0.0

    def update(self, view, now, known_direction=0):
        """Return (steer, mode, speed) while leaving, or None once finished.

        `known_direction` is a direction already fixed elsewhere (FORCE_DIRECTION).
        If given, it is OBEYED rather than measured: exiting the lot one way and
        then racing the other would be worse than either choice on its own.
        """
        if self.done:
            return None

        # ---- phase 1: stand still and measure ----
        if self.direction == 0:
            if known_direction:
                self.direction = known_direction
                self._until = now + self.time_s
                self.reason = f"direction already forced {'CW' if known_direction > 0 else 'CCW'}"
                print(f"[park] {self.reason} - leaving that way without measuring")
                return self.direction * self.angle, "park-exit", self.speed

            r = park_readings(view.hsv)
            self._acc = [a + b for a, b in zip(self._acc, r)]
            self._seen += 1
            if self._seen < self.settle_frames:
                # SPEED 0. The car must be STILL for this: these are the only
                # unblurred frames in the run, which is the whole reason the
                # measurement is taken here rather than while moving.
                return 0.0, "park-look", 0

            ml, mr, wl, wr = [a / self._seen for a in self._acc]
            if max(ml, mr) < self.min_magenta:
                self.done = True
                self.reason = (f"only {max(ml, mr):.4f} magenta - not in a "
                               f"parking lot, leaving direction to the lines")
                print(f"[park] {self.reason}")
                return None

            left = ml + (wl if self.use_wall else 0.0)
            right = mr + (wr if self.use_wall else 0.0)
            self.direction = 1 if left > right else -1
            if self.invert:
                self.direction = -self.direction
            self._until = now + self.time_s
            print(f"[park] magenta L={ml:.4f} R={mr:.4f} | "
                  f"wall L={wl:.4f} R={wr:.4f}")
            print(f"[park] {'LEFT' if left > right else 'RIGHT'} side is more "
                  f"blocked -> leaving to the "
                  f"{'RIGHT' if self.direction > 0 else 'LEFT'}, running "
                  f"{'CW' if self.direction > 0 else 'CCW'}")
            self.reason = f"magenta L={ml:.4f} R={mr:.4f}"

        # ---- phase 2: drive out ----
        if now < self._until:
            return self.direction * self.angle, "park-exit", self.speed

        self.done = True
        print(f"[park] out of the lot, direction locked "
              f"{'CW' if self.direction > 0 else 'CCW'}")
        return None


class CornerKick:
    """A fixed, open-loop steering kick fired when a corner is counted.

    WHY IT EXISTS
    The last sign before a corner leaves the car pushed to one side of the
    track. If it was pushed toward the INNER wall, the car enters the corner
    pointing across it: the next section is not in frame at all, so every
    closed-loop controller is reacting to a wall it is about to leave behind.
    A short, hard, OPEN-LOOP turn in the corner's own direction swings the nose
    round until the next section is visible, then normal control resumes.

    WHICH SIGN TRIGGERS IT depends on direction, because "inner" does:

        CW  - corners turn RIGHT, so the inner wall is on the RIGHT.
              RED is passed on the car's right, pushing it toward that inner
              wall  ->  trigger on RED, kick RIGHT.

        CCW - corners turn LEFT, so the inner wall is on the LEFT.
              GREEN is passed on the car's left, pushing it toward that inner
              wall  ->  trigger on GREEN, kick LEFT.

    Both trigger colours are constructor arguments, so if a venue proves the
    opposite convention they are a one-line change and no logic moves.

    The kick is deliberately open-loop and time-boxed: it is a manoeuvre, not a
    controller. It may exceed STEER_MAX (that is the point - it asks for real
    lock) but never exceeds the linkage's STEER_MECH_MAX.
    """

    def __init__(self, angle=30.0, duration_s=0.9, speed=55,
                 sign_cw="red", sign_ccw="green", enabled=True):
        self.angle = angle
        self.duration_s = duration_s
        self.speed = speed
        self.sign_cw = sign_cw
        self.sign_ccw = sign_ccw
        self.enabled = enabled
        self._until = 0.0
        self._dir = 0
        self.fired = 0            # how many kicks this run (shows in the summary)

    def trigger_colour(self, direction):
        """The sign colour that arms the kick for this driving direction."""
        return self.sign_cw if direction >= 0 else self.sign_ccw

    def maybe_fire(self, direction, last_sign, now):
        """Call once on the frame a quadrant is counted. True if a kick started."""
        if not self.enabled or direction == 0:
            return False
        if last_sign != self.trigger_colour(direction):
            return False
        self._until = now + self.duration_s
        self._dir = 1 if direction > 0 else -1
        self.fired += 1
        print(f"[kick] corner exit: last sign was {last_sign.upper()} in "
              f"{'CW' if direction > 0 else 'CCW'} -> "
              f"{self.angle:.0f} deg {'RIGHT' if self._dir > 0 else 'LEFT'} "
              f"for {self.duration_s:.1f}s")
        return True

    def active(self, now):
        return now < self._until

    def command(self):
        """(steer, servo_limit, speed) while the kick is running.
        +steer = right, so direction (+1 CW) already gives the correct sign."""
        return self._dir * self.angle, self.angle, self.speed

    def cancel(self):
        self._until = 0.0


# ==========================================================================
# STEERING
# ==========================================================================
def cruise_speed(base, steer):
    """Slow down in proportion to steering effort (fast on straights)."""
    return max(MIN_SPEED, base * (1.0 - SPEED_CORNER_CUT * min(1.0, abs(steer) / STEER_MAX)))


class OuterWallFollower:
    """PD on the distance to the OUTER wall ONLY.

    This is the control law used by the strongest camera-only WRO teams. Why one
    wall and not centring: in the Open Challenge the INNER walls are placed at
    random distances each round, so the corridor width changes. Centring chases a
    moving reference; the outer wall is the one constant on the track.

      clockwise         -> outer wall is on the LEFT
      counter-clockwise -> outer wall is on the RIGHT

    error = (outer - OUTER_TARGET), signed so that "too close to the outer wall"
    always steers away from it.
    """

    def __init__(self, kp=None, kd=None, target=None):
        self.kp = OUTER_KP if kp is None else kp
        self.kd = OUTER_KD if kd is None else kd
        self.target = OUTER_TARGET if target is None else target
        self._prev = 0.0

    def steer(self, left, right, direction):
        if direction > 0:             # CW  - follow the LEFT wall
            err = left - self.target
        elif direction < 0:           # CCW - follow the RIGHT wall
            err = self.target - right
        else:
            # Direction not known yet (no corner line crossed). Do NOT guess a
            # side - centre between the two walls, which is safe either way, and
            # switch to true outer-wall following the moment a line fixes it.
            err = (left - right) * 0.5
        if abs(err) < OUTER_DEADBAND:
            err = 0.0
        out = self.kp * err + self.kd * (err - self._prev)
        self._prev = err
        return max(-STEER_MAX, min(STEER_MAX, out))


class TurnSequencer:
    """A scripted 90 deg corner turn, triggered by CROSSING THE LINE.

    Deterministic by design: the line tells us we are physically at the corner,
    so we hold full lock for a fixed time instead of waiting for a tuned
    front-wall fraction to cross a threshold. Wall following is suspended while
    the turn runs; the wall EMERGENCY still overrides it.
    """

    def __init__(self):
        self.active = False
        self._until = 0.0
        self._min_until = 0.0
        self._dir = 0

    def trigger(self, direction):
        if direction == 0:
            return
        self.active = True
        self._dir = direction
        self._until = time.monotonic() + TURN_DURATION_S
        self._min_until = time.monotonic() + TURN_MIN_S
        print(f"[turn] scripted {'RIGHT' if direction > 0 else 'LEFT'} turn "
              f"for {TURN_DURATION_S:.1f}s")

    def update(self, front=None):
        """End the turn when the corner is CLEARED, not on a fixed clock.

        A fixed 1.1 s at full lock kept turning after the corner was done and
        drove the car into the INNER wall (log: inner density climbed 0.126 ->
        0.195 -> 0.278 during the turn, in both CW and CCW). Now the clock is
        only a maximum; the turn exits as soon as the way ahead is clear.
        """
        if not self.active:
            return
        now = time.monotonic()
        if now >= self._until:                      # hard cap
            self.active = False
            return
        if front is not None and now >= self._min_until and front < FRONT_EXIT:
            self.active = False

    def steer(self):
        return STEER_MAX * TURN_LOCK_FRAC * (1.0 if self._dir > 0 else -1.0)


def apply_bias(steer):
    """Add the straight-line drift trim and re-clamp.

    ONLY for lane-keeping. It must NOT be applied to corner turns or emergency
    escapes, which need the full mechanical range: a -4 deg trim on a CW corner
    turned +35 into +31, the car understeered and ran wide into the OUTER wall.
    In CCW the same trim clamped harmlessly at -35, which is why the fault only
    ever appeared clockwise.
    """
    return max(-STEER_MAX, min(STEER_MAX, steer + STEER_BIAS))


def wall_emergency(left, right, outer=None, direction=0):
    """Escape steering when a wall is too close, or None if there is no danger.

    THE HIGHEST PRIORITY IN BOTH CHALLENGES. Two hard-won details:

    1. IT IS FLOORED BY THE NORMAL CONTROLLER. The first version ramped up from
       zero, so just past the threshold it produced -0.8 deg while the wall
       follower wanted -17 deg: the "emergency" actually seized control and
       steered the car INTO the wall (log t=1.05 s, right=0.285). It now starts
       at HALF lock and is never weaker than the normal command in that sense.

    2. THE ESCAPE DIRECTION LATCHES when BOTH walls are close (facing into a
       corner). Left and right densities crossing each other made the sign flip
       between frames, so the car twitched instead of escaping.
    """
    if left <= WALL_EMERGENCY and right <= WALL_EMERGENCY:
        _esc["dir"] = 0
        return None

    if left > WALL_EMERGENCY and right > WALL_EMERGENCY:
        if _esc["dir"] == 0:
            _esc["dir"] = 1 if left > right else -1
        return STEER_MAX * _esc["dir"]

    _esc["dir"] = 0
    if left > WALL_EMERGENCY:                       # ramp 50% -> 100% of lock
        push = STEER_MAX * (0.5 + 0.5 * min(1.0, (left - WALL_EMERGENCY) / 0.12))
    else:
        push = -STEER_MAX * (0.5 + 0.5 * min(1.0, (right - WALL_EMERGENCY) / 0.12))

    if outer is not None and direction != 0:        # never weaker than normal
        normal = outer.steer(left, right, direction)
        push = max(push, normal) if push > 0 else min(push, normal)
    return max(-STEER_MAX, min(STEER_MAX, push))
