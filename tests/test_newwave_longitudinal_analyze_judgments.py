"""Offline checks for unknown-inclusive longitudinal label analysis."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import newwave_longitudinal_analyze_judgments as analysis


class AnalysisTests(unittest.TestCase):
    def test_unknown_full_indicator_is_bounded(self):
        self.assertEqual(analysis.indicator_bounds(None), (0, 1))
        self.assertEqual(analysis.indicator_bounds("UNASSESSABLE"), (0, 1))
        self.assertEqual(analysis.indicator_bounds("FULL"), (1, 1))
        self.assertEqual(analysis.indicator_bounds("PARTIAL"), (0, 0))

    def test_inconsistent_nonsubstantive_model_output_is_unknown(self):
        trial = {"valid_execution": True, "quote_validation_errors": [],
                 "response": {"main_claim_verdict": "FULL",
                              "source_observations": [{"source_id": "S1",
                                                       "substantive_text_observed": False}]}}
        self.assertIsNone(analysis.effective_label(trial))
        trial["response"]["main_claim_verdict"] = "UNASSESSABLE"
        self.assertEqual(analysis.effective_label(trial), "UNASSESSABLE")

    def test_invalid_quote_is_unknown_even_with_raw_full_response(self):
        trial = {"valid_execution": False, "quote_validation_errors": ["quote_word_limit"],
                 "response": {"main_claim_verdict": "FULL",
                              "source_observations": [{"source_id": "S1",
                                                       "substantive_text_observed": True}]}}
        self.assertIsNone(analysis.effective_label(trial))


if __name__ == "__main__":
    unittest.main()
