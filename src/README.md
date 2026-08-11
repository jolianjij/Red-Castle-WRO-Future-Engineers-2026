# src — control software

All Python runs together (on the Pi: `~/wro2026/`). Keep these files in one folder.

| File | Purpose |
|---|---|
| `robot.py` | Shared hardware + vision library (pins, `servo()`/`motor()`, HSV masks, wall/line/pillar analysis, `LapTracker`, `WallFollower`). Imported by both challenges. |
| `camera.py` | Locked camera setup — full 120° FOV, 180° flip, manual focus, fixed exposure/AWB. |
| `open_challenge.py` | Open Challenge: PD wall-follow, direction + 3-lap counting. |
| `obstacle_challenge.py` | Obstacle Challenge: wall-emergency → park → red/green pillar pass → wall-follow. |
| `color_tuner.py` | Interactive HSV tuner → writes `colors.json`. |
| `servo_center.py` | Find steering center → writes `servo_center.txt`. |
| `motor_speed_steps.py` | Motor speed staircase 100→50 % (stall test). |
| `motor_debug.py` | Direct-drive vs PWM diagnosis. |
| `driver_on.py` | Bare L9110S on/off test. |
| `test.py` | Menu hardware bring-up (servo/motor/camera). |
| `cam_capture.py` | Field capture / focus & exposure testing. |

**Runtime files (generated on the Pi, not committed):** `colors.json` (from the
tuner) and `servo_center.txt` (from the servo tool). `robot.py` loads both at start.

### Run
```bash
cd ~/wro2026 && source .venv/bin/activate
python open_challenge.py      # or obstacle_challenge.py
```
