# Bill of Materials — Team The Red Castle (WRO 2026 Future Engineers)

Items marked **(CONFIRM)** need the exact part/spec filled in.

## Electronics — compute & sensing
| # | Component | Spec / notes | Qty |
|---|---|---|---|
| 1 | Raspberry Pi 4 Model B | 2 GB+; runs Raspberry Pi OS Bookworm 64-bit | 1 |
| 2 | microSD card | 16–32 GB, A1/A2, with Bookworm flashed | 1 |
| 3 | **OV5647 wide-angle camera** | 5 MP, ~120° FOV, **fixed focus** (deep depth of field) — the only sensor | 1 |
| 4 | CSI camera ribbon cable | Pi 4 CSI port → camera on the mast (~15 cm); carries data **and** power | 1 |

## Electronics — actuation & motor driver
| # | Component | Spec / notes | Qty |
|---|---|---|---|
| 5 | **L9110S** dual H-bridge module | drives the DC motor; `A-IA`→GPIO24, `A-IB`→GPIO23; rated 2.5–12 V, ~0.8 A | 1 |
| 6 | DC drive motor | brushed DC gear motor on the rear axle **(CONFIRM exact model/voltage)** | 1 |
| 7 | **SG90** steering servo | 9 g micro servo; signal → GPIO13, powered from the Pi's 5 V | 1 |
| 8 | Drive wheels + tires | **(CONFIRM)** size | 2 |
| 9 | Steering wheels (front) + Ackermann linkage | 3D-printed knuckles + tie-rod + servo horn | 1 set |

## Power
| # | Component | Spec / notes | Qty |
|---|---|---|---|
| 10 | **18650 Li-ion cells** | **3 in series** (~11.1 V nominal, 12.6 V full); feeds L9110S `VCC` directly | 3 |
| 11 | 3× 18650 battery holder | series holder with leads | 1 |
| 12 | **DC-DC step-down (buck) converter** | adjustable, set to **5 V**, ≥ 3 A — dedicated to the Pi (separate rail) | 1 |
| 13 | Rocker power switch | master on/off in the battery line | 1 |
| 14 | Screw terminal blocks | 2-pin, for the battery/power distribution joints | 2–3 |
| 15 | Smoothing capacitor | ~1000 µF across L9110S `VCC`–`GND` (recommended) | 1 |
| 16 | Push button | start button → GPIO9 (optional) | 1 |

## Wiring & fasteners
| # | Component | Spec / notes | Qty |
|---|---|---|---|
| 17 | Jumper wires (M-F, F-F) | signal + power; **common ground** Pi↔driver↔battery | pack |
| 18 | Heat-shrink / connectors | tidy the power joints | as needed |
| 19 | M2 / M3 screws, nuts, standoffs | mount Pi, driver, servo, camera mast | assortment |

## 3D-printed parts (in `models/`)
| # | Part | Notes |
|---|---|---|
| 20 | Chassis / base plate | holds Pi, battery, driver, motor |
| 21 | Camera mast | rigid, holds camera at **12.5 cm**, tilt **~15° down** |
| 22 | Steering knuckles + tie-rod | Ackermann front steering |
| 23 | Motor & servo mounts | |

## Tools (not shipped, but needed to build)
- 3D printer + filament (PLA/PETG)
- Soldering iron + solder
- Screwdrivers, hex keys, pliers/cutters
- **Multimeter** (verify VCC, common ground, motor voltage)
- The WRO game mat + field walls for testing

---
### Still to confirm
1. **Drive motor** — exact model / rated voltage (affects L9110S headroom).
2. **Wheel/tire** diameter.
3. **Total cost** of the build.

### Power note
Three 18650 cells in series give ~11.1 V nominal (12.6 V fully charged). The
L9110S is rated **2.5–12 V**, so a freshly charged pack sits marginally above its
maximum — keep an eye on driver temperature. The motor sees the pack voltage minus
the L9110S's internal drop (~1.5–1.8 V). Full wiring: [`../schemes/`](../schemes).
