# Bill of Materials — Team The Red Castle (WRO 2026 Future Engineers)

Items marked **(CONFIRM)** need the exact part/spec filled in.

## Electronics — compute & sensing
| # | Component | Spec / notes | Qty |
|---|---|---|---|
| 1 | Raspberry Pi 4 Model B | 2 GB+; runs Raspberry Pi OS Bookworm 64-bit | 1 |
| 2 | microSD card | 16–32 GB, A1/A2, with Bookworm flashed | 1 |
| 3 | **OV5647 wide-angle camera** | 5 MP, ~120° FOV, **fixed focus** (deep depth of field) — the only sensor | 1 |
| 4 | CSI camera ribbon cable | fits Pi 4 CSI port (length to reach the mast) | 1 |

## Electronics — actuation & motor driver
| # | Component | Spec / notes | Qty |
|---|---|---|---|
| 5 | **L9110S** dual H-bridge module | drives the DC motor; `A-IA`→GPIO24, `A-IB`→GPIO23 | 1 |
| 6 | DC drive motor | **(CONFIRM)** type/voltage/gear ratio (e.g. TT 3–6 V / N20) | 1 |
| 7 | Steering servo | **(CONFIRM)** model (e.g. SG90 / MG90S); signal → GPIO13 | 1 |
| 8 | Drive wheels + tires | **(CONFIRM)** size | 2 |
| 9 | Steering wheels (front) + Ackermann linkage | 3D-printed knuckles + tie-rod + servo horn | 1 set |

## Power
| # | Component | Spec / notes | Qty |
|---|---|---|---|
| 10 | Main battery | **(CONFIRM)** e.g. 2S LiPo 7.4 V or 2×18650; feeds L9110S `VCC` directly | 1 |
| 11 | 5 V regulator / UBEC | **≥ 3 A**, dedicated to the Pi (separate rail from the motor) | 1 |
| 12 | Power switch | main on/off | 1 |
| 13 | Battery connector / holder | matches the battery | 1 |
| 14 | Smoothing capacitor | ~1000 µF across L9110S `VCC`–`GND` (recommended) | 1 |

## Wiring & fasteners
| # | Component | Spec / notes | Qty |
|---|---|---|---|
| 15 | Jumper wires (M-F, F-F) | signal + power; **common ground** Pi↔driver↔battery | pack |
| 16 | Heat-shrink / connectors | tidy the power joints | as needed |
| 17 | M2 / M3 screws, nuts, standoffs | mount Pi, driver, servo, camera mast | assortment |

## 3D-printed parts (in `models/`)
| # | Part | Notes |
|---|---|---|
| 18 | Chassis / base plate | holds Pi, battery, driver, motor |
| 19 | Camera mast | rigid, holds camera at **12.5 cm**, tilt **~15° down** |
| 20 | Steering knuckles + tie-rod | Ackermann front steering |
| 21 | Motor & servo mounts | |

## Tools (not shipped, but needed to build)
- 3D printer + filament (PLA/PETG)
- Soldering iron + solder
- Screwdrivers, hex keys, pliers/cutters
- **Multimeter** (verify VCC, common ground, motor voltage)
- The WRO game mat + field walls for testing

---
### To finish this BOM, confirm:
1. **Battery** — voltage & type (drives everything: regulator choice, motor performance).
2. **Drive motor** — model/voltage (affects L9110S headroom).
3. **Steering servo** — model.
4. **Wheel/tire** sizes.
