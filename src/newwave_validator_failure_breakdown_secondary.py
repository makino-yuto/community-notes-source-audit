"""Aggregate the frozen support validator's failure modes without relabeling.

Inputs are private, frozen source packets and selected original/retry journals.
Outputs contain only group counts, category definitions, and input hashes.
"""

from __future__ import annotations

import collections
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"
OUT = R / "newwave_validator_failure_breakdown_secondary.json"
TABLE = R / "newwave_validator_failure_breakdown_secondary.md"
GROUPS = ("AI_API", "non_API")
LABELS = ("FULL", "PARTIAL", "NONE", "CONTRADICTS", "UNASSESSABLE")
EVIDENCE_POSITIVE = {"FULL", "PARTIAL", "CONTRADICTS"}
CATEGORIES = ("nonliteral_only", "length_only", "both_nonliteral_and_length", "other_validation_failure", "invalid_execution", "no_validation_failure")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def validate_independently(response, packet_row):
    """Reimplement the frozen validator, without importing or changing it."""
    sources = {s["source_id"]: s for s in packet_row["sources"]}
    errors, words = [], {}
    if response["main_claim_verdict"] in EVIDENCE_POSITIVE and not response["evidence"]:
        errors.append("missing_positive_evidence")
    for evidence in response["evidence"]:
        source = sources.get(evidence["source_id"])
        if source is None or not evidence["quote"] or evidence["quote"] not in source["main_text"]:
            errors.append("quote_not_literal:" + evidence["source_id"])
        words[evidence["source_id"]] = words.get(evidence["source_id"], 0) + len(evidence["quote"].split())
    if any(n > 20 for n in words.values()):
        errors.append("quote_word_limit")
    if len(response["source_observations"]) != len(sources) or {s["source_id"] for s in response["source_observations"]} != set(sources):
        errors.append("source_coverage")
    return errors


def main():
    assert not OUT.exists() and not TABLE.exists(), "Secondary outputs exist; do not overwrite."
    paths = {name: R / filename for name, filename in {
        "packet": "newwave_support_packet_blind.json",
        "original_journal": "newwave_support_trials_PRIVATE.jsonl",
        "retry_journal": "newwave_support_retry_trials_PRIVATE.jsonl",
        "technical_amendment": "newwave_support_retry_amendment_PRIVATE.json",
        "key": "newwave_semantic_key_PRIVATE.json",
    }.items()}
    reference_path = R / "newwave_support_analysis.json"
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    for name, path in paths.items():
        assert sha(path) == reference["input_sha256"][name], "Frozen input hash mismatch: " + name
    amendment = json.loads(paths["technical_amendment"].read_text(encoding="utf-8"))
    packet = json.loads(paths["packet"].read_text(encoding="utf-8"))
    packets = {row["code"]: row for row in packet}
    assert len(packet) == len(packets) == 200
    original, retry = jsonl(paths["original_journal"]), jsonl(paths["retry_journal"])
    assert len(original) == 186 and sum(bool(r["valid_execution"]) for r in original) == 185
    assert len(retry) == len({r["code"] for r in retry}) == 15
    assert sum(bool(r["valid_execution"]) for r in retry) == 14
    assert {r["code"] for r in retry} == set(amendment["retry_codes"])
    selected = {row["code"]: row for row in original if row["valid_execution"]}
    assert len(selected) == 185 and not set(selected) & {r["code"] for r in retry}
    selected.update({row["code"]: row for row in retry})
    assert set(selected) == set(packets)
    key = json.loads(paths["key"].read_text(encoding="utf-8"))
    group_by_code = {pair["code"] + side: group for pair in key for side, group in pair["groups"].items()}
    assert len(key) == 100 and set(group_by_code) == set(selected)

    counts = {g: collections.Counter() for g in GROUPS}
    events = {g: collections.Counter() for g in GROUPS}
    raw_counts = {g: collections.Counter() for g in GROUPS}
    strict_counts = {g: collections.Counter() for g in GROUPS}
    all_recomputed_errors_match_stored = True
    for code, execution in selected.items():
        group = group_by_code[code]
        c = counts[group]
        c["selected_cases"] += 1
        if not execution["valid_execution"]:
            c["invalid_execution"] += 1
            events[group]["invalid_execution"] += 1
            raw_counts[group]["UNASSESSABLE"] += 1
            strict_counts[group]["UNASSESSABLE"] += 1
            continue
        c["valid_executions"] += 1
        response = execution["response"]
        errors = validate_independently(response, packets[code])
        assert errors == execution["quote_validation_errors"], "Stored and recomputed validator errors differ."
        label = response["main_claim_verdict"]
        raw_counts[group][label] += 1
        strict_counts[group]["UNASSESSABLE" if errors else label] += 1
        nonliteral = any(error.startswith("quote_not_literal:") for error in errors)
        length = "quote_word_limit" in errors
        other = any(error.split(":", 1)[0] not in {"quote_not_literal", "quote_word_limit"} for error in errors)
        assert not other, "Unexpected failure type; expand mutually exclusive breakdown before reporting."
        if nonliteral and length:
            c["both_nonliteral_and_length"] += 1
        elif nonliteral:
            c["nonliteral_only"] += 1
        elif length:
            c["length_only"] += 1
        elif errors:
            c["other_validation_failure"] += 1
        else:
            c["no_validation_failure"] += 1
        c["any_nonliteral_cases"] += int(nonliteral)
        c["any_length_cases"] += int(length)
        for error in errors:
            events[group][error.split(":", 1)[0]] += 1
        if label in EVIDENCE_POSITIVE:
            c["raw_evidence_positive_or_contradicts_cases"] += 1
            c["evidence_positive_cases_failing_validator"] += int(bool(errors))
            c["positive_to_UNASSESSABLE_under_frozen_strict_rule"] += int(bool(errors))
        if errors:
            assert label in EVIDENCE_POSITIVE, "A failed case was not evidence-positive."

    by_group = {}
    for group in GROUPS:
        c = counts[group]
        assert c["selected_cases"] == 100
        assert sum(c[category] for category in CATEGORIES) == 100
        raw = {label: raw_counts[group][label] for label in LABELS}
        strict = {label: strict_counts[group][label] for label in LABELS}
        assert raw == reference["raw"]["by_group"][group]["label_counts"]
        assert strict == reference["strict"]["by_group"][group]["label_counts"]
        by_group[group] = {
            "selected_notes_denominator": 100,
            "valid_executions": c["valid_executions"],
            "exclusive_case_categories": {category: c[category] for category in CATEGORIES},
            "overlapping_failure_case_counts": {name: c[name] for name in ("any_nonliteral_cases", "any_length_cases")},
            "validator_event_counts": {name: events[group][name] for name in ("quote_not_literal", "quote_word_limit", "invalid_execution", "missing_positive_evidence", "source_coverage")},
            "raw_evidence_positive_or_contradicts_cases": c["raw_evidence_positive_or_contradicts_cases"],
            "evidence_positive_cases_failing_validator": c["evidence_positive_cases_failing_validator"],
            "positive_to_UNASSESSABLE_under_frozen_strict_rule": c["positive_to_UNASSESSABLE_under_frozen_strict_rule"],
            "raw_labels_reproduced_unchanged": raw,
            "strict_labels_reproduced_unchanged": strict,
        }
    totals = {category: sum(counts[g][category] for g in GROUPS) for category in CATEGORIES}
    assert totals == {"nonliteral_only": 3, "length_only": 12, "both_nonliteral_and_length": 3, "other_validation_failure": 0, "invalid_execution": 1, "no_validation_failure": 181}
    assert sum(counts[g]["evidence_positive_cases_failing_validator"] for g in GROUPS) == 18
    assert sum(counts[g]["any_nonliteral_cases"] for g in GROUPS) == 6
    assert sum(counts[g]["any_length_cases"] for g in GROUPS) == 15
    output = {
        "analysis_kind": "post_result_secondary_frozen_evidence_validator_failure_breakdown",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "Post-result descriptive breakdown; no source observations, raw labels, strict labels, or frozen analyses were changed.",
        "selection": {"selected_notes": 200, "selected_post_pairs": 100, "notes_per_group": 100, "selected_original_valid_journal_records": 185, "selected_retry_records": 15, "selected_retry_valid": 14, "selected_retry_invalid": 1, "unjournaled_original_completions_used": 0},
        "category_definitions": {
            "nonliteral_only": "At least one quoted span failed literal occurrence, with no quote-length failure.",
            "length_only": "At least one source exceeded the cumulative 20 whitespace-delimited word limit, with no nonliteral quote failure.",
            "both_nonliteral_and_length": "The selected case had both nonliteral-quote and quote-length failures.",
            "invalid_execution": "The selected technical retry was invalid; UNASSESSABLE in both raw and strict summaries, not an additional positive-label downgrade.",
            "other_validation_failure": "Other frozen validator failures, including missing positive evidence or incomplete source-observation coverage; none occurred.",
            "no_validation_failure": "Valid execution with no frozen validator error, irrespective of semantic label.",
        },
        "by_group": by_group,
        "totals": {"selected_notes": 200, "exclusive_case_categories": totals, "any_nonliteral_cases": 6, "any_length_cases": 15, "overlap_both_cases": 3, "evidence_positive_cases_failing_validator": 18, "invalid_executions_already_UNASSESSABLE": 1},
        "checks": {"input_hashes_match_frozen_support_analysis": True, "all_199_valid_selected_executions_independently_revalidated": True, "stored_vs_recomputed_error_mismatches": 0, "raw_group_label_counts_match_frozen_analysis": True, "strict_group_label_counts_match_frozen_analysis": True},
        "interpretation": "These are technical evidence-format and execution-compliance categories, not human-verified semantic error rates. A literal quote need not entail the claim, and exceeding the quote-word limit does not imply that the source lacks support. Source coverage here checks observation records for all supplied sources, not semantic adequacy of extracted text.",
        "privacy": "Aggregate counts and file hashes only; no note/post/account/source identifiers, source URLs, source text, quotations, or opaque case codes are released.",
        "input_sha256": {name: sha(path) for name, path in paths.items()},
        "frozen_support_aggregate_sha256": sha(reference_path),
        "script_sha256": sha(Path(__file__)),
    }
    table_rows = (("Nonliteral quotation only", "nonliteral_only"), ("Quote length only", "length_only"), ("Both nonliteral and length", "both_nonliteral_and_length"), ("Other validation failure", "other_validation_failure"), ("Invalid execution", "invalid_execution"), ("No validation failure", "no_validation_failure"))
    markdown = "# Evidence-validator failure breakdown\n\n"
    markdown += "**Exclusive categories; 100 selected notes per group.** Counts reproduce the frozen selection of 185 valid original journal records plus all 15 technical retries.\n\n"
    markdown += "| Selected-case category | AI-API | Non-API |\n|---|---:|---:|\n"
    for label, category in table_rows:
        markdown += f"| {label} | {counts['AI_API'][category]} | {counts['non_API'][category]} |\n"
    markdown += "| Total | 100 | 100 |\n\n"
    markdown += "Thirteen AI-API and five non-API evidence-positive judgments failed the frozen validator and became UNASSESSABLE in the existing strict summary. Across groups, six cases had a nonliteral-quote failure and 15 had a quote-length failure, overlapping in three cases. The one invalid execution was already UNASSESSABLE in both summaries and is not an additional positive-label downgrade. All 199 valid selected executions were independently revalidated; their errors and the raw/strict group label counts exactly matched the frozen analysis. No labels changed.\n\n"
    markdown += "These categories measure technical evidence-format compliance, not semantic accuracy. In particular, a length-only failure does not imply that the cited source lacks support. The validator's source-coverage check verifies records for every supplied source; it does not certify semantic coverage.\n"
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    TABLE.write_text(markdown, encoding="utf-8")
    print(json.dumps({"outputs": [str(OUT), str(TABLE)], "exclusive_case_categories_by_group": {g: by_group[g]["exclusive_case_categories"] for g in GROUPS}, "stored_vs_recomputed_error_mismatches": 0}))


if __name__ == "__main__":
    main()
