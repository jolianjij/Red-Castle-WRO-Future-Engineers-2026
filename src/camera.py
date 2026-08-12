#!/usr/bin/env python3
"""
camera.py - camera setup for the WRO 2026 car.

Sensor: OV5647 Wide (FIXED FOCUS). Because it is fixed-focus with a small sensor
it has a large depth of field - the whole mat and the walls stay sharp, and there
is NO autofocus / LensPosition to set (unlike the Camera Module 3).

Locks exposure / gain / white balance so HSV thresholds stay stable, uses the full
120 deg FOV sensor mode, and rotates 180 deg (the camera is mounted upside-down).

    from camera import open_camera
    cam = open_camera()
    frame = cam.capture_array()   # RGB888, upright -> cv2.cvtColor(frame, COLOR_BGR2HSV)
"""
import json
import os
import time
from picamera2 import Picamera2
from libcamera import Transform

PROC_SIZE    = (640, 480)     # processing resolution
FULL_FOV     = (1296, 972)    # OV5647 full-FOV sensor mode (no crop) = full 120 deg
EXPOSURE_US  = 12000          # short shutter to limit motion blur (room is dim ~100 lux)
GAIN         = 8.0            # analogue gain to compensate the short shutter
COLOUR_GAINS = (1.6, 1.6)     # locked white balance (R, B) - re-tune if colours look off
SATURATION   = 1.4            # >1 separates red/orange/green/magenta in HSV
CONTRAST     = 1.1
FLIP_180     = True           # camera mounted upside-down

# tools/camera_tune.py writes camera_settings.json - it overrides the values above
_SETTINGS_FILE = "camera_settings.json"
if os.path.exists(_SETTINGS_FILE):
    try:
        _s = json.load(open(_SETTINGS_FILE))
        EXPOSURE_US = int(_s.get("ExposureTime", EXPOSURE_US))
        GAIN = float(_s.get("AnalogueGain", GAIN))
        SATURATION = float(_s.get("Saturation", SATURATION))
        CONTRAST = float(_s.get("Contrast", CONTRAST))
        COLOUR_GAINS = (float(_s.get("ColourGainR", COLOUR_GAINS[0])),
                        float(_s.get("ColourGainB", COLOUR_GAINS[1])))
        print(f"[camera] loaded {_SETTINGS_FILE}")
    except Exception as e:
        print(f"[camera] could not read {_SETTINGS_FILE}: {e}")


def open_camera(size=PROC_SIZE, exposure_us=EXPOSURE_US, gain=GAIN,
                colour_gains=COLOUR_GAINS):
    p = Picamera2()
    tf = Transform(hflip=1, vflip=1) if FLIP_180 else Transform()
    cfg = p.create_video_configuration(
        main={"size": size, "format": "RGB888"},
        raw={"size": FULL_FOV},        # force the full-FOV sensor mode
        transform=tf,
        buffer_count=4,
    )
    p.configure(cfg)
    p.start()
    # OV5647: no AfMode / LensPosition (fixed focus). Only lock AE + AWB.
    p.set_controls({
        "AeEnable": False, "ExposureTime": exposure_us, "AnalogueGain": gain,
        "AwbEnable": False, "ColourGains": colour_gains,
        "Saturation": SATURATION, "Contrast": CONTRAST,
    })
    time.sleep(0.5)
    return p


if __name__ == "__main__":
    import cv2
    cam = open_camera()
    md = cam.capture_metadata()
    frame = cam.capture_array()
    cam.close()
    cv2.imwrite("camera_selftest.jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    print("frame", frame.shape, "exp", md.get("ExposureTime"),
          "gain", md.get("AnalogueGain"), "colourgains", md.get("ColourGains"))
    print("saved camera_selftest.jpg")
