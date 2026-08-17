# Venue setup — wired networking, calibration, autostart

Everything needed on competition day, in the order you'll need it.

---

## 1. Wired networking — one cable, laptop to Pi

Laptop Ethernet port → Pi Ethernet port. Nothing else.

**Your laptop needs no setup.** Leave its wired adapter on *"Obtain an IP
address automatically"* — the default — and just plug in. The Pi runs the
address server itself, so it hands the laptop an address over the cable.

| | |
|---|---|
| Pi | `192.168.50.1` — fixed, always there |
| Laptop | `192.168.50.10`+ — given out by the Pi |
| Connect | `ssh pi@raspberrypi.local` |
| VNC | `raspberrypi.local:5900` |
| If `.local` fails | use `192.168.50.1` |

A **normal patch cable works** — Pi 4 Ethernet is auto-MDIX, so no crossover
cable is needed. Plug in, wait about five seconds, then:

```bash
ssh pi@raspberrypi.local
```

`raspberrypi.local` resolves over the cable because **avahi** (mDNS) runs on the
Pi and Windows 10/11 resolve `.local` natively.

### Wi-Fi and the cable together

They do not conflict, and you do not have to choose:

- **No cable** — Wi-Fi works exactly as normal. The Ethernet route exists but is
  marked `linkdown`, so it carries nothing.
- **Cable plugged in** — `192.168.50.x` goes over the cable, everything else
  still goes over Wi-Fi. The Pi's default route stays on Wi-Fi either way.

> **Testing at home, with both up:** the Pi advertises *both* of its addresses
> over mDNS, so `raspberrypi.local` may resolve to the **Wi-Fi** one and you
> will not actually be testing the cable. To prove the cable really works, use
> the address explicitly:
> ```bash
> ssh pi@192.168.50.1
> ```
> At the venue this cannot happen, because Wi-Fi will be off and
> `192.168.50.1` is the only address the Pi has.

### How it is set up

`eth0` uses NetworkManager's **shared** mode: a fixed `192.168.50.1/24` plus a
`dnsmasq` handing out `192.168.50.10–254`, started automatically at boot. Both
SSH and VNC already listen on every interface, so they need nothing enabling.

> This makes the Pi the address server on that cable. That is exactly right for
> a direct laptop link, but it means you should **not** plug this port into a
> venue network that has its own DHCP server — two servers on one network fight.
> If you ever need that instead:
> `sudo nmcli con mod "Wired connection 1" ipv4.method auto`

### Turning the radios off

Do this **only after** the cable is proven, and use the script:

```bash
./tools/venue_net.sh status      # says CONNECTED once the cable is in
./tools/venue_net.sh wifi-off
```

`wifi-off` refuses unless the cable is **physically connected**. It checks the
carrier, not the address — `eth0` keeps `192.168.50.1` even while unplugged, so
an address alone proves nothing. It also refuses if the address server is not
running, which would leave the laptop with no way in.

`./tools/venue_net.sh wifi-on` undoes it. If you ever lose both, a screen and
keyboard on the Pi plus `nmcli radio wifi on` recovers it.

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
| Laptop wired adapter | leave on automatic DHCP — the Pi gives it an address |
| VNC | `raspberrypi.local:5900` |
| Radios off / on | `./tools/venue_net.sh wifi-off` / `wifi-on` |
| Recalibrate | `tune_colors.py` → `tune_walls.py --detector` → `tune_walls.py` |
| Verify | `tools/test_logic.py`, then `tools/dryrun.py` |
| Choose program | `PROGRAM=` at the top of `run.sh` |
| Arm at boot | `./autostart.sh on` |
