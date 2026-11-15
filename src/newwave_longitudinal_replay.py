"""Bounded raw Wayback replay of a frozen, unconditional CDX panel.

The private selection and claim files must be frozen before this program is
run. It never follows a redirect to a live source or fetches subresources.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests

import newwave_collect_semantic as semantic
import newwave_longitudinal_cdx as cdx


HERE = Path(__file__).resolve()
PROJECT = HERE.parents[1]
PRIVATE = PROJECT.parent / "results"
DEFAULT_PROTOCOL = PROJECT / "protocols" / "2026-11-15-longitudinal-replay.json"
DEFAULT_SELECTION = PRIVATE / "newwave_longitudinal_replay_selection_PRIVATE.json"
DEFAULT_RESULTS = PRIVATE / "newwave_longitudinal_replay_PRIVATE.jsonl"
DEFAULT_COVERAGE = PRIVATE / "newwave_longitudinal_replay_coverage_PRIVATE.json"
DEFAULT_CDX_RUNLOG = PRIVATE / "newwave_longitudinal_cdx_v2_runlog_PRIVATE.jsonl"
MAX_BODY_BYTES = 2_000_000
MIN_START_INTERVAL = 10.0
MAX_REDIRECTS = 3
CAP_SECONDS = 90 * 60
CAPTURE_RE = re.compile(r"^/web/([0-9]{14})id_/(https?://.+)$")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_replay_url(address: str, original: str, *, selected_timestamp: str,
                    start_millis: int, end_millis: int) -> tuple[bool, str, str | None]:
    """Check every hop stays on an exact-original Archive identity replay."""
    try:
        parsed = urlsplit(address)
        safe_endpoint = (parsed.scheme == "https" and parsed.hostname == "web.archive.org" and
                         parsed.port in (None, 443))
    except ValueError:
        return False, "malformed_replay_url", None
    if not safe_endpoint:
        return False, "outside_archive_https_endpoint", None
    if parsed.username or parsed.password or parsed.fragment:
        return False, "replay_url_has_userinfo_or_fragment", None
    match = CAPTURE_RE.fullmatch(parsed.path)
    if match is None:
        return False, "not_raw_capture_path", None
    timestamp, path_original = match.groups()
    # The original's query appears as the Archive URL's query. Preserve it
    # byte-for-byte rather than treating it as an Archive control parameter.
    replay_original = path_original + ("?" + parsed.query if parsed.query else "")
    if replay_original != original:
        return False, "different_original_url", None
    if timestamp != selected_timestamp:
        return False, "changed_selected_capture_timestamp", None
    try:
        instant = datetime.strptime(timestamp, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return False, "invalid_capture_timestamp", None
    capture_ms = int(instant.timestamp() * 1000)
    if not (start_millis <= capture_ms and capture_ms + 1000 <= end_millis):
        return False, "capture_outside_pre_helpful_window", None
    return True, "ok", timestamp


def memento_check(headers: dict, selected_timestamp: str) -> tuple[bool, str]:
    value = headers.get("Memento-Datetime") or headers.get("memento-datetime")
    if not value:
        return True, "absent"
    try:
        parsed = parsedate_to_datetime(value).astimezone(timezone.utc)
        expected = datetime.strptime(selected_timestamp, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        if abs((parsed - expected).total_seconds()) > 1:
            return False, "memento_datetime_differs_from_selected_capture"
        return True, "matched_within_one_second"
    except (TypeError, ValueError, OverflowError):
        return False, "invalid_memento_datetime"


def prepare(protocol_path: Path, selection_path: Path, claims_path: Path,
            cdx_runlog_path: Path, results_path: Path) -> dict:
    """Freeze public replay rules and private-input hashes, without network."""
    if protocol_path.exists() or results_path.exists():
        raise FileExistsError("Protocol or replay result already exists")
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    if (selection.get("panel_units") != 100 or len(selection.get("entries", [])) != 100 or
        selection.get("archived_body_requests_at_freeze") != 0):
        raise ValueError("Replay selection is not the frozen 100-unit pre-body panel")
    if len({row["query_id"] for row in selection["entries"]}) != 100:
        raise ValueError("Duplicate replay-panel unit")
    log = cdx.read_jsonl(cdx_runlog_path)
    if sum(row.get("event") == "v2_stage_start" for row in log) != 1 or sum(
        row.get("event") == "v2_stage_end" for row in log) != 1:
        raise ValueError("V2 CDX stage has not ended cleanly")
    claim_rows = cdx.read_jsonl(claims_path)
    claim_keys = {(row["pair_code"], row["side"], row["note_id"]) for row in claim_rows}
    if len(claim_rows) != 200 or len(claim_keys) != 200:
        raise ValueError("Expected 200 distinct frozen note claims")
    for unit in selection["entries"]:
        for ref in unit["associated_citation_refs"]:
            if (ref["pair_code"], ref["side"], ref["note_id"]) not in claim_keys:
                raise ValueError("Panel citation has no matching frozen note claim")
    payload = {
        "schema": "newwave-longitudinal-archive-body-replay-v1",
        "status": "FROZEN BEFORE ANY V2 PANEL ARCHIVED BODY REQUEST",
        "prepared_utc": now(),
        "public_methods": {
            "frame": "All 100 preselected URL+first-Helpful-anchor units remain in denominator; no substitution or outcome-based selection.",
            "capture_choice": "Nearest exact-original HTTP200 permitted-MIME pre-anchor capture plus one preselected next-nearest fallback from valid exhausted CDX results only.",
            "fallback_only": ["transport_failure", "non200", "provenance_failure", "parse_or_empty_unassessable"],
            "no_fallback_for": ["lack_of_claim_support", "semantic_nonassessability", "body_too_large_unassessable", "archive_http_429", "budget_not_attempted"],
            "source_safety": "Never replay original hosts previously blocked by browser safety policy; retain censored units in denominator. No alternative archive endpoint, live-source redirect, proxy, credentials or subresources.",
            "replay_mode": "Raw https://web.archive.org/web/{timestamp}id_/{exact-original-URL}; at most three archive-only redirects; require exact selected timestamp and original URL at every hop; verify Memento-Datetime if present.",
            "network": "One worker, at least 10 seconds between request starts including redirects/fallback, no environment proxy or netrc, connect timeout 5 seconds, per-read timeout 10 seconds, stream guards before every blocking read and combined CDX+replay 90-minute wall cap; stop on HTTP429.",
            "body": "At most 2 MB decoded body; same frozen HTML/PDF/text parser as current-content pass; PDF first 50 pages and text first 120000 characters; later semantic judge receives first 24000 characters per source.",
            "coverage": "Record all 100 panel units as assessable, nonassessable, policy-censored, CDX-missing, archive-failed or budget/service-unattempted unknown; no unknown=zero imputation.",
            "error_page_policy": "Archive transport/status/provenance/parse errors are not judged for claim support. A readable Archive wrapper or error page must be flagged nonassessable during blinded source review.",
        },
        "inputs": {
            "selection_sha256": cdx.sha_file(selection_path),
            "frozen_claims_sha256": cdx.sha_file(claims_path),
            "pre_source_claim_log_sha256": "282fbde3e1cfe8100d2baa9798fdb0c0aa169d349a4bfd91893d18b1e096d8b1",
            "pre_source_pair_key_sha256": "8246f299b02fe7feb4a6dd8cef29e9861e22517e16c5aa5a8ac568b2b5ef3e4f",
            "claims_extractor_sha256": cdx.sha_file(PROJECT / "src" / "newwave_longitudinal_freeze_claims.py"),
            "cdx_runlog_sha256": cdx.sha_file(cdx_runlog_path),
            "current_parser_sha256": cdx.sha_file(Path(semantic.__file__)),
            "replay_script_sha256": cdx.sha_file(HERE),
        },
        "input_counts": {"panel_units": 100, "frozen_main_claims": 200,
                         "eligible_for_replay": selection["states"].get("eligible_for_replay", 0)},
        "private_input_filenames": {"selection": selection_path.name,
                                    "frozen_claims": claims_path.name,
                                    "cdx_runlog": cdx_runlog_path.name},
        "v2_panel_archived_body_requests_at_plan_time": 0,
    }
    protocol_path.parent.mkdir(parents=True, exist_ok=True)
    protocol_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"protocol_sha256": cdx.sha_file(protocol_path),
                      "eligible_for_replay": payload["input_counts"]["eligible_for_replay"],
                      "v2_panel_body_requests": 0}), flush=True)
    return payload


class Rate:
    def __init__(self):
        self.last_start = 0.0

    def wait(self, deadline: float) -> bool:
        sleep = self.last_start + MIN_START_INTERVAL - time.monotonic()
        if sleep > 0:
            if time.monotonic() + sleep >= deadline:
                return False
            time.sleep(sleep)
        if time.monotonic() >= deadline:
            return False
        self.last_start = time.monotonic()
        return True


def fetch_capture(entry: dict, capture: dict, rate: Rate, deadline: float) -> dict:
    original = entry["network_url"]
    original_host = urlsplit(original).hostname or ""
    if cdx.policy_censored(original_host):
        raise ValueError("Policy-censored original must not be replayed")
    timestamp = capture["timestamp"]
    address = f"https://web.archive.org/web/{timestamp}id_/{original}"
    row = {
        "requested_capture_key_sha256": capture["capture_key_sha256"],
        "requested_timestamp": timestamp,
        "requested_original_sha256": digest(original.encode("utf-8")),
        "started_utc": now(), "redirect_chain": [],
    }
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": "Apart-Epistemics-Longitudinal/1.0 (research; one capture)",
                            "Accept": "text/html,application/pdf,text/plain,application/json,application/xml"})
    try:
        for hop in range(MAX_REDIRECTS + 1):
            okay, reason, resolved_timestamp = safe_replay_url(
                address, original, selected_timestamp=timestamp,
                start_millis=entry["window_start_millis"],
                end_millis=entry["window_end_exclusive_millis"],
            )
            if not okay:
                row.update({"outcome": "provenance_failure", "reason": reason,
                            "finished_utc": now()})
                return row
            if not rate.wait(deadline):
                row.update({"outcome": "budget_not_attempted", "reason": "90_minute_cap",
                            "finished_utc": now()})
                return row
            if deadline - time.monotonic() < 25:
                row.update({"outcome": "budget_not_attempted", "reason": "insufficient_time_for_bounded_request",
                            "finished_utc": now()})
                return row
            hop_record = {"url": address, "started_utc": now(),
                          "resolved_timestamp": resolved_timestamp}
            request_started = time.monotonic()
            try:
                response = session.get(address, allow_redirects=False, timeout=(5, 10), stream=True)
                if response.url != address:
                    response.close()
                    row["redirect_chain"].append({**hop_record, "effective_url": response.url})
                    row.update({"outcome": "provenance_failure", "reason": "client_normalized_replay_url",
                                "finished_utc": now()})
                    return row
                hop_record["http_status"] = response.status_code
                hop_record["content_type"] = response.headers.get("Content-Type", "")[:200]
                hop_record["memento_datetime"] = response.headers.get("Memento-Datetime", "")[:100]
                if response.is_redirect:
                    location = response.headers.get("Location", "")
                    address = urljoin(address, location)
                    hop_record["location"] = address
                    row["redirect_chain"].append(hop_record)
                    response.close()
                    continue
                row["redirect_chain"].append(hop_record)
                row["final_url"] = address
                row["final_http_status"] = response.status_code
                row["content_type"] = response.headers.get("Content-Type", "")[:200]
                row["memento_datetime"] = response.headers.get("Memento-Datetime")
                if response.status_code == 429:
                    row.update({"outcome": "archive_rate_limited_stop", "reason": "http_429",
                                "finished_utc": now()})
                    response.close()
                    return row
                if response.status_code != 200:
                    row.update({"outcome": "non200", "reason": f"http_{response.status_code}",
                                "finished_utc": now()})
                    response.close()
                    return row
                valid_date, date_reason = memento_check(response.headers, timestamp)
                row["memento_check"] = date_reason
                if not valid_date:
                    row.update({"outcome": "provenance_failure", "reason": date_reason,
                                "finished_utc": now()})
                    response.close()
                    return row
                chunks = []
                size = 0
                too_large = False
                chunks_iter = response.iter_content(chunk_size=65536)
                while True:
                    # Requests' read timeout is an inactivity limit. Guard
                    # before each blocking read as well as after each chunk.
                    remaining_stage = deadline - time.monotonic()
                    remaining_request = request_started + 30 - time.monotonic()
                    if remaining_stage < 12 or remaining_request < 12:
                        response.close()
                        row["body_bytes_observed"] = size
                        row.update({"outcome": "budget_not_attempted" if remaining_stage < 12 else "transport_failure",
                                    "reason": "bounded_stream_deadline", "finished_utc": now()})
                        return row
                    try:
                        chunk = next(chunks_iter)
                    except StopIteration:
                        break
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > MAX_BODY_BYTES:
                        too_large = True
                        break
                    chunks.append(chunk)
                response.close()
                row["body_bytes_observed"] = size
                row["body_limit_exceeded"] = too_large
                if too_large:
                    row.update({"outcome": "body_too_large_unassessable", "reason": "2MB_cap",
                                "finished_utc": now()})
                    return row
                raw = b"".join(chunks)
                row["body_sha256"] = digest(raw)
                parsed = semantic.parse_content(raw, row["content_type"].split(";", 1)[0].lower())
                row["parsed"] = parsed
                if parsed.get("parse_status") != "ok" or parsed.get("main_text", {}).get("chars_saved", 0) == 0:
                    row.update({"outcome": "parse_or_empty_unassessable",
                                "reason": parsed.get("parse_status", "unknown"), "finished_utc": now()})
                    return row
                row.update({"outcome": "body_replayed_parseable_text", "reason": "ok",
                            "finished_utc": now()})
                return row
            except requests.RequestException as exc:
                row["redirect_chain"].append({**hop_record, "request_error": type(exc).__name__})
                row.update({"outcome": "transport_failure", "reason": type(exc).__name__,
                            "finished_utc": now()})
                return row
        row.update({"outcome": "provenance_failure", "reason": "too_many_redirects",
                    "finished_utc": now()})
        return row
    finally:
        session.close()


def collect(protocol_path: Path, selection_path: Path, claims_path: Path,
            cdx_runlog_path: Path, results_path: Path, coverage_path: Path) -> dict:
    if coverage_path.exists():
        raise FileExistsError("Replay coverage already finalized")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    if cdx.sha_file(selection_path) != protocol["inputs"]["selection_sha256"]:
        raise ValueError("Frozen replay selection hash changed")
    if cdx.sha_file(claims_path) != protocol["inputs"]["frozen_claims_sha256"]:
        raise ValueError("Frozen claim file hash changed")
    if cdx.sha_file(Path(semantic.__file__)) != protocol["inputs"]["current_parser_sha256"]:
        raise ValueError("Current parser changed")
    if cdx.sha_file(HERE) != protocol["inputs"]["replay_script_sha256"]:
        raise ValueError("Replay script changed")
    if cdx.sha_file(cdx_runlog_path) != protocol["inputs"]["cdx_runlog_sha256"]:
        raise ValueError("CDX stage log changed")
    if selection["panel_units"] != 100 or len(selection["entries"]) != 100:
        raise ValueError("Panel must retain all 100 units")
    starts = [row for row in cdx.read_jsonl(cdx_runlog_path) if row.get("event") == "v2_stage_start"]
    ends = [row for row in cdx.read_jsonl(cdx_runlog_path) if row.get("event") == "v2_stage_end"]
    if len(starts) != 1 or len(ends) != 1:
        raise ValueError("CDX stage start/end not frozen")
    deadline_wall = datetime.fromisoformat(starts[0]["utc"]).timestamp() + CAP_SECONDS
    done = {}
    for item in cdx.read_jsonl(results_path):
        if item["query_id"] in done:
            raise ValueError("Duplicate replay result")
        done[item["query_id"]] = item
    rate = Rate()
    # CDX has already ended, but force a full interval before the first
    # archived-body request so pacing also spans the stage boundary.
    rate.last_start = time.monotonic()
    stop_reason = ("archive_http_429" if any(row["outcome"] == "archive_rate_limited_stop"
                                          for row in done.values()) else
                   "combined_90_minute_budget" if any(row["outcome"] in
                                                      {"budget_not_attempted", "budget_unattempted_unknown"}
                                                     for row in done.values()) else None)
    for item in selection["entries"]:
        if item["query_id"] in done:
            continue
        output = {"query_id": item["query_id"], "state": item["state"],
                  "network_url_sha256": item["network_url_sha256"], "started_utc": now(),
                  "primary": None, "fallback": None}
        if item["state"] != "eligible_for_replay":
            output["outcome"] = item["state"]
        elif stop_reason:
            output["outcome"] = ("service_unattempted_unknown" if stop_reason == "archive_http_429"
                                 else "budget_unattempted_unknown")
        elif time.time() >= deadline_wall:
            stop_reason = "combined_90_minute_budget"
            output["outcome"] = "budget_unattempted_unknown"
        else:
            if cdx.policy_censored(urlsplit(item["network_url"]).hostname or ""):
                raise ValueError("Unsafe replay candidate in selected panel")
            # Translate the absolute wall cap into a monotonic deadline for
            # rate waits. Every selected eligible unit is visited in rank order.
            deadline = time.monotonic() + max(0.0, deadline_wall - time.time())
            primary = fetch_capture(item, item["primary_capture"], rate, deadline)
            output["primary"] = primary
            output["outcome"] = primary["outcome"]
            if primary["outcome"] == "archive_rate_limited_stop":
                stop_reason = "archive_http_429"
            elif primary["outcome"] in {"transport_failure", "non200", "provenance_failure",
                                             "parse_or_empty_unassessable"} and item["fallback_capture"]:
                fallback = fetch_capture(item, item["fallback_capture"], rate, deadline)
                output["fallback"] = fallback
                output["outcome"] = fallback["outcome"]
                if fallback["outcome"] == "archive_rate_limited_stop":
                    stop_reason = "archive_http_429"
            if output["outcome"] == "budget_not_attempted":
                stop_reason = "combined_90_minute_budget"
        output["finished_utc"] = now()
        cdx.append_jsonl(results_path, output)
        done[item["query_id"]] = output
    if stop_reason is None:
        stop_reason = "all_100_panel_units_processed"
    if len(done) != 100:
        raise ValueError("Replay log omitted panel units")
    eligible_unattempted = sum(row["state"] == "eligible_for_replay" and row["primary"] is None
                               for row in done.values())
    attempted = sum(row["primary"] is not None for row in done.values())
    coverage = {"schema": "newwave-longitudinal-replay-coverage-v1",
                "generated_utc": now(), "selection_sha256": cdx.sha_file(selection_path),
                "protocol_sha256": cdx.sha_file(protocol_path),
                "claims_sha256": cdx.sha_file(claims_path),
                "results_sha256": cdx.sha_file(results_path),
                "stop_reason": stop_reason, "panel_units": 100,
                "recorded_units": len(done), "body_attempted_units": attempted,
                "eligible_body_unattempted_units": eligible_unattempted,
                "outcomes": {kind: sum(row["outcome"] == kind for row in done.values())
                             for kind in sorted({row["outcome"] for row in done.values()})},
                "units": [{"query_id": item["query_id"],
                           "outcome": done[item["query_id"]]["outcome"]}
                          for item in selection["entries"]]}
    coverage_path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"recorded_units": len(done), "eligible_body_unattempted_units": eligible_unattempted,
                      "stop_reason": stop_reason, "outcomes": coverage["outcomes"]}), flush=True)
    return coverage


def main() -> None:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--prepare", action="store_true")
    action.add_argument("--collect", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--claims", type=Path, required=True)
    parser.add_argument("--cdx-runlog", type=Path, default=DEFAULT_CDX_RUNLOG)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE)
    args = parser.parse_args()
    if args.prepare:
        prepare(args.protocol, args.selection, args.claims, args.cdx_runlog, args.results)
    else:
        collect(args.protocol, args.selection, args.claims,
                args.cdx_runlog, args.results, args.coverage)


if __name__ == "__main__":
    main()
