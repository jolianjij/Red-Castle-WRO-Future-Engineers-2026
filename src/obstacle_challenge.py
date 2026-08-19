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
import numpy as np
import time
from picamera2 import Picamera2
from libcamera import Transform            # PORTED: our camera is upside down
import RPi.GPIO as GPIO
from array import array
import csv
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
RED_HUE_LO, RED_HUE_HI = 15, 175          # hue < 15 OR hue > 175
GREEN_SAT_MIN, GREEN_VAL_MIN, GREEN_VAL_MAX = 120, 60, 240
GREEN_HUE_MIN, GREEN_HUE_MAX = 45, 90
PURPLE_SAT_MIN, PURPLE_VAL_MIN, PURPLE_VAL_MAX = 120, 60, 240
PURPLE_HUE_MIN, PURPLE_HUE_MAX = 135, 175
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
WALL_VAL_MAX = 70
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
line_cycle_delay = 20
blue_line_threshould = 900
orange_line_threshould = 900

blue_line_pixel_count = 0
blue_line_next_allowed_cycle = 0
orange_line_pixel_count = 0
orange_line_next_allowed_cycle = 0

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
logfile = open("robot_log.csv", "w", newline="")
logwriter = csv.writer(logfile)
logwriter.writerow(["cycle", "Err", "dir", "quadrant", "traffic_light", "target_x", "target_y", "target_area"])


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


def servo(angle):
    """Adjust and set the servo angle using RPi.GPIO."""

    global SERVO_PIN

    # PORTED: their centre was 105 with a deviation of 50. Ours is 90 plus a
    # measured trim, clamped to the linkage's real 35 degrees.
    angle += SERVO_CENTER
    deviation = STEER_DEVIATION
    if angle < SERVO_CENTER - deviation:
        angle = SERVO_CENTER - deviation
    if angle > SERVO_CENTER + deviation:
        angle = SERVO_CENTER + deviation
    angle += SERVO_TRIM

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
    GPIO.setwarnings(False)          # PORTED

    GPIO.setup(SERVO_PIN, OUTPUT)
    GPIO.setup(MOTOR_IN1, OUTPUT)
    GPIO.setup(MOTOR_IN2, OUTPUT)
    # PORTED: GPIO.setup(10, OUTPUT) was the NeoPixel data pin - not on this car
    GPIO.setup(BUTTON_PIN, INPUT, pull_up_down=GPIO.PUD_UP)   # PORTED: pull-up
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

    dark = v < WALL_VAL_MAX
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
    global blue_line_state, blue_line_detected, blue_line_next_allowed_cycle
    global orange_line_state, orange_line_detected, orange_line_next_allowed_cycle
    global cycle_count,pre_line,direction

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


def process_traffic_contours(box, type_idx):
    global target
    for contour in box:
        area = cv2.contourArea(contour)
        if area > target[2]:
            boundingBox = cv2.boundingRect(contour)
            if boundingBox[2] < boundingBox[3]:
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
    walls = np.where(v < WALL_VAL_MAX, 255, 0).astype(np.uint8)
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
    if direction >= 0:
        if target[3] in [1, 2]:  # Green
            Err = -((260 + target[1] * 5) - target[0])
            if target[0] > 220:
                Err = 0
            if target[2] > 1000:
                last_detected_traffic_light = 1
        elif target[3] in [0, 3]:  # Red
            Err = (target[0] - (120 - target[1] * 5))
            if target[2] > 1000:
                last_detected_traffic_light = 0
                red_start_timer =time.time()
        else:
            Err = 0
    if direction < 0:
        if target[3] in [1, 2]:  # Green
            Err = -((220 + target[1] * 5) - target[0])
            if target[2] > 1500:
                last_detected_traffic_light = 1
                green_start_timer = time.time()
        elif target[3] in [0, 3]:  # Red
            Err = (target[0] - (120 - target[1] * 5))
            if target[0] < 90:
                Err = 0
            if target[2] > 1500:
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
    if direction >= 0:
        if last_detected_traffic_light == 0:
            if right_wall > 0.6:
                dir = -40*right_wall
        else:
            if left_wall > 0.6:
                dir = 30*left_wall
            elif right_wall > 0.6:
                dir =-30*right_wall
        if last_detected_traffic_light ==1 and orange_line_state==2:
            servo(45)
            time.sleep(0.7)
    else:
        if last_detected_traffic_light == 1:
            if left_wall > 0.6:
                dir = 40*left_wall
        else:
            if right_wall > 0.6:
                dir = -30*left_wall
            elif left_wall > 0.6:
                dir = 30*right_wall
        if last_detected_traffic_light ==0 and blue_line_state==2:
            servo(-45)
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
            if left_wall + right_wall > 0.8:
                wall_aligment_state = 1
        else:
            if direction >= 0:
                dir = (left_wall - 0.8) * 50
                if right_wall > 0.5:
                    dir = 45
            else:
                dir = (0.8 - right_wall) * 50
                if left_wall > 0.5:
                    dir = -45

            if parking[2] > 3400:
                STOP = True

            R, G, B = 255, 0, 255
    # Debug log to console
    print(f"[left_wall {left_wall}] right_wall={right_wall}, dir={dir:.2f}, quadrant={quadrant_count}, target={list(target)}, traffic={last_detected_traffic_light}")

    # Log to CSV
    logwriter.writerow([cycle_count, Err, dir, quadrant_count, last_detected_traffic_light,
                        target[0], target[1], target[2]])
    logfile.flush()

    servo(dir)
    LED_color(R, G, B)


def main():
    global STOP, cycle_count, raw_frame, frame, hsv, red_mask, green_mask, purple_mask,Zaid
    global servo_pwm, motor_pwm, picam2, direction

    Setup_GPIO()
    picam2 = Setup_Camera()
    LED_hsv(0, 255, 255)  # Initial blue

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

    cycle(picam2)
    if purple_left > purple_right:
        direction=1
        motor(50)
        servo(45)
        time.sleep(0.7)
        Zaid=True
        servo(-35)
        time.sleep(0.7)
    else:
        direction=-1
        motor(50)
        servo(-45)
        time.sleep(0.6)
        Zaid=True
        servo(35)
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
        if direction >= 0:
            servo(30)
            time.sleep(0.45)
            servo(-30)
            time.sleep(1.3)
            servo(0)
            time.sleep(0.3)
        else:
            motor(0.5 * 255)
            servo(-30)
            time.sleep(0.45)
            servo(30)
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

    LED_hsv(0, 0, 0)  # Off
    picam2.close()
    GPIO.cleanup()
    sys.exit(0)


main()
