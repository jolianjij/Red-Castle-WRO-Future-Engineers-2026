#!/usr/bin/env python3
"""
servo_center.py - find the steering servo's true CENTER (straight-ahead) trim.

Servo is on GPIO13. Type an angle and the servo goes there; nudge until the
wheels point dead straight, then save. The saved number is the center trim you
add to every steering command so 0 = straight.

Commands at the prompt:
    <number>   go to that angle in degrees (-45..45), 0 = nominal center
    +  / -     nudge +1 / -1 degree
    s          SAVE the current angle as the center trim -> servo_center.txt
    q          quit
"""
import time
import RPi.GPIO as GPIO

SERVO_PIN = 13          # steering servo (moved to GPIO13)
PWM_HZ = 50
OUTFILE = "servo_center.txt"

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(SERVO_PIN, GPIO.OUT)
pwm = GPIO.PWM(SERVO_PIN, PWM_HZ)
pwm.start(0)

angle = 0.0


def set_angle(a):
    a = max(-45.0, min(45.0, a))
    duty = 2.5 + ((a + 90.0) / 180.0) * 10.0   # 2.5=full left, 12.5=full right
    pwm.ChangeDutyCycle(duty)
    time.sleep(0.3)
    pwm.ChangeDutyCycle(0)                       # release to stop buzzing
    return a


print(__doc__)
try:
    angle = set_angle(0.0)
    while True:
        cmd = input(f"[{angle:+.1f} deg] > ").strip().lower()
        if cmd in ("q", "quit", "exit"):
            break
        elif cmd == "+":
            angle = set_angle(angle + 1)
        elif cmd == "-":
            angle = set_angle(angle - 1)
        elif cmd == "s":
            with open(OUTFILE, "w") as f:
                f.write(str(angle))
            print(f"  SAVED center trim = {angle:+.1f} -> {OUTFILE}")
            print(f"  In your servo(): use  effective = commanded + ({angle:+.1f})")
        else:
            try:
                angle = set_angle(float(cmd))
            except ValueError:
                print("  enter a number, + , - , s , or q")
finally:
    pwm.stop()
    GPIO.cleanup()
    print("done")
