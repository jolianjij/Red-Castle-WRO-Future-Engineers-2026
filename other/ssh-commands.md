# Terminal commands — moving code and files to and from the Pi

Every command here is copy-pasteable. Run them from the repo folder on the
laptop unless it says otherwise.

```
laptop folder :  C:\Users\jolian\Desktop\WRO Future Engineers 2026
Pi folder     :  /home/pi/wro2026     (written below as ~/wro2026)
login         :  pi@raspberrypi
```

---

## The three you will actually use

```bash
./sync.sh pull        # Pi  ->  laptop   (grab what you tuned over SSH)
./sync.sh push-safe   # laptop -> Pi     (runs the tests first, refuses if they fail)
./backup.sh save "it worked"
```

> **`pull` before you edit.** You tune values directly on the Pi between runs.
> `push` overwrites them — that is what `push` means. Pull first, or lose them.

---

## Connecting

```bash
ssh pi@raspberrypi
```

If the name does not resolve:

```bash
ssh pi@raspberrypi.local      # mDNS
ssh pi@192.168.50.1           # over the Ethernet cable
```

Run one command and come straight back:

```bash
ssh pi@raspberrypi 'cd ~/wro2026 && ls'
```

Run something in the virtual environment (needed for anything using the camera):

```bash
ssh pi@raspberrypi 'source ~/wro2026/.venv/bin/activate && cd ~/wro2026 && python tools/test_logic.py'
```

---

## Copying files

**`scp` = secure copy. The direction is whichever way the arrow of the arguments
points: `scp FROM TO`.**

### Laptop → Pi

```bash
scp src/robot.py pi@raspberrypi:wro2026/                    # one file
scp src/*.py pi@raspberrypi:wro2026/                        # several
scp src/tools/*.py pi@raspberrypi:wro2026/tools/            # into a subfolder
scp -r src/tools pi@raspberrypi:wro2026/                    # a whole folder
```

### Pi → laptop

```bash
scp pi@raspberrypi:wro2026/colors.json src/                 # one file
scp pi@raspberrypi:wro2026/logs/*.csv logs-from-pi/         # all the logs
scp -r pi@raspberrypi:wro2026/frames ./frames-from-pi       # a whole folder
```

> The Pi path `wro2026/...` is relative to `/home/pi`, so `wro2026/colors.json`
> and `/home/pi/wro2026/colors.json` are the same file.

### The newest log, without knowing its name

```bash
scp "pi@raspberrypi:$(ssh pi@raspberrypi 'ls -t ~/wro2026/logs/*.csv | head -1')" .
```

---

## Running a challenge

```bash
ssh pi@raspberrypi
cd ~/wro2026 && source .venv/bin/activate
python obstacle_challenge.py     # then PRESS THE BUTTON
```

Or with the runner, which takes the program name from one line inside itself:

```bash
./run.sh
./run.sh open_challenge.py       # override just this once
```

**Keep it running after you disconnect** — otherwise closing the terminal kills
the run:

```bash
ssh pi@raspberrypi 'cd ~/wro2026 && nohup ./run.sh > run.log 2>&1 &'
ssh pi@raspberrypi 'tail -f ~/wro2026/run.log'      # watch it
```

---

## The tools

All of these need the venv, so they are shown with it:

```bash
V='source ~/wro2026/.venv/bin/activate && cd ~/wro2026 &&'

ssh pi@raspberrypi "$V python tools/test_logic.py"      # the brain, offline
ssh pi@raspberrypi "$V python tools/dryrun.py"          # camera live, motor untouched
ssh pi@raspberrypi "$V python tools/button_test.py"     # is the button wired right
ssh pi@raspberrypi "$V python tools/line_check.py"      # what is triggering a line
ssh pi@raspberrypi "$V python tools/park_check.py"      # which way out of the lot
ssh pi@raspberrypi "$V python tools/tune_colors.py --check"
```

Anything that saves a picture leaves it in `~/wro2026`, so bring it back:

```bash
scp pi@raspberrypi:wro2026/line_check.png .
```

---

## Watching a run from the laptop

```bash
ssh pi@raspberrypi 'tail -f ~/wro2026/run.log'          # live output
ssh pi@raspberrypi './wro2026/autostart.sh log'         # if running as a service
```

---

## Housekeeping

```bash
# free space
ssh pi@raspberrypi 'df -h / | tail -1'

# clear old logs and frames before a session
ssh pi@raspberrypi 'rm -f ~/wro2026/logs/*.csv ~/wro2026/frames/*'

# is anything still running?
ssh pi@raspberrypi 'pgrep -af "python.*challenge" || echo "nothing running"'

# stop a runaway program
ssh pi@raspberrypi 'pkill -f "python.*challenge"; echo stopped'

# reboot / shutdown
ssh pi@raspberrypi 'sudo reboot'
ssh pi@raspberrypi 'sudo shutdown -h now'
```

> **Always shut down properly before pulling power.** Yanking it mid-write is
> the classic way to corrupt an SD card, and the card holds the OS, the Python
> environment and every calibration file.

---

## Not typing the password every time

```bash
ssh-keygen -t ed25519 -C "wro-laptop"        # press Enter at every prompt
ssh-copy-id pi@raspberrypi                   # asks for the password ONE last time
ssh pi@raspberrypi                           # ...and never again
```

If `ssh-copy-id` is missing on Windows:

```bash
cat ~/.ssh/id_ed25519.pub | ssh pi@raspberrypi 'mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys'
```

---

## When something goes wrong

| symptom | try |
|---|---|
| `Could not resolve hostname` | `ssh pi@raspberrypi.local`, then `ssh pi@192.168.50.1` |
| `Connection timed out` | the Pi is off, rebooting, or off the network |
| `Permission denied` | wrong password, or the wrong user (it is `pi`) |
| `REMOTE HOST IDENTIFICATION HAS CHANGED` | the SD card was reimaged: `ssh-keygen -R raspberrypi` |
| Copied a file but nothing changed | you copied to the wrong folder — it must be `~/wro2026/`, and tools go in `~/wro2026/tools/` |
| Edited on the Pi, then pushed, and lost it | that is what `push` does. `./backup.sh undo` |

### Prove which machine you are on

Easy to lose track in a long session:

```bash
hostname        # "raspberrypi" = the Pi.  Anything else = the laptop.
```
