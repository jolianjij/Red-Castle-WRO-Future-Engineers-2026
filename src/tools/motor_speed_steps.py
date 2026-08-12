#!/usr/bin/env python3
"""
motor_speed_steps.py - drive the motor down a speed staircase.

100% -> 90 -> 80 -> 70 -> 60 -> 50 %, each for 10 seconds.
Watch/listen: the % where it stops turning (starts buzzing) is your stall point.

Also sets the TRUE forward direction: if the car runs backwards, flip
MOTOR_FORWARD_PIN below (or swap the motor's two wires).
Keep the wheels off the ground.
"""
import time
import RPi.GPIO as GPIO

IN1, IN2 = 24, 23            # L9110S A-IA / A-IB
MOTOR_FORWARD_PIN = IN1      # <-- PWM on this pin = forward. Swap to IN2 if reversed.
MOTOR_REVERSE_PIN = IN2 if MOTOR_FORWARD_PIN == IN1 else IN1

PWM_HZ = 1000
STEP_SECONDS = 10
SPEEDS = [100, 90, 80, 70, 60, 50]

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(IN1, GPIO.OUT)
GPIO.setup(IN2, GPIO.OUT)

GPIO.output(MOTOR_REVERSE_PIN, 0)          # reverse input held LOW
pwm = GPIO.PWM(MOTOR_FORWARD_PIN, PWM_HZ)
pwm.start(0)

try:
    for s in SPEEDS:
        print(f"{s:3d}%  for {STEP_SECONDS}s", flush=True)
        pwm.ChangeDutyCycle(s)
        time.sleep(STEP_SECONDS)
    pwm.ChangeDutyCycle(0)
finally:
    pwm.ChangeDutyCycle(0)
    pwm.stop()
    GPIO.output(IN1, 0)
    GPIO.output(IN2, 0)
    GPIO.cleanup()
    print("done, motor off")
