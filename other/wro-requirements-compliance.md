# WRO 2026 Future Engineers — official requirements & our compliance

Source: *WRO Future Engineers Category – Game Rules 2026*, **§7 (Engineer's
documentation on GitHub)** and **Appendix C (Engineering Journal and
Documentation Requirements)**.

---

## A. What must be submitted

| # | Requirement (rules §7) | Status |
|---|---|---|
| 1 | Documentation uploaded to a **public GitHub repository** | ✅ done |
| 2 | **Hard copy** of the documentation submitted at the international final | ✅ print `Documentation.pdf` |
| 3 | A structured **Engineering Journal (PDF or similar)** — Appendix C.2 | ✅ `Documentation.pdf`, built via `build_pptx_journal.py` in last year's team template/structure |
| 4 | Discussion/motivation for **mobility**, **power & sense**, and **obstacle management** | ✅ README §3, §4, §5 |
| 5 | Photos of the vehicle **from every side, top and bottom** | ✅ `v-photos/` (6 photos) |
| 6 | **Team photo** | ✅ `t-photos/` (member + group photos) |
| 7 | **YouTube URL**, driving autonomously, **≥30 s** of driving, **one video per challenge** | ✅ `video/video.md` |
| 8 | Repository with the **code for all programmed components** | ✅ `src/` |
| 9 | May include **3D printer / laser / CNC model files** | ✅ `models/` — 20 part STLs, 5 sliced 3MF plates, source BOM |
| 10 | **README.md ≥ 5000 characters**, in English | ✅ ~31 000 characters |
| 11 | Code **well documented with comments** | ✅ every module documented |
| 12 | All documentation **in English** (international) | ✅ |
| 13 | Repo **public** from submission and for **≥ 12 months** after | ✅ public |

## B. Commit history rule

The rules require **at least 3 commits**, with deadlines relative to the competition:

| Commit | Deadline | Content requirement |
|---|---|---|
| 1st | no later than **2 months** before | must contain **≥ 1/5** of the final code |
| 2nd | no later than **1 month** before | — |
| 3rd | no later than **2 weeks** before | **this is the one used for scoring** |

> ⚠️ **Action required:** we currently have 15+ commits, but they all date from the
> final build period. Check these dates against your actual competition date — if
> the 2-month/1-month milestones have passed, raise it with your organiser now.
> Also note the rules state that **changes made after the scoring commit may not be
> counted**, so everything important must be in the repository by that date.

The repository link must be submitted **no later than 3 weeks before** the
competition (organisers announce the exact date).

## C. Scoring rubric (Appendix C) — 5 criteria × 6 points = **30 points**

| Score | Meaning |
|---|---|
| **6** | Advanced engineering — fully justified decisions, testing, trade-offs, systems thinking |
| **4** | Competent engineering — clear, structured, reproducible |
| **2** | Limited evidence — incomplete or weakly justified |
| **0** | No evidence |

| # | Criterion | What earns a **6** | Where we cover it |
|---|---|---|---|
| 1 | Mobility & Mechanical Design | torque/speed reasoning, trade-offs, testing that changed the design | README §3.2–3.4, journal §6 |
| 2 | Power & Sensor Architecture | power budget, sensor trade-offs, placement justified by **field geometry**, calibration, failure points | README §4.1–4.3, `schemes/` |
| 3 | Software Architecture & Obstacle Strategy | state machine + rationale, justified algorithms, edge cases, testing metrics | README §5.1b–5.1c, §5.7 |
| 4 | Systems Thinking & Engineering Decisions | explicit constraints, trade-offs, iteration, risk & mitigation, "we chose X instead of Y" | README §5.6, §5.8, journal |
| 5 | Reproducibility & GitHub Quality | fully reproducible, clear structure, meaningful commits, testing workflow, **versioning/release notes** | repo structure, README §7 |

### What still separates us from a 6

| Criterion | Gap |
|---|---|
| 1 | A measured (timed) real top speed, not just the theoretical no-load figure |
| 2 | Measured current draw (we have datasheet estimates, not a clamp-meter reading) |
| 3 | **Quantitative metrics from real runs** (lap times, success rate over N runs) — the CSV logging is built and used for debugging; a summarised results table across multiple runs is not yet written up |
| 4 | A documented version history (v1 → v2 → v3) of the mechanical design specifically, beyond what the journal already narrates |
| 5 | A tagged release (`v1.0`) on GitHub |

> The rules' own level-6 examples are explicitly **quantitative**, e.g. *"increased
> lap consistency from 60 % to 85 % over 20 runs"* and *"reduced misdetection by
> 40 %"*. Numbers from real testing are the single highest-value thing left to add.

## D. Notes

- **Appendix D** (minimal component set — encoder, IMU, distance sensors, etc.) is
  explicitly *"a suggestion rather than the requirements"*, so our camera-only
  design is fully compliant.
- The rules state: *"The main source for scoring points is the GitHub repository."*
  The hard copy is a backup if the repo is unreachable, and helps judges track
  teams during the competition.
- An official template exists at
  `github.com/World-Robot-Olympiad-Association/wro2022-fe-template`; our structure
  follows it (`src`, `models`, `schemes`, `t-photos`, `v-photos`, `video`, `other`).
