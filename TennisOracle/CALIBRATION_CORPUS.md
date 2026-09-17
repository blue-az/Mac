# TennisOracle serve calibration corpus (frozen)

Read-only inventory. Do not retune `SERVE_AXIS_DOMINANCE` / speed floors from this
file. Silver sessions are listed but **not** backfilled.

**Source DBs (this Mac):**
- Oracle + IMU: `/Users/blueaz/Python/Mac/tennis_sessions.db`
- Zepp pull: `/Users/blueaz/Downloads/SensorDownload/Current/ztennis.db`
  (from Avant `SM_G386T` `/data/data/com.zepp.ztennis/databases/ztennis.db`)

Zepp `racket_speed` is 0 in serve mode; linked mph is `impact_vel * 2.23694`
(estimate). Clock offset can flip mid-session — use v2 DP alignment, not a 4s window.

## Gold calibration — `serve_session_1`

| | |
|---|---|
| Label | `serve_session_1` (`linked_sessions.date=2026-09-02`) |
| Oracle session | `oracle_20260902_022039` |
| AW shots | o12–o19 (8) |
| Zepp | z21610–z21619 (10) |
| Expected match | **7** |
| oracle_only | 1 (o12 confirmed whiff) |
| zepp_only | 3 (z21614, z21615 chaotic-rotation; z21616 sub-floor) |
| IMU | 578 batches / 28906 samples |
| Role | **calibration fit set** |

## Gold holdout — `serve_session_2`

| | |
|---|---|
| Label | `serve_session_2` (`linked_sessions.date=2026-09-03`) |
| Oracle session | `oracle_20260903_000652` |
| AW shots | o31–o38 (8) |
| Zepp | z21640–z21649 (10) |
| Expected match | **7** |
| oracle_only | 1 (o37) |
| zepp_only | 3 (z21646, z21648, z21649) |
| IMU | 539 batches / 26908 samples |
| Role | **holdout** (do not fit thresholds here) |

## Detector fixture — `serve_session_3`

| | |
|---|---|
| Label | `serve_session_3` (`linked_sessions.date=2026-09-16`) |
| Oracle session | `oracle_20260916_183314` |
| Persisted AW (pre-fix) | o39, o40 (2) |
| Zepp | z21650–z21653 (4) |
| Persisted match (pre-fix) | 2 |
| IMU | 372 batches / 18604 samples |
| Role | **detector regression only** — not a speed/axis calibration set |

Replay of IMU through `TennisShotDetector` after the cross-batch medium-serve
carry should yield **3 AW detections** (peaks ~24.06, ~21.58, ~25.02 rad/s)
matching z21650, z21651, z21653. The ~26.05 rad/s / 44.4% axis burst (z21652)
must stay rejected. Do not rewrite gold `oracle_shots` rows from replay.

## Not in corpus

- `oracle_20260902_224140` + z21620–29 (silver, unlinked, Watch drop)
- `oracle_20260902_231853` + z21630–39 (silver, unlinked, phone timeout)
- Aug 24 AW-only; Aug 25 zero Oracle shots; June Zepp without TennisOracle IMU
