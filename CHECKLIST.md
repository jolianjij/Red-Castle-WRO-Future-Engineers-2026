# Submission Checklist — Team The Red Castle

Two days to go. **📷 = only you can do it · 🤖 = Claude can do/commit.**

## Done
- [x] Official WRO repo structure (`src`, `models`, `schemes`, `t-photos`, `v-photos`, `video`, `other`)
- [x] Engineering `README.md` (mobility, power/sense, camera/vision, both algorithms, setup/run)
- [x] All control code + tools in `src/`
- [x] Bill of Materials (`other/bill-of-materials.md`)
- [x] Public repo pushed

## 🔴 Mandatory for judging
- [x] 📷 `v-photos/` — 6 vehicle photos (front, back, left, right, top, bottom)
- [ ] 📷 `t-photos/` — 2 group photos (`team-official.jpg`, `team-fun.jpg`)
- [ ] 🎥 `video/video.md` — driving video links (Open + Obstacle, one take each)
- [x] 🖼️ `schemes/` — wiring diagram image (Pi ↔ L9110S ↔ servo ↔ power, common ground)
- [ ] 🧩 `models/` — actual CAD/STL files of the printed parts
- [x] ✍️ Team names + roles in `README.md`
- [ ] 📷 Member photos → `t-photos/` (ahmad-kalthom.jpg, jolian-wassof.jpg, omar-shammout.jpg, louay-rashwan.jpg)
- [ ] ✍️ Bio + email for each member (placeholders are in README §12)

## 🟡 Recommended (higher documentation score)
- [ ] 🤖 Wiring pin-table / ASCII schematic in `schemes/` (text backup to the image)
- [ ] 🤖 Assembly / build-steps section
- [ ] 🤖 Engineering journal (design process: brownout fix, no-diff steering, focus/exposure)
- [x] 🤖 BOM: battery (3×18650), buck converter, SG90 servo confirmed from the wiring diagram
- [ ] 🤖 BOM: drive motor model + wheel diameter + total cost still needed
- [ ] 🤖 Commit reference `colors.json` + `servo_center.txt` (pull from Pi once tuning is final)

## ⚙️ To actually compete (not GitHub, but required)
- [ ] Finish color tuning — orange, green, red, magenta with each object in view
- [ ] Open Challenge field test → tune `STEER_MAX` and PD gains
- [ ] Obstacle Challenge field test → pillar passing + parking
- [ ] Record the runs for the video

## Info Claude needs from you
- [x] ~~Team members' names + roles~~ — done
- [x] ~~Battery voltage & type~~ — 3×18650 in series
- [x] ~~Steering servo model~~ — SG90
- [ ] Drive motor model/voltage
- [ ] Wheel/tire diameter
- [ ] Each member's bio + email
