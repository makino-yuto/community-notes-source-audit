"""Offline service-pacing and Retry-After interpretation checks."""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import newwave_longitudinal_cdx_v2 as v2


class ArchiveServiceCalibrationTests(unittest.TestCase):
    def test_retry_after_delta_and_http_date(self):
        at = datetime(2026, 11, 15, 5, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(v2.retry_after_seconds("HTTP/2 429\r\nRetry-After: 120\r\n", at), 120)
        self.assertEqual(
            v2.retry_after_seconds("HTTP/2 429\r\nRetry-After: Sun, 15 Nov 2026 05:05:00 GMT\r\n", at),
            300,
        )
        self.assertIsNone(v2.retry_after_seconds("HTTP/2 429\r\n", at))

    def test_last_retry_after_header_wins(self):
        at = datetime(2026, 11, 15, 5, 0, 0, tzinfo=timezone.utc)
        headers = "HTTP/1.1 200 Connection established\r\nRetry-After: 1\r\n\r\nHTTP/2 429\r\nRetry-After: 300\r\n"
        self.assertEqual(v2.retry_after_seconds(headers, at), 300)

    def test_v1_base_is_frozen(self):
        v2.setup_base()
        self.assertEqual(v2.base.sha_file(Path(v2.base.__file__)), v2.BASE_SHA256)
        self.assertEqual(v2.base.GLOBAL_START_INTERVAL, 10.0)
        self.assertEqual(v2.base.MAX_WORKERS, 1)


if __name__ == "__main__":
    unittest.main()
