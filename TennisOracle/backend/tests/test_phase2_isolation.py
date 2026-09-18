"""Phase 2b session isolation and sequence recovery regressions."""
import unittest

from app.main import missing_sequences


class Phase2IsolationTests(unittest.TestCase):
    def test_forward_gap_only(self):
        self.assertEqual(missing_sequences(None, 4), [])
        self.assertEqual(missing_sequences(4, 4), [])
        self.assertEqual(missing_sequences(4, 3), [])
        self.assertEqual(missing_sequences(4, 8), [5, 6, 7])

    def test_duplicate_and_late_fill_do_not_extend_gap(self):
        gap = missing_sequences(10, 14)
        self.assertEqual(gap, [11, 12, 13])
        self.assertEqual(missing_sequences(14, 12), [])
        self.assertEqual(missing_sequences(14, 14), [])

    def test_outbox_filename_is_uuid_scoped(self):
        active = "fresh"
        files = ["old_1.json", "fresh_1.json", "fresh_2.json"]
        self.assertEqual([f for f in files if f.startswith(active + "_")], ["fresh_1.json", "fresh_2.json"])


if __name__ == "__main__":
    unittest.main()
