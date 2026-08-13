# Submission Checklist — Team The Red Castle

**📷 = only you can do it · 🤖 = Claude can do/commit.**

## Done
- [x] Official WRO repo structure (`src`, `models`, `schemes`, `t-photos`, `v-photos`, `video`, `other`)
- [x] Engineering `README.md` (mobility, power/sense, camera/vision, both algorithms, setup/run)
- [x] All control code + tools in `src/`
- [x] Bill of Materials (`other/bill-of-materials.md`)
- [x] Public repo pushed

## 🔴 Mandatory for judging
- [x] 📷 `v-photos/` — 6 vehicle photos (front, back, left, right, top, bottom)
- [x] 📷 `t-photos/` — 2 group photos (`team-official.jpg`, `team-fun.jpg`)
- [x] 🎥 `video/video.md` — Open Challenge + Obstacle Challenge YouTube links added
- [x] 🖼️ `schemes/` — wiring diagram image (Pi ↔ L9110S ↔ servo ↔ power, common ground)
- [x] 🧩 `models/3d-parts/` — 20 part STLs (5 subassemblies) + Mechanical-BOM.docx
- [x] 🧩 `models/printing/` — 5 sliced 3MF plates, ready to print
- [x] ✍️ Team names + roles in `README.md`
- [x] 📷 Member photos → all 4 members done (Ahmad, Jolian, Omar, Louay)
- [x] ✍️ Bio + email for each member — filled in README §12

## 🟡 Recommended (higher documentation score)
- [ ] 🤖 Wiring pin-table / ASCII schematic in `schemes/` (text backup to the image)
- [ ] 🤖 Assembly / build-steps section
- [x] 🤖 Engineering journal (design process, iterative debugging) — `ENGINEERING-JOURNAL.md`
- [x] 🤖 BOM: battery (3×18650), buck converter, SG90 servo confirmed from the wiring diagram
- [x] 🤖 BOM: N20 motor (12 V 200 rpm), differential, 25:20 gears, PLA+ Silk Silver / Bambu A1 / Fusion 360, Pi 2 GB
- [x] 🤖 BOM: 20-part printed-parts table with quantities and fixed/moving status
- [x] 📏 Measurements: mass (407g), wheel diameter (4.7cm), wheelbase (9.4cm), track (8.5cm), dimensions (14.2x9.3x15cm), camera height/tilt confirmed
- [ ] 📏 Measured (timed) real max speed — theoretical 0.39 m/s is in the docs as a placeholder
- [ ] 🤖 BOM: total cost
- [ ] 🤖 BOM: fastener sizes/counts and bronze spacer types per assembly (not in the current Mechanical-BOM.docx)
- [ ] 🤖 Commit reference `colors.json` + `servo_center.txt` (pull from Pi once tuning is final)
- [ ] 📷 BOM part photos (one per printed part — placeholders are in `models/README.md`)
- [ ] 📷 Full Fusion 360 assembly file (`.f3d`/`.step`) + differential/steering assembly photos

## ⚙️ Competition readiness
- [x] Color tuning (orange, green, red, magenta) calibrated on the real field
- [x] Open Challenge field-tested, both directions
- [x] Obstacle Challenge field-tested — sign passing + lane keeping between signs
- [x] Both challenge runs recorded and uploaded

## 📓 Engineering Journal (PPTX → PDF) — **on hold**
Per instruction: **do not start this until the GitHub repo is finished** and the
final `src/` + algorithm are confirmed. Once given the go-ahead:
- [ ] Build in last year's template/structure (from `Documentation.pdf`)
- [ ] Team members / intro page
- [ ] Open Challenge section (algorithm, step-by-step, figures)
- [ ] Obstacle Challenge section (algorithm, step-by-step, figures)
- [ ] Mobility Management (steering, drive, differential, body/3D design)
- [ ] Power and Sense Management (power source, components, wiring diagrams, sensing)
- [ ] Robot's Evolution (past → present iterations)
- [ ] Leave named placeholders for photos not yet available
- [ ] Export as PDF once complete

## Info still needed from you
- [ ] Real measured max speed (timed run)
- [ ] Total build cost
- [ ] Fastener/spacer BOM (screw sizes, counts, bronze spacer types)
- [ ] BOM part photos + Fusion assembly file (you mentioned these are coming)
