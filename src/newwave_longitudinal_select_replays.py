"""Freeze the unconditional 100-unit archival replay panel before body reads.

The panel IDs were selected before CDX and current GET outcomes. This program
uses v2 CDX metadata only to preselect the nearest and one fallback capture;
units with missing/error index results remain in the frozen panel as unknown.
No network requests are made.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import newwave_longitudinal_cdx as cdx


HERE = Path(__file__).resolve()
PROJECT = HERE.parents[1]
PRIVATE_RESULTS = PROJECT.parent / "results"
DEFAULT_PROTOCOL = PROJECT / "protocols" / "2026-11-15-longitudinal-followup-v2.json"
DEFAULT_QUERIES = PRIVATE_RESULTS / "newwave_longitudinal_queries_PRIVATE.jsonl"
DEFAULT_CDX_MANIFEST = PRIVATE_RESULTS / "newwave_longitudinal_cdx_v2_manifest_PRIVATE.json"
DEFAULT_CDX_RESULTS = PRIVATE_RESULTS / "newwave_longitudinal_cdx_v2_PRIVATE.jsonl"
DEFAULT_CDX_COVERAGE = PRIVATE_RESULTS / "newwave_longitudinal_cdx_v2_coverage_PRIVATE.json"
DEFAULT_CONTENT = PRIVATE_RESULTS / "newwave_semantic_content_PRIVATE.jsonl"
DEFAULT_CONTENT_MANIFEST = PRIVATE_RESULTS / "newwave_semantic_content_manifest_PRIVATE.json"
DEFAULT_OUTPUT = PRIVATE_RESULTS / "newwave_longitudinal_replay_selection_PRIVATE.json"
REPLAY_ORDER_NAMESPACE = "2026111517|replay-order|"
CAPTURE_FIELDS = ("timestamp", "original", "mimetype", "statuscode", "digest", "length")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def capture_tuple(row: dict) -> tuple[str, ...]:
    return tuple(str(row[field]) for field in CAPTURE_FIELDS)


def selected_candidates(result: dict | None, network_url: str) -> list[dict]:
    # A partial CDX pagination chain cannot identify the nearest capture.
    # Keep the panel unit, but do not select a body from incomplete metadata.
    if result is None or not result.get("outcome", "").startswith("valid_"):
        return []
    unique: dict[tuple[str, str], dict] = {}
    for row in result.get("captures", []):
        if not row.get("primary_body_candidate"):
            continue
        if (row.get("original") != network_url or row.get("statuscode") != "200" or
            not row.get("within_pre_helpful_window") or not row.get("permitted_mime")):
            raise ValueError("CDX result candidate flag inconsistent with frozen rule")
        if not isinstance(row.get("timestamp_start_millis"), int):
            raise ValueError("Candidate capture lacks a valid UTC timestamp")
        # Wayback replay addresses are identified by timestamp + original.
        # Two CDX metadata rows for that same address are not independent
        # fallback captures, even when digest or length differs.
        address_key = (row["timestamp"], row["original"])
        previous = unique.get(address_key)
        if previous is None or capture_tuple(row) < capture_tuple(previous):
            unique[address_key] = row
    # Nearest pre-anchor first; exact ties break lexically on the remaining
    # CDX fields, as declared before archived bodies were opened.
    return sorted(unique.values(), key=lambda row: (
        -row["timestamp_start_millis"],
        row["original"], row["mimetype"], row["digest"], row["length"],
    ))


def capture_plan(row: dict, anchor_millis: int) -> dict:
    fields = {field: row[field] for field in CAPTURE_FIELDS}
    fields["timestamp_start_millis"] = row["timestamp_start_millis"]
    fields["capture_to_anchor_lag_millis"] = anchor_millis - row["timestamp_start_millis"]
    fields["capture_key_sha256"] = hashlib.sha256(
        json.dumps(fields, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return fields


def freeze(protocol_path: Path, queries_path: Path, cdx_manifest_path: Path,
           cdx_results_path: Path, cdx_coverage_path: Path, content_path: Path,
           content_manifest_path: Path, output_path: Path) -> dict:
    if output_path.exists():
        raise FileExistsError("Replay selection already frozen; use a new versioned path")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if cdx.sha_file(Path(cdx.__file__)) != protocol["implementation"]["frozen_v1_base_script_sha256"]:
        raise ValueError("Frozen CDX base script changed")
    if cdx.sha_file(queries_path) != protocol["private_query_manifest"]["sha256"]:
        raise ValueError("Private query manifest changed")
    ordered = cdx.validate_queries(cdx.read_jsonl(queries_path), protocol)
    cdx_manifest = json.loads(cdx_manifest_path.read_text(encoding="utf-8"))
    if (cdx_manifest["script_sha256"] != protocol["implementation"]["cdx_script_sha256"] or
        cdx_manifest["protocol_sha256"] != cdx.sha_file(protocol_path) or
        cdx_manifest["query_sha256"] != cdx.sha_file(queries_path) or
        cdx_manifest["query_count"] != len(ordered)):
        raise ValueError("V2 CDX manifest/code/protocol mismatch")
    results = {}
    for row in cdx.read_jsonl(cdx_results_path):
        if row["query_id"] in results:
            raise ValueError("Duplicate V2 CDX result")
        results[row["query_id"]] = row
    coverage = json.loads(cdx_coverage_path.read_text(encoding="utf-8"))
    if coverage["manifest_sha256"] != cdx.sha_file(cdx_manifest_path):
        raise ValueError("V2 coverage manifest mismatch")
    if len(coverage["units"]) != len(ordered):
        raise ValueError("V2 coverage lacks universe units")
    by_coverage = {row["query_id"]: row for row in coverage["units"]}
    if len(by_coverage) != len(ordered) or set(by_coverage) != {item["query_id"] for item in ordered}:
        raise ValueError("V2 coverage unit IDs changed")
    for query_id, result in results.items():
        if by_coverage[query_id]["outcome"] != result["outcome"]:
            raise ValueError("V2 coverage/result outcome mismatch")
    # Static current-content input integrity is a gate, not a selection
    # variable. It provides a frozen comparator for later same-claim judging.
    content_manifest = json.loads(content_manifest_path.read_text(encoding="utf-8"))
    if content_manifest.get("fixed_semantic_pairs") != 100:
        raise ValueError("Current content manifest is not the fixed 100-pair frame")
    if (content_manifest.get("key_sha256") != protocol["input_integrity"]["newwave_semantic_key_PRIVATE.json"] or
        content_manifest.get("candidate_sha256") != protocol["input_integrity"]["revision_samepost_candidates_v2_PRIVATE.jsonl"] or
        content_manifest.get("script_sha256") != protocol["input_integrity"]["src/newwave_collect_semantic.py"] or
        cdx.sha_file(content_manifest_path.parent / content_manifest["mapping_file"]) !=
        content_manifest["mapping_sha256"]):
        raise ValueError("Current-content preparation provenance mismatch")
    current_content = cdx.read_jsonl(content_path)
    if len(current_content) != content_manifest["unique_network_urls"]:
        raise ValueError("Current content collection incomplete")
    if len({row["url_sha256"] for row in current_content}) != len(current_content):
        raise ValueError("Duplicate current-content URL")
    expected_urls = {(row["url_sha256"], row["url"]) for row in content_manifest["urls"]}
    actual_urls = {(row["url_sha256"], row["url"]) for row in current_content}
    if len(expected_urls) != len(current_content) or actual_urls != expected_urls:
        raise ValueError("Current-content URL set differs from frozen manifest")
    if any(cdx.sha_bytes(row["url"].encode("utf-8")) != row["url_sha256"]
           for row in current_content):
        raise ValueError("Current-content URL hash mismatch")

    panel = [item for item in ordered if item["unconditional_panel_selected"]]
    if len(panel) != 100:
        raise ValueError("Unconditional replay panel changed")
    entries = []
    for item in panel:
        query_id = item["query_id"]
        result = results.get(query_id)
        if result is not None and (result.get("network_url") != item["network_url"] or
                                   result.get("helpful_anchor_millis") != item["helpful_anchor_millis"]):
            raise ValueError("CDX result URL/anchor differs from frozen query")
        body_censored = cdx.policy_censored(urlsplit(item["network_url"]).hostname or "")
        candidates = selected_candidates(result, item["network_url"])
        primary = capture_plan(candidates[0], item["helpful_anchor_millis"]) if candidates else None
        fallback = capture_plan(candidates[1], item["helpful_anchor_millis"]) if len(candidates) > 1 else None
        if body_censored:
            state = "policy_censored_no_body_replay"
        elif result is None:
            state = "cdx_unknown_no_body_replay"
        elif result["outcome"] in {"transport_or_http_error", "parse_error", "pagination_unresolved"}:
            state = "cdx_error_no_body_replay"
        elif primary is None:
            state = "no_eligible_exact_original_capture"
        else:
            state = "eligible_for_replay"
        entries.append({
            "query_id": query_id,
            "network_url": item["network_url"],
            "network_url_sha256": item["network_url_sha256"],
            "helpful_anchor_millis": item["helpful_anchor_millis"],
            "window_start_millis": item["window_start_millis"],
            "window_end_exclusive_millis": item["window_end_exclusive_millis"],
            "associated_citation_refs": item["associated_citation_refs"],
            "cdx_outcome": result["outcome"] if result else "query_not_attempted",
            "state": state,
            "eligible_distinct_capture_count": len(candidates),
            "primary_capture": primary,
            "fallback_capture": fallback,
            "replay_order_key": hashlib.sha256(
                (REPLAY_ORDER_NAMESPACE + query_id).encode("ascii")
            ).hexdigest(),
        })
    entries.sort(key=lambda row: (row["replay_order_key"], row["query_id"]))
    payload = {
        "schema": "newwave-longitudinal-unconditional-replay-selection-v1",
        "frozen_utc": now(),
        "protocol_sha256": cdx.sha_file(protocol_path),
        "query_manifest_sha256": cdx.sha_file(queries_path),
        "cdx_manifest_sha256": cdx.sha_file(cdx_manifest_path),
        "cdx_results_sha256": cdx.sha_file(cdx_results_path),
        "cdx_coverage_sha256": cdx.sha_file(cdx_coverage_path),
        "current_content_manifest_sha256": cdx.sha_file(content_manifest_path),
        "current_content_results_sha256": cdx.sha_file(content_path),
        "selection_script_sha256": cdx.sha_file(HERE),
        "replay_order_namespace": REPLAY_ORDER_NAMESPACE,
        "panel_units": len(entries),
        "states": dict(Counter(row["state"] for row in entries)),
        "entries": entries,
        "archived_body_requests_at_freeze": 0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({"panel_units": len(entries), "states": payload["states"],
                      "selection_sha256": cdx.sha_file(output_path),
                      "archived_body_requests": 0}), flush=True)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    parser.add_argument("--cdx-manifest", type=Path, default=DEFAULT_CDX_MANIFEST)
    parser.add_argument("--cdx-results", type=Path, default=DEFAULT_CDX_RESULTS)
    parser.add_argument("--cdx-coverage", type=Path, default=DEFAULT_CDX_COVERAGE)
    parser.add_argument("--current-content", type=Path, default=DEFAULT_CONTENT)
    parser.add_argument("--current-content-manifest", type=Path, default=DEFAULT_CONTENT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    freeze(args.protocol, args.queries, args.cdx_manifest, args.cdx_results,
           args.cdx_coverage, args.current_content, args.current_content_manifest,
           args.output)


if __name__ == "__main__":
    main()
