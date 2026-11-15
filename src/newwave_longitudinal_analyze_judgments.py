"""Conservative analysis of the frozen archival support judgments.

This script was drafted before the 62-item judgment run completed. It keeps
all 100 selected URL-anchor units, treats invalid or nonassessable judgments
as unknown, and emits private candidates for independent review. A label
change alone is never called source-version semantic drift.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve()
PUBLIC = HERE.parents[1]
PRIVATE = PUBLIC.parent / "results"
LABELS = {"FULL", "PARTIAL", "NONE", "CONTRADICTS", "UNASSESSABLE"}
ASSESSED = LABELS - {"UNASSESSABLE"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def effective_label(trial: dict) -> str | None:
    """Invalid execution, quote, or nonsubstantive text yields unknown."""
    if not trial.get("valid_execution") or trial.get("quote_validation_errors"):
        return None
    response = trial.get("response")
    if not isinstance(response, dict) or response.get("main_claim_verdict") not in LABELS:
        return None
    observations = response.get("source_observations")
    if not isinstance(observations, list) or len(observations) != 1:
        return None
    if observations[0].get("source_id") != "S1":
        return None
    label = response["main_claim_verdict"]
    if label in ASSESSED and observations[0].get("substantive_text_observed") is not True:
        return None
    return label


def indicator_bounds(label: str | None) -> tuple[int, int]:
    if label is None or label == "UNASSESSABLE":
        return 0, 1
    value = int(label == "FULL")
    return value, value


def actual_capture(replay_row: dict) -> dict:
    if replay_row["outcome"] != "body_replayed_parseable_text":
        raise ValueError("No successful archived body in replay row")
    for key in ("primary", "fallback"):
        attempt = replay_row.get(key)
        if attempt and attempt.get("outcome") == "body_replayed_parseable_text":
            if attempt.get("final_http_status") != 200 or attempt.get("memento_check") != "matched_within_one_second":
                raise ValueError("Archive provenance missing from successful replay")
            return attempt
    raise ValueError("Replay success has no successful attempt")


def timestamp_millis(stamp: str) -> int:
    return int(datetime.strptime(stamp, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).timestamp() * 1000)


def summarize(protocol: Path, continuation_protocol: Path,
              selection_path: Path, replay_path: Path,
              mapping_path: Path, packet_path: Path, judgment_v1_path: Path,
              judgment_v2_path: Path,
              public_out: Path, private_out: Path) -> dict:
    if public_out.exists() or private_out.exists():
        raise FileExistsError("Analysis outputs already exist")
    plan = json.loads(protocol.read_text(encoding="utf-8"))
    continuation = json.loads(continuation_protocol.read_text(encoding="utf-8"))
    if (continuation["inputs"]["v1_protocol_sha256"] != sha(protocol) or
        continuation["inputs"]["packet_sha256"] != sha(packet_path)):
        raise ValueError("No-retry continuation does not bind frozen v1 protocol/packet")
    for name, path in (("selection_sha256", selection_path),
                       ("replay_sha256", replay_path),
                       ("crosswalk_sha256", mapping_path),
                       ("packet_sha256", packet_path)):
        if sha(path) != plan["inputs"][name]:
            raise ValueError(f"Frozen input hash changed: {name}")
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    panel = selection["entries"]
    if len(panel) != 100 or len({item["query_id"] for item in panel}) != 100:
        raise ValueError("Panel must contain 100 distinct selected units")
    replay_rows = read_jsonl(replay_path)
    replay = {item["query_id"]: item for item in replay_rows}
    if len(replay_rows) != 100 or set(replay) != {item["query_id"] for item in panel}:
        raise ValueError("Replay log does not cover the frozen panel")
    mapping = read_jsonl(mapping_path)
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    packet_by_code = {item["code"]: item for item in packet}
    if sha(judgment_v1_path) != continuation["inputs"]["v1_log_sha256"]:
        raise ValueError("Original three-row judgment log changed")
    original_judgments = read_jsonl(judgment_v1_path)
    continued_judgments = read_jsonl(judgment_v2_path)
    if ([row["code"] for row in original_judgments] != [f"J{i:03d}" for i in range(1, 4)] or
        [row["code"] for row in continued_judgments] != [f"J{i:03d}" for i in range(4, 63)]):
        raise ValueError("No-retry judgment continuation is incomplete or reordered")
    judgments = original_judgments + continued_judgments
    by_code = {item["code"]: item for item in judgments}
    if (len(mapping) != 62 or len(packet_by_code) != 62 or len(packet) != 62 or
        len(judgments) != 62 or len(by_code) != 62 or
        {item["code"] for item in mapping} != set(packet_by_code) or
        set(by_code) != set(packet_by_code)):
        raise ValueError("All 62 frozen judgment items, including invalid ones, are required")
    paired = defaultdict(dict)
    for item in mapping:
        code = item["code"]
        if item["version"] not in {"historical", "current"}:
            raise ValueError("Unrecognized version in private crosswalk")
        packet_row_hash = text_sha(json.dumps(packet_by_code[code], sort_keys=True,
                                              ensure_ascii=False, separators=(",", ":")))
        logged_hash = by_code[code].get("packet_row_sha256")
        if logged_hash is not None and logged_hash != packet_row_hash:
            raise ValueError("Judgment row was not run on the frozen packet item")
        if by_code[code].get("valid_execution") and logged_hash is None:
            raise ValueError("Valid judgment lacks frozen packet-row hash")
        query_id = item["query_id"]
        if item["version"] in paired[query_id]:
            raise ValueError("Duplicate version for a selected unit")
        paired[query_id][item["version"]] = {
            "code": code,
            "label": effective_label(by_code[code]),
            "raw_execution_valid": bool(by_code[code].get("valid_execution")),
            "saved_text_sha256": item["main_text_sha256"],
            "judged_text_sha256": text_sha(packet_by_code[code]["sources"][0]["main_text"]),
        }
    if len(paired) != 31 or any(set(value) != {"historical", "current"}
                                 for value in paired.values()):
        raise ValueError("Expected 31 complete parser-level historical/current pairs")
    if {key for key, value in replay.items() if value["outcome"] == "body_replayed_parseable_text"} != set(paired):
        raise ValueError("Judgment packet selected a changed replay subset")

    counts = {
        "panel_units": 100,
        "parser_paired_units": 31,
        "raw_model_executions_valid": sum(bool(row.get("valid_execution")) for row in judgments),
        "invalid_or_failed_model_items": sum(not bool(row.get("valid_execution")) for row in judgments),
        "effective_unknown_judgment_items": sum(effective_label(row) is None for row in judgments),
    }
    label_counts = {version: Counter() for version in ("historical", "current")}
    full_transitions = Counter()
    detailed_transitions = Counter()
    postcreation_full_transitions = Counter()
    cohort = defaultdict(lambda: Counter())
    candidate_details = []
    private_units = []
    lower_sum = upper_sum = 0
    both_assessed_notes = set()
    postcreation_parser = postcreation_both_assessed = 0
    postcreation_assessed_notes = set()
    equal_saved_text = equal_judged_text = same_label = 0

    for item in panel:
        query_id = item["query_id"]
        refs = item["associated_citation_refs"]
        if len(refs) != 1:
            raise ValueError("This frozen panel must have one citation reference per unit")
        ref = refs[0]
        group = ref["group"]
        cohort[group]["panel"] += 1
        versions = paired.get(query_id)
        old = versions["historical"]["label"] if versions else None
        new = versions["current"]["label"] if versions else None
        old_low, old_high = indicator_bounds(old)
        new_low, new_high = indicator_bounds(new)
        unit_lower, unit_upper = new_low - old_high, new_high - old_low
        lower_sum += unit_lower
        upper_sum += unit_upper
        cohort[group]["lower_sum"] += unit_lower
        cohort[group]["upper_sum"] += unit_upper
        capture_precreation = None
        if versions:
            for version, label in (("historical", old), ("current", new)):
                label_counts[version][label if label is not None else "INVALID_OR_INCONSISTENT_EXECUTION"] += 1
            capture = actual_capture(replay[query_id])
            capture_ms = timestamp_millis(capture["requested_timestamp"])
            capture_precreation = capture_ms < ref["created_at_millis"]
            cohort[group]["parser_paired"] += 1
            postcreation_parser += not capture_precreation
            equal_saved_text += (versions["historical"]["saved_text_sha256"] ==
                                 versions["current"]["saved_text_sha256"])
            equal_judged_text += (versions["historical"]["judged_text_sha256"] ==
                                  versions["current"]["judged_text_sha256"])
            same_label += (old == new) and (old is not None)
            if old in ASSESSED and new in ASSESSED:
                both_assessed_notes.add(ref["note_id"])
                cohort[group]["both_semantically_assessable"] += 1
                postcreation_both_assessed += not capture_precreation
                detailed_transitions[f"{old}->{new}"] += 1
                old_full, new_full = old == "FULL", new == "FULL"
                full_transitions[(old_full, new_full)] += 1
                if not capture_precreation:
                    postcreation_full_transitions[(old_full, new_full)] += 1
                    postcreation_assessed_notes.add(ref["note_id"])
                cohort[group]["historical_full_complete_case"] += old_full
                cohort[group]["current_full_complete_case"] += new_full
                if old_full != new_full:
                    candidate_details.append({
                        "query_id": query_id,
                        "pair_code": ref["pair_code"],
                        "note_id": ref["note_id"],
                        "group": group,
                        "capture_precreation": capture_precreation,
                        "historical_label": old,
                        "current_label": new,
                        "historical_code": versions["historical"]["code"],
                        "current_code": versions["current"]["code"],
                        "saved_main_text_hash_equal":
                            versions["historical"]["saved_text_sha256"] ==
                            versions["current"]["saved_text_sha256"],
                        "judged_24000_text_hash_equal":
                            versions["historical"]["judged_text_sha256"] ==
                            versions["current"]["judged_text_sha256"],
                        "interpretation": "AI FULL-label change; source-version drift unverified",
                    })
        private_units.append({
            "query_id": query_id, "group": group,
            "historical_label": old, "current_label": new,
            "capture_precreation": capture_precreation,
            "full_difference_lower": unit_lower,
            "full_difference_upper": unit_upper,
        })
    both_assessed = sum(full_transitions.values())
    gate = both_assessed >= 30 and len(both_assessed_notes) >= 20
    full_matrix = {
        "both_full": full_transitions[(True, True)],
        "historical_full_only": full_transitions[(True, False)],
        "current_full_only": full_transitions[(False, True)],
        "neither_full": full_transitions[(False, False)],
    }
    aggregate = {
        "schema": "newwave-longitudinal-aggregate-v1",
        "judgment_protocol_sha256": sha(protocol),
        "no_retry_continuation_protocol_sha256": sha(continuation_protocol),
        "judgment_v1_log_sha256": sha(judgment_v1_path),
        "judgment_v2_log_sha256": sha(judgment_v2_path),
        "selection_sha256": sha(selection_path),
        "replay_sha256": sha(replay_path),
        "frozen_packet_sha256": sha(packet_path),
        "counts": counts,
        "replay_outcomes_on_all_100_units": dict(sorted(Counter(value["outcome"] for value in replay.values()).items())),
        "labels_among_31_parser_pairs": {key: dict(sorted(value.items())) for key, value in label_counts.items()},
        "both_semantically_assessable_units": both_assessed,
        "both_semantically_assessable_distinct_notes": len(both_assessed_notes),
        "prespecified_descriptive_paired_gate_met": gate,
        "full_support_transitions_conditional_on_both_assessed": full_matrix,
        "detailed_transitions_conditional_on_both_assessed": dict(sorted(detailed_transitions.items())),
        "full_current_minus_historical_100_unit_missingness_bounds": {
            "lower": lower_sum / 100,
            "upper": upper_sum / 100,
            "unit": "proportion",
        },
        "source_text_diagnostics_on_31_parser_pairs": {
            "equal_saved_main_text_hash": equal_saved_text,
            "equal_judged_first_24000_characters_hash": equal_judged_text,
            "same_valid_ai_label": same_label,
        },
        "timing": {
            "post_note_creation_captures_among_31_parser_pairs": postcreation_parser,
            "post_note_creation_and_both_assessable": postcreation_both_assessed,
            "post_note_creation_both_assessable_distinct_notes": len(postcreation_assessed_notes),
            "post_note_creation_full_transitions": {
                "both_full": postcreation_full_transitions[(True, True)],
                "historical_full_only": postcreation_full_transitions[(True, False)],
                "current_full_only": postcreation_full_transitions[(False, True)],
                "neither_full": postcreation_full_transitions[(False, False)],
            },
        },
        "exploratory_group_counts": {key: dict(sorted(value.items())) for key, value in cohort.items()},
        "independent_review_candidates": {
            "all_full_label_change": len(candidate_details),
            "with_different_judged_text": sum(not x["judged_24000_text_hash_equal"] for x in candidate_details),
            "with_identical_judged_text": sum(x["judged_24000_text_hash_equal"] for x in candidate_details),
        },
        "interpretation": "AI source-to-claim labels are not note truth. Unknown includes invalid judgments, UNASSESSABLE bodies, and the 69 units without parser-level pairs. Bounds retain all 100 units. Label changes do not establish semantic source drift; candidates require separate identity/text review. Most successful captures predate note creation.",
    }
    private_detail = {"aggregate": aggregate,
                      "candidate_full_label_change_PRIVATE": candidate_details,
                      "all_100_units_PRIVATE": private_units}
    public_out.parent.mkdir(parents=True, exist_ok=True)
    private_out.parent.mkdir(parents=True, exist_ok=True)
    public_out.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    private_out.write_text(json.dumps(private_detail, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"both_assessable": both_assessed, "gate_met": gate,
                      "candidate_count": len(candidate_details),
                      "bounds": aggregate["full_current_minus_historical_100_unit_missingness_bounds"]}), flush=True)
    return aggregate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=PUBLIC / "protocols" / "2026-11-15-longitudinal-judge.json")
    parser.add_argument("--continuation-protocol", type=Path,
                        default=PUBLIC / "protocols" / "2026-11-15-longitudinal-judge-v2.json")
    parser.add_argument("--selection", type=Path, default=PRIVATE / "newwave_longitudinal_replay_selection_PRIVATE.json")
    parser.add_argument("--replay", type=Path, default=PRIVATE / "newwave_longitudinal_replay_PRIVATE.jsonl")
    parser.add_argument("--mapping", type=Path, default=PRIVATE / "newwave_longitudinal_judge_mapping_PRIVATE.jsonl")
    parser.add_argument("--packet", type=Path, default=PRIVATE / "newwave_longitudinal_judge_packet_PRIVATE.json")
    parser.add_argument("--judgments-v1", type=Path, default=PRIVATE / "newwave_longitudinal_judgments_PRIVATE.jsonl")
    parser.add_argument("--judgments-v2", type=Path, default=PRIVATE / "newwave_longitudinal_judgments_v2_PRIVATE.jsonl")
    parser.add_argument("--public-output", type=Path, default=PRIVATE / "newwave_longitudinal_aggregate_PUBLIC_CANDIDATE.json")
    parser.add_argument("--private-output", type=Path, default=PRIVATE / "newwave_longitudinal_analysis_PRIVATE.json")
    args = parser.parse_args()
    summarize(args.protocol, args.continuation_protocol,
              args.selection, args.replay, args.mapping, args.packet,
              args.judgments_v1, args.judgments_v2,
              args.public_output, args.private_output)


if __name__ == "__main__":
    main()
