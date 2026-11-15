"""Offline checks for archival replay provenance and failure policy."""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import newwave_longitudinal_replay as replay


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.timestamp = "20250902030405"
        self.anchor = int(datetime(2025, 9, 3, tzinfo=timezone.utc).timestamp() * 1000)
        self.start = self.anchor - 30 * 86400 * 1000

    def test_exact_original_with_query_and_pre_anchor_capture(self):
        original = "https://example.org/article?id=12&lang=en"
        address = f"https://web.archive.org/web/{self.timestamp}id_/{original}"
        self.assertEqual(replay.safe_replay_url(
            address, original, selected_timestamp=self.timestamp,
            start_millis=self.start, end_millis=self.anchor)[:2], (True, "ok"))

    def test_changed_capture_or_original_or_host_rejected(self):
        original = "https://example.org/article"
        for address in (
            f"https://web.archive.org/web/20250902030406id_/{original}",
            f"https://web.archive.org/web/{self.timestamp}id_/https://other.org/article",
            f"https://example.org/web/{self.timestamp}id_/{original}",
            f"https://web.archive.org/web/{self.timestamp}/{original}",
        ):
            self.assertFalse(replay.safe_replay_url(
                address, original, selected_timestamp=self.timestamp,
                start_millis=self.start, end_millis=self.anchor)[0])

    def test_malformed_archive_port_is_recordable_failure(self):
        original = "https://example.org/article"
        address = f"https://web.archive.org:bad/web/{self.timestamp}id_/{original}"
        self.assertEqual(replay.safe_replay_url(
            address, original, selected_timestamp=self.timestamp,
            start_millis=self.start, end_millis=self.anchor)[:2],
            (False, "malformed_replay_url"))

    def test_memento_date_mismatch_rejected(self):
        self.assertEqual(replay.memento_check(
            {"Memento-Datetime": "Wed, 03 Sep 2025 03:04:05 GMT"},
            self.timestamp), (False, "memento_datetime_differs_from_selected_capture"))


if __name__ == "__main__":
    unittest.main()
