#!/usr/bin/env python3
"""
test.py - Hardware bring-up test for the WRO 2026 Future Engineers car.

Runs on the Raspberry Pi 4 (Bookworm), inside the --system-site-packages venv.
Menu:
    1. Steering servo   (GPIO13)
    2. Drive motor      (GPIO24 = IN1 / GPIO23 = IN2, one pin PWM, other LOW)
    3. Pi Camera        (capture + save + report HSV; frame rotated 180)
    4. Button           (GPIO9, optional - disabled)
    5. NeoPixel LED     (board.D10, optional - disabled)
    a. Run all
    q. Quit
"""

import sys
import time

# --------------------------------------------------------------------------
# PIN CONFIG (BCM numbering)
# --------------------------------------------------------------------------
SERVO_PIN = 13          # steering servo (GPIO13, phys pin 33, hardware PWM1)
MOTOR_IN1 = 24          # PWM here = FORWARD (IN2 held LOW)
MOTOR_IN2 = 23          # PWM here = REVERSE (IN1 held LOW)
BUTTON_PIN = 9          # optional
LED_COUNT = 4           # optional NeoPixel on board.D10

ENABLE_BUTTON = False   # no button wired yet
ENABLE_LED = False      # no NeoPixel wired yet

SERVO_HZ = 50
MOTOR_HZ = 1000
STOP_FLIP_DELAY = 0.3   # s to coast before reversing (protects the regulator)
SERVO_CENTER_TRIM = 0.0 # deg; set from servo_center.py so 0 = wheels straight
CAMERA_FLIP_180 = True  # camera mounted upside-down -> rotate frames 180

# --------------------------------------------------------------------------
import RPi.GPIO as GPIO

OUTPUT = GPIO.OUT
INPUT = GPIO.IN

servo_pwm = None
motor1_pwm = None
motor2_pwm = None
pixels = None
_led_ok = False
_last_dir = 0           # last non-zero drive direction actually applied


# --------------------------------------------------------------------------
# Low-level helpers
# --------------------------------------------------------------------------
def servo(angle):
    """angle deg, 0 = straight ahead (after trim), - left / + right, clamped +-45."""
    angle += SERVO_CENTER_TRIM
    angle += 90
    deviation = 45
    angle = max(90 - deviation, min(90 + deviation, angle))
    min_duty, max_duty = 2.5, 12.5
    duty = min_duty + (angle / 180.0) * (max_duty - min_duty)
    servo_pwm.ChangeDutyCycle(duty)
    time.sleep(0.25)
    servo_pwm.ChangeDutyCycle(0)


def motor(speed):
    """speed -100..100. Never flips fwd<->rev directly (back-EMF kills the regulator)."""
    global _last_dir
    speed = max(-100, min(100, speed))
    new_dir = 1 if speed > 0 else (-1 if speed < 0 else 0)

    if new_dir != 0 and _last_dir != 0 and new_dir != _last_dir:
        motor1_pwm.ChangeDutyCycle(0)      # coast
        motor2_pwm.ChangeDutyCycle(0)
        time.sleep(STOP_FLIP_DELAY)

    mag = abs(speed)
    if speed > 0:
        motor1_pwm.ChangeDutyCycle(mag)
        motor2_pwm.ChangeDutyCycle(0)
    elif speed < 0:
        motor1_pwm.ChangeDutyCycle(0)
        motor2_pwm.ChangeDutyCycle(mag)
    else:
        motor1_pwm.ChangeDutyCycle(0)
        motor2_pwm.ChangeDutyCycle(0)

    if new_dir != 0:
        _last_dir = new_dir


def led_color(r, g, b):
    if not _led_ok:
        return
    for i in range(LED_COUNT):
        pixels[i] = (r, g, b)
    pixels.show()


def is_button_down():
    return GPIO.input(BUTTON_PIN) == 0


# --------------------------------------------------------------------------
def setup_gpio():
    global servo_pwm, motor1_pwm, motor2_pwm, pixels, _led_ok

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    GPIO.setup(SERVO_PIN, OUTPUT)
    GPIO.setup(MOTOR_IN1, OUTPUT)
    GPIO.setup(MOTOR_IN2, OUTPUT)

    servo_pwm = GPIO.PWM(SERVO_PIN, SERVO_HZ)
    servo_pwm.start(0)
    motor1_pwm = GPIO.PWM(MOTOR_IN1, MOTOR_HZ)
    motor2_pwm = GPIO.PWM(MOTOR_IN2, MOTOR_HZ)
    motor1_pwm.start(0)
    motor2_pwm.start(0)

    if ENABLE_BUTTON:
        GPIO.setup(BUTTON_PIN, INPUT, pull_up_down=GPIO.PUD_UP)

    if ENABLE_LED:
        try:
            import board
            import neopixel
            pixels = neopixel.NeoPixel(board.D10, LED_COUNT, brightness=0.2,
                                       auto_write=False, pixel_order=neopixel.GRB)
            _led_ok = True
        except Exception as e:
            print(f"[LED] disabled ({e})")
            _led_ok = False


# --------------------------------------------------------------------------
def test_servo():
    print("\n[SERVO] centre -> left -> right -> centre. Watch the wheels.")
    for label, a in [("centre", 0), ("left -45", -45), ("centre", 0),
                     ("right +45", 45), ("centre", 0)]:
        print(f"   {label}")
        servo(a)
        time.sleep(0.6)
    print("[SERVO] done. If centre isn't straight, set SERVO_CENTER_TRIM (servo_center.py).")


def test_motor():
    print("\n[MOTOR] *** LIFT THE WHEELS OFF THE GROUND ***")
    input("   Press Enter when the car is safely lifted...")
    try:
        print("   forward 60%  (2s)")
        motor(60); time.sleep(2); motor(0); time.sleep(0.5)
        print("   reverse 60%  (2s)")
        motor(-60); time.sleep(2); motor(0)
        print("[MOTOR] done. If direction is inverted, swap IN1/IN2.")
    finally:
        motor(0)


def test_camera():
    print("\n[CAMERA] initialising Picamera2 ...")
    import cv2
    from picamera2 import Picamera2

    cam = Picamera2()
    cam.configure(cam.create_preview_configuration(
        main={"format": "RGB888", "size": (640, 480)}))
    cam.start()
    time.sleep(1.0)
    frame = cam.capture_array()
    cam.close()

    if CAMERA_FLIP_180:
        frame = cv2.rotate(frame, cv2.ROTATE_180)   # camera is upside-down

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)     # matches main pipeline
    cy, cx = frame.shape[0] // 2, frame.shape[1] // 2
    h, s, v = hsv[cy, cx]

    cv2.imwrite("test_capture.png", frame)
    print(f"   frame shape : {frame.shape}")
    print(f"   centre pixel HSV : H={h} S={s} V={v}")
    print("   saved -> test_capture.png (open it to check framing/flip)")


def test_button():
    if not ENABLE_BUTTON:
        print("\n[BUTTON] disabled (ENABLE_BUTTON=False).")
        return
    print("\n[BUTTON] press the button within 5 seconds ...")
    t_end = time.time() + 5
    seen = False
    while time.time() < t_end:
        if is_button_down():
            seen = True
            break
        time.sleep(0.02)
    print("[BUTTON] PRESS DETECTED." if seen else "[BUTTON] no press seen.")


def test_led():
    if not _led_ok:
        print("\n[LED] disabled / not detected.")
        return
    print("\n[LED] red -> green -> blue -> off")
    for name, (r, g, b) in [("red", (255, 0, 0)), ("green", (0, 255, 0)),
                            ("blue", (0, 0, 255)), ("off", (0, 0, 0))]:
        print(f"   {name}")
        led_color(r, g, b)
        time.sleep(0.7)
    print("[LED] done.")


# --------------------------------------------------------------------------
def menu():
    tests = {"1": test_servo, "2": test_motor, "3": test_camera,
             "4": test_button, "5": test_led}
    while True:
        print("\n==== WRO 2026 hardware test ====")
        print(" 1) servo   2) motor   3) camera   4) button   5) LED")
        print(" a) run all          q) quit")
        choice = input(" select: ").strip().lower()
        if choice == "q":
            break
        elif choice == "a":
            for k in ["1", "2", "3", "4", "5"]:
                tests[k]()
        elif choice in tests:
            tests[choice]()
        else:
            print(" ? unknown option")


def main():
    setup_gpio()
    servo(0)
    led_color(0, 0, 40)
    try:
        menu()
    except KeyboardInterrupt:
        pass
    finally:
        motor(0)
        servo(0)
        led_color(0, 0, 0)
        time.sleep(0.2)
        GPIO.cleanup()
        print("\nclean exit.")
        sys.exit(0)


if __name__ == "__main__":
    main()
