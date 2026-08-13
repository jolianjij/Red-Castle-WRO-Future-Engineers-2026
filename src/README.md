# src — control software

```
src/
├── robot.py               # shared library: hardware (servo/motor) + vision (masks, wall/line/sign)
├── camera.py               # locked camera setup (OV5647 fixed focus, full FOV, 180 flip, locked exposure/AWB)
├── config.py               # EVERY tunable constant, in one place
├── open_challenge.py       # Open Challenge main
├── obstacle_challenge.py   # Obstacle Challenge main
├── legacy_open.py          # last year's Open Challenge logic, ported to this year's hardware (reference)
├── pure_open.py             # the single-wall control law in isolation, nothing else (diagnostic)
└── tools/                  # calibration, tests, and diagnostics (run individually)
    ├── preview.py           # live camera window (view over VNC)
    ├── camera_tune.py       # lock exposure/gain/white balance -> camera_settings.json
    ├── color_tuner.py       # tune HSV colours -> colors.json
    ├── servo_center.py      # find steering center -> servo_center.txt
    ├── test.py              # menu hardware bring-up (servo/motor/camera)
    ├── motor_debug.py       # direct-drive vs PWM diagnosis
    ├── motor_speed_steps.py # speed staircase 100->50% (stall test)
    ├── driver_on.py         # bare L9110S on/off
    ├── cam_capture.py       # still capture / focus & exposure test
    ├── shadow_check.py      # splits dark pixels into "real wall" vs "shadow"
    ├── outer_test.py        # validate the outer-wall controller by hand, motor untouched
    ├── freespace_test.py    # draw the detected wall boundary/gap on a real frame, motor untouched
    ├── dryrun.py             # run the FULL navigate() decision chain, camera live, motor untouched
    └── mjpeg_stream.py      # browser MJPEG stream (optional)
```

## Runtime layout on the Pi
Everything lives under `~/wro2026/` with the same structure. The generated
calibration files stay at the **root** so `robot.py` finds them:

```
~/wro2026/
├── robot.py  camera.py  config.py  open_challenge.py  obstacle_challenge.py
├── colors.json           # from tools/color_tuner.py   (committed as reference)
├── camera_settings.json  # from tools/camera_tune.py   (committed as reference)
├── servo_center.txt      # from tools/servo_center.py  (committed as reference, -9)
└── tools/                # all the tools above
```

## Run (always from ~/wro2026 so paths resolve)
```bash
cd ~/wro2026 && source .venv/bin/activate

python tools/camera_tune.py    # lock exposure/gain/white balance
python tools/color_tuner.py    # tune colours  -> colors.json
python tools/servo_center.py   # center steering -> servo_center.txt

python open_challenge.py       # Open Challenge
python obstacle_challenge.py   # Obstacle Challenge
```

Before trusting a change at speed, validate it stationary first — none of these
touch the motor:
```bash
python tools/outer_test.py     # move the car by hand, check the steering it would command
python tools/dryrun.py         # runs navigate() exactly as the challenge does
python tools/freespace_test.py # draws the detected wall boundary on a real frame
python tools/shadow_check.py   # tells a real wall apart from shadow on the mat
```

The core files import each other and read `colors.json` / `camera_settings.json`
/ `servo_center.txt` from the current directory — so **always run from
`~/wro2026`**. Every tunable constant used by any of the above lives in
`config.py`; that is the only file you should need to edit at the competition.
