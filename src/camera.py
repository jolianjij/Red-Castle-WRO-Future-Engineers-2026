#!/usr/bin/env python3
"""
camera.py - reusable camera setup for the WRO 2026 car (imx708 Wide).

Locks everything that must stay constant so HSV thresholds are stable and the
image is sharp and motion-frozen:
  - FULL 120 deg FOV (2304x1296 sensor mode), scaled to the processing size
  - 180 flip (camera is mounted upside-down)
  - MANUAL focus at the mat distance (no autofocus hunting mid-run)
  - LOCKED exposure / gain / white balance

Usage in the challenge code:
    from camera import open_camera
    cam = open_camera()          # started, ready
    frame = cam.capture_array()  # RGB888 -> use cv2.cvtColor(frame, COLOR_BGR2HSV)

All values were measured on the field (12.5 cm height, 15 deg down tilt, ~100 lux).
Re-tune EXPOSURE_US / GAIN if you change the field lighting.
"""
import time
from picamera2 import Picamera2
from libcamera import Transform, controls

PROC_SIZE    = (640, 480)     # what the pipeline processes
FULL_FOV     = (2304, 1296)   # full-width sensor mode = full 120 deg FOV
LENS_POS     = 3.0            # manual focus ~0.33 m (sharp across the mat)
EXPOSURE_US  = 9000           # short shutter to freeze motion (~1/110 s)
GAIN         = 8.0            # analogue gain to compensate the short shutter
COLOUR_GAINS = (1.94, 2.17)   # locked white balance (R, B)
FLIP_180     = True


def open_camera(size=PROC_SIZE, exposure_us=EXPOSURE_US, gain=GAIN,
                lens=LENS_POS, colour_gains=COLOUR_GAINS):
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
    p.set_controls({
        "AfMode": controls.AfModeEnum.Manual, "LensPosition": lens,
        "AeEnable": False, "ExposureTime": exposure_us, "AnalogueGain": gain,
        "AwbEnable": False, "ColourGains": colour_gains,
    })
    time.sleep(0.5)   # let the locked controls take effect
    return p


if __name__ == "__main__":
    # quick self-test: open, grab one frame, report
    import cv2
    cam = open_camera()
    md = cam.capture_metadata()
    frame = cam.capture_array()
    cam.close()
    cv2.imwrite("camera_selftest.jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
    print("frame", frame.shape, "exp", md.get("ExposureTime"),
          "gain", md.get("AnalogueGain"), "lens", md.get("LensPosition"))
    print("saved camera_selftest.jpg")
