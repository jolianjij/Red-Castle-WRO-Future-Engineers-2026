#!/usr/bin/env python3
"""
motor_debug.py - figure out why the motor stalls.

Runs three phases so you can compare:
  1. DIRECT full HIGH  (no PWM at all) - pure on/off
  2. DIRECT full reverse
  3. PWM ramp 40 -> 100%

While it runs, measure with a multimeter:
  - VCC to GND on the L9110S      (should read your battery voltage)
  - the two MOTOR-A output pins    (should read ~battery minus ~1.8V when driven)

If the motor spins in phase 1 but NOT with PWM in phase 3  -> PWM/software issue.
If it won't spin even in phase 1                          -> power/driver/motor issue.
Keep the wheels lifted.
"""
import time
import RPi.GPIO as GPIO

IN1, IN2 = 24, 23   # A-IA, A-IB on the L9110S

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(IN1, GPIO.OUT)
GPIO.setup(IN2, GPIO.OUT)


def stop():
    GPIO.output(IN1, 0)
    GPIO.output(IN2, 0)


try:
    print("[1] DIRECT full FORWARD (no PWM), 3s -- measure MOTOR-A terminals now")
    GPIO.output(IN2, 0)
    GPIO.output(IN1, 1)
    time.sleep(3)
    stop()
    time.sleep(1)

    print("[2] DIRECT full REVERSE (no PWM), 3s")
    GPIO.output(IN1, 0)
    GPIO.output(IN2, 1)
    time.sleep(3)
    stop()
    time.sleep(1)

    print("[3] PWM forward ramp (1000 Hz): 40 -> 60 -> 80 -> 100 %")
    GPIO.output(IN2, 0)
    p = GPIO.PWM(IN1, 1000)
    p.start(0)
    for duty in (40, 60, 80, 100):
        print(f"    duty = {duty}%")
        p.ChangeDutyCycle(duty)
        time.sleep(1.5)
    p.ChangeDutyCycle(0)
    p.stop()

finally:
    stop()
    GPIO.cleanup()
    print("done.")
