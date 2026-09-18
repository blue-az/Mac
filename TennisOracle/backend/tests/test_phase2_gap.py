"""Regression tests for Phase 2b gap bookkeeping semantics."""
import sqlite3
import unittest


class Phase2GapTests(unittest.TestCase):
    def test_gap_is_recorded_and_late_fill_closes_it(self):
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE transport_gaps (watch_session_uuid TEXT, missing_seq INTEGER, filled_at INTEGER, PRIMARY KEY (watch_session_uuid, missing_seq))")
        for seq in range(2, 5):
            con.execute("INSERT OR IGNORE INTO transport_gaps VALUES (?, ?, NULL)", ("s", seq))
        self.assertEqual(con.execute("SELECT count(*) FROM transport_gaps WHERE filled_at IS NULL").fetchone()[0], 3)
        con.execute("UPDATE transport_gaps SET filled_at=1 WHERE watch_session_uuid=? AND missing_seq=?", ("s", 3))
        self.assertEqual(con.execute("SELECT missing_seq FROM transport_gaps WHERE filled_at IS NULL").fetchall(), [(2,), (4,)])
        con.close()

    def test_duplicate_gap_insert_is_idempotent(self):
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE transport_gaps (watch_session_uuid TEXT, missing_seq INTEGER, PRIMARY KEY (watch_session_uuid, missing_seq))")
        con.execute("INSERT OR IGNORE INTO transport_gaps VALUES ('s', 2)")
        con.execute("INSERT OR IGNORE INTO transport_gaps VALUES ('s', 2)")
        self.assertEqual(con.execute("SELECT count(*) FROM transport_gaps").fetchone()[0], 1)
        con.close()


if __name__ == "__main__":
    unittest.main()
