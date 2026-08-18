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

import cv2
import sys
import numpy as np
import time
from picamera2 import Picamera2, Preview
from libcamera import Transform            # PORTED: our camera is mounted upside down
import RPi.GPIO as GPIO
# PORTED: no NeoPixel on this car. `import board` and `import neopixel` are gone
#         and the LED functions below are no-ops, so every call site still works.

# ==========================================================================
# TUNABLES - the only numbers you should need to change
# ==========================================================================

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


speed = 100

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

# --------------------------------------------------
# Map lines variables
line_cycle_delay = 15

# PORTED: line thresholds are PIXEL COUNTS out of 38400 and belong to the
# camera that measured them. Re-measure with tools/line_check.py.
blue_line_threshould = 1100
orange_line_threshould = 1300

# PORTED: their colour tests, with OUR measured saturation floors.
# Theirs used sat > 60 for blue. On our camera the MAT reads S~68 and the blue
# LINE reads S~238, so a floor of 60 matched the floor itself - and the mat is
# five times bigger than the line, so the count measured the mat.
BLUE_SAT_MIN, BLUE_VAL_MIN, BLUE_VAL_MAX = 140, 70, 200
BLUE_HUE_MIN, BLUE_HUE_MAX = 90, 135
ORANGE_SAT_MIN, ORANGE_VAL_MIN, ORANGE_VAL_MAX = 70, 30, 240
ORANGE_HUE_MIN, ORANGE_HUE_MAX = 0, 30
# PORTED: ORANGE'S BRIGHTNESS FLOOR. Theirs demanded V > 125. MEASURED on our
# field, the orange line is a clear 1648 px 320x19 band at S~178 - but its
# V median is 78 and its p95 only 106, because our whole frame tops out at
# V=143 where theirs was brighter. Their floor made orange UNREACHABLE, so the
# direction could never lock CW and every run fell to blue and went CCW.
# Hue alone separates orange from the mat here anyway - orange H~13 against the
# mat's H~70 - so the brightness floor was never doing the work.
WALL_VAL_MAX = 70            # a pixel darker than this is wall

# --------------------------------------------------
# P controller variables
kp = 0.25
# ==========================================================================

OUTPUT = GPIO.OUT
INPUT = GPIO.IN
# --------------------------------------------------

STOP = False
mission_end_cycle = int(1e9)
mission_end_not_activated = True

cycle_count = 0
direction = 0
quadrant_count = 0

hue = 0

# --------------------------------------------------
# Image variables

raw_frame = np.empty((480, 640, 3), dtype=np.uint8)
frame = np.empty((120, 320, 3), dtype=np.uint8)
hsv = np.empty((120, 320, 3), dtype=np.uint8)

# --------------------------------------------------
# Wall variables

left_wall = 0.0
right_wall = 0.0

# --------------------------------------------------

blue_line_pixel_count = 0
blue_line_next_allowed_cycle = 0

orange_line_pixel_count = 0
orange_line_next_allowed_cycle = 0

blue_line_detected = False
orange_line_detected = False

blue_line_state = 0
orange_line_state = 0

Err = 0
dir = 0.0


# PORTED: log every cycle, so a bad run can be read afterwards instead of
# guessed at. Their open file wrote nothing.
import csv
logfile = open("open_log.csv", "w", newline="")
logwriter = csv.writer(logfile)
logwriter.writerow(["cycle", "dir", "left_wall", "right_wall",
                    "blue", "orange", "direction", "quadrant"])


# --------------------------------------------------
def is_button_down():
    # PORTED: our button is wired to GND with the internal pull-up, so PRESSED
    # reads LOW. Theirs read HIGH. Same function, opposite sense.
    return GPIO.input(BUTTON_PIN) == 0


def LED_color(r, g, b):
    # PORTED: no NeoPixel on this car. Kept so every call site is unchanged.
    pass


def LED_hsv(hue_val, sat, val):
    # PORTED: no NeoPixel on this car. Kept so every call site is unchanged.
    pass


def servo(angle):
    """Adjust and set the servo angle using RPi.GPIO."""

    global SERVO_PIN

    angle += 90
    deviation = STEER_DEVIATION      # PORTED: was 45; our linkage stops at 35
    if angle < 90 - deviation:
        angle = 90 - deviation
    if angle > 90 + deviation:
        angle = 90 + deviation
    angle += SERVO_TRIM          # PORTED: was `angle += 0`

    min_duty = 2.5  # Duty cycle for 0 degrees
    max_duty = 12.5 # Duty cycle for 180 degrees

    duty_range = max_duty - min_duty
    duty = min_duty + (angle / 180.0) * duty_range

    servo_pwm.ChangeDutyCycle(duty)
    time.sleep(SERVO_SETTLE_S)          # PORTED: was 0.1 - see SERVO_SETTLE_S
    if not SERVO_HOLD:                  # PORTED: theirs always released here
        servo_pwm.ChangeDutyCycle(0)


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
    global servo_pwm, motor1_pwm, motor2_pwm
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

    dark = v < WALL_VAL_MAX
    left_wall = float(np.count_nonzero(dark[:, :160]))
    right_wall = float(np.count_nonzero(dark[:, 160:]))

    left_wall /= (12800)                       #answer for 160 * 80
    right_wall /= (12800)                      #answer for 160 * 80


def update_lines():
    global blue_line_pixel_count, blue_line_threshould, blue_line_next_allowed_cycle, blue_line_detected, blue_line_state
    global orange_line_pixel_count, orange_line_threshould, orange_line_next_allowed_cycle, orange_line_detected, orange_line_state
    global cycle_count, line_cycle_delay

    if blue_line_pixel_count > blue_line_threshould:
        blue_line_state = 1
        if cycle_count >= blue_line_next_allowed_cycle:
            blue_line_detected = True
    else:
        blue_line_state = 0
        if blue_line_detected:
            blue_line_state = 2
            blue_line_next_allowed_cycle = cycle_count + line_cycle_delay
        blue_line_detected = False

    if orange_line_pixel_count > orange_line_threshould:
        orange_line_state = 1
        if cycle_count >= orange_line_next_allowed_cycle:
            orange_line_detected = True
    else:
        orange_line_state = 0
        if orange_line_detected:
            orange_line_state = 2
            orange_line_next_allowed_cycle = cycle_count + line_cycle_delay
        orange_line_detected = False


def extra_imagery(hsv_arr):
    # PORTED: same output, numpy instead of a per-pixel loop
    walls = np.where(hsv_arr[:, :, 2] < WALL_VAL_MAX, 255, 0).astype(np.uint8)
    cv2.imwrite("walls.png", walls)


def cycle(picam2):
    global cycle_count, dir, blue_line_state, orange_line_state, direction, quadrant_count
    global mission_end_not_activated, mission_end_cycle, STOP, hue, left_wall, right_wall
    global blue_line_pixel_count, orange_line_pixel_count, raw_frame, frame, hsv

    cycle_count += 1

    dir = 0.0

    raw = capture_array(picam2)
    raw_frame[:] = raw
    frame = np.empty((120, 320, 3), dtype=np.uint8)
    process_frame(raw_frame, frame)
    hsv_mat = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    process_hsv(hsv_mat)
    update_lines()

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

    if direction >= 0:
        if orange_line_state == 2:
            quadrant_count += 1
    else:
        if blue_line_state == 2:
            quadrant_count += 1

    color = (122, 0, 0)  # Default color
    if blue_line_state != 0:
        color = (0, 0, 255)  # Blue
    if orange_line_state != 0:
        color = (255, 122, 0)  # Orange
    LED_color(*color)

    if direction == 1:
        dir = (left_wall - 0.3) * 75
    elif direction == -1:
        dir = (0.4 - right_wall) * 75
    else:
        if left_wall > 0.5:
            dir = (left_wall - 0.5) * 75
        if right_wall > 0.5:
            dir = (0.5 - right_wall) * 75

    if quadrant_count == 12 and mission_end_not_activated:
        mission_end_not_activated = False
        mission_end_cycle = cycle_count + 100

    if quadrant_count == 12:
        STOP = True
    print("c%-4d dir=%+6.1f  L=%.3f R=%.3f  blue=%4d orange=%4d  D=%+d q=%d"
          % (cycle_count, dir, left_wall, right_wall,
             blue_line_pixel_count, orange_line_pixel_count,
             direction, quadrant_count))
    logwriter.writerow([cycle_count, round(dir, 2), round(left_wall, 4),
                        round(right_wall, 4), blue_line_pixel_count,
                        orange_line_pixel_count, direction, quadrant_count])
    logfile.flush()
    servo(dir)

    # LED_rainbow(hue)


def main():
    global STOP, cycle_count, raw_frame, frame, hsv, hue, picam2, motor1_pwm, motor2_pwm, servo_pwm
    Setup_GPIO()
    picam2 = Setup_Camera()

    # LED_color(0, 0, 255)  # Initial blue
    LED_hsv(0, 255, 255)

    # PORTED: wait for the button before anything moves. Their program started
    # the motor immediately; the rules want the car still until it is pressed,
    # and it is also the emergency stop below.
    print("Open Challenge ready. PRESS THE BUTTON to start...")
    while not is_button_down():
        time.sleep(0.01)
    while is_button_down():
        time.sleep(0.01)
    print("  GO")

    start = time.time()
    button_sum = 0
    cycle(picam2)
    # LED_color(0, 255, 0)  # Green for start
    LED_hsv(85, 255, 255)

    motor(speed)
    stop_time = None
    while not STOP:
        cycle_start_time = time.time()
        cycle(picam2)
        cycle_duration = time.time() - cycle_start_time
        print(f"Cycle {cycle_count}: {cycle_duration:.4f} seconds")
        if STOP and stop_time is None:
            stop_time =time.time()
        if stop_time is not None and time.time()- stop_time >= 10:
            break
        if is_button_down():
            button_sum += 1
            break                # PORTED: the button is also the emergency stop
        print(STOP)
    motor(0)
    servo(0)

    # LED_color(0, 0, 255)  # Back to blue
    LED_hsv(0, 255, 255)

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

    GPIO.cleanup()               # PORTED: leave the pins in a sane state
    sys.exit(0)


main()
