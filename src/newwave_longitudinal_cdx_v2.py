"""Slower whole-universe CDX pass after the v1 service-rate-limit interruption.

This pass uses exactly the same 354 frozen URL+anchor units and query order.
The public v2 protocol records the reactive service calibration. It does not
reuse v1 outcomes or selectively retry only failed units.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import newwave_longitudinal_cdx as base


HERE = Path(__file__).resolve()
PROJECT = HERE.parents[1]
PRIVATE_RESULTS = PROJECT.parent / "results"
BASE_SHA256 = "bc8b93c2379b4fe0faf9602bdf397a4a7d4d96b4d8b8bc1c073ea17ff43831e1"
DEFAULT_PROTOCOL = PROJECT / "protocols" / "2026-11-15-longitudinal-followup-v2.json"
DEFAULT_QUERIES = PRIVATE_RESULTS / "newwave_longitudinal_queries_PRIVATE.jsonl"
DEFAULT_MANIFEST = PRIVATE_RESULTS / "newwave_longitudinal_cdx_v2_manifest_PRIVATE.json"
DEFAULT_PAGES = PRIVATE_RESULTS / "newwave_longitudinal_cdx_v2_pages_PRIVATE.jsonl"
DEFAULT_RESULTS = PRIVATE_RESULTS / "newwave_longitudinal_cdx_v2_PRIVATE.jsonl"
DEFAULT_COVERAGE = PRIVATE_RESULTS / "newwave_longitudinal_cdx_v2_coverage_PRIVATE.json"
DEFAULT_RUNLOG = PRIVATE_RESULTS / "newwave_longitudinal_cdx_v2_runlog_PRIVATE.jsonl"
GLOBAL_INTERVAL_SECONDS = 10.0
MAX_WORKERS = 1
STAGE_CAP_SECONDS = 90 * 60
NO_RETRY_AFTER_429_SECONDS = 10 * 60
OTHER_RETRY_SECONDS = 30


def setup_base() -> None:
    if base.sha_file(Path(base.__file__)) != BASE_SHA256:
        raise ValueError("Frozen v1 base script changed; no network requests")
    base.HERE = HERE
    base.GLOBAL_START_INTERVAL = GLOBAL_INTERVAL_SECONDS
    base.MAX_WORKERS = MAX_WORKERS
    base.STAGE_WALL_CAP_SECONDS = STAGE_CAP_SECONDS
    base.RETRY_SECONDS = 0.0


def retry_after_seconds(headers: str, at: datetime) -> float | None:
    matches = re.findall(r"(?im)^retry-after:\s*([^\r\n]+)", headers)
    if not matches:
        return None
    value = matches[-1].strip()
    if value.isdecimal():
        return float(value)
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0.0, (parsed - at).total_seconds())
    except (ValueError, TypeError, OverflowError):
        return None


def curl_once_v2(url: str, rate: base.GlobalRate, tmp_dir: Path) -> dict:
    """Bounded Archive GET retaining all response headers for Retry-After."""
    rate.acquire()
    started = base.now()
    with tempfile.TemporaryDirectory(prefix="cdx_v2_", dir=tmp_dir) as temp_dir:
        body_path = Path(temp_dir) / "body"
        header_path = Path(temp_dir) / "headers"
        command = [
            "curl.exe", "--silent", "--show-error", "--compressed",
            "--proto", "=https", "--max-redirs", "0",
            "--connect-timeout", "5", "--max-time", str(base.PER_ATTEMPT_TOTAL_TIMEOUT),
            "--max-filesize", str(base.MAX_RESPONSE_BYTES),
            "--header", "Accept: application/json",
            "--output", str(body_path), "--dump-header", str(header_path),
            "--write-out", "%{http_code}", url,
        ]
        try:
            process = subprocess.run(command, capture_output=True, text=True,
                                     timeout=base.PER_ATTEMPT_TOTAL_TIMEOUT + 5, check=False)
            raw = body_path.read_bytes() if body_path.exists() else b""
            headers = header_path.read_text(encoding="latin-1", errors="replace") if header_path.exists() else ""
            try:
                status = int(process.stdout.strip())
            except ValueError:
                status = 0
            return {
                "started_utc": started, "finished_utc": base.now(),
                "http_status": status, "curl_exit": process.returncode,
                "stderr_excerpt": process.stderr[:400],
                "response_bytes": len(raw), "response_sha256": base.sha_bytes(raw),
                "response_text": raw.decode("utf-8", errors="replace"),
                "response_headers_excerpt": headers[:1200],
                "response_headers_full": headers[:16000],
                "response_headers_sha256": base.sha_bytes(headers.encode("latin-1", errors="replace")),
                "headers_truncated": len(headers) > 16000,
                "body_limit_exceeded": len(raw) >= base.MAX_RESPONSE_BYTES or process.returncode == 63,
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "started_utc": started, "finished_utc": base.now(),
                "http_status": 0, "curl_exit": -1,
                "stderr_excerpt": f"subprocess_timeout:{type(exc).__name__}",
                "response_bytes": 0, "response_sha256": base.sha_bytes(b""),
                "response_text": "", "response_headers_excerpt": "",
                "response_headers_full": "", "response_headers_sha256": base.sha_bytes(b""),
                "headers_truncated": False, "body_limit_exceeded": False,
            }


def collect(protocol_path: Path, query_path: Path, manifest_path: Path,
            pages_path: Path, results_path: Path, coverage_path: Path,
            runlog_path: Path) -> None:
    setup_base()
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    not_before = datetime.fromisoformat(protocol["v1_interruption"]["v2_earliest_first_request_utc"])
    if datetime.now(timezone.utc) < not_before:
        raise RuntimeError(f"V2 Archive cooldown remains in force until {not_before.isoformat()}; no network requests")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_sha = base.sha_file(manifest_path)
    if (manifest["script_sha256"] != base.sha_file(HERE) or
        manifest["protocol_sha256"] != base.sha_file(protocol_path) or
        manifest["query_sha256"] != base.sha_file(query_path) or
        manifest["endpoint"] != base.ENDPOINT or
        manifest["max_workers"] != MAX_WORKERS or
        manifest["global_start_interval_seconds"] != GLOBAL_INTERVAL_SECONDS or
        manifest["stage_wall_cap_seconds"] != STAGE_CAP_SECONDS):
        raise ValueError("Frozen v2 manifest mismatch; no network requests")
    ordered = base.validate_queries(base.read_jsonl(query_path), protocol)
    if [item["query_id"] for item in ordered] != manifest["ordered_query_ids"]:
        raise ValueError("Frozen query order changed; no network requests")
    results = {}
    for row in base.read_jsonl(results_path):
        if row["query_id"] in results:
            raise ValueError("Duplicate v2 result")
        results[row["query_id"]] = row
    page_history = {}
    for row in base.read_jsonl(pages_path):
        if row.get("query_id") not in manifest["ordered_query_ids"]:
            raise ValueError("Unexpected v2 query ID in page log")
        page_history.setdefault(row["query_id"], []).append(row)

    started = time.monotonic()
    deadline = started + STAGE_CAP_SECONDS
    rate = base.GlobalRate()
    first_failure_count = 0
    stop_reason = None
    original_curl_once = base.curl_once
    original_retryable = base.retryable_page_failure
    seen_failure_by_request = {}
    health = {"headers_truncated": False}

    def cautious_curl_once(url: str, limiter: base.GlobalRate, tmp_dir: Path) -> dict:
        response = curl_once_v2(url, limiter, tmp_dir)
        failure = original_retryable(response)
        count = seen_failure_by_request.get(url, 0)
        if failure:
            seen_failure_by_request[url] = count + 1
        if failure and count == 0:
            if response.get("headers_truncated"):
                response["cooldown_exceeds_budget"] = True
                response["cooldown_source"] = "retry_headers_truncated_stop"
                health["headers_truncated"] = True
                return response
            server_wait = retry_after_seconds(response.get("response_headers_full", ""),
                                              datetime.now(timezone.utc))
            if server_wait is not None:
                cooldown = server_wait
                source = "retry_after"
            elif response["http_status"] == 429:
                cooldown = NO_RETRY_AFTER_429_SECONDS
                source = "default_429_cooldown"
            else:
                cooldown = OTHER_RETRY_SECONDS
                source = "other_transport_cooldown"
            response["cooldown_source"] = source
            response["cooldown_seconds_requested"] = cooldown
            remaining = deadline - time.monotonic()
            if cooldown >= remaining:
                response["cooldown_exceeds_budget"] = True
                response["cooldown_seconds_applied"] = 0
            else:
                time.sleep(cooldown)
                response["cooldown_exceeds_budget"] = False
                response["cooldown_seconds_applied"] = cooldown
        return response

    def cautious_retryable(row: dict) -> bool:
        return not row.get("cooldown_exceeds_budget", False) and original_retryable(row)

    base.curl_once = cautious_curl_once
    base.retryable_page_failure = cautious_retryable
    base.append_jsonl(runlog_path, {
        "event": "v2_stage_start", "utc": base.now(),
        "manifest_sha256": manifest_sha,
        "existing_completed": len(results),
        "v1_results_not_reused": True,
    })
    try:
        for index, item in enumerate(ordered):
            if item["query_id"] in results:
                result = results[item["query_id"]]
            else:
                if time.monotonic() >= deadline:
                    stop_reason = "90_minute_total_budget"
                    break
                seen_failure_by_request.clear()
                result = base.collect_one(item, rate, pages_path,
                                          page_history.get(item["query_id"], []),
                                          manifest_sha, deadline)
                base.append_jsonl(results_path, result)
                results[item["query_id"]] = result
            if result["outcome"] in {"transport_or_http_error", "parse_error"}:
                first_failure_count += 1
            elif result["outcome"].startswith("valid_"):
                first_failure_count = 0
            if health["headers_truncated"]:
                stop_reason = "truncated_retry_headers_stop"
                break
            # An exhausted 429 means the Archive itself is refusing this
            # instrument. Do not continue hammering other query units.
            if result["outcome"] == "transport_or_http_error" and "http=429" in (result.get("reason") or ""):
                stop_reason = "repeated_429_stop"
                break
            if index == 2 and all(results[x["query_id"]]["outcome"] in
                                  {"transport_or_http_error", "parse_error"}
                                  for x in ordered[:3]):
                stop_reason = "first_three_service_failures"
                break
            if index >= 2 and first_failure_count >= 2:
                stop_reason = "two_consecutive_service_failures"
                break
            if len(results) % 25 == 0:
                print(f"CDX v2 completed {len(results)}/{len(ordered)}", flush=True)
        if stop_reason is None:
            stop_reason = "all_queries_attempted" if len(results) == len(ordered) else "90_minute_total_budget"
    finally:
        base.curl_once = original_curl_once
        base.retryable_page_failure = original_retryable
    base.write_coverage(coverage_path, manifest_sha, ordered, results, stop_reason)
    base.append_jsonl(runlog_path, {
        "event": "v2_stage_end", "utc": base.now(), "reason": stop_reason,
        "completed": len(results), "unattempted": len(ordered) - len(results),
    })
    print(json.dumps({"completed": len(results), "unattempted": len(ordered) - len(results),
                      "stop_reason": stop_reason}), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare", action="store_true")
    group.add_argument("--collect", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--pages", type=Path, default=DEFAULT_PAGES)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--runlog", type=Path, default=DEFAULT_RUNLOG)
    args = parser.parse_args()
    setup_base()
    if args.prepare:
        base.prepare(args.protocol, args.queries, args.manifest)
    else:
        collect(args.protocol, args.queries, args.manifest, args.pages,
                args.results, args.coverage, args.runlog)


if __name__ == "__main__":
    main()
