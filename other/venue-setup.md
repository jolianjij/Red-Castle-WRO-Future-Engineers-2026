# Venue setup — wired networking, calibration, autostart

Everything needed on competition day, in the order you'll need it.

---

## 1. Wired networking (no wireless allowed)

Both **SSH** and **VNC** already listen on every interface (`0.0.0.0:22` and
`*:5900`), so nothing needs enabling — they start working the moment `eth0`
has an address. The only question is where that address comes from.

### Cable straight from laptop to Pi (the usual case)

There is no DHCP server on a bare cable, so the Pi carries a **fixed address**
for exactly this situation:

| | |
|---|---|
| Pi | `192.168.50.1` / 24 — always on, set on the `Wired connection 1` profile |
| Laptop | set the wired adapter to `192.168.50.2`, mask `255.255.255.0` |

No gateway or DNS needed. Modern Pi 4 Ethernet is auto-MDIX, so a **normal
patch cable works** — no crossover cable.

Setting the laptop side on Windows:

```bash
netsh interface ip set address name="Ethernet" static 192.168.50.2 255.255.255.0
```

To hand it back to DHCP afterwards:

```bash
netsh interface ip set address name="Ethernet" dhcp
```

### Venue switch with DHCP

Just plug in — the profile is `method=auto`, so it takes a DHCP lease *and*
keeps `192.168.50.1` as a second address. Either route works.

### Connecting

```bash
ssh pi@raspberrypi.local
```

`raspberrypi.local` works over the cable because **avahi** (mDNS) is running
and Windows 10/11 resolve `.local` natively. If it ever fails, `192.168.50.1`
is the fallback.

**VNC:** connect to `raspberrypi.local:5900`. It is `wayvnc` (the Wayland
server Bookworm uses), already enabled at boot, authenticating with the normal
Pi login.

### Turning the radios off

Do this **only after** the cable is proven, and use the script — it refuses to
run if Ethernet has no address, so it cannot lock you out:

```bash
./tools/venue_net.sh status
./tools/venue_net.sh wifi-off
```

`wifi-off` turns off Wi-Fi **and** Bluetooth. `./tools/venue_net.sh wifi-on`
undoes it. If you ever lose both, a screen and keyboard on the Pi plus
`nmcli radio wifi on` recovers it.

---

## 2. Recalibrating for the venue's light

**Order matters.** Each step is measured through the previous one, so doing
them out of order silently invalidates the earlier work.

### Step 1 — camera, then colours

```bash
python tools/tune_colors.py
```

Guided and **headless** — it runs in a plain SSH terminal, no display needed.
It first re-locks exposure and white balance to the room, then walks through
blue, orange, green, red and magenta. You fill the middle of the view with each
object and press Enter; it samples the centre box, discards background by hue,
and builds a range from the percentiles.

Finally it checks **every pair for overlap**, because a range that is right on
its own is still wrong if it also matches the pillar beside it. That check is
what caught red swallowing magenta in testing.

```bash
python tools/tune_colors.py --check     # what do the current ranges see?
python tools/tune_colors.py red green   # redo just these two
```

`colors.json` and `camera_settings.json` are backed up to `.bak` first.

### Step 2 — the wall detector

```bash
python tools/tune_walls.py --detector
```

This is the one that is easy to miss. **The wall detector does not use a colour
range** — it uses `WALL_V_HARD` / `WALL_V_SOFT` / `WALL_S_MAX`, three
brightness/saturation cuts. Tuning the colours does *not* retune the walls.

It samples the wall, the mat, and a coloured line, then places the thresholds
in the gap between them. If the wall and mat overlap in brightness it says so
and writes nothing — that means the room is too dim and no threshold can work.

Results go to `wall_settings.json`, which `robot.py` loads automatically.

### Step 3 — distance calibration

```bash
python tools/tune_walls.py
```

The car never measures distance; it measures **density** — the fraction of one
half of the picture that is wall. This parks the car at several known distances,
fits a straight line, and prints the exact constants to paste into
`LANE_TARGET`, `OUTER_TARGET` and `WALL_EMERGENCY`.

Measure from the **side of the car** to the wall, at camera height, with the car
**parallel** to the wall. Parallel matters more than exact: at an angle the
camera sees a wedge of wall and reads high.

```bash
python tools/tune_walls.py --live    # live read-out while you move the car
```

**Re-run step 3 after step 2** — changing the detector changes every density.

### Step 4 — prove it

```bash
python tools/test_logic.py    # the brain, on synthetic numbers
python tools/dryrun.py        # both challenges, live camera, motor untouched
```

---

## 3. Running at the start line

### Which program runs

One line, at the top of `run.sh`:

```bash
PROGRAM="obstacle_challenge.py"
```

### Starting it automatically at power-on

```bash
./autostart.sh on
```

From then on: **power the car, wait for boot, press the button.** No laptop, no
terminal, no network. This is safe because the program waits for the button
before anything moves — booting into it just means the car is armed.

When a run finishes the program exits and the service restarts it, so it is
immediately re-armed for the next press. It never drives on its own.

| command | |
|---|---|
| `./autostart.sh on` | run at every boot |
| `./autostart.sh off` | stop doing that |
| `./autostart.sh status` | which program, is it armed, did it crash |
| `./autostart.sh log` | watch the live output |
| `./autostart.sh restart` | pick up an edited `run.sh` without rebooting |

After editing `PROGRAM`, run `./autostart.sh restart` (or just power-cycle).

### Running by hand instead

```bash
./run.sh                      # whatever PROGRAM says
./run.sh open_challenge.py    # override, just this once
```

---

## Quick reference

| | |
|---|---|
| Pi over cable | `ssh pi@raspberrypi.local` or `192.168.50.1` |
| Laptop wired adapter | `192.168.50.2 / 255.255.255.0` |
| VNC | `raspberrypi.local:5900` |
| Radios off / on | `./tools/venue_net.sh wifi-off` / `wifi-on` |
| Recalibrate | `tune_colors.py` → `tune_walls.py --detector` → `tune_walls.py` |
| Verify | `tools/test_logic.py`, then `tools/dryrun.py` |
| Choose program | `PROGRAM=` at the top of `run.sh` |
| Arm at boot | `./autostart.sh on` |
