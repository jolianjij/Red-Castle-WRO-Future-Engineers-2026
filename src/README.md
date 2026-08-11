# src — control software

```
src/
├── robot.py               # shared library: hardware (servo/motor) + vision (masks, wall/line/pillar)
├── camera.py              # locked camera setup (full FOV, 180 flip, manual focus, fixed exposure/AWB)
├── open_challenge.py      # Open Challenge main
├── obstacle_challenge.py  # Obstacle Challenge main
└── tools/                 # calibration, tests, and camera utilities (run individually)
    ├── preview.py         # live camera window (view over VNC)
    ├── color_tuner.py     # tune HSV colours -> colors.json
    ├── servo_center.py    # find steering center -> servo_center.txt
    ├── test.py            # menu hardware bring-up (servo/motor/camera)
    ├── motor_debug.py     # direct-drive vs PWM diagnosis
    ├── motor_speed_steps.py  # speed staircase 100->50% (stall test)
    ├── driver_on.py       # bare L9110S on/off
    ├── cam_capture.py     # still capture / focus & exposure test
    └── mjpeg_stream.py    # browser MJPEG stream (optional)
```

## Runtime layout on the Pi
Everything lives under `~/wro2026/` with the same structure. The generated
calibration files stay at the **root** so `robot.py` finds them:

```
~/wro2026/
├── robot.py  camera.py  open_challenge.py  obstacle_challenge.py
├── colors.json          # from tools/color_tuner.py
├── servo_center.txt     # from tools/servo_center.py
└── tools/               # all the tools above
```

## Run (always from ~/wro2026 so paths resolve)
```bash
cd ~/wro2026 && source .venv/bin/activate

python tools/preview.py        # live view on VNC
python tools/color_tuner.py    # tune colours  -> colors.json
python tools/servo_center.py   # center steering -> servo_center.txt

python open_challenge.py       # Open Challenge
python obstacle_challenge.py   # Obstacle Challenge
```

The four core files import each other and read `colors.json` / `servo_center.txt`
from the current directory — so **always run from `~/wro2026`**.
