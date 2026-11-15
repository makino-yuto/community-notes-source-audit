"""Analyze the frozen matched cohort and bounded URL-probe results.

Only machine-observable reachability is summarized here. A later adjudication
file can replace categories after source-role and access-barrier review.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import random
from pathlib import Path
from urllib.parse import urlsplit


ALLOWED = {"open_candidate", "access_barrier", "gone_candidate", "transient_uncertain"}


def wilson(successes: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    radius = z / denom * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return (max(0.0, center - radius), min(1.0, center + radius))


def quantile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return float("nan")
    position = (len(sorted_values) - 1) * p
    left = int(position)
    right = min(left + 1, len(sorted_values) - 1)
    return sorted_values[left] + (sorted_values[right] - sorted_values[left]) * (position - left)


def load_probe_rows(path: Path) -> dict[str, dict]:
    probes: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        note_id = str(row["note_id"])
        if note_id in probes:
            raise ValueError(f"Duplicate note_id in probes: {note_id}")
        if row["category"] not in ALLOWED:
            raise ValueError(f"Unexpected category {row['category']}")
        probes[note_id] = row
    return probes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--probes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overrides", type=Path, help="Optional JSON keyed by note_id with final_category")
    parser.add_argument("--bootstrap", type=int, default=10000)
    args = parser.parse_args()

    cohort = json.loads(args.cohort.read_text(encoding="utf-8"))
    matched = cohort["matched"]
    if len(matched) % 2:
        raise ValueError("Cohort must contain AI/human pairs")
    probes = load_probe_rows(args.probes)
    cohort_ids = {str(row["note_id"]) for row in matched}
    if cohort_ids != set(probes):
        raise ValueError(f"Probe coverage mismatch: missing={len(cohort_ids - set(probes))}, extra={len(set(probes) - cohort_ids)}")
    overrides = json.loads(args.overrides.read_text(encoding="utf-8")) if args.overrides else {}
    unknown_override_ids = set(overrides) - cohort_ids
    if unknown_override_ids:
        raise ValueError(f"Overrides outside cohort: {len(unknown_override_ids)}")

    rows: dict[str, dict] = {}
    pairs_by_month = collections.defaultdict(list)
    category_counts = collections.defaultdict(collections.Counter)
    per_domain = collections.defaultdict(lambda: collections.Counter())
    for pair_start in range(0, len(matched), 2):
        ai, human = matched[pair_start:pair_start + 2]
        if ai["author_type"] != "AI_API" or human["author_type"] != "non_API":
            raise ValueError(f"Pair {pair_start // 2} is not AI/non-API")
        if ai["month_utc"] != human["month_utc"]:
            raise ValueError(f"Pair {pair_start // 2} is not month matched")
        pair_values = []
        for source in (ai, human):
            note_id = str(source["note_id"])
            probe = probes[note_id]
            if probe["url"] != source["selected_url"]:
                raise ValueError(f"URL mismatch for {note_id}")
            category = overrides.get(note_id, {}).get("final_category", probe["category"])
            if category not in ALLOWED:
                raise ValueError(f"Unexpected override category {category}")
            group = source["author_type"]
            category_counts[group][category] += 1
            host = (urlsplit(source["selected_url"]).hostname or "").lower()
            per_domain[group][host] += 1
            rows[note_id] = {"group": group, "month": source["month_utc"], "host": host, "category": category}
            pair_values.append(int(category == "open_candidate"))
        pairs_by_month[ai["month_utc"]].append(tuple(pair_values))

    n_pairs = len(matched) // 2
    ai_open = category_counts["AI_API"]["open_candidate"]
    human_open = category_counts["non_API"]["open_candidate"]
    difference = (ai_open - human_open) / n_pairs if n_pairs else float("nan")
    rng = random.Random(20261115)
    bootstrap_differences = []
    for _ in range(args.bootstrap):
        total = 0
        for month_pairs in pairs_by_month.values():
            for _ in range(len(month_pairs)):
                ai_value, human_value = month_pairs[rng.randrange(len(month_pairs))]
                total += ai_value - human_value
        bootstrap_differences.append(total / n_pairs)
    bootstrap_differences.sort()

    summary = {
        "snapshot_date": cohort["snapshot_date"],
        "sample_note_count": len(matched),
        "matched_pairs": n_pairs,
        "analysis_kind": "machine_observable_reachability_before_semantic_source_review",
        "overrides_count": len(overrides),
        "counts": {group: dict(category_counts[group]) for group in ("AI_API", "non_API")},
        "open_rate": {
            "AI_API": ai_open / n_pairs,
            "non_API": human_open / n_pairs,
        },
        "open_rate_wilson_95": {
            "AI_API": wilson(ai_open, n_pairs),
            "non_API": wilson(human_open, n_pairs),
        },
        "ai_minus_non_api_open_difference": difference,
        "ai_minus_non_api_bootstrap_95": [quantile(bootstrap_differences, 0.025), quantile(bootstrap_differences, 0.975)],
        "by_month": {
            month: {
                "pairs": len(pair_values),
                "AI_API_open": sum(ai for ai, _ in pair_values),
                "non_API_open": sum(human for _, human in pair_values),
            }
            for month, pair_values in sorted(pairs_by_month.items())
        },
        "top_hosts": {
            group: per_domain[group].most_common(15) for group in ("AI_API", "non_API")
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
