# Bill of Materials — Team The Red Castle (WRO 2026 Future Engineers)

## Electronics — compute & sensing
| # | Component | Spec / notes | Qty |
|---|---|---|---|
| 1 | Raspberry Pi 4 Model B | **2 GB RAM**; Raspberry Pi OS Bookworm 64-bit | 1 |
| 2 | microSD card | 16–32 GB, A1/A2, with Bookworm flashed | 1 |
| 3 | **OV5647 wide-angle camera** | 5 MP, ~120° FOV, **fixed focus** (deep depth of field) — the only sensor | 1 |
| 4 | CSI camera ribbon cable | Pi 4 CSI port → camera on the mast (~15 cm); carries data **and** power | 1 |

## Electronics — actuation & motor driver
| # | Component | Spec / notes | Qty |
|---|---|---|---|
| 5 | **L9110S** dual H-bridge module | drives the DC motor; `A-IA`→GPIO24, `A-IB`→GPIO23; rated 2.5–12 V, ~0.8 A | 1 |
| 6 | **N20 gear motor** | 12 V, **200 rpm**, brushed micro gear motor — rear-axle drive | 1 |
| 6a | **Differential** | rear axle differential — lets the driven wheels turn at different speeds | 1 |
| 6b | Transmission gears | **25:20** spur pair (1.25:1 reduction), motor pinion → differential | 1 set |
| 7 | **MG90S** steering servo | ~13 g metal-gear micro servo; signal → GPIO13, powered from the Pi's 5 V | 1 |
| 8 | Drive wheels + tires | rear, on the differential axle, **4.7 cm** diameter | 2 |
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
| 19 | M3 × 8 mm screws | mounting the printed chassis parts | 18 |
| 20 | M3 × 20 mm screws | mounting the printed chassis parts | 4 |
| 21 | Brass standoff, male–female, 25 mm | Pi mounting stack | 4 |
| 22 | Brass standoff, female–female, 20 mm | Pi mounting stack | 4 |

## 3D-printed parts

20 printed parts across 5 subassemblies (chassis, steering, rear drive/differential,
wheels, battery slider) — full quantities, fixed/moving status and source files
are in **[`../models/README.md`](../models/README.md)**. All parts are PLA+.

## Tools (not shipped, but needed to build)
- 3D printer + filament (PLA/PETG)
- Soldering iron + solder
- Screwdrivers, hex keys, pliers/cutters
- **Multimeter** (verify VCC, common ground, motor voltage)
- The WRO game mat + field walls for testing

---
## Manufacturing
| Item | Detail |
|---|---|
| CAD | **Fusion 360** — full assembly + parts in [`../models/`](../models) |
| 3D printer | **Bambu Lab A1** |
| Material | **PLA+ Silk Silver** |
| Sliced plates | print-ready plates with settings in [`../models/printing/`](../models/printing) |

## Total build cost

**≈ $120**, electronics, printed parts (filament), fasteners and battery combined.

### Power note
Three 18650 cells in series give ~11.1 V nominal (12.6 V fully charged). The
L9110S is rated **2.5–12 V**, so a freshly charged pack sits marginally above its
maximum — keep an eye on driver temperature. The motor sees the pack voltage minus
the L9110S's internal drop (~1.5–1.8 V). Full wiring: [`../schemes/`](../schemes).
