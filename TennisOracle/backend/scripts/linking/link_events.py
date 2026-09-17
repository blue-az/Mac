"""Generalized Oracle↔Zepp event linker.

Dry-run by default. Does not replace link_session_v1/v2 templates.
Never UPDATE rows that already have zepp_id (gold-link guard).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from typing import List, Optional, Sequence, Tuple

MPS_TO_MPH = 2.23694
GOLD_LABELS = frozenset({"serve_session_1", "serve_session_2"})


@dataclass
class Event:
    id: int
    ts: float
    speed_mph: float
    mode: str
    extra: dict = field(default_factory=dict)


@dataclass
class LinkConfig:
    mode: str = "auto"
    max_gap_sec: Optional[float] = None
    speed_weight: Optional[float] = None
    zepp_speed_unit: str = "auto"
    ambiguous_dt_sec: float = 2.0
    # 25 mph: ss1 o14 is ~20.3; ss194708 o45 is ~34 (ambiguous). Not a detector threshold.
    ambiguous_dv_mph: float = 25.0

    def resolved(self, mode: str) -> "LinkConfig":
        gap = self.max_gap_sec
        weight = self.speed_weight
        if gap is None:
            gap = 15.0 if mode == "serve" else 2.5
        if weight is None:
            weight = 0.5 if mode == "serve" else 0.0
        return LinkConfig(
            mode=mode,
            max_gap_sec=gap,
            speed_weight=weight,
            zepp_speed_unit=self.zepp_speed_unit,
            ambiguous_dt_sec=self.ambiguous_dt_sec,
            ambiguous_dv_mph=self.ambiguous_dv_mph,
        )


@dataclass
class Pair:
    aw_id: int
    zepp_id: int
    dt_sec: float
    aw_mph: float
    z_mph: float
    aw_mode: str
    z_type: str

    def as_report(self) -> dict:
        return asdict(self)


class GoldLinkGuard(RuntimeError):
    pass


def parse_utc(ts: str) -> float:
    return dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp()


def parse_id_range(spec: str) -> Tuple[int, int]:
    if "-" in spec:
        a, b = spec.split("-", 1)
        return int(a), int(b)
    v = int(spec)
    return v, v


def zepp_speed_mph(racket_speed: float, impact_vel: float, mode: str, unit: str) -> float:
    """Normalize Zepp speed to mph. Serve racket_speed is usually 0."""
    rs = float(racket_speed or 0.0)
    iv = float(impact_vel or 0.0)
    resolved = unit
    if unit == "auto":
        if mode == "serve" and rs == 0.0:
            resolved = "impact_mps"
        elif 15.0 < rs < 45.0:
            resolved = "mps"
        else:
            resolved = "mph"
    if resolved == "impact_mps":
        return iv * MPS_TO_MPH
    if resolved == "mps":
        return rs * MPS_TO_MPH
    return rs


def align(oracle: Sequence[Event], zepp: Sequence[Event], cfg: LinkConfig) -> dict:
    """Monotonic DP. Report splits time_pairs vs match/ambiguous/only."""
    mode = cfg.mode
    cfg = cfg.resolved(mode)
    n, m = len(oracle), len(zepp)
    gap = float(cfg.max_gap_sec)
    w = float(cfg.speed_weight)
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = dp[i - 1][0] + gap
    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] + gap
    choice = [[None] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            o, z = oracle[i - 1], zepp[j - 1]
            cost = abs(o.ts - z.ts) + w * abs(o.speed_mph - z.speed_mph)
            options = [
                (dp[i - 1][j - 1] + cost, "match"),
                (dp[i - 1][j] + gap, "skip_o"),
                (dp[i][j - 1] + gap, "skip_z"),
            ]
            best = min(options, key=lambda x: x[0])
            dp[i][j] = best[0]
            choice[i][j] = best[1]

    i, j = n, m
    pairs: List[Pair] = []
    aw_only: List[int] = []
    zepp_only: List[int] = []
    while i > 0 or j > 0:
        if i > 0 and j > 0 and choice[i][j] == "match":
            o, z = oracle[i - 1], zepp[j - 1]
            pairs.append(
                Pair(
                    aw_id=o.id,
                    zepp_id=z.id,
                    dt_sec=o.ts - z.ts,
                    aw_mph=o.speed_mph,
                    z_mph=z.speed_mph,
                    aw_mode=o.mode,
                    z_type=str(z.extra.get("swing_type", "")),
                )
            )
            i -= 1
            j -= 1
        elif i > 0 and (j == 0 or choice[i][j] == "skip_o"):
            aw_only.append(oracle[i - 1].id)
            i -= 1
        else:
            zepp_only.append(zepp[j - 1].id)
            j -= 1
    pairs.reverse()
    aw_only.reverse()
    zepp_only.reverse()

    matches, ambiguous = [], []
    for p in pairs:
        dv = abs(p.aw_mph - p.z_mph)
        # Serve gold pairs have |dt| of 0–10s (known Zepp clock flip). Strokes
        # use a tight time window; velocity still splits match vs ambiguous.
        if cfg.mode == "serve":
            ok = dv <= max(cfg.ambiguous_dv_mph, 40.0)
        else:
            ok = abs(p.dt_sec) <= cfg.ambiguous_dt_sec and dv <= cfg.ambiguous_dv_mph
        if ok:
            matches.append(p)
        else:
            ambiguous.append(p)

    return {
        "mode": cfg.mode,
        "max_gap_sec": cfg.max_gap_sec,
        "speed_weight": cfg.speed_weight,
        "n_aw": n,
        "n_zepp": m,
        "time_pairs": [p.as_report() for p in pairs],
        "match": [p.as_report() for p in matches],
        "ambiguous": [p.as_report() for p in ambiguous],
        "aw_only": aw_only,
        "zepp_only": zepp_only,
        "n_time_pairs": len(pairs),
        "n_match": len(matches),
        "n_ambiguous": len(ambiguous),
        "n_aw_only": len(aw_only),
        "n_zepp_only": len(zepp_only),
    }


SESSION_TO_TAG = {
    "oracle_20260902_022039": ("2026-09-02", None),
    "oracle_20260903_000652": ("2026-09-03", None),
    "oracle_20260916_183314": (None, (39, 40)),  # ss3 persisted shots only
    "oracle_20260916_194708": ("oracle_20260916_194708", None),
}


def load_oracle_shots(con: sqlite3.Connection, *, session: Optional[str] = None,
                      ids: Optional[Tuple[int, int]] = None,
                      session_tag: Optional[str] = None) -> List[Event]:
    if ids:
        lo, hi = ids
        rows = con.execute(
            "SELECT id, ts, oracle_mph, mode FROM oracle_shots WHERE id BETWEEN ? AND ? ORDER BY ts",
            (lo, hi),
        ).fetchall()
    elif session_tag:
        rows = con.execute(
            "SELECT id, ts, oracle_mph, mode FROM oracle_shots WHERE session_tag=? ORDER BY ts",
            (session_tag,),
        ).fetchall()
    elif session:
        mapped = SESSION_TO_TAG.get(session)
        if mapped:
            tag, id_pair = mapped
            if id_pair:
                return load_oracle_shots(con, ids=id_pair)
            return load_oracle_shots(con, session_tag=tag)
        rows = con.execute(
            "SELECT id, ts, oracle_mph, mode FROM oracle_shots WHERE session_tag=? ORDER BY ts",
            (session,),
        ).fetchall()
    else:
        raise SystemExit("need --oracle-session or --oracle-ids")
    return [Event(id=r[0], ts=parse_utc(r[1]), speed_mph=float(r[2] or 0), mode=r[3] or "") for r in rows]


def load_zepp(con: sqlite3.Connection, id_lo: int, id_hi: int, mode: str, unit: str) -> List[Event]:
    rows = con.execute(
        """SELECT _id, client_created/1000.0, swing_type, racket_speed, impact_vel
           FROM swings WHERE _id BETWEEN ? AND ? ORDER BY client_created""",
        (id_lo, id_hi),
    ).fetchall()
    out = []
    for zid, ts, stype, rs, iv in rows:
        mph = zepp_speed_mph(rs, iv, mode, unit)
        out.append(Event(id=zid, ts=float(ts), speed_mph=mph, mode=str(stype), extra={"swing_type": stype, "racket_speed": rs, "impact_vel": iv}))
    return out


def infer_mode(oracle: Sequence[Event], explicit: str) -> str:
    if explicit and explicit != "auto":
        return explicit
    modes = [o.mode for o in oracle if o.mode]
    if not modes:
        return "serve"
    return max(set(modes), key=modes.count)


def gold_guard(con: sqlite3.Connection, oracle: Sequence[Event], label: Optional[str]) -> None:
    if label in GOLD_LABELS:
        raise GoldLinkGuard(f"refusing --write for gold label {label}")
    ids = [o.id for o in oracle]
    if not ids:
        return
    q = f"SELECT id FROM oracle_shots WHERE id IN ({','.join('?'*len(ids))}) AND zepp_id IS NOT NULL"
    hit = con.execute(q, ids).fetchall()
    if hit:
        raise GoldLinkGuard(f"refusing --write: already linked oracle ids {[r[0] for r in hit]}")
    if label:
        row = con.execute("SELECT session_label FROM linked_sessions WHERE session_label=?", (label,)).fetchone()
        if row:
            raise GoldLinkGuard(f"refusing --write: linked_sessions already has {label}")


def format_report(report: dict) -> str:
    lines = [
        f"mode={report['mode']} gap={report['max_gap_sec']} speed_weight={report['speed_weight']}",
        f"AW={report['n_aw']} Zepp={report['n_zepp']}  "
        f"time_pairs={report['n_time_pairs']} match={report['n_match']} "
        f"ambiguous={report['n_ambiguous']} aw_only={report['n_aw_only']} zepp_only={report['n_zepp_only']}",
        "",
        "TIME PAIRS (DP, not yet validated):",
    ]
    for p in report["time_pairs"]:
        lines.append(
            f"  o{p['aw_id']} ↔ z{p['zepp_id']}  dt={p['dt_sec']:+.2f}s  "
            f"AW={p['aw_mph']:.1f}mph  Z={p['z_mph']:.1f}mph"
        )
    lines.append("MATCH (|dt| and |dv| within thresholds):")
    if not report["match"]:
        lines.append("  (none)")
    for p in report["match"]:
        lines.append(f"  o{p['aw_id']} ↔ z{p['zepp_id']}  dt={p['dt_sec']:+.2f}s")
    lines.append("AMBIGUOUS (time-paired but dt/dv fail):")
    if not report["ambiguous"]:
        lines.append("  (none)")
    for p in report["ambiguous"]:
        lines.append(
            f"  o{p['aw_id']} ↔ z{p['zepp_id']}  dt={p['dt_sec']:+.2f}s  "
            f"dv={p['aw_mph']-p['z_mph']:+.1f}mph"
        )
    lines.append(f"AW-only: {report['aw_only']}")
    lines.append(f"Zepp-only: {report['zepp_only']}")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Oracle↔Zepp linker (dry-run default)")
    p.add_argument("--oracle-db", required=True)
    p.add_argument("--zepp-db", required=True)
    p.add_argument("--oracle-session")
    p.add_argument("--oracle-ids", help="lo-hi inclusive")
    p.add_argument("--zepp-ids", required=True, help="lo-hi inclusive")
    p.add_argument("--mode", default="auto", choices=["auto", "serve", "strokes"])
    p.add_argument("--label")
    p.add_argument("--date")
    p.add_argument("--max-gap-sec", type=float)
    p.add_argument("--speed-weight", type=float)
    p.add_argument("--zepp-speed-unit", default="auto", choices=["auto", "mps", "mph", "impact_mps"])
    p.add_argument("--write", action="store_true", help="persist (off by default)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    zlo, zhi = parse_id_range(args.zepp_ids)
    oids = parse_id_range(args.oracle_ids) if args.oracle_ids else None
    con_o = sqlite3.connect(f"file:{args.oracle_db}?mode=ro", uri=True)
    con_z = sqlite3.connect(f"file:{args.zepp_db}?mode=ro", uri=True)
    oracle = load_oracle_shots(con_o, session=args.oracle_session, ids=oids)
    mode = infer_mode(oracle, args.mode)
    zepp = load_zepp(con_z, zlo, zhi, mode, args.zepp_speed_unit)
    cfg = LinkConfig(
        mode=mode,
        max_gap_sec=args.max_gap_sec,
        speed_weight=args.speed_weight,
        zepp_speed_unit=args.zepp_speed_unit,
    )
    report = align(oracle, zepp, cfg)
    report["label"] = args.label
    report["date"] = args.date
    report["oracle_session"] = args.oracle_session
    if args.write:
        try:
            gold_guard(con_o, oracle, args.label)
        except GoldLinkGuard as exc:
            print(f"GOLD GUARD: {exc}", file=sys.stderr)
            return 2
        print("ERROR: --write is implemented as guard-only; no current-session writes.", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_report(report))
        print("\nDRY-RUN: no DB writes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
