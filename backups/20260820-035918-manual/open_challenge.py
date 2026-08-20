#!/usr/bin/env python3
"""
open_challenge.py - the team's PROVEN open-challenge program, ported to this car.

This is "openchallenge final code.py" with its LOGIC AND STRUCTURE UNCHANGED.
Same functions, same order, same control law, same constants. The only edits are
the ones this car physically forces, and every one of them is marked

    PORTED:

so you can find them all with a single search. Nothing else was touched, on
purpose: this file is a tested win and the point of the port is to keep it that
way.

Run:  cd ~/wro2026 && source .venv/bin/activate && python open_challenge.py
"""
#new variable for the open challenge surprise challenge.

#tuneables in openchallenge
blue_line_threshould = 830 #detect blue line number count of pexiles
orange_line_threshould = 930 #detect orange line number count of pexiles
speed = 100
#note in syntax if the variable is written all capital with underscore its considered constant 
LINE_BLANK_S = 1.2 # the time in second needed to wait before counting new line
#orange color in HSV after tuning.
ORANGE_SAT_MIN, ORANGE_VAL_MIN, ORANGE_VAL_MAX = 70, 30, 240
ORANGE_HUE_MIN, ORANGE_HUE_MAX = 0, 30
#blue color in HSV after tuning.
BLUE_SAT_MIN, BLUE_VAL_MIN, BLUE_VAL_MAX = 140, 20, 200
BLUE_HUE_MIN, BLUE_HUE_MAX = 90, 135
#continue driving after the 12 quadrnt 
FINISH_RUN_S = 3.0#3 seconds of drive
CW_TARGET  = 0.215      # CW follows the LEFT wall   (theirs: 0.30)
                        # NOT the raw CW measurement of 0.241 - see below.
CCW_TARGET = 0.214      # CCW follows the RIGHT wall (theirs: 0.40) MEASURED
NEUTRAL_TARGET = 0.25   # BEFORE THE DIRECTION LOCKS. Theirs was 0.5, and on
                        # OUR camera the densities only reach about 0.25 - so
                        # nothing ever exceeded it, dir stayed 0, and the car
                        # drove DEAD STRAIGHT out of the start until it found a
                        # line. Pointed even slightly inward, that is a crash
                        # into the inner wall. CCW only survived it because a
                        # line arrived at 2.7 s.
                        # Centred reads 0.215, so 0.25 does nothing until the
                        # car is genuinely close to one side.
WALL_GAIN = 75.0        # their fixed *75
#we put a limit to our servo at 20(software limit)
STEER_MAX = 20

#libraries
import cv2
import sys
import csv
import os
import shutil
# PORTED: over SSH stdout is a PIPE, and Python block-buffers pipes - so a
# run that is killed, or watched live, shows NOTHING. Line buffering makes
# the log appear cycle by cycle however the program is launched.
try:
    sys.stdout.reconfigure(line_buffering=True)
except AttributeError:
    pass
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view as _swv
import time
from picamera2 import Picamera2
from libcamera import Transform            # PORTED: our camera is mounted upside down
import RPi.GPIO as GPIO
# PORTED: no NeoPixel on this car. `import board` and `import neopixel` are gone
#         and the LED functions below are no-ops, so every call site still works.

# ==========================================================================
# TUNABLES - the only numbers you should need to change
# ==========================================================================
#note from jolian those are hardware configuration.
# PORTED: our pin map (was SERVO 23, MOTOR 27/22, BUTTON 9)
SERVO_PIN = 13
MOTOR_IN1 = 24          # PWM here = FORWARD
MOTOR_IN2 = 23
BUTTON_PIN = 19
SERVO_TRIM = -9.0       # PORTED: their `angle += 0`; ours is measured at -9
STEER_DEVIATION = 35    # PORTED: their deviation was 45. OUR ACKERMANN LINKAGE
                        # STOPS AT 35 - commanding more drives the servo into
                        # its own mechanical stop, where it stalls and buzzes.

# PORTED: SMOOTHNESS. Their servo() set the angle, slept 0.1 s, then set the
# duty to ZERO - stopping the pulse train, which makes the servo go limp until
# the next command. On their slow Python loop that was once per ~0.3 s, so the
# steering was commanded, released, commanded again. That is what shakes and
# stutters.
#   SERVO_SETTLE_S  how long servo() blocks. It also CAPS THE CONTROL RATE:
#                   at 0.1 the loop cannot exceed 10 Hz no matter how fast the
#                   vision is, and slow steering on a fast car is what makes it
#                   hunt. 0.02 gives about 40 Hz.
#   SERVO_HOLD      True = keep the pulse so the servo HOLDS its angle.
#                   False = their original release-to-limp behaviour.
SERVO_SETTLE_S = 0.02
SERVO_HOLD = True

# PORTED: SHAKE. Two separate causes, two separate knobs.
#
#   SERVO_SMOOTH    The controller is a pure P term running at 34 Hz on a
#                   density signal that moves as the car does. Every cycle it
#                   hands the servo a slightly different angle, so the servo
#                   is never still. This is an exponential average on the
#                   COMMAND: 1.0 is their original raw behaviour, lower is
#                   smoother. 0.35 gives a time constant of about 85 ms -
#                   far quicker than the car turns, so it costs no response.
#
#   SERVO_DEADBAND  RPi.GPIO drives this pin with SOFTWARE PWM, and every
#                   ChangeDutyCycle call re-times the pulse train, which the
#                   servo feels as a twitch. Below this many degrees of change
#                   the duty is simply not rewritten, so a car already going
#                   straight stops being nudged 34 times a second.
#                   Set to 0.0 to write every cycle like theirs did.
SERVO_SMOOTH = 0.35
SERVO_DEADBAND = 0.8

# PORTED: WHAT THE SHAKE ACTUALLY WAS.
# RPi.GPIO generates PWM in SOFTWARE, from a Python thread. Every scheduling
# hiccup moves the pulse edge, and on a 1.5 ms servo pulse 100 us of jitter is
# about 9 degrees of commanded position - so the servo hunts no matter how
# smooth the commands are. GPIO13 is a hardware PWM pin and pigpio times the
# pulse by DMA instead.
#
# TESTED with tools/servo_jitter.py, holding ONE CONSTANT ANGLE three ways:
#     RPi.GPIO, pulse held      -> audible buzzing
#     RPi.GPIO, pulse released  -> audible buzzing
#     pigpio, DMA-timed         -> SILENT
# The command never changed inside a phase, so this was never the control loop.
#
# pigpio needs its daemon:  sudo systemctl enable --now pigpiod
# If the daemon is not running this falls back to RPi.GPIO automatically and
# says so at startup - it will drive, it will just buzz again.
SERVO_BACKEND = "pigpio"        # "pigpio" or "rpigpio" for their original


# PORTED: our camera is fixed and mounted UPSIDE DOWN, so it is flipped in
# hardware and its exposure/white balance are LOCKED. Auto anything makes the
# colour thresholds below drift under the car while it drives.
CAM_FLIP_180 = True
CAM_EXPOSURE_US = 12000
CAM_GAIN = 8.0
CAM_COLOUR_GAINS = (1.329, 1.446)
CAM_SATURATION = 1.3
CAM_CONTRAST = 1.1

# PORTED: their frame builder rotated the crop 180 degrees in software, because
# their camera was not flipped in hardware. OURS IS, so rotating again would
# swap left and right and the car would steer into the wall it is avoiding.
# If it ever does exactly that, this is the one line to flip.
ROTATE_180 = False

# PORTED: how far down the raw frame the crop starts. Theirs was 240 (the
# bottom half). Ours needs 160 - see process_frame for the measurement.
CROP_TOP = 160


# PORTED: line thresholds are PIXEL COUNTS and belong to the camera AND THE
# CROP that measured them. Re-measure with tools/line_audit.py.
#
# BLUE was SILENT on a line filling the view. MEASURED: 1077 px against their
# threshold of 1100, and 1059-1104 across 12 frames - the threshold sat INSIDE
# the frame-to-frame spread, so the same crossing flickered on and off and
# would have been counted more than once.
#
# The cause is our CROP, not the colour. CROP_TOP had to move from their 240 to
# 160 to get the walls in frame at all, which squashes 320 rows into 120 instead
# of 240 into 120. A line is mostly HORIZONTAL, so it loses pixels in direct
# proportion: the same frame gives 1421 px through their crop and 1077 through
# ours - 76%, against the 75% the geometry predicts.
#
# Their threshold fired at 1100/1421 = 77% of a full line. Keeping that same
# design ratio on our crop gives 1077 * 0.774 = 834. Bare mat reads 3-9 px, so
# there is no false-positive risk anywhere near this number.
#
# NOT changed, deliberately: BLUE_SAT_MIN. 9556 px pass every other bound and
# fail only S>140 - that is the MAT, whose hue sits inside the blue range.
# Saturation is the only thing keeping it out. Lowering it re-admits the mat.
# The hue floor of 90 does cost 580 real line pixels (the blurred edges), and
# lowering it to 88 would recover some - but green pillars measure H81-86, and
# obstacle_challenge shares this range, so it is not worth the collision.
# PORTED: BLUE'S BRIGHTNESS FLOOR, for the same reason as orange's below.
# MEASURED with the blue line in view: it is a clear 1520 px 307x36 band at
# S~223 - but its V median is 43 and its p95 only 79, against their floor of
# 70. Most of the line failed on brightness. Saturation was never the problem
# for blue; S>140 is what keeps the MAT out (the mat sits at S~71 even when its
# hue drifts into the blue range), and V was doing nothing but rejecting the
# line itself.
#     BLUE_VAL_MIN 70 -> 20
#
# PORTED: ORANGE'S BRIGHTNESS FLOOR. Theirs demanded V > 125. MEASURED on our
# field, the orange line is a clear 1648 px 320x19 band at S~178 - but its
# V median is 78 and its p95 only 106, because our whole frame tops out at
# V=143 where theirs was brighter. Their floor made orange UNREACHABLE, so the
# direction could never lock CW and every run fell to blue and went CCW.
# Hue alone separates orange from the mat here anyway - orange H~13 against the
# mat's H~70 - so the brightness floor was never doing the work.
# PORTED: ORANGE WAS SILENT TOO, and worse than blue - it never reached its
# threshold at all. MEASURED on a line filling the view: 1161-1246 across 12
# frames against a threshold of 1300. Never fires.
# Same cause, same fix: their 1300 came from their crop, which gives 1389 px on
# the very same frame our crop reads 1161 from - we keep 84%. Applying the same
# 77%-of-a-full-line rule blue got: 1199 * 0.774 = 928, so 930.
# Bare mat reads 0-87 px orange, so the margin below is about 13x.
#
# NOT changed, deliberately:
#   ORANGE_VAL_MIN stays at 30 although 444 px pass every other bound and fail
#   only it. Those are the line's shadowed edges and recovering them would
#   widen the margin - but shadow is grey, its hue is unstable at low
#   saturation, and S>70 is weak protection against it. The margin is already
#   1.25x; buying more of it with a bound that lets shadow in is a bad trade.
#   ORANGE_HUE_MAX stays at 30. The 13639 px it rejects are the MAT, not line.
#
# WHY CW_TARGET IS 0.215 AND NOT THE 0.241 THAT WAS MEASURED.
# Both directions follow the OUTER wall: clockwise the car turns right, so the
# inside of the loop is on its right and the LEFT wall is the outer one;
# counter-clockwise is the mirror. A centred car must therefore read the SAME
# density whichever way it points, and its own two halves must be nearly equal.
#
#     CCW placement:  left 0.2184   right 0.2138   gap 0.005   <- self-consistent
#     CW  placement:  left 0.2415   right 0.1825   gap 0.059   <- NOT centred
#
# The CCW reading checks out against itself; the CW one does not. The car was
# sitting nearer the left wall when CW was measured, so 0.241 encodes an
# off-centre position - it asks the car to hold 13% closer to the outer wall
# than the middle. Taking the trustworthy reading for both gives 0.215.
# Re-measure with tools/wall_calib.py if you want it confirmed: a properly
# centred CW placement should read left and right within about 0.01 of each
# other, like the CCW one does.

# NOTE these are STATIC readings at one distance. During a run the car drives
# over the line and the count PEAKS higher than this. open_log.csv records
# blue_px and orange_px every cycle, so after a run the real peak at each
# crossing can be read off directly - that is better evidence than any static
# measurement, including this one.
WALL_VAL_MAX = 70            # LEGACY single test, used only if shadow
                             # rejection below is turned OFF

# TURNING THIS ON CHANGES THE MEASURED DENSITIES, so CW_TARGET and CCW_TARGET
# must be re-measured with tools/wall_calib.py. The tool prints the old and new
# densities side by side so you can see how much shadow was being counted.
# Set WALL_SHADOW_REJECT = False to go straight back to the bare v < 70.
WALL_SHADOW_REJECT = True
WALL_V_HARD = 32        # below this it is wall regardless of saturation
WALL_V_SOFT = 62        # up to this it is wall ONLY if desaturated
WALL_S_MAX = 90         # coloured lines exceed this and are rejected
WALL_OPEN_K = 3         # square open - drops speckle and printed dots
WALL_MIN_RUN = 6        # a wall needs this many consecutive dark rows.
                        # RAISE IT if shadow still gets through; LOWER IT if
                        # distant walls start disappearing from the reading.


# ==========================================================================

OUTPUT = GPIO.OUT
INPUT = GPIO.IN
# --------------------------------------------------

STOP = False
mission_end_t = 0.0            # PORTED: a TIME now, not a cycle number
mission_end_not_activated = True

cycle_count = 0
direction = 0
quadrant_count = 0


# --------------------------------------------------
# Image variables

raw_frame = np.empty((480, 640, 3), dtype=np.uint8)
frame = np.empty((120, 320, 3), dtype=np.uint8)

# --------------------------------------------------
# Wall variables

left_wall = 0.0
right_wall = 0.0

# --------------------------------------------------

blue_line_pixel_count = 0
blue_line_next_allowed_t = 0.0

orange_line_pixel_count = 0
orange_line_next_allowed_t = 0.0

blue_line_detected = False
orange_line_detected = False

blue_line_state = 0
orange_line_state = 0

dir = 0.0
_dir_smooth = 0.0        # PORTED: state for SERVO_SMOOTH


# PORTED: log every cycle, so a bad run can be read afterwards instead of
# guessed at. Their open file wrote nothing.

# PORTED: the log is opened by main(), NOT at import. It used to be opened at
# module level, which meant that merely importing this file - which the tools
# and the test suite now do - TRUNCATED the previous run's log.
logfile = None
logwriter = None
_prev_t = 0.0
_t0 = 0.0


LOG_PATH = None


def _open_log():
    # PORTED: every run used to truncate open_log.csv, so the evidence from a
    # BAD run was destroyed by the next run - which is precisely backwards,
    # because a failure is the run worth keeping. Each run now writes its own
    # timestamped file under logs/ and open_log.csv is a copy of the latest.
    global logfile, logwriter, LOG_PATH
    os.makedirs("logs", exist_ok=True)
    LOG_PATH = os.path.join("logs", "open_%s.csv"
                            % time.strftime("%Y%m%d-%H%M%S"))
    logfile = open(LOG_PATH, "w", newline="")
    logwriter = csv.writer(logfile)
    logwriter.writerow(["cycle", "t_s", "dt_ms", "left_wall", "right_wall",
                        "blue_px", "blue_state", "orange_px", "orange_state",
                        "direction", "quadrant",
                        "dir_raw", "dir_clamped", "dir_servo"])


# --------------------------------------------------
def is_button_down():
    # PORTED: our button is wired to GND with the internal pull-up, so PRESSED
    # reads LOW. Theirs read HIGH. Same function, opposite sense.
    return GPIO.input(BUTTON_PIN) == 0

def _write_servo(angle):
    # PORTED: the two backends, writing the SAME pulse for the same angle.
    # Their duty ran 2.5% to 12.5% at 50 Hz, and 50 Hz means a 20 ms frame, so
    # their duty was really a pulse of 500 us to 2500 us across 0-180 degrees.
    # pigpio is given that pulse directly, so the centre and the throw are
    # identical either way and SERVO_TRIM does not change meaning.
    if _pi is not None:
        _pi.set_servo_pulsewidth(SERVO_PIN, 500.0 + (angle / 180.0) * 2000.0)
    else:
        servo_pwm.ChangeDutyCycle(2.5 + (angle / 180.0) * 10.0)

_last_angle = None
_pi = None                   # the pigpio handle, or None for RPi.GPIO
def servo(angle):
    """Adjust and set the servo angle."""

    global SERVO_PIN, _last_angle

    angle += 90
    deviation = STEER_DEVIATION      # PORTED: was 45; our linkage stops at 35
    if angle < 90 - deviation:
        angle = 90 - deviation
    if angle > 90 + deviation:
        angle = 90 + deviation
    angle += SERVO_TRIM          # PORTED: was `angle += 0`

    # PORTED: DEADBAND - do not rewrite the pulse for a change too small to
    # matter. Small changes still accumulate, so this cannot cause a permanent
    # offset: once the command has drifted SERVO_DEADBAND degrees it is written.
    if _last_angle is None or abs(angle - _last_angle) >= SERVO_DEADBAND:
        _write_servo(angle)
        _last_angle = angle
    time.sleep(SERVO_SETTLE_S)          # PORTED: was 0.1 - see SERVO_SETTLE_S
    if not SERVO_HOLD:                  # PORTED: theirs always released here
        if _pi is not None:
            _pi.set_servo_pulsewidth(SERVO_PIN, 0)
        else:
            servo_pwm.ChangeDutyCycle(0)
        _last_angle = None


def motor(speed):  # Speed is -1 to 1
    global MOTOR_IN1, MOTOR_IN2

    speed = max(-100, min(100, speed))
    speed_pwm = abs(speed)  # Calculate absolute speed for PWM

    if speed > 0:  # Forward

        motor1_pwm.ChangeDutyCycle(speed_pwm)
        motor2_pwm.ChangeDutyCycle(0)
    elif speed < 0:  # Reverse
        motor1_pwm.ChangeDutyCycle(0)
        motor2_pwm.ChangeDutyCycle(speed_pwm)
    else:  # Stop
        motor1_pwm.ChangeDutyCycle(0)
        motor2_pwm.ChangeDutyCycle(0)


def Setup_GPIO():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)          # PORTED: quiet the re-run warning

    GPIO.setup(SERVO_PIN, OUTPUT)
    GPIO.setup(MOTOR_IN1, OUTPUT)
    GPIO.setup(MOTOR_IN2, OUTPUT)
    # PORTED: GPIO.setup(10, OUTPUT) was the NeoPixel data pin - not on this car
    # PORTED: the button needs the internal pull-up, being wired to GND
    GPIO.setup(BUTTON_PIN, INPUT, pull_up_down=GPIO.PUD_UP)
    global servo_pwm, motor1_pwm, motor2_pwm, _pi
    # PORTED: prefer pigpio for the servo - see SERVO_BACKEND. It is the whole
    # reason the steering stopped buzzing. Falls back to their RPi.GPIO PWM,
    # loudly, if the daemon is not up.
    servo_pwm = None
    _pi = None
    if SERVO_BACKEND == "pigpio":
        try:
            import pigpio
            _pi = pigpio.pi()
            if not _pi.connected:
                _pi = None
        except ImportError:
            _pi = None
        if _pi is None:
            print("!! pigpiod IS NOT RUNNING - falling back to RPi.GPIO software")
            print("   PWM, which is what makes the steering buzz. Fix with:")
            print("       sudo systemctl enable --now pigpiod")
    if _pi is None:
        servo_pwm = GPIO.PWM(SERVO_PIN, 50)
        servo_pwm.start(0)

    motor1_pwm = GPIO.PWM(MOTOR_IN1, 1000)
    motor2_pwm = GPIO.PWM(MOTOR_IN2, 1000)
    motor1_pwm.start(0)
    motor2_pwm.start(0)

    # PORTED: NeoPixel initialisation removed


def Setup_Camera():
    global picam2
    picam2 = Picamera2()
    # PORTED: flipped in hardware, and exposure/white balance LOCKED. Their
    # camera needed neither; ours is mounted upside down and drifts if left
    # on auto, which moves every colour threshold in this file.
    tf = Transform(hflip=1, vflip=1) if CAM_FLIP_180 else Transform()
    config = picam2.create_preview_configuration(
        main={"format": 'RGB888', "size": (640, 480)}, transform=tf)
    picam2.configure(config)
    picam2.start()
    picam2.set_controls({
        "AeEnable": False, "ExposureTime": CAM_EXPOSURE_US,
        "AnalogueGain": CAM_GAIN,
        "AwbEnable": False, "ColourGains": CAM_COLOUR_GAINS,
        "Saturation": CAM_SATURATION, "Contrast": CAM_CONTRAST,
    })
    time.sleep(1)
    return picam2


def capture_array(picam2):
    raw_frame_arr = picam2.capture_array()
    return raw_frame_arr


def process_frame(raw_frame_arr, frame_arr):
    # PORTED: identical result to their per-pixel loop, done with numpy.
    #
    # THE CROP HAD TO MOVE. Theirs took rows 240-480 - the bottom half - and on
    # their camera that half contained the walls. Ours is a 120 degree lens at
    # 12.5 cm, so the bottom half is almost entirely FLOOR: measured on the
    # field, their crop read left_wall 0.024 against their own target of 0.30,
    # and no gain can steer from a signal that is not there. Starting at
    # CROP_TOP puts the walls back in frame - the same scene then reads 0.15,
    # which is the range their constants were written for.
    crop = raw_frame_arr[CROP_TOP:480, 0:640:2]
    crop = cv2.resize(crop, (320, 120), interpolation=cv2.INTER_AREA)
    if ROTATE_180:
        crop = crop[::-1, ::-1]
    frame_arr[:] = crop

def _tall_runs(m, k):
    # Keep only pixels belonging to a VERTICAL RUN of at least k dark pixels.
    # This is the SHADOW TEST: a real wall is a tall solid run, a shadow is a
    # broad shallow smear.
    #
    # Done by hand rather than with cv2.morphologyEx(MORPH_OPEN, vertical
    # kernel), which is wrong here in two separate ways, both MEASURED:
    #   1. Its erosion uses an INFINITE border value, so where the wall band
    #      touches the top of the frame it is not eroded - but the dilation
    #      that follows still grows it DOWNWARD, inventing wall out of mat.
    #      That added ~270 px per frame at V 70-138, brighter than every
    #      threshold in this file, and inflated one wall reading by 4.4%.
    #   2. Even with the border forced to 0 the result is SHIFTED, because
    #      OpenCV does not reflect the kernel for dilation and this kernel has
    #      an even length. It kept the right NUMBER of pixels, 5517, but 324 of
    #      them were in the wrong rows.
    # This version can only ever remove pixels, and has no anchor to get wrong.
    h_ = m.shape[0]
    if h_ < k:
        return np.zeros_like(m)
    er = _swv(m, k, axis=0).all(axis=-1)      # er[j]: rows j..j+k-1 all dark
    pad = np.zeros((h_ + k - 1, m.shape[1]), bool)
    pad[k - 1:k - 1 + er.shape[0]] = er
    return m & _swv(pad, k, axis=0).any(axis=-1)[:h_]

_WK_SQ = None
def wall_mask(h, s, v):
    # PORTED: see the WALL DETECTION block at the top. Their test was a bare
    # v < WALL_VAL_MAX, which counts shadow on the mat as wall.
    global _WK_SQ
    if not WALL_SHADOW_REJECT:
        return v < WALL_VAL_MAX
    if _WK_SQ is None:
        _WK_SQ = np.ones((WALL_OPEN_K, WALL_OPEN_K), np.uint8)
    raw = ((v < WALL_V_HARD) | ((v < WALL_V_SOFT) & (s < WALL_S_MAX)))
    m = raw
    if WALL_OPEN_K > 1:                 # speckle and printed dots
        o = cv2.morphologyEx(raw.astype(np.uint8), cv2.MORPH_OPEN, _WK_SQ) > 0
        m = o & raw                     # & raw: never let the border add pixels
    if WALL_MIN_RUN > 1:                # THE SHADOW TEST: keep tall runs only
        m = _tall_runs(m, WALL_MIN_RUN)
    return m


def process_hsv(hsv_arr):
    # PORTED: identical result to their per-pixel loop, done with numpy.
    global blue_line_pixel_count, orange_line_pixel_count, left_wall, right_wall

    h = hsv_arr[:, :, 0].astype(np.int16)
    s = hsv_arr[:, :, 1].astype(np.int16)
    v = hsv_arr[:, :, 2].astype(np.int16)

    blue_line_pixel_count = int(np.count_nonzero(
        (s > BLUE_SAT_MIN) & (v > BLUE_VAL_MIN) & (v < BLUE_VAL_MAX) &
        (h > BLUE_HUE_MIN) & (h < BLUE_HUE_MAX)))

    orange_line_pixel_count = int(np.count_nonzero(
        (s > ORANGE_SAT_MIN) & (v > ORANGE_VAL_MIN) & (v < ORANGE_VAL_MAX) &
        (h >= ORANGE_HUE_MIN) & (h <= ORANGE_HUE_MAX)))

    dark = wall_mask(h, s, v)
    left_wall = float(np.count_nonzero(dark[:, :160]))
    right_wall = float(np.count_nonzero(dark[:, 160:]))

    left_wall /= (12800)                       #answer for 160 * 80
    right_wall /= (12800)                      #answer for 160 * 80


def update_lines():
    # PORTED: identical state machine. The ONLY change is that the blanking
    # deadline is a TIME instead of a cycle number - see LINE_BLANK_S.
    global blue_line_pixel_count, blue_line_threshould, blue_line_next_allowed_t, blue_line_detected, blue_line_state
    global orange_line_pixel_count, orange_line_threshould, orange_line_next_allowed_t, orange_line_detected, orange_line_state
    global LINE_BLANK_S

    now = time.time()

    if blue_line_pixel_count > blue_line_threshould:
        blue_line_state = 1
        if now >= blue_line_next_allowed_t:
            blue_line_detected = True
    else:
        blue_line_state = 0
        if blue_line_detected:
            blue_line_state = 2
            blue_line_next_allowed_t = now + LINE_BLANK_S
        blue_line_detected = False

    if orange_line_pixel_count > orange_line_threshould:
        orange_line_state = 1
        if now >= orange_line_next_allowed_t:
            orange_line_detected = True
    else:
        orange_line_state = 0
        if orange_line_detected:
            orange_line_state = 2
            orange_line_next_allowed_t = now + LINE_BLANK_S
        orange_line_detected = False


def extra_imagery(hsv_arr):
    # PORTED: same output, numpy instead of a per-pixel loop, and through the
    # SAME wall_mask the controller used - so walls.png shows what it actually
    # steered on, shadow rejection included.
    h = hsv_arr[:, :, 0].astype(np.int16)
    s = hsv_arr[:, :, 1].astype(np.int16)
    v = hsv_arr[:, :, 2].astype(np.int16)
    walls = np.where(wall_mask(h, s, v), 255, 0).astype(np.uint8)
    cv2.imwrite("walls.png", walls)


def cycle(picam2):
    global cycle_count, dir, blue_line_state, orange_line_state, direction, quadrant_count
    global mission_end_not_activated, mission_end_t, STOP, left_wall, right_wall
    global blue_line_pixel_count, orange_line_pixel_count, raw_frame, frame

    cycle_count += 1

    dir = 0.0
    #we get the frame from the camera
    raw = capture_array(picam2)
    #store the frame
    raw_frame[:] = raw
    #an empty matrix so we store the new processed frame in it.
    frame = np.empty((120, 320, 3), dtype=np.uint8)
    #calling the function that process frame cut and crop
    process_frame(raw_frame, frame)
    #now we turn our frame from RGB coloring to HSV 
    hsv_mat = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    #now we pass the frame into process hsv function that will give us blue line and orange line and left and right wall count.
    process_hsv(hsv_mat)
    #based on the lines thresholds determine the direction adnd lines state with the timer to prevent lines repeats in small area
    update_lines()
    #now this fixes the direction the whole run direction in this if / else.
    if blue_line_state != 0 and direction == 0:
        direction = -1
        # PORTED: say it out loud. Following the INNER wall all run is what a
        # wrong direction looks like from outside, and it is otherwise silent.
        print(">>> DIRECTION LOCKED CCW (-1) on the BLUE line, cycle %d "
              "- will follow the RIGHT wall" % cycle_count)
    if orange_line_state != 0 and direction == 0:
        direction = 1
        print(">>> DIRECTION LOCKED CW (+1) on the ORANGE line, cycle %d "
              "- will follow the LEFT wall" % cycle_count)
    #end of the determination if/else for direction
    #the quadrnt count logic.
    #warning we might need to change this to make it based on both lines with a timer so it count on the one detected first. 
    if direction >= 0:
        if orange_line_state == 2:
            quadrant_count += 1
    else:
        if blue_line_state == 2:
            quadrant_count += 1


    #that is the whole controll logic.
    #note wallgain is just propotional control value.
    if direction == 1:
        #the direction is cw so we need to follow the outer wall which in this case is the left wall.
        dir = (left_wall - CW_TARGET) * WALL_GAIN
    elif direction == -1:
        #the direction is ccw so we need to follow the outer wall which in this case is the right wall.
        dir = (CCW_TARGET - right_wall) * WALL_GAIN
    else:
        # center between both walls.
        if left_wall > NEUTRAL_TARGET:
            dir = (left_wall - NEUTRAL_TARGET) * WALL_GAIN
        if right_wall > NEUTRAL_TARGET:
            dir = (NEUTRAL_TARGET - right_wall) * WALL_GAIN
    
    # PORTED: THE 20 DEGREE RULE. servo() clamps at STEER_DEVIATION=35, which
    # is the mechanical stop and the wrong limit for ordinary driving.
    dir_raw = dir
    dir = max(-STEER_MAX, min(STEER_MAX, dir))

    #smoothing the shaking of the servo.
    global _dir_smooth
    _dir_smooth = SERVO_SMOOTH * dir + (1.0 - SERVO_SMOOTH) * _dir_smooth
    dir_servo = _dir_smooth
    #end of the servo smothing function.

    #calculate the stop timer.
    if quadrant_count == 12 and mission_end_not_activated:
        mission_end_not_activated = False
        mission_end_t = time.time() + FINISH_RUN_S
        print(">>> 12 QUADRANTS at cycle %d - driving on for %.1f s"
              % (cycle_count, FINISH_RUN_S))
    #stop the robot after hitting the stop timer.
    if (not mission_end_not_activated) and time.time() >= mission_end_t:
        STOP = True
    
    # PORTED: FULL per-cycle log. Everything the controller looked at and
    # everything it decided, on one line, so a bad run can be read afterwards
    # instead of guessed at.
    global _prev_t, _t0
    now = time.time()
    dt = (now - _prev_t) if _prev_t else 0.0
    _prev_t = now
    hz = (1.0 / dt) if dt > 0 else 0.0
    clamped = "CLAMP" if abs(dir_raw) > STEER_MAX + 0.01 else "     "
    dname = {1: "CW ", -1: "CCW", 0: "?? "}[direction]

    print("c%-5d t=%6.2f dt=%5.1fms %4.1fHz | L=%.3f R=%.3f | "
          "blu=%5d s%d  org=%5d s%d | %s q=%2d | raw=%+6.1f clamp=%+6.1f "
          "srv=%+6.1f %s"
          % (cycle_count, now - _t0, dt * 1000.0, hz,
             left_wall, right_wall,
             blue_line_pixel_count, blue_line_state,
             orange_line_pixel_count, orange_line_state,
             dname, quadrant_count, dir_raw, dir, dir_servo, clamped))

    if logwriter is not None:
        logwriter.writerow([cycle_count, round(now - _t0, 3),
                            round(dt * 1000, 2),
                            round(left_wall, 4), round(right_wall, 4),
                            blue_line_pixel_count, blue_line_state,
                            orange_line_pixel_count, orange_line_state,
                            direction, quadrant_count,
                            round(dir_raw, 2), round(dir, 2),
                            round(dir_servo, 2)])
        logfile.flush()
    servo(dir_servo)


def print_config():
    # PORTED: dump every tunable at start, so a saved log says what produced it.
    print("=" * 78)
    print("  OPEN CHALLENGE - configuration for this run")
    print("=" * 78)
    print("  steering   trim=%+.1f  STEER_MAX=%d deg (normal)  mech stop=%d deg"
          % (SERVO_TRIM, STEER_MAX, STEER_DEVIATION))
    print("  servo      settle=%.3f s  hold=%s  smooth=%.2f  deadband=%.1f deg"
          % (SERVO_SETTLE_S, SERVO_HOLD, SERVO_SMOOTH, SERVO_DEADBAND))
    print("             pulse driver: %s"
          % ("pigpio, DMA-timed (steady)" if _pi is not None
             else "RPi.GPIO SOFTWARE PWM - THIS BUZZES"))
    print("  motor      speed=%d" % speed)
    print("  camera     flip180=%s  exposure=%d us  gain=%.1f  gains=%s"
          % (CAM_FLIP_180, CAM_EXPOSURE_US, CAM_GAIN, CAM_COLOUR_GAINS))
    print("             saturation=%.2f contrast=%.2f crop_top=%d rotate180=%s"
          % (CAM_SATURATION, CAM_CONTRAST, CROP_TOP, ROTATE_180))
    print("  walls      CW_TARGET=%.3f (left)   CCW_TARGET=%.3f (right)"
          % (CW_TARGET, CCW_TARGET))
    print("             NEUTRAL=%.3f  GAIN=%.0f" % (NEUTRAL_TARGET, WALL_GAIN))
    if WALL_SHADOW_REJECT:
        print("             mask: V<%d, or V<%d and S<%d; open %d; "
              "vertical run >=%d"
              % (WALL_V_HARD, WALL_V_SOFT, WALL_S_MAX, WALL_OPEN_K,
                 WALL_MIN_RUN))
        print("             SHADOW REJECTION ON")
    else:
        print("             mask: V<%d (legacy, SHADOW REJECTION OFF)"
              % WALL_VAL_MAX)
    print("             %d deg needs a density error of %.3f"
          % (STEER_MAX, STEER_MAX / WALL_GAIN))
    print("  lines      blue>%d px   orange>%d px   blanking=%.2f s"
          % (blue_line_threshould, orange_line_threshould, LINE_BLANK_S))
    print("             blue   H %d-%d  S>%d  V %d-%d"
          % (BLUE_HUE_MIN, BLUE_HUE_MAX, BLUE_SAT_MIN,
             BLUE_VAL_MIN, BLUE_VAL_MAX))
    print("             orange H %d-%d  S>%d  V %d-%d"
          % (ORANGE_HUE_MIN, ORANGE_HUE_MAX, ORANGE_SAT_MIN,
             ORANGE_VAL_MIN, ORANGE_VAL_MAX))
    print("  finish     drive on %.1f s after the 12th quadrant" % FINISH_RUN_S)
    print("  logging    logs/open_<timestamp>.csv, every cycle")
    print("=" * 78)


def main():
    global STOP, cycle_count, raw_frame, frame, picam2, motor1_pwm, motor2_pwm, servo_pwm, _t0
    #setup the hardware
    Setup_GPIO()
    #setup the camera instance
    picam2 = Setup_Camera()
    #print all our tunable parameters so we can see them on logs.
    print_config()
    print("Open Challenge ready. PRESS THE BUTTON to start...")
    while not is_button_down():
        time.sleep(0.01)
    while is_button_down():
        time.sleep(0.01)
    print("  GO")

    _open_log()
    start = time.time()
    _t0 = start
    button_sum = 0
    cycle(picam2)
    motor(speed)
    stop_time = None
    while not STOP:
        cycle(picam2)
        if STOP and stop_time is None:
            stop_time =time.time()
        if stop_time is not None and time.time()- stop_time >= 10:
            break
        if is_button_down():
            button_sum += 1
            print(">>> BUTTON PRESSED - emergency stop")
            break                # PORTED: the button is also the emergency stop
    motor(0)
    servo(0)


    end = time.time()
    duration = end - start
    full_time = duration * 1000.0

    print("\n")
    print("time         : {:.3f} s".format(full_time / 1000.0))
    print("cycle amount : {} cycles".format(cycle_count))
    print("speed        : {:.3f} ms / cycle".format(full_time / cycle_count if cycle_count else 0))

    # Save extra imagery outputs
    hsv_mat = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    extra_imagery(hsv_mat)
    cv2.imwrite("input.png", raw_frame)
    cv2.imwrite("frame.png", frame)

    # PORTED: keep the timestamped log, and copy it to the familiar name.
    if logfile is not None:
        logfile.close()
        try:
            shutil.copy(LOG_PATH, "open_log.csv")
        except Exception:
            pass
        print("log saved: %s  (also copied to open_log.csv)" % LOG_PATH)

    # PORTED: stop driving the servo before letting go of the pins.
    if _pi is not None:
        _pi.set_servo_pulsewidth(SERVO_PIN, 0)
        _pi.stop()
    GPIO.cleanup()               # PORTED: leave the pins in a sane state
    sys.exit(0)


# PORTED: theirs called main() unconditionally, so merely IMPORTING this
# file started the car. The guard changes nothing when it is run as a
# script - it just lets the tools and the test suite read the tunables.
if __name__ == "__main__":
    main()
