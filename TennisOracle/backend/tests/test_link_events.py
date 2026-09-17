"""Literal-pair regression for scripts.linking.link_events.

Does not overwrite v1/v2 templates. Does not write gold or 194708 links.
"""
from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from scripts.linking.link_events import (  # noqa: E402
    GOLD_LABELS,
    GoldLinkGuard,
    LinkConfig,
    align,
    gold_guard,
    infer_mode,
    load_oracle_shots,
    load_zepp,
    main,
)

ORACLE_DB = "/Users/blueaz/Python/Mac/tennis_sessions.db"
ZEPP_DB = "/Users/blueaz/Downloads/SensorDownload/Current/ztennis.db"

# Frozen gold / fixture pair lists — not n_aw == n_match
SS1_MATCH = [
    (13, 21610), (14, 21611), (15, 21612), (16, 21613),
    (17, 21617), (18, 21618), (19, 21619),
]
SS1_AW_ONLY = [12]
SS1_ZEPP_ONLY = [21614, 21615, 21616]

SS2_MATCH = [
    (31, 21640), (32, 21641), (33, 21642), (34, 21643),
    (35, 21644), (36, 21645), (38, 21647),
]
SS2_AW_ONLY = [37]
SS2_ZEPP_ONLY = [21646, 21648, 21649]

SS3_MATCH = [(39, 21651), (40, 21653)]
SS3_ZEPP_ONLY = [21650, 21652]

SS194708_TIME_PAIRS = [
    (41, 21679), (42, 21680), (43, 21681), (44, 21682),
    (45, 21683), (46, 21684), (47, 21685), (48, 21691),
    (49, 21693), (50, 21694), (51, 21696), (52, 21697),
    (53, 21698),
]
SS194708_ZEPP_ONLY = [21686, 21687, 21688, 21689, 21690, 21692, 21695]
SS194708_AMBIGUOUS = [(45, 21683)]


def _run(session, zlo, zhi, mode):
    con_o = sqlite3.connect(f"file:{ORACLE_DB}?mode=ro", uri=True)
    con_z = sqlite3.connect(f"file:{ZEPP_DB}?mode=ro", uri=True)
    oracle = load_oracle_shots(con_o, session=session)
    mode = infer_mode(oracle, mode)
    zepp = load_zepp(con_z, zlo, zhi, mode, "auto")
    return align(oracle, zepp, LinkConfig(mode=mode))


def _pairs(rows):
    return [(p["aw_id"], p["zepp_id"]) for p in rows]


@unittest.skipUnless(Path(ORACLE_DB).exists() and Path(ZEPP_DB).exists(), "local DBs missing")
class LinkEventsRegression(unittest.TestCase):
    def test_ss1_gold_literal_pairs(self):
        r = _run("oracle_20260902_022039", 21610, 21619, "serve")
        self.assertEqual(_pairs(r["match"]), SS1_MATCH)
        self.assertEqual(r["aw_only"], SS1_AW_ONLY)
        self.assertEqual(r["zepp_only"], SS1_ZEPP_ONLY)
        self.assertEqual(r["n_match"], 7)
        self.assertNotEqual(r["n_match"], r["n_aw"])

    def test_ss2_holdout_literal_pairs(self):
        r = _run("oracle_20260903_000652", 21640, 21649, "serve")
        self.assertEqual(_pairs(r["match"]), SS2_MATCH)
        self.assertEqual(r["aw_only"], SS2_AW_ONLY)
        self.assertEqual(r["zepp_only"], SS2_ZEPP_ONLY)
        self.assertEqual(r["n_match"], 7)
        self.assertNotEqual(r["n_match"], r["n_aw"])

    def test_ss3_persisted_fixture(self):
        r = _run("oracle_20260916_183314", 21650, 21653, "serve")
        self.assertEqual(_pairs(r["match"]), SS3_MATCH)
        self.assertEqual(r["zepp_only"], SS3_ZEPP_ONLY)
        self.assertEqual(r["aw_only"], [])
        self.assertEqual(r["n_aw"], 2)

    def test_ss194708_time_pairs_vs_match_vs_ambiguous(self):
        r = _run("oracle_20260916_194708", 21679, 21698, "strokes")
        self.assertEqual(_pairs(r["time_pairs"]), SS194708_TIME_PAIRS)
        self.assertEqual(r["zepp_only"], SS194708_ZEPP_ONLY)
        self.assertEqual(r["aw_only"], [])
        self.assertEqual(_pairs(r["ambiguous"]), SS194708_AMBIGUOUS)
        self.assertNotIn((45, 21683), _pairs(r["match"]))
        self.assertEqual(r["n_time_pairs"], 13)
        self.assertEqual(r["n_match"], 12)
        self.assertEqual(r["n_zepp_only"], 7)
        self.assertNotEqual(r["n_match"], r["n_aw"])
        self.assertNotEqual(r["n_match"], r["n_time_pairs"])

    def test_dry_run_cli_no_writes(self):
        con = sqlite3.connect(ORACLE_DB)
        before = con.execute(
            "SELECT id, zepp_id FROM oracle_shots WHERE id BETWEEN 41 AND 53"
        ).fetchall()
        rc = main([
            "--oracle-db", ORACLE_DB,
            "--zepp-db", ZEPP_DB,
            "--oracle-session", "oracle_20260916_194708",
            "--zepp-ids", "21679-21698",
            "--mode", "strokes",
            "--json",
        ])
        self.assertEqual(rc, 0)
        after = con.execute(
            "SELECT id, zepp_id FROM oracle_shots WHERE id BETWEEN 41 AND 53"
        ).fetchall()
        self.assertEqual(before, after)

    def test_write_gold_label_aborts(self):
        rc = main([
            "--oracle-db", ORACLE_DB,
            "--zepp-db", ZEPP_DB,
            "--oracle-session", "oracle_20260902_022039",
            "--zepp-ids", "21610-21619",
            "--mode", "serve",
            "--label", "serve_session_1",
            "--write",
        ])
        self.assertEqual(rc, 2)
        self.assertIn("serve_session_1", GOLD_LABELS)

    def test_gold_guard_on_existing_zepp_id(self):
        con = sqlite3.connect(f"file:{ORACLE_DB}?mode=ro", uri=True)
        oracle = load_oracle_shots(con, session="oracle_20260902_022039")
        with self.assertRaises(GoldLinkGuard):
            gold_guard(con, oracle, "stroke_session_new")


if __name__ == "__main__":
    unittest.main(verbosity=2)
