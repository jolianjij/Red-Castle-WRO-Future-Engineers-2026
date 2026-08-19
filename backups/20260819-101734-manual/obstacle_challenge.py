#!/usr/bin/env python3
"""
obstacle_challenge.py - the team's PROVEN obstacle program, ported to this car.

This is "promad obstacle.py" with its LOGIC AND STRUCTURE UNCHANGED. Same
functions, same order, same control law, same constants, same parking exit.
The only edits are the ones this car physically forces, and every one is marked

    PORTED:

so you can find them all with a single search.

Run:  cd ~/wro2026 && source .venv/bin/activate && python obstacle_challenge.py
"""
import cv2
import sys

# PORTED: over SSH stdout is a PIPE and Python block-buffers pipes, so a run
# that is killed or watched live shows NOTHING. Line buffering fixes that
# however the program is launched.
try:
    sys.stdout.reconfigure(line_buffering=True)
except AttributeError:
    pass
import numpy as np
import time
from picamera2 import Picamera2
from libcamera import Transform            # PORTED: our camera is upside down
import RPi.GPIO as GPIO
from array import array
import csv
import os
import shutil
from numpy.lib.stride_tricks import sliding_window_view as _swv
# PORTED: `import board` / `import neopixel` removed - no LED on this car.

#two new var
green_start_timer = None
red_start_timer = None
#parking out
purple_left=0.0
purple_right=0.0
Zaid=False

# ==========================================================================
# TUNABLES - the only numbers you should need to change
# ==========================================================================
# PORTED: our pin map (was SERVO 23, MOTOR 27/22, BUTTON 9)
SERVO_PIN = 13
MOTOR_IN1 = 24          # PWM here = FORWARD
MOTOR_IN2 = 23
BUTTON_PIN = 19

# PORTED: their servo centred on 105 with a deviation of 50. OUR ACKERMANN
# LINKAGE STOPS AT 35 DEGREES - commanding more drives the servo into its own
# mechanical stop and it stalls there, drawing current and buzzing. Centre is
# 90 plus our measured trim.
SERVO_CENTER = 90
SERVO_TRIM = -9.0
STEER_DEVIATION = 35

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

# PORTED: WHAT THE SHAKE ACTUALLY WAS - proven on this car with
# tools/servo_jitter.py, holding ONE CONSTANT ANGLE three ways:
#     RPi.GPIO, pulse held      -> buzzed
#     RPi.GPIO, pulse released  -> buzzed        (their original behaviour)
#     pigpio, DMA-timed         -> SILENT
# RPi.GPIO makes PWM in SOFTWARE from a Python thread, so every scheduling
# hiccup moves the pulse edge; 100 us of jitter on a 1.5 ms pulse is about 9
# degrees. No amount of command smoothing can fix that. GPIO13 is a hardware
# PWM pin and pigpio times it by DMA.
#   needs:  sudo systemctl enable --now pigpiod
# Falls back to RPi.GPIO automatically, loudly, if the daemon is down.
SERVO_BACKEND = "pigpio"
SERVO_SMOOTH = 0.35      # exponential average on the command; 1.0 = raw
SERVO_DEADBAND = 0.8     # deg - below this the pulse is not rewritten

# PORTED: THE 20 DEGREE RULE. config.py has always said STEER_MAX=20 is the
# software limit for ordinary driving and STEER_MECH_MAX=35 is the linkage's
# real stop. Their code had no such split - it clamped everything at its
# deviation - so wall following and sign following could command the full 35.
# Normal steering is clamped to STEER_MAX; the corner kick, the parking
# alignment and the final manoeuvre pass limit=STEER_DEVIATION explicitly,
# because those are the special cases the rule exists to make room for.
STEER_MAX = 20


speed=0

# PORTED: our camera is fixed, mounted UPSIDE DOWN, and must have exposure and
# white balance LOCKED - on auto they drift and move every threshold below.
CAM_FLIP_180 = True
CAM_EXPOSURE_US = 12000
CAM_GAIN = 8.0
CAM_COLOUR_GAINS = (1.329, 1.446)
CAM_SATURATION = 1.3
CAM_CONTRAST = 1.1
# PORTED: their process_frame rotated the crop 180 because their camera was not
# flipped in hardware. Ours is. Verified by correlating the column brightness
# profile against our proven pipeline: False +0.803, True -0.466.
ROTATE_180 = False

# PORTED: how far down the raw frame the crop starts. Theirs was 240 (the
# bottom half). Ours needs 160 - see process_frame for the measurement.
CROP_TOP = 160

# PORTED: colour tests. Theirs are kept EXCEPT the blue saturation floor: at 60
# it matched OUR MAT, which reads S~68 against the blue line's S~238 - and the
# mat is five times bigger than the line, so the count measured the floor.
RED_SAT_MIN, RED_VAL_MIN, RED_VAL_MAX = 120, 60, 240
# PORTED: RED'S UPPER WRAP IS OFF. MEASURED in the start box, the magenta
# parking wall runs to H179 (p50=174, p95=179, p99=179) - and red's `h > 175`
# claimed 4558 px of that WALL as a sign. Our red cube measures H0-7 (p50=7),
# nowhere near the wrap, so the upper branch was buying nothing and costing the
# whole top of the parking wall. 179 disables it: h > 179 can never be true.
RED_HUE_LO, RED_HUE_HI = 15, 179          # hue < 15 only
# PORTED: MEASURED on the green cube on our field, and this is why the car
# never reacted to green. The cube is DARK here - its V runs p50=38, p95=56,
# p99=61 - so their floor of 60 kept SIXTEEN of its 1107 pixels. One percent.
# Green never reached PARALELIPIPED_MIN_AREA, so no green target was ever
# built and the sign law never saw one. Red, at the same distance, measured
# 1222 px and worked fine, which is what made it look like a green-specific
# problem: it was.
#     GREEN_VAL_MIN  60 -> 25   keeps 1088 of 1107 (98%)
# The saturation floor goes UP at the same time, because our MAT sits at
# H70-79 - inside the green hue band - so saturation is the only thing
# separating cube from floor. MEASURED: mat p99=146, cube p01=157, a clean gap.
#     GREEN_SAT_MIN 120 -> 150  cube 1088 px, mat leak ZERO (at 120: 61 px)
GREEN_SAT_MIN, GREEN_VAL_MIN, GREEN_VAL_MAX = 150, 25, 240
GREEN_HUE_MIN, GREEN_HUE_MAX = 45, 90
# PORTED: MEASURED on the parking wall from the start box. The wall is 20226
# px and the mask was catching 11005 - barely half - in two separate ways:
#   H <= 175 threw away 4558 px, because the wall runs to H179 (p95=179).
#            Those are the same pixels red was claiming as a sign.
#   V >  60  kept only 77% of it. The wall is DARK: V p01=45 p05=52 p50=67.
#            V>40 keeps 99%.
# Saturation stays at 120: the wall reads S p01=127 p05=143, so 120 already
# clears it, and lowering it only invites the mat back in.
PURPLE_SAT_MIN, PURPLE_VAL_MIN, PURPLE_VAL_MAX = 120, 40, 240
PURPLE_HUE_MIN, PURPLE_HUE_MAX = 135, 179
BLUE_SAT_MIN, BLUE_VAL_MIN, BLUE_VAL_MAX = 140, 20, 200   # PORTED: 60 -> 140
BLUE_HUE_MIN, BLUE_HUE_MAX = 90, 135
ORANGE_SAT_MIN, ORANGE_VAL_MIN, ORANGE_VAL_MAX = 70, 30, 240
ORANGE_HUE_MIN, ORANGE_HUE_MAX = 0, 30
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
WALL_VAL_MAX = 70            # LEGACY single test, used only if shadow
                             # rejection below is turned OFF

# --------------------------------------------------
# WALL DETECTION - the shadow fix, same as open_challenge.py
# A bare  v < 70  counts ANY dark pixel as wall, and a shadow lying on the mat
# is exactly that. Two independent halves:
#   1. A TWO-CASE test. Saturation is unreliable when V is tiny - a black wall
#      can report S>200 from noise - so testing S alone rejects REAL WALLS and
#      testing V alone accepts the coloured LINES.
#   2. A GEOMETRIC test: a real wall is a TALL SOLID VERTICAL RUN, a shadow is
#      a broad SHALLOW smear. Anything without a run of WALL_MIN_RUN rows goes.
WALL_SHADOW_REJECT = True
WALL_V_HARD = 32
WALL_V_SOFT = 62
WALL_S_MAX = 90
WALL_OPEN_K = 3
WALL_MIN_RUN = 6

# --------------------------------------------------
# WALL DENSITIES ARE ON A DIFFERENT SCALE FROM THEIRS.
# Their wall thresholds (0.5, 0.6, 0.8) belong to their crop, where a centred
# car read about 0.30 a side. MEASURED on ours with tools/wall_calib.py, a
# centred car reads 0.215 a side - so every one of their numbers is roughly
# 40% too high here, and the branches guarded by them fire late or never.
# These are their values rescaled by the measured ratio 0.215/0.30.
WALL_CENTRED = 0.215     # MEASURED, car parked centred, both directions
WALL_CLOSE = 0.43        # was 0.6  - "getting close to that wall"
WALL_NEAR = 0.36         # was 0.5  - "very close, override"
PARK_WALL_TARGET = 0.57  # was 0.8  - the density to hold while parking
PARK_ALIGN_TOTAL = 0.57  # was 0.8  - left+right sum that means "aligned"

# --------------------------------------------------
# SIGN FOLLOWING - THE VERTICAL AXIS WAS INVERTED BY THE PORT.
#
# Their process_frame filled the output buffer BACKWARDS (f started at the end
# and decremented), which rotates the crop 180 degrees. Ours does not, because
# our camera is flipped in HARDWARE instead. The ROTATE_180 check that was done
# correlated COLUMN profiles - it verified left/right and never touched rows.
#
#     their row y <-> raw row r :  y = 119 - (r-240)/2     y=0   is NEAREST
#     our   row y <-> raw row r :  y = (r-160)*0.375       y=0   is FURTHEST
#
# Their law uses y as a DISTANCE term - "the further the pillar, the further
# off-frame I aim" - so feeding it our y reads every distance BACKWARDS:
#
#     pillar at our y=119 (NEAR): their formula aims at 855, correct is 262
#     pillar at our y=30  (far) : their formula aims at 410, correct is 855
#
# That inverts the whole avoidance behaviour, and is why the car would not pass
# the green pillars properly. Converting y properly (y_theirs = 159 - 1.333*y)
# and folding the constants back gives the same law in OUR coordinates:
#
#     green target x = GREEN_NEAR + SIGN_Y_GAIN * (119 - y)
#     red   target x = RED_NEAR   - SIGN_Y_GAIN * (119 - y)
#
# Verified to reproduce their numbers exactly at every distance.
SIGN_Y_GAIN = 6.667      # their 5 per row, rescaled for our crop
GREEN_NEAR_CW = 262      # their 260 at their y=0
GREEN_NEAR_CCW = 222     # their 220 at their y=0
RED_NEAR = 118           # their 120 at their y=0

# --------------------------------------------------
# AREAS also shrink with the crop. Ours squashes 320 rows into 120 where theirs
# squashed 240 into 120, so a pillar keeps about 75% of its pixel area. Their
# area gates rescaled by that factor.
# PORTED: process_traffic_contours discards any blob that is not TALLER THAN
# WIDE, to keep the horizontal lines out. MEASURED, a cube at mid distance is
# 36 wide x 44 tall - it passes, but only by 1.22x. As a cube gets CLOSE its
# bottom runs off the frame, so its height stops growing while its width keeps
# going, and it can flip to wider-than-tall exactly when it matters most.
# Raise this if the car loses a pillar at close range; 1.0 is their behaviour.
SIGN_MAX_ASPECT = 1.0

# --------------------------------------------------
# THE PARKING EXIT DECIDES THE WHOLE LAP DIRECTION, off ONE comparison:
#     more purple on the LEFT  -> way out is RIGHT -> CW  (+1)
#     more purple on the RIGHT -> way out is LEFT  -> CCW (-1)
# Their code took that from a SINGLE frame. MEASURED in the start box the two
# sides differ by only about 1.25x, so it is a close call by geometry - the car
# sits between two walls and sees a lot of both. A close call decided on one
# frame is not worth the risk when it sets the direction for the entire run.
PARK_EXIT_FRAMES = 8       # average the purple counts over this many frames
PARK_EXIT_MIN_TOTAL = 2000 # below this the lot is not really in view
PARK_EXIT_MIN_RATIO = 1.10 # below this the two sides are too close to call

SIGN_CLOSE_AREA_CW = 750     # was 1000
SIGN_CLOSE_AREA_CCW = 1125   # was 1500
PARK_STOP_AREA = 2550        # was 3400
# ==========================================================================

LED_PIN = 10
OUTPUT = GPIO.OUT
INPUT = GPIO.IN
#
pre_line = 0
# Global variables
STOP = False
wall_aligment_state = 0
# direction swap mechanic disabled, keep structure
direction_swap_cycle_threshould = -1
direction_swap_havent_started = True

cycle_count = 0
direction = 0
quadrant_count = 0

red_index = 0
green_index = 1

R, G, B = 0, 0, 0

traffic_index_not_changed_on_cycle_12 = True

parking_near_outer_wall_setup_quadrant = 12
parking_caused_program_override_quadrant_threshould = 13
parking_wall_detected_as_a_wall_quadrant_threshould = 14

# Image variables
raw_frame = np.empty((480, 640, 3), dtype=np.uint8)
frame = np.empty((120, 320, 3), dtype=np.uint8)
hsv = np.empty((120, 320, 3), dtype=np.uint8)

# Traffic light variables
red_mask = np.zeros((120, 320), dtype=np.uint8)
green_mask = np.zeros((120, 320), dtype=np.uint8)

PARALELIPIPED_MIN_AREA = 75

last_detected_traffic_light = -1

target = array('i', [0, 0, 0, 0])  # Biggest traffic light {x, y, area, type}

red_box = []
green_box = []

# Wall variables
left_wall = 0.0
right_wall = 0.0

# Map lines variables
#
# PORTED: THEIR BLANKING WAS IN CYCLES, AND WE CHANGED THE CYCLE RATE. Theirs
# waited 20 CYCLES at about 2 Hz - some 10 seconds. Our numpy pipeline runs at
# 20-30 Hz, where 20 cycles is under a second. Now in SECONDS, so it does not
# care how fast the loop runs. MEASURED on a real run: consecutive counted
# lines are about 5.2 s apart and a crossing lasts under 0.5 s.
LINE_BLANK_S = 1.2

# PORTED: their 900/900 belong to their crop. MEASURED on ours with
# tools/line_audit.py, on a line filling the view: blue 1017-1048, orange
# 1107-1196, and on a real run the peaks reach 1900-4300. Their own thresholds
# fired at about 77% of a full line, which on our crop is these numbers. Bare
# mat reads 3-9 px blue and 0-87 px orange, so the margin below is tenfold.
blue_line_threshould = 830
orange_line_threshould = 930

blue_line_pixel_count = 0
blue_line_next_allowed_t = 0.0
orange_line_pixel_count = 0
orange_line_next_allowed_t = 0.0

blue_line_detected = False
orange_line_detected = False

blue_line_state = 0
orange_line_state = 0

# P controller variables
kp = 0.05
Err = 0
dir = 0.0

# Parking
PARKING_MIN_AREA = 1000
purple_mask = np.zeros((120, 320), dtype=np.uint8)
parking = array('i', [0, 0, 0])  # parking gate {x, y, area}
purple_box = []

# CSV logging setup
# PORTED: opened by main(), NOT at import - it used to be truncated merely by
# importing the file, which the tools and the test suite now do. And each run
# gets its OWN timestamped file, because the old single name meant the next run
# destroyed the evidence from the one that failed.
logfile = None
logwriter = None
LOG_PATH = None
_prev_t = 0.0
_t0 = 0.0
_dir_smooth = 0.0
_dir_limit = None        # raised to STEER_DEVIATION for a manoeuvre


def _open_log():
    global logfile, logwriter, LOG_PATH
    os.makedirs("logs", exist_ok=True)
    LOG_PATH = os.path.join("logs", "obstacle_%s.csv"
                            % time.strftime("%Y%m%d-%H%M%S"))
    logfile = open(LOG_PATH, "w", newline="")
    logwriter = csv.writer(logfile)
    logwriter.writerow(["cycle", "t_s", "dt_ms", "left_wall", "right_wall",
                        "blue_px", "blue_state", "orange_px", "orange_state",
                        "direction", "quadrant", "traffic_light",
                        "target_x", "target_y", "target_area", "target_type",
                        "parking_area", "purple_left", "purple_right",
                        "Err", "dir_raw", "dir_cmd"])


def print_config():
    print("=" * 78)
    print("  OBSTACLE CHALLENGE - configuration for this run")
    print("=" * 78)
    print("  steering   centre=%d  trim=%+.1f  STEER_MAX=%d (normal)  "
          "mech stop=%d" % (SERVO_CENTER, SERVO_TRIM, STEER_MAX,
                            STEER_DEVIATION))
    print("  servo      settle=%.3f s  hold=%s  smooth=%.2f  deadband=%.1f"
          % (SERVO_SETTLE_S, SERVO_HOLD, SERVO_SMOOTH, SERVO_DEADBAND))
    print("             pulse driver: %s"
          % ("pigpio, DMA-timed (steady)" if _pi is not None
             else "RPi.GPIO SOFTWARE PWM - THIS BUZZES"))
    print("  camera     flip180=%s  exposure=%d us  gain=%.1f  crop_top=%d"
          % (CAM_FLIP_180, CAM_EXPOSURE_US, CAM_GAIN, CROP_TOP))
    print("  walls      centred=%.3f  close=%.2f  near=%.2f"
          % (WALL_CENTRED, WALL_CLOSE, WALL_NEAR))
    if WALL_SHADOW_REJECT:
        print("             mask V<%d, or V<%d and S<%d; open %d; run >=%d"
              % (WALL_V_HARD, WALL_V_SOFT, WALL_S_MAX, WALL_OPEN_K,
                 WALL_MIN_RUN))
        print("             SHADOW REJECTION ON")
    else:
        print("             mask V<%d (legacy, SHADOW REJECTION OFF)"
              % WALL_VAL_MAX)
    print("  lines      blue>%d  orange>%d  blanking=%.2f s"
          % (blue_line_threshould, orange_line_threshould, LINE_BLANK_S))
    print("  signs      kp=%.3f  y_gain=%.3f  green_near CW=%d CCW=%d  red=%d"
          % (kp, SIGN_Y_GAIN, GREEN_NEAR_CW, GREEN_NEAR_CCW, RED_NEAR))
    print("             min area=%d  close area CW=%d CCW=%d"
          % (PARALELIPIPED_MIN_AREA, SIGN_CLOSE_AREA_CW, SIGN_CLOSE_AREA_CCW))
    print("  parking    min area=%d  wall target=%.2f  align total=%.2f  "
          "stop area=%d" % (PARKING_MIN_AREA, PARK_WALL_TARGET,
                            PARK_ALIGN_TOTAL, PARK_STOP_AREA))
    print("  logging    logs/obstacle_<timestamp>.csv, every cycle")
    print("=" * 78)


def LED_color(r, g, b):
    # PORTED: no NeoPixel on this car. Kept so every call site is unchanged.
    pass


def LED_hsv(hue_val, sat, val):
    # PORTED: no NeoPixel on this car. Kept so every call site is unchanged.
    pass


def is_button_down():
    # PORTED: ours is wired to GND with the internal pull-up, so PRESSED = LOW.
    # Their obstacle file already read it this way, so this matches.
    return GPIO.input(BUTTON_PIN) == 0


_last_angle = None
_pi = None                   # pigpio handle, or None for RPi.GPIO


def _write_servo(angle):
    # PORTED: both backends write the SAME pulse for the same angle. Their duty
    # ran 2.5%-12.5% at 50 Hz, and 50 Hz is a 20 ms frame, so it was always
    # really a 500-2500 us pulse across 0-180 degrees. pigpio is handed that
    # pulse directly, so the centre, the throw and SERVO_TRIM keep their exact
    # meaning - this changes how the pulse is TIMED, not what it says.
    if _pi is not None:
        _pi.set_servo_pulsewidth(SERVO_PIN, 500.0 + (angle / 180.0) * 2000.0)
    else:
        servo_pwm.ChangeDutyCycle(2.5 + (angle / 180.0) * 10.0)


def servo(angle, limit=None):
    """Set the steering angle.

    limit=None  -> the 20 degree rule, for ordinary driving.
    limit=STEER_DEVIATION -> the special manoeuvres (corner kick, parking
                             alignment, the final exit) that the rule exists
                             to make room for.
    """

    global SERVO_PIN, _last_angle

    # PORTED: THE 20 DEGREE RULE. Their code clamped everything at its
    # deviation; only the manoeuvres may go past STEER_MAX, and nothing may go
    # past the linkage's real stop.
    lim = STEER_MAX if limit is None else min(abs(limit), STEER_DEVIATION)
    if angle < -lim:
        angle = -lim
    if angle > lim:
        angle = lim

    angle += SERVO_CENTER
    angle += SERVO_TRIM

    # PORTED: DEADBAND - do not rewrite the pulse for a change too small to
    # matter. Changes still accumulate, so this cannot cause a lasting offset.
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
    GPIO.setwarnings(False)          # PORTED

    GPIO.setup(SERVO_PIN, OUTPUT)
    GPIO.setup(MOTOR_IN1, OUTPUT)
    GPIO.setup(MOTOR_IN2, OUTPUT)
    # PORTED: GPIO.setup(10, OUTPUT) was the NeoPixel data pin - not on this car
    GPIO.setup(BUTTON_PIN, INPUT, pull_up_down=GPIO.PUD_UP)   # PORTED: pull-up
    global servo_pwm, motor1_pwm, motor2_pwm, _pi
    # PORTED: prefer pigpio for the servo - see SERVO_BACKEND. It is the whole
    # reason the steering stopped buzzing.
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
    # PORTED: flipped in hardware, exposure and white balance locked
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

_WK_SQ = None


def _tall_runs(m, k):
    # Keep only pixels in a VERTICAL RUN of at least k dark pixels - the shadow
    # test. Done by hand, not with cv2 MORPH_OPEN: that erodes with an INFINITE
    # border value, so where the wall band touches the top of the frame it is
    # not eroded but the following dilation still grows it DOWNWARD, inventing
    # wall out of mat. MEASURED at ~270 px/frame of V 70-138 in open_challenge.
    # Forcing the border to 0 instead leaves the result SHIFTED, because OpenCV
    # does not reflect the kernel and this one has an even length.
    h_ = m.shape[0]
    if h_ < k:
        return np.zeros_like(m)
    er = _swv(m, k, axis=0).all(axis=-1)
    pad = np.zeros((h_ + k - 1, m.shape[1]), bool)
    pad[k - 1:k - 1 + er.shape[0]] = er
    return m & _swv(pad, k, axis=0).any(axis=-1)[:h_]


def wall_mask(h, s, v):
    global _WK_SQ
    if not WALL_SHADOW_REJECT:
        return v < WALL_VAL_MAX
    if _WK_SQ is None:
        _WK_SQ = np.ones((WALL_OPEN_K, WALL_OPEN_K), np.uint8)
    raw = ((v < WALL_V_HARD) | ((v < WALL_V_SOFT) & (s < WALL_S_MAX)))
    m = raw
    if WALL_OPEN_K > 1:
        o = cv2.morphologyEx(raw.astype(np.uint8), cv2.MORPH_OPEN, _WK_SQ) > 0
        m = o & raw                     # & raw: the border can never ADD pixels
    if WALL_MIN_RUN > 1:
        m = _tall_runs(m, WALL_MIN_RUN)
    return m


def process_hsv(hsv_arr, red_data, green_data, purple_data):
    # PORTED: identical result to their per-pixel loop, with numpy.
    global blue_line_pixel_count, orange_line_pixel_count, left_wall, right_wall,purple_left,purple_right
    global Zaid

    h = hsv_arr[:, :, 0].astype(np.int16)
    s = hsv_arr[:, :, 1].astype(np.int16)
    v = hsv_arr[:, :, 2].astype(np.int16)

    red_m = ((s > RED_SAT_MIN) & (v > RED_VAL_MIN) & (v < RED_VAL_MAX) &
             ((h < RED_HUE_LO) | (h > RED_HUE_HI)))
    green_m = ((s > GREEN_SAT_MIN) & (v > GREEN_VAL_MIN) & (v < GREEN_VAL_MAX) &
               (h > GREEN_HUE_MIN) & (h < GREEN_HUE_MAX))
    purple_m = ((s > PURPLE_SAT_MIN) & (v > PURPLE_VAL_MIN) & (v < PURPLE_VAL_MAX) &
                (h >= PURPLE_HUE_MIN) & (h <= PURPLE_HUE_MAX))

    red_data[:] = np.where(red_m, 255, 0).astype(np.uint8)
    green_data[:] = np.where(green_m, 255, 0).astype(np.uint8)
    purple_data[:] = np.where(purple_m, 255, 0).astype(np.uint8)

    blue_line_pixel_count = int(np.count_nonzero(
        (s > BLUE_SAT_MIN) & (v > BLUE_VAL_MIN) & (v < BLUE_VAL_MAX) &
        (h > BLUE_HUE_MIN) & (h < BLUE_HUE_MAX)))
    orange_line_pixel_count = int(np.count_nonzero(
        (s > ORANGE_SAT_MIN) & (v > ORANGE_VAL_MIN) & (v < ORANGE_VAL_MAX) &
        (h >= ORANGE_HUE_MIN) & (h <= ORANGE_HUE_MAX)))

    purple_left = float(np.count_nonzero(purple_m[:, :160]))
    purple_right = float(np.count_nonzero(purple_m[:, 160:]))

    dark = wall_mask(h, s, v)
    left_wall = float(np.count_nonzero(dark[:, :160]))
    right_wall = float(np.count_nonzero(dark[:, 160:]))

    # their extra: purple counts as wall too, before the parking quadrant
    if quadrant_count < parking_wall_detected_as_a_wall_quadrant_threshould and Zaid:
        pw = purple_m & (v >= 70)
        left_wall += 0.8 * float(np.count_nonzero(pw[:, :160]))
        right_wall += 0.8 * float(np.count_nonzero(pw[:, 160:]))

    left_wall /= (160 * 80)
    right_wall /= (160 * 80)


def update_lines():
    global blue_line_state, blue_line_detected, blue_line_next_allowed_t
    global orange_line_state, orange_line_detected, orange_line_next_allowed_t
    global cycle_count,pre_line,direction

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


def process_traffic_contours(box, type_idx):
    global target
    for contour in box:
        area = cv2.contourArea(contour)
        if area > target[2]:
            boundingBox = cv2.boundingRect(contour)
            if boundingBox[2] < SIGN_MAX_ASPECT * boundingBox[3]:
                moments = cv2.moments(contour)
                if moments['m00'] != 0:
                    x = int(moments['m10'] / moments['m00'])
                    y = int(moments['m01'] / moments['m00'])
                    target = array('i', [x, y, int(area), type_idx])


def process_parking_contours(box):
    global parking
    for contour in box:
        area = cv2.contourArea(contour)
        if area > parking[2]:
            moments = cv2.moments(contour)
            if moments['m00'] != 0:
                x = int(moments['m10'] / moments['m00'])
                y = int(moments['m01'] / moments['m00'])
                parking = array('i', [x, y, int(area)])


def draw(frame, box_red, box_grn):
    for i, contour in enumerate(box_red):
        area = cv2.contourArea(contour)
        if area > PARALELIPIPED_MIN_AREA:
            cv2.drawContours(frame, box_red, i, (0, 0, 255), 2)
            moments = cv2.moments(contour)
            if moments['m00'] != 0:
                center = (int(moments['m10'] / moments['m00']), int(moments['m01'] / moments['m00']))
                cv2.circle(frame, center, 5, (0, 0, 255), -1)
            boundingBox = cv2.boundingRect(contour)
            if boundingBox[2] < boundingBox[3]:
                cv2.rectangle(frame, (boundingBox[0], boundingBox[1]),
                             (boundingBox[0] + boundingBox[2], boundingBox[1] + boundingBox[3]),
                             (0, 0, 255), 3)
            else:
                cv2.rectangle(frame, (boundingBox[0], boundingBox[1]),
                             (boundingBox[0] + boundingBox[2], boundingBox[1] + boundingBox[3]),
                             (255, 0, 122), 3)

    for i, contour in enumerate(box_grn):
        area = cv2.contourArea(contour)
        if area > PARALELIPIPED_MIN_AREA:
            cv2.drawContours(frame, box_grn, i, (0, 255, 0), 2)
            moments = cv2.moments(contour)
            if moments['m00'] != 0:
                center = (int(moments['m10'] / moments['m00']), int(moments['m01'] / moments['m00']))
                cv2.circle(frame, center, 5, (0, 255, 0), -1)
            boundingBox = cv2.boundingRect(contour)
            if boundingBox[2] < boundingBox[3]:
                cv2.rectangle(frame, (boundingBox[0], boundingBox[1]),
                             (boundingBox[0] + boundingBox[2], boundingBox[1] + boundingBox[3]),
                             (0, 255, 0), 3)
            else:
                cv2.rectangle(frame, (boundingBox[0], boundingBox[1]),
                             (boundingBox[0] + boundingBox[2], boundingBox[1] + boundingBox[3]),
                             (255, 122, 0), 3)


def extra_imagery(hsv_arr):
    # PORTED: same three images, numpy instead of a per-pixel loop
    h = hsv_arr[:, :, 0].astype(np.int16)
    s = hsv_arr[:, :, 1].astype(np.int16)
    v = hsv_arr[:, :, 2].astype(np.int16)
    blue_mask = np.where(
        (s > BLUE_SAT_MIN) & (v > BLUE_VAL_MIN) & (v < BLUE_VAL_MAX) &
        (h > BLUE_HUE_MIN) & (h < BLUE_HUE_MAX), 255, 0).astype(np.uint8)
    orange_mask = np.where(
        (s > ORANGE_SAT_MIN) & (v > ORANGE_VAL_MIN) & (v < ORANGE_VAL_MAX) &
        (h >= ORANGE_HUE_MIN) & (h <= ORANGE_HUE_MAX), 255, 0).astype(np.uint8)
    walls = np.where(wall_mask(h, s, v), 255, 0).astype(np.uint8)
    cv2.imwrite("blue.png", blue_mask)
    cv2.imwrite("orange.png", orange_mask)
    cv2.imwrite("walls.png", walls)


def cycle(picam2):
    global R, G, B, cycle_count, dir, target, parking, red_box, green_box, purple_box
    global Err, last_detected_traffic_light, quadrant_count, direction ,green_start_timer
    global red_index, green_index, traffic_index_not_changed_on_cycle_12 ,red_start_timer
    global direction_swap_havent_started, direction_swap_cycle_threshould
    global STOP, wall_aligment_state, raw_frame, frame, hsv,Zaid,pre_line

    R, G, B = 122, 122, 122
    cycle_count += 1
    dir = 0.0
    global _dir_limit
    _dir_limit = None            # PORTED: the 20 degree rule, unless a
                                 # manoeuvre below raises it for this cycle

    target = array('i', [160, 0, PARALELIPIPED_MIN_AREA, -1])
    parking = array('i', [160, 0, PARKING_MIN_AREA])

    raw = capture_array(picam2)
    raw_frame[:] = raw
    frame = np.empty((120, 320, 3), dtype=np.uint8)
    process_frame(raw_frame, frame)
    hsv_mat = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    process_hsv(hsv_mat, red_mask, green_mask, purple_mask)

    red_box, _ = cv2.findContours(red_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    green_box, _ = cv2.findContours(green_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    purple_box, _ = cv2.findContours(purple_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    process_traffic_contours(red_box, red_index)
    process_traffic_contours(green_box, green_index)
    process_parking_contours(purple_box)

    update_lines()

    if blue_line_state != 0 and direction == 0:
        direction = -1
    if orange_line_state != 0 and direction == 0:
        direction = 1

    if direction >= 0:
        if orange_line_state == 2:
            quadrant_count += 1
        if blue_line_state ==2:
            pre_line +=1
        quadrant_count = max(quadrant_count,pre_line)
    else:
        if blue_line_state == 2:
            quadrant_count += 1
        if orange_line_state == 2:
            pre_line +=1
        quadrant_count = max(quadrant_count,pre_line)
    #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    # PORTED: THE SAME LAW, WITH THE VERTICAL AXIS PUT BACK THE RIGHT WAY UP.
    # Their y=0 was the NEAREST ground; ours is the FURTHEST - see the SIGN
    # FOLLOWING block at the top. `_d` is the distance term their `target[1]*5`
    # was, expressed in our coordinates.
    _d = SIGN_Y_GAIN * (119 - target[1])
    if direction >= 0:
        if target[3] in [1, 2]:  # Green
            Err = -((GREEN_NEAR_CW + _d) - target[0])
            if target[0] > 220:
                Err = 0
            if target[2] > SIGN_CLOSE_AREA_CW:
                last_detected_traffic_light = 1
        elif target[3] in [0, 3]:  # Red
            Err = (target[0] - (RED_NEAR - _d))
            if target[2] > SIGN_CLOSE_AREA_CW:
                last_detected_traffic_light = 0
                red_start_timer =time.time()
        else:
            Err = 0
    if direction < 0:
        if target[3] in [1, 2]:  # Green
            Err = -((GREEN_NEAR_CCW + _d) - target[0])
            if target[2] > SIGN_CLOSE_AREA_CCW:
                last_detected_traffic_light = 1
                green_start_timer = time.time()
        elif target[3] in [0, 3]:  # Red
            Err = (target[0] - (RED_NEAR - _d))
            if target[0] < 90:
                Err = 0
            if target[2] > SIGN_CLOSE_AREA_CCW:
                last_detected_traffic_light = 0

        else:
            Err = 0
    if last_detected_traffic_light == 0 and red_start_timer is not None and direction == 1:
        if time.time() - red_start_timer >= 2.5:   # 5 seconds passed
            last_detected_traffic_light = 1
            print(time.time() - red_start_timer)
            red_start_timer = None
    if last_detected_traffic_light ==1 and green_start_timer is not None and direction ==-1:
        if time.time() - green_start_timer >= 2.5:   # 5 seconds passed
            last_detected_traffic_light = 0
            green_start_timer = None
            print("Traffic light back to Red (default)")

    if target[3] % 2 == 1:
        R, G, B = 0, 255, 0
    if target[3] % 2 == 0:
        R, G, B = 255, 0, 0
    if blue_line_state != 0:
        R, G, B = 0, 0, 255
    if orange_line_state != 0:
        R, G, B = 255, 122, 0

    dir = Err * kp
    # check if we need to return to green
    # PORTED: their 0.6 is WALL_CLOSE here - see the WALL DENSITIES block. On
    # our scale 0.6 is nearly three times a centred reading, so these branches
    # fired far too late or not at all.
    if direction >= 0:
        if last_detected_traffic_light == 0:
            if right_wall > WALL_CLOSE:
                dir = -40*right_wall
        else:
            if left_wall > WALL_CLOSE:
                dir = 30*left_wall
            elif right_wall > WALL_CLOSE:
                dir =-30*right_wall
        if last_detected_traffic_light ==1 and orange_line_state==2:
            servo(45, limit=STEER_DEVIATION)     # PORTED: the corner kick
            time.sleep(0.7)
    else:
        if last_detected_traffic_light == 1:
            if left_wall > WALL_CLOSE:
                dir = 40*left_wall
        else:
            # PORTED: THEIR TYPO. This pair tested one wall and scaled the
            # steering by the OTHER one, so a car hard against the right wall
            # with a clear left side was pushed away by almost nothing. The
            # matching CW branch above is written correctly, which is what
            # makes it a slip rather than a design. Set WALL_MISMATCH_BUG_KEPT
            # to restore it verbatim if this ever needs comparing.
            if right_wall > WALL_CLOSE:
                dir = -30*right_wall
            elif left_wall > WALL_CLOSE:
                dir = 30*left_wall
        if last_detected_traffic_light ==0 and blue_line_state==2:
            servo(-45, limit=STEER_DEVIATION)    # PORTED: the corner kick
            time.sleep(0.7)
    # --- Disabled swap mechanic ---
    # if quadrant_count == 8 and direction_swap_havent_started:
    #     direction *= -1
    #     direction_swap_cycle_threshould = cycle_count + 20
    #     direction_swap_havent_started = False

    # if cycle_count < direction_swap_cycle_threshould:
    #     dir = 45 if direction >= 0 else -45
    # --------------------------------

    if (quadrant_count == parking_near_outer_wall_setup_quadrant and
            traffic_index_not_changed_on_cycle_12 and abs(dir) < 15):
        if direction == 1:
            red_index = 2
        if direction == -1:
            green_index = 3
        traffic_index_not_changed_on_cycle_12 = False
        motor(60)  # Scale back to 0-255 range

    # Enter parking mode at quadrant >= 12
    if quadrant_count >= 12:
        if wall_aligment_state == 0:
            dir = 0
            if left_wall + right_wall > PARK_ALIGN_TOTAL:
                wall_aligment_state = 1
        else:
            # PORTED: their 0.8 and 0.5 rescaled to our densities, and the
            # hard 45s allowed past the 20 degree rule because parking IS one
            # of the manoeuvres the rule exists to make room for.
            if direction >= 0:
                dir = (left_wall - PARK_WALL_TARGET) * 50
                if right_wall > WALL_NEAR:
                    dir = 45
                    _dir_limit = STEER_DEVIATION
            else:
                dir = (PARK_WALL_TARGET - right_wall) * 50
                if left_wall > WALL_NEAR:
                    dir = -45
                    _dir_limit = STEER_DEVIATION

            if parking[2] > PARK_STOP_AREA:
                STOP = True

            R, G, B = 255, 0, 255
    # PORTED: the 20 degree rule, then the smoothing. A MANOEUVRE (the corner
    # kick, parking) skips both - it is a deliberate hard command and lagging
    # it through an exponential average would blunt exactly the move that has
    # to be sharp.
    global _dir_smooth, _prev_t
    dir_raw = dir
    if _dir_limit is not None and _dir_limit > STEER_MAX:
        dir_cmd = dir
        _dir_smooth = dir
    else:
        dir_cmd = max(-STEER_MAX, min(STEER_MAX, dir))
        _dir_smooth = SERVO_SMOOTH * dir_cmd + (1.0 - SERVO_SMOOTH) * _dir_smooth
        dir_cmd = _dir_smooth

    # PORTED: FULL per-cycle log - everything the controller looked at and
    # everything it decided, so a bad run can be read instead of guessed at.
    now = time.time()
    dt = (now - _prev_t) if _prev_t else 0.0
    _prev_t = now
    tname = {0: "RED  ", 1: "GREEN", 2: "RED2 ", 3: "GRN2 ", -1: "  -  "}.get(
        target[3], "?")
    print("c%-5d t=%6.2f %4.1fHz | L=%.3f R=%.3f | blu=%5d s%d org=%5d s%d | "
          "D=%+d q=%2d | %s x=%3d y=%3d a=%5d | tl=%+d | Err=%+7.1f "
          "raw=%+6.1f cmd=%+6.1f%s"
          % (cycle_count, now - _t0, (1.0 / dt) if dt > 0 else 0.0,
             left_wall, right_wall,
             blue_line_pixel_count, blue_line_state,
             orange_line_pixel_count, orange_line_state,
             direction, quadrant_count, tname,
             target[0], target[1], target[2],
             last_detected_traffic_light, Err, dir_raw, dir_cmd,
             "  MANOEUVRE" if (_dir_limit is not None
                               and _dir_limit > STEER_MAX) else ""))

    if logwriter is not None:
        logwriter.writerow([cycle_count, round(now - _t0, 3),
                            round(dt * 1000, 2),
                            round(left_wall, 4), round(right_wall, 4),
                            blue_line_pixel_count, blue_line_state,
                            orange_line_pixel_count, orange_line_state,
                            direction, quadrant_count,
                            last_detected_traffic_light,
                            target[0], target[1], target[2], target[3],
                            parking[2], round(purple_left, 1),
                            round(purple_right, 1),
                            round(Err, 2), round(dir_raw, 2),
                            round(dir_cmd, 2)])
        logfile.flush()

    servo(dir_cmd, limit=_dir_limit)
    LED_color(R, G, B)


def main():
    global STOP, cycle_count, raw_frame, frame, hsv, red_mask, green_mask, purple_mask,Zaid
    global servo_pwm, motor_pwm, picam2, direction

    global _t0
    Setup_GPIO()
    picam2 = Setup_Camera()
    LED_hsv(0, 255, 255)  # Initial blue
    _open_log()
    print_config()

    button_sum = 0

    # PORTED: wait for the button before anything moves. Their program drove off
    # immediately; the rules want the car still until it is pressed.
    print("Obstacle Challenge ready. PRESS THE BUTTON to start...")
    while not is_button_down():
        time.sleep(0.01)
    while is_button_down():
        time.sleep(0.01)
    print("  GO")

    start = time.time()
    _t0 = start

    # PORTED: average the purple counts over several frames instead of
    # deciding the whole run's direction from one. See PARK_EXIT_FRAMES.
    pl = pr = 0.0
    for _ in range(PARK_EXIT_FRAMES):
        cycle(picam2)
        pl += purple_left
        pr += purple_right
    pl /= PARK_EXIT_FRAMES
    pr /= PARK_EXIT_FRAMES
    ratio = max(pl, pr) / max(1.0, min(pl, pr))

    # PORTED: the parking exit is a MANOEUVRE - it passes limit explicitly so
    # the 20 degree rule does not blunt it. More purple on the LEFT means the
    # way out is to the right, which sets the lap direction clockwise.
    print(">>> parking exit: purple left=%.0f right=%.0f (ratio %.2f over %d "
          "frames) -> %s"
          % (pl, pr, ratio, PARK_EXIT_FRAMES,
             "CW (+1), out to the RIGHT" if pl > pr else "CCW (-1), out to the LEFT"))
    # PORTED: SAY IT WHEN THE DECISION IS NOT REALLY A DECISION. The comparison
    # is `left > right`, so with NO purple at all that is False and the car
    # silently commits to CCW - it looks like a choice and is really a default.
    if pl + pr < PARK_EXIT_MIN_TOTAL:
        print("!!! ALMOST NO PURPLE IN VIEW (%.0f px total, want %d)."
              % (pl + pr, PARK_EXIT_MIN_TOTAL))
        print("    The direction was NOT chosen from the parking lot - it fell")
        print("    through to CCW. Check the car can see the magenta walls.")
    elif ratio < PARK_EXIT_MIN_RATIO:
        print("!!! THE TWO SIDES ARE TOO CLOSE TO CALL (ratio %.2f, want %.2f)."
              % (ratio, PARK_EXIT_MIN_RATIO))
        print("    This direction is close to a coin toss. Re-place the car so")
        print("    one side clearly wins, or check with tools/park_calib.py.")
    if pl > pr:
        direction=1
        motor(50)
        servo(45, limit=STEER_DEVIATION)
        time.sleep(0.7)
        Zaid=True
        servo(-35, limit=STEER_DEVIATION)
        time.sleep(0.7)
    else:
        direction=-1
        motor(50)
        servo(-45, limit=STEER_DEVIATION)
        time.sleep(0.6)
        Zaid=True
        servo(35, limit=STEER_DEVIATION)
        time.sleep(0.9)
    LED_hsv(85, 255, 255)  # Green for startScale to 0-255 range
    servo(0)
    motor(50)
    while not STOP:
        cycle(picam2)
        print(purple_right,purple_left)
        if is_button_down():
            button_sum += 1
            break                # PORTED: the button is also the emergency stop

    if button_sum < 30:
        motor(0.5 * 255)  # Scale to 0-255 range
        # PORTED: the final park-in manoeuvre, also allowed past 20 degrees
        if direction >= 0:
            servo(30, limit=STEER_DEVIATION)
            time.sleep(0.45)
            servo(-30, limit=STEER_DEVIATION)
            time.sleep(1.3)
            servo(0)
            time.sleep(0.3)
        else:
            motor(0.5 * 255)
            servo(-30, limit=STEER_DEVIATION)
            time.sleep(0.45)
            servo(30, limit=STEER_DEVIATION)
            time.sleep(1.3)
            servo(0)
            time.sleep(0.3)

    motor(0)
    servo(0)
    LED_hsv(0, 255, 255)  # Back to blue

    end = time.time()
    full_time = (end - start) * 1000.0

    print("\n")
    print(f"time         : {full_time / 1000.0:.3f} s")
    print(f"cycle amount : {cycle_count} cycles")
    print(f"speed        : {full_time / cycle_count if cycle_count else 0:.3f} ms / cycle")

    hsv_mat = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    extra_imagery(hsv_mat)
    draw(frame, red_box, green_box)
    cv2.imwrite("input.png", raw_frame)
    cv2.imwrite("frame.png", frame)
    cv2.imwrite("red.png", red_mask)
    cv2.imwrite("green.png", green_mask)
    cv2.imwrite("purple.png", purple_mask)

    # PORTED: their final "press to exit" loop spun with no delay, pinning a
    # core. Same behaviour, but it sleeps between polls.
    button_sum = 0
    while button_sum < 10:
        if is_button_down():
            button_sum += 1
        time.sleep(0.01)

    # PORTED: keep the timestamped log, and copy it to the familiar name.
    if logfile is not None:
        logfile.close()
        try:
            shutil.copy(LOG_PATH, "robot_log.csv")
        except Exception:
            pass
        print("log saved: %s  (also copied to robot_log.csv)" % LOG_PATH)

    LED_hsv(0, 0, 0)  # Off
    picam2.close()
    # PORTED: stop driving the servo before letting go of the pins
    if _pi is not None:
        _pi.set_servo_pulsewidth(SERVO_PIN, 0)
        _pi.stop()
    GPIO.cleanup()
    sys.exit(0)


# PORTED: theirs called main() unconditionally, so merely IMPORTING this
# file started the car. The guard changes nothing when it is run as a
# script - it just lets the tools and the test suite read the tunables.
if __name__ == "__main__":
    main()
