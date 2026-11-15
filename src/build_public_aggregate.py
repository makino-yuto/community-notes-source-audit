"""Validate private inputs and emit a publication-safe aggregate JSON.

The input cohort and probe logs contain note text, author IDs, and URLs. Keep
them local. This program writes only group-level counts and file hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

GROUPS = ("AI_API", "non_API")
CATEGORIES = ("open_candidate", "access_barrier", "transient_uncertain", "gone_candidate")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--probes", type=Path, required=True)
    parser.add_argument("--primary-analysis", type=Path, required=True)
    parser.add_argument("--corrected-analysis", type=Path, required=True)
    parser.add_argument("--correction-overrides", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    cohort = read_json(args.cohort)
    primary = read_json(args.primary_analysis)
    corrected = read_json(args.corrected_analysis)
    overrides = read_json(args.correction_overrides)
    rows = cohort["matched"]
    probes = [json.loads(line) for line in args.probes.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != len(probes) or len(rows) != 600:
        raise ValueError("Expected exactly 600 matched notes and probe records")
    by_id = {row["note_id"]: row for row in rows}
    observed = {row["note_id"]: row for row in probes}
    if len(by_id) != 600 or len(observed) != 600 or by_id.keys() != observed.keys():
        raise ValueError("Missing or duplicated note/probe IDs")
    for note_id, row in by_id.items():
        probe = observed[note_id]
        if (row["selected_url"], row["author_type"], row["month_utc"]) != (
            probe["url"], probe["author_type"], probe["month_utc"]
        ):
            raise ValueError("Probe does not match frozen cohort")
        if probe["category"] not in CATEGORIES:
            raise ValueError("Unknown probe category")
    if len(rows) % 2:
        raise ValueError("Expected adjacent matched pairs")
    for i in range(0, len(rows), 2):
        first, second = rows[i:i + 2]
        if (first["author_type"], second["author_type"]) != GROUPS or first["month_utc"] != second["month_utc"]:
            raise ValueError("Invalid month-matched pair")

    primary_counts = {
        group: {category: sum(p["author_type"] == group and p["category"] == category for p in probes)
                for category in CATEGORIES}
        for group in GROUPS
    }
    if any(sum(primary_counts[group].values()) != 300 for group in GROUPS):
        raise ValueError("Wrong group denominator")
    if primary_counts != {g: {c: primary["counts"][g].get(c, 0) for c in CATEGORIES} for g in GROUPS}:
        raise ValueError("Stored primary counts differ from raw probes")
    primary_difference = (primary_counts["AI_API"]["open_candidate"] - primary_counts["non_API"]["open_candidate"]) / 300
    if abs(primary_difference - primary["ai_minus_non_api_open_difference"]) > 1e-12:
        raise ValueError("Wrong primary difference")
    if primary["overrides_count"] != 0:
        raise ValueError("Primary analysis must be uncorrected")

    if not set(overrides).issubset(by_id) or len(overrides) != corrected["overrides_count"]:
        raise ValueError("Correction override count/IDs do not match")
    corrected_counts = {g: Counter() for g in GROUPS}
    for note_id, probe in observed.items():
        category = overrides.get(note_id, {}).get("final_category", probe["category"])
        if category not in CATEGORIES:
            raise ValueError("Invalid corrected category")
        corrected_counts[probe["author_type"]][category] += 1
    if {g: {c: corrected_counts[g][c] for c in CATEGORIES} for g in GROUPS} != {
        g: {c: corrected["counts"][g].get(c, 0) for c in CATEGORIES} for g in GROUPS
    }:
        raise ValueError("Stored corrected counts differ from overrides")
    corrected_difference = (corrected_counts["AI_API"]["open_candidate"] - corrected_counts["non_API"]["open_candidate"]) / 300
    if abs(corrected_difference - corrected["ai_minus_non_api_open_difference"]) > 1e-12:
        raise ValueError("Wrong corrected difference")

    author_counts = {group: Counter(row["author_id"] for row in rows if row["author_type"] == group) for group in GROUPS}
    group_summary = {}
    for group in GROUPS:
        group_summary[group] = {
            "notes": 300,
            "authors": len(author_counts[group]),
            "max_notes_per_author": max(author_counts[group].values()),
            "machine_categories": primary_counts[group],
            "machine_open_candidate_rate": primary_counts[group]["open_candidate"] / 300,
            "machine_open_candidate_wilson_95": primary["open_rate_wilson_95"][group],
        }

    public = {
        "status": "machine_observable_url_retrievability_before_semantic_source_review",
        "snapshot_date": cohort["snapshot_date"],
        "selected_creation_months": sorted({row["month_utc"] for row in rows}),
        "sample": "300 month-matched AI-API/non-API pairs; one seeded external URL per currently Helpful note",
        "source_cohort_sha256": file_hash(args.cohort),
        "private_probe_log_sha256": file_hash(args.probes),
        "groups": group_summary,
        "primary": {
            "measure": "machine open candidate, not confirmed supporting evidence",
            "ai_api_minus_non_api_rate_difference": primary_difference,
            "month_stratified_pair_bootstrap_95": primary["ai_minus_non_api_bootstrap_95"],
            "bootstrap_replicates": 10000,
            "bootstrap_seed": 20261115,
            "manual_overrides": 0,
        },
        "post_hoc_corrected_sensitivity": {
            "status": "two browser-reviewed syntax corrections; not the primary estimate",
            "override_file_sha256": file_hash(args.correction_overrides),
            "changed_notes": len(overrides),
            "machine_categories": {g: {c: corrected_counts[g][c] for c in CATEGORIES} for g in GROUPS},
            "ai_api_minus_non_api_rate_difference": corrected_difference,
            "month_stratified_pair_bootstrap_95": corrected["ai_minus_non_api_bootstrap_95"],
        },
        "interpretation_limits": [
            "Descriptive comparison, not a causal effect of AI writing.",
            "non_API is an observed enrollment category, not verified human authorship.",
            "A machine-open URL may not contain the cited evidence or support the note.",
            "Access barriers and uncertain probes are not evidence that a source is gone.",
            "Only currently Helpful notes with surviving content and a selected external URL are sampled.",
            "Authors, source hosts, topics, and notes are not independent or fully matched.",
            "Current web responses can differ from the dated primary probe observations.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(public, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"validated_pairs": 300, "primary_difference": primary_difference,
                      "post_hoc_difference": corrected_difference, "output": str(args.output)}))


if __name__ == "__main__":
    main()
