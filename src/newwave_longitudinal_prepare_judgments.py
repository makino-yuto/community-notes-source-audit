"""Freeze a time/group-blinded source-support packet for archival follow-up."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve()
PUBLIC = HERE.parents[1]
PRIVATE = PUBLIC.parent / "results"
CLAIMS_SHA = "125f670032cf6ea46962ce00bed7163c3887176f7cc475d3fc5a8360d5de8585"
SELECTION_SHA = "b7002926296de4f046f78e0aff601d882779ea375bddb5a0628ed69e89cd6ffb"
CAP = 24_000
SEED = "2026111518|archive-source-judge|"
WRAPPER = re.compile(
    r"(?i)(?:the wayback machine has not archived that url|"
    r"wayback machine doesn't have that page archived|"
    r"this page is not available on the web because|"
    r"cannot be displayed due to robots\.txt)"
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def quality_warning(parsed: dict) -> str | None:
    title = (parsed.get("title") or "").strip().lower()
    body = parsed["main_text"]["text"]
    if title in {"wayback machine", "internet archive: wayback machine"}:
        return "archive_wrapper_title"
    if WRAPPER.search(body[:1500]):
        return "archive_error_body"
    return None


def freeze(claims: Path, selection: Path, replay: Path, current: Path,
           replay_protocol: Path, current_manifest: Path, packet: Path,
           mapping: Path, protocol: Path, judge_script: Path) -> dict:
    for out in (packet, mapping, protocol):
        if out.exists():
            raise FileExistsError(out)
    if sha(claims) != CLAIMS_SHA or sha(selection) != SELECTION_SHA:
        raise ValueError("Frozen claims/selection hash changed")
    sel = json.loads(selection.read_text(encoding="utf-8"))
    rp = json.loads(replay_protocol.read_text(encoding="utf-8"))
    if rp["inputs"]["frozen_claims_sha256"] != CLAIMS_SHA or rp["inputs"]["selection_sha256"] != SELECTION_SHA:
        raise ValueError("Replay protocol did not bind frozen claims/selection")
    replays = read_rows(replay)
    by_replay = {row["query_id"]: row for row in replays}
    if len(sel["entries"]) != 100 or len(replays) != 100 or len(by_replay) != 100:
        raise ValueError("Expected full 100-unit replay log")
    claim_rows = read_rows(claims)
    by_claim = {(r["pair_code"], r["side"], r["note_id"]): r for r in claim_rows}
    if len(claim_rows) != 200 or len(by_claim) != 200:
        raise ValueError("Expected 200 frozen claims")
    current_rows = read_rows(current)
    by_current = {row["url_sha256"]: row for row in current_rows}
    manifest = json.loads(current_manifest.read_text(encoding="utf-8"))
    if (len(current_rows) != 319 or len(by_current) != 319 or
        {(r["url_sha256"], r["url"]) for r in current_rows} !=
        {(r["url_sha256"], r["url"]) for r in manifest["urls"]} or
        sel["current_content_results_sha256"] != sha(current) or
        sel["current_content_manifest_sha256"] != sha(current_manifest)):
        raise ValueError("Current-content census not frozen or complete")
    items = []
    outcomes = Counter()
    both_parseable = 0
    warnings = 0
    for unit in sel["entries"]:
        result = by_replay[unit["query_id"]]
        outcomes[result["outcome"]] += 1
        if result["outcome"] != "body_replayed_parseable_text":
            continue
        refs = unit["associated_citation_refs"]
        if len(refs) != 1:
            raise ValueError("Expected one claim reference per replayed unit")
        ref = refs[0]
        claim = by_claim[(ref["pair_code"], ref["side"], ref["note_id"])]["main_claim"]
        historical = next((r for r in (result["primary"], result["fallback"])
                           if r is not None and r["outcome"] == "body_replayed_parseable_text"), None)
        if (historical is None or historical["final_http_status"] != 200 or
            historical["memento_check"] != "matched_within_one_second"):
            raise ValueError("Historical source lacks verified replay provenance")
        current_row = by_current[unit["network_url_sha256"]]
        current_parsed = current_row.get("parsed")
        if (current_parsed is None or current_parsed.get("parse_status") != "ok" or
            current_parsed["main_text"]["chars_saved"] == 0):
            continue
        both_parseable += 1
        for version, parsed, body_hash in (
            ("historical", historical["parsed"], historical["body_sha256"]),
            ("current", current_parsed, current_row["body_sha256"]),
        ):
            warning = quality_warning(parsed)
            warnings += warning is not None
            field = parsed["main_text"]
            blinded = {"code": "", "main_claim": claim,
                       "sources": [{"source_id": "S1", "main_text": field["text"][:CAP],
                                    "format": parsed["format"],
                                    "text_truncated": field["chars_total"] > CAP or field["truncated"]}],
                       "source_quality_warning": warning}
            crosswalk = {"code": "", "query_id": unit["query_id"],
                         "pair_code": ref["pair_code"], "side": ref["side"],
                         "note_id": ref["note_id"], "version": version,
                         "body_sha256": body_hash,
                         "main_text_sha256": field["sha256_saved"]}
            rank = hashlib.sha256((SEED + unit["query_id"] + "|" + version).encode("ascii")).hexdigest()
            items.append((rank, blinded, crosswalk))
    if both_parseable != 31 or len(items) != 62:
        raise ValueError(f"Expected 31 paired parseable units; got {both_parseable}/{len(items)}")
    items.sort(key=lambda row: row[0])
    packet_rows = []
    map_rows = []
    for i, (_, blinded, crosswalk) in enumerate(items, 1):
        code = f"J{i:03d}"
        blinded["code"] = code
        crosswalk["code"] = code
        packet_rows.append(blinded)
        map_rows.append(crosswalk)
    packet.parent.mkdir(parents=True, exist_ok=True)
    packet.write_text(json.dumps(packet_rows, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":")) + "\n", encoding="utf-8")
    mapping.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True,
                                          separators=(",", ":")) + "\n" for row in map_rows),
                       encoding="utf-8")
    plan = {
        "schema": "newwave-longitudinal-blinded-source-support-v1",
        "status": "FROZEN BEFORE ANY NEW ARCHIVE SOURCE-SUPPORT MODEL LABEL",
        "prepared_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "conditional_frame": {"frozen_panel_units": 100, "both_parseable_query_units": both_parseable,
                              "single_source_judgment_items": len(packet_rows),
                              "wrapper_markers": warnings,
                              "all_panel_replay_outcomes": dict(sorted(outcomes.items()))},
        "method": {"blinding": "Opaque codes and shuffled order hide author group and historical/current labels. Source text can itself expose dates.",
                   "claim": "Exact pre-source first main correction; never revise after source inspection.",
                   "judgment": "Independent one-claim/one-source labels FULL, PARTIAL, NONE, CONTRADICTS, UNASSESSABLE; pair only after all labels freeze.",
                   "text_cap_characters": CAP,
                   "wrapper": "Archive wrapper/error markers are technical warnings, not support labels; absent substantive intended evidence is UNASSESSABLE.",
                   "quote": "Positive/contradictory labels require literal source quotation, at most 20 words per source.",
                   "scope": "Observed source-to-claim support, not external truth or note correctness; all 100 panel outcomes remain in availability denominator."},
        "inputs": {"claims_sha256": sha(claims), "selection_sha256": sha(selection),
                   "replay_sha256": sha(replay), "replay_protocol_sha256": sha(replay_protocol),
                   "current_sha256": sha(current), "current_manifest_sha256": sha(current_manifest),
                   "packet_sha256": sha(packet), "crosswalk_sha256": sha(mapping),
                   "prepare_script_sha256": sha(HERE), "judge_script_sha256": sha(judge_script)},
        "private_filenames": {"packet": packet.name, "crosswalk": mapping.name,
                              "claims": claims.name, "replay": replay.name, "current": current.name}
    }
    protocol.parent.mkdir(parents=True, exist_ok=True)
    protocol.write_text(json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                        encoding="utf-8")
    return {"packet_sha256": sha(packet), "crosswalk_sha256": sha(mapping),
            "protocol_sha256": sha(protocol), "items": len(packet_rows), "wrapper_markers": warnings}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--claims", type=Path, default=PRIVATE / "newwave_longitudinal_claims_PRIVATE.jsonl")
    p.add_argument("--selection", type=Path, default=PRIVATE / "newwave_longitudinal_replay_selection_PRIVATE.json")
    p.add_argument("--replay", type=Path, default=PRIVATE / "newwave_longitudinal_replay_PRIVATE.jsonl")
    p.add_argument("--current", type=Path, default=PRIVATE / "newwave_semantic_content_PRIVATE.jsonl")
    p.add_argument("--replay-protocol", type=Path, default=PUBLIC / "protocols" / "2026-11-15-longitudinal-replay.json")
    p.add_argument("--current-manifest", type=Path, default=PRIVATE / "newwave_semantic_content_manifest_PRIVATE.json")
    p.add_argument("--packet", type=Path, default=PRIVATE / "newwave_longitudinal_judge_packet_PRIVATE.json")
    p.add_argument("--mapping", type=Path, default=PRIVATE / "newwave_longitudinal_judge_mapping_PRIVATE.jsonl")
    p.add_argument("--protocol", type=Path, default=PUBLIC / "protocols" / "2026-11-15-longitudinal-judge.json")
    p.add_argument("--judge-script", type=Path, default=PUBLIC / "src" / "newwave_longitudinal_judge.py")
    a = p.parse_args()
    print(json.dumps(freeze(a.claims, a.selection, a.replay, a.current, a.replay_protocol,
                            a.current_manifest, a.packet, a.mapping, a.protocol, a.judge_script)), flush=True)


if __name__ == "__main__":
    main()
