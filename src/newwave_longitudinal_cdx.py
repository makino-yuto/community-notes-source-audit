"""Prospective, metadata-only CDX census for the frozen 100-pair frame.

No archived body is opened here. Run --prepare without network, publish the
protocol and this code, then run --collect. Raw responses and URLs remain in
private files. Missing/error queries are unknown, never zero coverage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import threading
import time
from collections import defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, unquote_plus, urlencode, urldefrag, urlsplit


HERE = Path(__file__).resolve()
PROJECT = HERE.parents[1]
PRIVATE_RESULTS = PROJECT.parent / "results"
DEFAULT_PROTOCOL = PROJECT / "protocols" / "2026-11-15-longitudinal-followup.json"
DEFAULT_QUERIES = PRIVATE_RESULTS / "newwave_longitudinal_queries_PRIVATE.jsonl"
DEFAULT_MANIFEST = PRIVATE_RESULTS / "newwave_longitudinal_cdx_manifest_PRIVATE.json"
DEFAULT_PAGES = PRIVATE_RESULTS / "newwave_longitudinal_cdx_pages_PRIVATE.jsonl"
DEFAULT_RESULTS = PRIVATE_RESULTS / "newwave_longitudinal_cdx_PRIVATE.jsonl"
DEFAULT_COVERAGE = PRIVATE_RESULTS / "newwave_longitudinal_cdx_coverage_PRIVATE.json"
DEFAULT_RUNLOG = PRIVATE_RESULTS / "newwave_longitudinal_cdx_runlog_PRIVATE.jsonl"
ENDPOINT = "https://web.archive.org/cdx/search/cdx"
FIELDS = ["urlkey", "timestamp", "original", "mimetype", "statuscode", "digest", "length"]
LIMIT_RECORDS = 1000
MAX_RESPONSE_BYTES = 4_000_000
MAX_PAGES_PER_UNIT = 100
MAX_WORKERS = 4
GLOBAL_START_INTERVAL = 1.0
RETRY_SECONDS = 5.0
MAX_ATTEMPTS_PER_PAGE = 2
PER_ATTEMPT_TOTAL_TIMEOUT = 20
STAGE_WALL_CAP_SECONDS = 60 * 60
THIRTY_DAYS_MS = 30 * 24 * 60 * 60 * 1000
SENSITIVE_KEYS = {"access_token", "api_key", "apikey", "auth", "key", "password",
                  "secret", "session", "sessionid", "sig", "signature", "token"}
BODY_CENSORED_HOSTS = {
    "tass.com", "britannica.com", "unicourt.com", "voterrecords.com",
    "usatoday.com", "g1.globo.com", "globaltimes.cn", "cnet.com",
    "pcmag.com", "onlyfans.com", "nytimes.com", "timesnownews.com",
}
HEX = re.compile(r"[0-9a-f]{64}\Z")
CAPTURE_TS = re.compile(r"[0-9]{14}\Z")
_WRITE_LOCK = threading.Lock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    with _WRITE_LOCK, path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    result = []
    with path.open(encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                raise ValueError(f"Blank line in {path.name}:{line_no}")
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError(f"Non-object in {path.name}:{line_no}")
            result.append(item)
    return result


def policy_censored(host: str) -> bool:
    return any(host == blocked or host.endswith("." + blocked) for blocked in BODY_CENSORED_HOSTS)


def validate_queries(queries: list[dict], protocol: dict) -> list[dict]:
    counts = protocol["counts"]
    if len(queries) != counts["distinct_url_anchor_query_units"]:
        raise ValueError("Query count differs from frozen protocol")
    ids = set()
    keys = set()
    refs = 0
    panel = 0
    for item in queries:
        query_id = item.get("query_id")
        network_url = item.get("network_url")
        if not isinstance(query_id, str) or not HEX.fullmatch(query_id) or query_id in ids:
            raise ValueError("Invalid or duplicate query ID")
        ids.add(query_id)
        if not isinstance(network_url, str) or urldefrag(network_url).url != network_url:
            raise ValueError("Invalid or fragment-bearing network URL")
        parsed = urlsplit(network_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Malformed source URL")
        if any(key.lower() in SENSITIVE_KEYS for key, _ in parse_qsl(parsed.query, keep_blank_values=True)):
            raise ValueError("Sensitive query key in source URL")
        if len(network_url) > 2000 or not item.get("safe_for_cdx"):
            raise ValueError("Unsafe CDX query unit in frozen manifest")
        if sha_bytes(network_url.encode("utf-8")) != item.get("network_url_sha256"):
            raise ValueError("Network URL hash mismatch")
        anchor = item.get("helpful_anchor_millis")
        start = item.get("window_start_millis")
        end = item.get("window_end_exclusive_millis")
        if not all(isinstance(value, int) for value in (anchor, start, end)):
            raise ValueError("Noninteger query window")
        if end != anchor or start != anchor - THIRTY_DAYS_MS:
            raise ValueError("Nonfrozen 30-day pre-Helpful window")
        key = (network_url, anchor)
        if key in keys:
            raise ValueError("Duplicate URL+anchor unit")
        keys.add(key)
        if not HEX.fullmatch(str(item.get("query_order_key", ""))):
            raise ValueError("Missing query order rank")
        refs += len(item.get("associated_citation_refs", []))
        panel += bool(item.get("unconditional_panel_selected"))
    if refs != counts["citation_references"] or panel != counts["unconditional_panel_query_units"]:
        raise ValueError("Reference or panel count differs from protocol")
    return sorted(queries, key=lambda x: (x["query_order_key"], x["query_id"]))


def prepare(protocol_path: Path, query_path: Path, manifest_path: Path) -> dict:
    if manifest_path.exists():
        raise FileExistsError(f"Already frozen: {manifest_path}")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if sha_file(query_path) != protocol["private_query_manifest"]["sha256"]:
        raise ValueError("Private query SHA-256 differs from public protocol")
    ordered = validate_queries(read_jsonl(query_path), protocol)
    manifest = {
        "schema": "newwave-longitudinal-cdx-manifest-v1",
        "prepared_utc": now(),
        "protocol_file": protocol_path.name,
        "protocol_sha256": sha_file(protocol_path),
        "query_file": query_path.name,
        "query_sha256": sha_file(query_path),
        "script_sha256": sha_file(HERE),
        "endpoint": ENDPOINT,
        "fields": FIELDS,
        "limit_records": LIMIT_RECORDS,
        "show_resume_key": True,
        "max_pages_per_unit": MAX_PAGES_PER_UNIT,
        "max_workers": MAX_WORKERS,
        "global_start_interval_seconds": GLOBAL_START_INTERVAL,
        "stage_wall_cap_seconds": STAGE_WALL_CAP_SECONDS,
        "query_count": len(ordered),
        "ordered_query_ids": [item["query_id"] for item in ordered],
        "known_browser_blocked_hosts_archive_body_censored": sorted(BODY_CENSORED_HOSTS),
        "network_requests_at_prepare": 0,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"prepared_queries": len(ordered), "manifest_sha256": sha_file(manifest_path),
                      "script_sha256": manifest["script_sha256"], "network_requests": 0}))
    return manifest


class GlobalRate:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.next_start = 0.0

    def acquire(self) -> None:
        with self.lock:
            start = max(time.monotonic(), self.next_start)
            self.next_start = start + GLOBAL_START_INTERVAL
        delay = start - time.monotonic()
        if delay > 0:
            time.sleep(delay)


def cdx_url(item: dict, resume_key: str | None) -> str:
    # The server's JSON resume key is already percent-encoded; decode exactly
    # once so urlencode does not double-encode the percent signs.
    start = datetime.fromtimestamp(item["window_start_millis"] / 1000, timezone.utc)
    end = datetime.fromtimestamp(item["window_end_exclusive_millis"] / 1000, timezone.utc)
    params = {
        "url": item["network_url"],
        "matchType": "exact",
        "output": "json",
        "fl": ",".join(FIELDS),
        "from": start.strftime("%Y%m%d"),
        "to": end.strftime("%Y%m%d"),
        "limit": str(LIMIT_RECORDS),
        "showResumeKey": "true",
    }
    if resume_key is not None:
        params["resumeKey"] = unquote_plus(resume_key)
    return ENDPOINT + "?" + urlencode(params)


def curl_once(url: str, rate: GlobalRate, tmp_dir: Path) -> dict:
    rate.acquire()
    started = now()
    with tempfile.TemporaryDirectory(prefix="cdx_", dir=tmp_dir) as temp_dir:
        body_path = Path(temp_dir) / "body"
        header_path = Path(temp_dir) / "headers"
        command = [
            "curl.exe", "--silent", "--show-error", "--compressed",
            "--proto", "=https", "--max-redirs", "0",
            "--connect-timeout", "5", "--max-time", str(PER_ATTEMPT_TOTAL_TIMEOUT),
            "--max-filesize", str(MAX_RESPONSE_BYTES),
            "--header", "Accept: application/json",
            "--output", str(body_path), "--dump-header", str(header_path),
            "--write-out", "%{http_code}", url,
        ]
        try:
            proc = subprocess.run(command, capture_output=True, text=True,
                                  timeout=PER_ATTEMPT_TOTAL_TIMEOUT + 5, check=False)
            raw = body_path.read_bytes() if body_path.exists() else b""
            headers = header_path.read_text(encoding="latin-1", errors="replace") if header_path.exists() else ""
            try:
                status = int(proc.stdout.strip())
            except ValueError:
                status = 0
            return {
                "started_utc": started,
                "finished_utc": now(),
                "http_status": status,
                "curl_exit": proc.returncode,
                "stderr_excerpt": proc.stderr[:400],
                "response_bytes": len(raw),
                "response_sha256": sha_bytes(raw),
                "response_text": raw.decode("utf-8", errors="replace"),
                "response_headers_excerpt": headers[:1200],
                "body_limit_exceeded": len(raw) >= MAX_RESPONSE_BYTES or proc.returncode == 63,
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "started_utc": started, "finished_utc": now(),
                "http_status": 0, "curl_exit": -1,
                "stderr_excerpt": f"subprocess_timeout:{type(exc).__name__}",
                "response_bytes": 0, "response_sha256": sha_bytes(b""),
                "response_text": "", "response_headers_excerpt": "",
                "body_limit_exceeded": False,
            }


def parse_cdx_response(payload: str) -> tuple[list[dict], str | None]:
    parsed = json.loads(payload)
    if not isinstance(parsed, list):
        raise ValueError("CDX JSON is not an array")
    if not parsed:
        return [], None
    if parsed[0] != FIELDS:
        raise ValueError("CDX header differs from requested field order")
    trailing = parsed[1:]
    resume_key = None
    if len(trailing) >= 2 and trailing[-2] == [] and isinstance(trailing[-1], list) and len(trailing[-1]) == 1 and isinstance(trailing[-1][0], str):
        resume_key = trailing[-1][0]
        trailing = trailing[:-2]
    if any(not isinstance(row, list) or len(row) != len(FIELDS) or
           any(not isinstance(value, str) for value in row) for row in trailing):
        raise ValueError("CDX capture row malformed or resume marker unsupported")
    return [dict(zip(FIELDS, row)) for row in trailing], resume_key


def annotate_capture(capture: dict, item: dict) -> dict:
    value = capture["timestamp"]
    stamp_ms = None
    if CAPTURE_TS.fullmatch(value):
        try:
            stamp_ms = int(datetime.strptime(value, "%Y%m%d%H%M%S").replace(
                tzinfo=timezone.utc).timestamp() * 1000)
        except ValueError:
            pass
    inside = stamp_ms is not None and (
        item["window_start_millis"] <= stamp_ms and
        stamp_ms + 1000 <= item["window_end_exclusive_millis"]
    )
    mime = capture["mimetype"].lower().split(";", 1)[0].strip()
    permitted_mime = mime in {
        "text/html", "application/xhtml+xml", "application/pdf",
        "text/plain", "application/json", "text/json",
        "application/xml", "text/xml",
    } or mime.endswith("+json") or mime.endswith("+xml")
    exact = capture["original"] == item["network_url"]
    primary_candidate = inside and exact and capture["statuscode"] == "200" and permitted_mime
    return {
        **capture,
        "timestamp_start_millis": stamp_ms,
        "within_pre_helpful_window": inside,
        "exact_original": exact,
        "permitted_mime": permitted_mime,
        "primary_body_candidate": primary_candidate,
    }


def retryable_page_failure(row: dict) -> bool:
    return (not row.get("body_limit_exceeded", False) and
            (row.get("curl_exit", 0) != 0 or row.get("http_status") == 429 or
             (isinstance(row.get("http_status"), int) and row["http_status"] >= 500)))


def summary(item: dict, successful_pages: list[dict], terminal: str | None,
            reason: str | None) -> dict:
    captures = [annotate_capture(row, item) for page in successful_pages for row in page["captures"]]
    retained = [row for row in captures if row["within_pre_helpful_window"]]
    candidate = [row for row in retained if row["primary_body_candidate"]]
    if terminal is None:
        terminal = ("valid_positive_exact_original_http200_candidate" if candidate else
                    "valid_positive_any_capture" if retained else
                    "valid_zero_retained_captures")
    return {
        "query_id": item["query_id"],
        "network_url": item["network_url"],
        "network_url_sha256": item["network_url_sha256"],
        "helpful_anchor_millis": item["helpful_anchor_millis"],
        "window_start_millis": item["window_start_millis"],
        "window_end_exclusive_millis": item["window_end_exclusive_millis"],
        "anchor_quality": item["anchor_quality"],
        "associated_citation_refs": item["associated_citation_refs"],
        "unconditional_panel_selected": item["unconditional_panel_selected"],
        "policy_blocked_original_host_body_censored": policy_censored(urlsplit(item["network_url"]).hostname or ""),
        "outcome": terminal,
        "reason": reason,
        "pages_successfully_parsed": len(successful_pages),
        "raw_capture_count": len(captures),
        "retained_pre_helpful_count": len(retained),
        "exact_original_http200_candidate_count": len(candidate),
        "captures": captures,
        "completed_utc": now(),
    }


def collect_one(item: dict, rate: GlobalRate, pages_path: Path,
                prior_pages: list[dict], manifest_sha: str,
                deadline: float) -> dict:
    by_page: dict[int, list[dict]] = defaultdict(list)
    for row in prior_pages:
        if row.get("manifest_sha256") != manifest_sha:
            raise ValueError("Page log manifest SHA mismatch")
        by_page[row["page_index"]].append(row)
    successes: list[dict] = []
    seen_resume: set[str] = set()
    resume = None
    for page_index in range(MAX_PAGES_PER_UNIT):
        history = by_page.get(page_index, [])
        valid = [row for row in history if row.get("page_valid")]
        if len(valid) > 1:
            return summary(item, successes, "pagination_unresolved", "duplicate_valid_page_records")
        if valid:
            page = valid[0]
            if page.get("resume_key_in") != resume:
                return summary(item, successes, "pagination_unresolved", "resume_chain_mismatch")
        else:
            if time.monotonic() >= deadline:
                return summary(item, successes, "pagination_unresolved", "stage_wall_cap_mid_query")
            if any(row.get("resume_key_in") != resume for row in history):
                return summary(item, successes, "pagination_unresolved", "attempt_resume_chain_mismatch")
            if history and (len(history) >= MAX_ATTEMPTS_PER_PAGE or
                            not retryable_page_failure(history[-1])):
                last = history[-1]
                terminal = "parse_error" if last.get("parse_error") else "transport_or_http_error"
                return summary(item, successes, terminal,
                               f"http={last['http_status']};curl={last['curl_exit']};"
                               f"{last.get('parse_error') or ''}")
            page = None
            for attempt in range(len(history) + 1, MAX_ATTEMPTS_PER_PAGE + 1):
                if time.monotonic() >= deadline:
                    return summary(item, successes, "pagination_unresolved", "stage_wall_cap_mid_page")
                url = cdx_url(item, resume)
                response = curl_once(url, rate, pages_path.parent)
                parsed_rows: list[dict] = []
                next_resume = None
                parse_error = None
                if response["http_status"] == 200 and response["curl_exit"] == 0 and not response["body_limit_exceeded"]:
                    try:
                        parsed_rows, next_resume = parse_cdx_response(response["response_text"])
                    except (ValueError, json.JSONDecodeError) as exc:
                        parse_error = f"{type(exc).__name__}:{str(exc)[:160]}"
                page = {
                    "manifest_sha256": manifest_sha,
                    "query_id": item["query_id"],
                    "page_index": page_index,
                    "attempt": attempt,
                    "resume_key_in": resume,
                    "request_url_sha256": sha_bytes(url.encode("utf-8")),
                    **response,
                    "parse_error": parse_error,
                    "captures": parsed_rows,
                    "resume_key_out": next_resume,
                    "page_valid": response["http_status"] == 200 and response["curl_exit"] == 0
                                  and not response["body_limit_exceeded"] and parse_error is None,
                }
                append_jsonl(pages_path, page)
                retryable = retryable_page_failure(page)
                if page["page_valid"] or not retryable:
                    break
                if attempt < MAX_ATTEMPTS_PER_PAGE:
                    time.sleep(RETRY_SECONDS)
            if page is None:
                return summary(item, successes, "pagination_unresolved", "missing_page_attempt")
        if not page["page_valid"]:
            terminal = "parse_error" if page.get("parse_error") else "transport_or_http_error"
            return summary(item, successes, terminal,
                           f"http={page['http_status']};curl={page['curl_exit']};{page.get('parse_error') or ''}")
        successes.append(page)
        next_resume = page.get("resume_key_out")
        if next_resume is None:
            if len(page["captures"]) >= LIMIT_RECORDS:
                return summary(item, successes, "pagination_unresolved", "full_page_without_resume_key")
            return summary(item, successes, None, None)
        if not next_resume or next_resume in seen_resume:
            return summary(item, successes, "pagination_unresolved", "empty_or_repeated_resume_key")
        seen_resume.add(next_resume)
        resume = next_resume
    return summary(item, successes, "pagination_unresolved", "max_pages_per_unit")


def write_coverage(path: Path, manifest_sha: str, ordered: list[dict],
                   results: dict[str, dict], stop_reason: str) -> None:
    covered = []
    for item in ordered:
        result = results.get(item["query_id"])
        covered.append({
            "query_id": item["query_id"],
            "outcome": result["outcome"] if result else "query_not_attempted",
            "reason": result.get("reason") if result else stop_reason,
        })
    payload = {
        "schema": "newwave-longitudinal-cdx-coverage-v1",
        "manifest_sha256": manifest_sha,
        "written_utc": now(),
        "stop_reason": stop_reason,
        "query_universe": len(ordered),
        "attempted_or_completed": len(results),
        "units": covered,
    }
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def collect(protocol_path: Path, query_path: Path, manifest_path: Path,
            pages_path: Path, results_path: Path, coverage_path: Path,
            runlog_path: Path) -> None:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_sha = sha_file(manifest_path)
    if (manifest["script_sha256"] != sha_file(HERE) or
        manifest["protocol_sha256"] != sha_file(protocol_path) or
        manifest["query_sha256"] != sha_file(query_path) or
        manifest["endpoint"] != ENDPOINT or manifest["limit_records"] != LIMIT_RECORDS):
        raise ValueError("Frozen code/protocol/query manifest mismatch; no network requests")
    ordered = validate_queries(read_jsonl(query_path), protocol)
    if [item["query_id"] for item in ordered] != manifest["ordered_query_ids"]:
        raise ValueError("Frozen query order changed; no network requests")
    existing_results = read_jsonl(results_path)
    results = {}
    for row in existing_results:
        if row["query_id"] in results:
            raise ValueError("Duplicate completed query ID")
        results[row["query_id"]] = row
    page_history: dict[str, list[dict]] = defaultdict(list)
    for row in read_jsonl(pages_path):
        if row.get("query_id") not in manifest["ordered_query_ids"]:
            raise ValueError("Unexpected query ID in page log")
        page_history[row["query_id"]].append(row)
    rate = GlobalRate()
    started = time.monotonic()
    deadline = started + STAGE_WALL_CAP_SECONDS
    append_jsonl(runlog_path, {"event": "stage_start", "utc": now(), "manifest_sha256": manifest_sha,
                               "existing_results": len(results)})

    def task(item: dict) -> dict:
        return collect_one(item, rate, pages_path, page_history.get(item["query_id"], []),
                           manifest_sha, deadline)

    # Check the first three frozen ranks sequentially. Three failures mean
    # service health is unknown and all other units remain unattempted.
    for item in ordered[:3]:
        if item["query_id"] not in results:
            result = task(item)
            append_jsonl(results_path, result)
            results[item["query_id"]] = result
        print(f"CDX initial {len([x for x in ordered[:3] if x['query_id'] in results])}/3 "
              f"{results[item['query_id']]['outcome']}", flush=True)
    # A pagination anomaly on one URL does not establish a service-wide block.
    service_failures = {"transport_or_http_error", "parse_error"}
    if all(results[item["query_id"]]["outcome"] in service_failures for item in ordered[:3]):
        stop_reason = "first_three_service_failures"
        write_coverage(coverage_path, manifest_sha, ordered, results, stop_reason)
        append_jsonl(runlog_path, {"event": "stage_stop", "utc": now(), "reason": stop_reason,
                                   "completed": len(results), "unattempted": len(ordered) - len(results)})
        print(f"Stopped after first three failures; {len(ordered)-len(results)} unknown/unattempted.", flush=True)
        return

    remaining = [item for item in ordered[3:] if item["query_id"] not in results]
    cursor = 0
    pending = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        while pending or cursor < len(remaining):
            while cursor < len(remaining) and len(pending) < MAX_WORKERS and time.monotonic() < deadline:
                item = remaining[cursor]
                cursor += 1
                pending[executor.submit(task, item)] = item
            if not pending:
                break
            done, _ = wait(pending, timeout=1, return_when=FIRST_COMPLETED)
            for future in done:
                item = pending.pop(future)
                result = future.result()
                append_jsonl(results_path, result)
                results[item["query_id"]] = result
                if len(results) % 25 == 0:
                    print(f"CDX completed {len(results)}/{len(ordered)}", flush=True)
    stop_reason = "wall_cap" if len(results) < len(ordered) else "all_queries_attempted"
    write_coverage(coverage_path, manifest_sha, ordered, results, stop_reason)
    append_jsonl(runlog_path, {"event": "stage_end", "utc": now(), "reason": stop_reason,
                               "completed": len(results), "unattempted": len(ordered) - len(results)})
    print(json.dumps({"completed": len(results), "unattempted": len(ordered) - len(results),
                      "stop_reason": stop_reason}), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare", action="store_true", help="Validate and freeze inputs; no network")
    group.add_argument("--collect", action="store_true", help="Query frozen CDX metadata only")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--pages", type=Path, default=DEFAULT_PAGES)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--runlog", type=Path, default=DEFAULT_RUNLOG)
    args = parser.parse_args()
    if args.prepare:
        prepare(args.protocol, args.queries, args.manifest)
    else:
        collect(args.protocol, args.queries, args.manifest, args.pages,
                args.results, args.coverage, args.runlog)


if __name__ == "__main__":
    main()
