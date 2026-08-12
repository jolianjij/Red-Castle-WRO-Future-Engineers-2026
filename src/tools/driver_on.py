#!/usr/bin/env python3
# Bare driver test: turn the L9110S full ON (forward, no PWM) and hold.
# IN1 HIGH + IN2 LOW = motor full forward at max power. Ctrl+C to stop.

import time
import RPi.GPIO as GPIO

IN1, IN2 = 24, 23   # A-IA, A-IB on the L9110S

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(IN1, GPIO.OUT)
GPIO.setup(IN2, GPIO.OUT)

GPIO.output(IN2, 0)   # reverse input LOW
GPIO.output(IN1, 1)   # forward input HIGH -> motor ON

print("motor ON (full forward, no PWM). Ctrl+C to stop.")
try:
    while True:
        time.sleep(0.5)
except KeyboardInterrupt:
    pass
finally:
    GPIO.output(IN1, 0)
    GPIO.output(IN2, 0)
    GPIO.cleanup()
    print("\nmotor OFF")
