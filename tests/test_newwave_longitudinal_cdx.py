"""Offline invariants for the prospective archive metadata collector."""

import json
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import newwave_longitudinal_cdx as cdx


class CdxProtocolTests(unittest.TestCase):
    def item(self):
        anchor = int(datetime(2026, 2, 1, 12, 0, 0, 440000, timezone.utc).timestamp() * 1000)
        return {
            "query_id": "0" * 64,
            "network_url": "https://example.org/a?x=1&y=2",
            "network_url_sha256": cdx.sha_bytes(b"https://example.org/a?x=1&y=2"),
            "window_start_millis": anchor - cdx.THIRTY_DAYS_MS,
            "window_end_exclusive_millis": anchor,
            "helpful_anchor_millis": anchor,
            "anchor_quality": "exact_first_non_nmr_helpful",
            "associated_citation_refs": [],
            "unconditional_panel_selected": True,
        }

    def test_resume_key_json_marker_and_single_encoding(self):
        row = ["org,example)/a", "20260110120000", "https://example.org/a?x=1&y=2",
               "text/html", "200", "DIGEST", "123"]
        marker = "org%2Cexample%29%2Fa+20260110120000%21"
        captures, resume = cdx.parse_cdx_response(json.dumps([cdx.FIELDS, row, [], [marker]]))
        self.assertEqual(captures[0]["original"], row[2])
        self.assertEqual(resume, marker)
        params = parse_qs(urlsplit(cdx.cdx_url(self.item(), resume)).query)
        self.assertEqual(params["resumeKey"], ["org,example)/a 20260110120000!"])
        self.assertEqual(params["url"], ["https://example.org/a?x=1&y=2"])
        self.assertEqual(params["limit"], ["1000"])
        self.assertEqual(params["showResumeKey"], ["true"])
        self.assertNotIn("filter", params)

    def test_zero_and_malformed_cdx_are_distinct(self):
        self.assertEqual(cdx.parse_cdx_response("[]"), ([], None))
        with self.assertRaises(ValueError):
            cdx.parse_cdx_response(json.dumps([cdx.FIELDS, ["partial"]]))

    def test_whole_second_window_and_exact_original(self):
        item = self.item()
        sample = {
            "urlkey": "org,example)/a",
            "timestamp": "20260201120000",
            "original": item["network_url"],
            "mimetype": "text/html",
            "statuscode": "200",
            "digest": "DIGEST",
            "length": "100",
        }
        self.assertFalse(cdx.annotate_capture(sample, item)["within_pre_helpful_window"])
        sample["timestamp"] = "20260201115959"
        self.assertTrue(cdx.annotate_capture(sample, item)["primary_body_candidate"])
        sample["original"] = "http://example.org/a?x=1&y=2"
        self.assertFalse(cdx.annotate_capture(sample, item)["primary_body_candidate"])
        sample["original"] = item["network_url"]
        sample["timestamp"] = "20260102120000"
        self.assertFalse(cdx.annotate_capture(sample, item)["within_pre_helpful_window"])

    def test_blocked_source_hosts_are_body_censored(self):
        self.assertTrue(cdx.policy_censored("www.nytimes.com"))
        self.assertTrue(cdx.policy_censored("g1.globo.com"))
        self.assertFalse(cdx.policy_censored("gshow.globo.com"))

    def test_resume_chain_exhausts_two_pages(self):
        item = self.item()
        row1 = ["org,example)/a", "20260110120000", item["network_url"],
                "text/html", "200", "A", "100"]
        row2 = ["org,example)/a", "20260111120000", item["network_url"],
                "text/html", "302", "B", "200"]
        seen = []

        def fake_fetch(url, rate, tmp_dir):
            params = parse_qs(urlsplit(url).query)
            seen.append(params)
            data = ([cdx.FIELDS, row1, [], ["org%2Cexample%29%2Fa+next"]]
                    if "resumeKey" not in params else [cdx.FIELDS, row2])
            raw = json.dumps(data)
            return {"started_utc": "2026-11-15T00:00:00+00:00",
                    "finished_utc": "2026-11-15T00:00:01+00:00",
                    "http_status": 200, "curl_exit": 0, "stderr_excerpt": "",
                    "response_bytes": len(raw), "response_sha256": cdx.sha_bytes(raw.encode()),
                    "response_text": raw, "response_headers_excerpt": "HTTP/2 200",
                    "body_limit_exceeded": False}

        with tempfile.TemporaryDirectory() as temp, patch.object(cdx, "curl_once", side_effect=fake_fetch):
            result = cdx.collect_one(item, cdx.GlobalRate(), Path(temp) / "pages.jsonl",
                                     [], "f" * 64, time.monotonic() + 60)
            self.assertEqual(result["outcome"], "valid_positive_exact_original_http200_candidate")
            self.assertEqual(result["pages_successfully_parsed"], 2)
            self.assertEqual(result["raw_capture_count"], 2)
            self.assertEqual(result["exact_original_http200_candidate_count"], 1)
            self.assertEqual(len(cdx.read_jsonl(Path(temp) / "pages.jsonl")), 2)
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[1]["resumeKey"], ["org,example)/a next"])

    def test_resume_does_not_retry_prior_nonretryable_error(self):
        item = self.item()
        previous = {"manifest_sha256": "f" * 64, "query_id": item["query_id"],
                    "page_index": 0, "attempt": 1, "resume_key_in": None,
                    "page_valid": False, "http_status": 403, "curl_exit": 0,
                    "body_limit_exceeded": False, "parse_error": None}
        with tempfile.TemporaryDirectory() as temp, patch.object(cdx, "curl_once") as fetch:
            result = cdx.collect_one(item, cdx.GlobalRate(), Path(temp) / "pages.jsonl",
                                     [previous], "f" * 64, time.monotonic() + 60)
            fetch.assert_not_called()
        self.assertEqual(result["outcome"], "transport_or_http_error")

    def test_full_page_without_resume_is_unresolved(self):
        item = self.item()
        row = ["org,example)/a", "20260110120000", item["network_url"],
               "text/html", "200", "A", "100"]
        raw = json.dumps([cdx.FIELDS] + [row] * cdx.LIMIT_RECORDS)
        response = {"started_utc": "2026-11-15T00:00:00+00:00",
                    "finished_utc": "2026-11-15T00:00:01+00:00",
                    "http_status": 200, "curl_exit": 0, "stderr_excerpt": "",
                    "response_bytes": len(raw), "response_sha256": cdx.sha_bytes(raw.encode()),
                    "response_text": raw, "response_headers_excerpt": "HTTP/2 200",
                    "body_limit_exceeded": False}
        with tempfile.TemporaryDirectory() as temp, patch.object(cdx, "curl_once", return_value=response):
            result = cdx.collect_one(item, cdx.GlobalRate(), Path(temp) / "pages.jsonl",
                                     [], "f" * 64, time.monotonic() + 60)
        self.assertEqual(result["outcome"], "pagination_unresolved")
        self.assertEqual(result["reason"], "full_page_without_resume_key")


if __name__ == "__main__":
    unittest.main()
