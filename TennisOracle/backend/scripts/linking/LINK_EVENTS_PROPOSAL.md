# Generalized event linker — proposal (no implementation yet)

Does **not** replace `link_session_v1_naive_window.py` or
`link_session_v2_dp_alignment.py` (ss1 historical templates). No gold
`linked_sessions` / `zepp_id` rows are written until `--write` is added later.

## Why

Backend never auto-links. Current v2 is a hardcoded serve_session_1 script
(`impact_vel * 2.23694` because serve `racket_speed=0`). Strokes have a
usable `racket_speed` that is **not** the same unit as `oracle_mph`.

## CLI (dry-run default)

```text
python3 -m scripts.linking.link_events
  --oracle-db /Users/blueaz/Python/Mac/tennis_sessions.db
  --zepp-db   /Users/blueaz/Downloads/SensorDownload/Current/ztennis.db
  --oracle-session oracle_YYYYMMDD_HHMMSS   # or --oracle-ids 41-53
  --zepp-ids 21679-21698                    # or --zepp-id-min/--max
  --mode serve|strokes|auto                 # auto: majority oracle_shots.mode
  --label stroke_session_1
  --date 2026-09-16                         # local date for linked_sessions
  --max-gap-sec AUTO                        # serve 15, strokes 2.5
  --speed-weight 0.5
  --zepp-speed-unit auto|mps|mph            # auto: serve→impact_vel mps;
                                            #        strokes racket in (15,45)→mps
  --ambiguous-dt-sec 2.0
  --ambiguous-dv-mph 20
  --write                                   # OFF by default; refuse if gold
                                            # session_label already exists
```

Exit 0 on dry-run. `--write` requires stdin `yes` or `--i-mean-it` and still
refuses to UPDATE rows whose `zepp_id` is already set (ss1/ss2).

## Library API

```python
@dataclass
class LinkConfig:
    mode: str
    max_gap_sec: float
    speed_weight: float
    zepp_speed_unit: str
    ambiguous_dt_sec: float = 2.0
    ambiguous_dv_mph: float = 20.0

def zepp_speed_mph(row, cfg) -> float: ...
def align(oracle: list[Event], zepp: list[Event], cfg: LinkConfig) -> Alignment:
    # monotonic DP, cost = |dt| + speed_weight * |v_aw_mph - v_z_mph|
    # gap penalty = max_gap_sec; one-to-one
```

`Alignment` rows: `match | aw_only | zepp_only | ambiguous`
- **match**: DP pair and `|dt|<=ambiguous_dt` and `|dv|<=ambiguous_dv`
- **ambiguous**: DP pair that fails dt/dv (kept, not forced into match)
- **aw_only / zepp_only**: DP skips (unmatched rows **preserved** in the report)

Dry-run prints a table + JSON summary; does not INSERT/UPDATE.

## Tests (`backend/tests/test_link_events.py`)

| Fixture | Inputs | Expect (do not infer n_aw == n_match) |
|---|---|---|
| **ss1 gold** | session `oracle_20260902_022039` / z21610–21619 | 7 match (o13–19↔those z), o12 aw_only, z21614–16 zepp_only |
| **ss2 holdout** | `oracle_20260903_000652` / z21640–21649 | 7 match, o37 aw_only, z21646/48/49 zepp_only |
| **ss3 fixture** | persisted o39–40 / z21650–21653 | 2 match, 2 zepp_only (detector replay 3rd shot is **out of scope** for linker) |
| **ss194708 fixture** | o41–53 / z21679–21698 | 13 time-pairs; **7 zepp_only**; **o45↔z21683 ambiguous** (dt~0, dv huge); 0 aw_only |
| dry-run | `--write` omitted | zero SQL writes (`query_only` / rowcount unchanged) |
| gold guard | `--write --label serve_session_1` | abort, ss1 `zepp_id` untouched |
| unit | synthetic two clocks + extra Zepp | monotonic, no 1-to-many |

ss1/ss2 expected pairs frozen as literals in the test, not “count == 7”.

## Non-goals (this change)

- Overwrite v1/v2 templates
- Auto-link from uvicorn
- Retune `SERVE_AXIS_DOMINANCE`
- Backfill silver 224140 / 231853
- `--write` on 194708 until the dry-run is accepted
