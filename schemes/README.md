# schemes — electromechanical wiring

![Wiring diagram](wiring-diagram.png)

## Power chain

```
3 × 18650 (series, ~11.1 V nominal) ──► rocker switch ──┬──► L9110S  VCC   (motor power, direct)
                                                        │
                                                        └──► DC-DC buck converter ──► Raspberry Pi 4  5 V
Battery −  ────────── COMMON GROUND ────────── L9110S GND ────────── Pi GND
```

Two rules this diagram exists to enforce:

1. **Separate rails.** The motor is fed **straight from the battery** into the
   L9110S `VCC`. The Pi is fed from its **own step-down converter**. Motor current
   spikes therefore never pass through the Pi's supply. Wiring the motor through
   the Pi's 5 V rail caused repeated brownout reboots early in the build.
2. **One common ground.** Battery −, L9110S `GND` and Pi `GND` are all tied
   together. Without it the only electrical link between Pi and driver is the
   signal wire, and motor return current back-feeds a GPIO pin — the Pi shuts down
   (and the pin can be damaged).

A rocker switch in the battery line is the master on/off.

## Signal connections (authoritative pin map — see [`src/config.py`](../src/config.py))

| Signal | Pi pin (BCM) | Goes to |
|---|---|---|
| Steering servo PWM | **GPIO13** | MG90S servo signal (orange/white) |
| Motor `A-IA` | **GPIO24** | L9110S input — PWM here = **forward** |
| Motor `A-IB` | **GPIO23** | L9110S input — PWM here = **reverse** |
| Start / stop button | **GPIO19** | push button to **GND**. The Pi's internal pull-up holds the pin high, so the button needs **no resistor**; pressing pulls it low. One press starts the run, a second press stops it (the emergency stop). |
| Ground | any GND | common ground rail |

The servo takes its 5 V power from the Pi's 5 V rail (it is small and only moves
the steering linkage); the **drive motor never does**.

## Camera — CSI, not GPIO

The **OV5647 wide-angle camera** is *not* on the diagram because it does not use
any GPIO pin. It connects to the Pi's dedicated **CSI camera port** with a flat
**CSI ribbon cable**:

```
OV5647 wide camera ──[ CSI ribbon cable ]──► Raspberry Pi 4  CAMERA (CSI) port
```

- Ribbon length must reach from the camera mast down to the Pi (~15 cm on our car).
- Contacts face the correct way at both ends — on the Pi the **blue backing faces
  the Ethernet/USB side**.
- The camera is mounted **upside-down** on the mast, which is corrected in software
  (180° rotation in [`src/camera.py`](../src/camera.py)), not by rewiring.
- It draws its power over the CSI cable — no separate supply.

## Notes / cautions

- **Battery voltage vs driver rating.** The L9110S is rated **2.5–12 V**. Three
  18650 cells in series read ~**12.6 V fully charged**, which is marginally above
  that rating; it sits within spec for most of the run as the pack drops toward
  11 V. Worth watching if the driver runs hot.
- The motor's usable voltage is the battery minus the L9110S's internal drop
  (~1.5–1.8 V), which is why a healthy pack matters for pulling away from rest.
- Recommended: a ~1000 µF capacitor across the L9110S `VCC`–`GND` to absorb
  switching spikes.
- **Never** switch the motor directly from forward to reverse — the software
  enforces a coast-and-settle first (`STOP_FLIP_DELAY`), because the back-EMF
  spike can destroy the Pi's regulator.
