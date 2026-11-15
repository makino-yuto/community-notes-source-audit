"""Offline capture selection invariants; no archived body reads."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import newwave_longitudinal_select_replays as select


class ReplaySelectionTests(unittest.TestCase):
    def test_nearest_exact_candidate_and_single_fallback(self):
        url = "https://example.org/article"
        def capture(stamp, digest, exact=True, candidate=True):
            return {
                "timestamp": stamp,
                "timestamp_start_millis": int(stamp[-2:]) * 1000,
                "original": url if exact else "http://example.org/article",
                "mimetype": "text/html", "statuscode": "200",
                "digest": digest, "length": "100",
                "primary_body_candidate": candidate,
                "within_pre_helpful_window": True,
                "permitted_mime": True,
            }
        old = capture("20260101000001", "A")
        latest = capture("20260101000009", "B")
        result = {"outcome": "valid_positive_exact_original_http200_candidate",
                  "captures": [old, latest, latest.copy(), capture("20260101000010", "C", candidate=False)]}
        selected = select.selected_candidates(result, url)
        self.assertEqual([row["digest"] for row in selected], ["B", "A"])
        self.assertEqual(len(selected), 2)
        self.assertGreater(select.capture_plan(selected[0], 20000)["capture_to_anchor_lag_millis"], 0)

    def test_inconsistent_candidate_flag_fails_closed(self):
        with self.assertRaises(ValueError):
            select.selected_candidates({"outcome": "valid_positive_exact_original_http200_candidate", "captures": [{
                "timestamp": "20260101000001", "timestamp_start_millis": 1000,
                "original": "http://example.org/article", "mimetype": "text/html",
                "statuscode": "200", "digest": "X", "length": "100",
                "primary_body_candidate": True, "within_pre_helpful_window": True,
                "permitted_mime": True,
            }]}, "https://example.org/article")

    def test_incomplete_pagination_cannot_choose_nearest_capture(self):
        partial = {"outcome": "pagination_unresolved", "captures": [{
            "primary_body_candidate": True,
        }]}
        self.assertEqual(select.selected_candidates(partial, "https://example.org/article"), [])


if __name__ == "__main__":
    unittest.main()
