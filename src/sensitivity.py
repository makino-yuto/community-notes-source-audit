"""Descriptive sensitivity analyses for the frozen Community Notes URL cohort.

This is secondary analysis. It neither probes URLs nor changes the primary
month-matched, note-weighted estimator in analyze_probes.py. In particular,
one-per-author draws and author-cluster bootstrap intervals answer different
questions from the primary matched-pair bootstrap.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import math
import random
from pathlib import Path
from urllib.parse import urlsplit


GROUPS = ("AI_API", "non_API")
ALLOWED = {"open_candidate", "access_barrier", "gone_candidate", "transient_uncertain"}
SOCIAL_VIDEO = (
    "youtube.com", "youtu.be", "instagram.com", "facebook.com", "fb.com",
    "tiktok.com", "reddit.com", "pinterest.com", "threads.net", "linkedin.com",
    "t.me", "telegram.org", "weibo.com", "bilibili.com", "vimeo.com",
)
WIKI = ("wikipedia.org", "wikimedia.org", "wikidata.org", "wiktionary.org")


def suffix_match(host: str, suffixes: tuple[str, ...]) -> bool:
    return any(host == suffix or host.endswith("." + suffix) for suffix in suffixes)


def domain_class(host: str) -> str:
    """Fixed, coarse classes; unclassified sites remain `other_public_web`."""
    host = host.lower().removeprefix("www.")
    if suffix_match(host, SOCIAL_VIDEO):
        return "social_or_video"
    if suffix_match(host, WIKI):
        return "wiki_reference"
    labels = host.split(".")
    if any(label in {"gov", "gob", "go", "edu", "ac"} for label in labels[:-1]):
        return "government_or_education"
    return "other_public_web"


def age_band(days: int) -> str:
    if days < 120:
        return "0-119_days"
    if days < 240:
        return "120-239_days"
    return "240_plus_days"


def wilson(successes: int, n: int) -> list[float] | None:
    if not n:
        return None
    z = 1.959963984540054
    p = successes / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    radius = z / denominator * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [max(0.0, center - radius), min(1.0, center + radius)]


def percentile(sorted_values: list[float], fraction: float) -> float:
    position = fraction * (len(sorted_values) - 1)
    lo = math.floor(position)
    hi = math.ceil(position)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (position - lo)


def interval(values: list[float]) -> list[float]:
    ordered = sorted(values)
    return [percentile(ordered, 0.025), percentile(ordered, 0.975)]


def category_rate(rows: list[dict]) -> dict:
    counts = collections.Counter(row["category"] for row in rows)
    n = len(rows)
    opened = counts["open_candidate"]
    return {
        "n": n,
        "open_n": opened,
        "open_rate": opened / n if n else None,
        "open_wilson_95": wilson(opened, n),
        "categories": {category: counts[category] for category in sorted(ALLOWED)},
    }


def paired_stratum(rows: list[dict]) -> dict:
    result = {group: category_rate([row for row in rows if row["group"] == group]) for group in GROUPS}
    if all(result[group]["n"] for group in GROUPS):
        result["AI_minus_non_API_open_difference"] = (
            result["AI_API"]["open_rate"] - result["non_API"]["open_rate"]
        )
    else:
        result["AI_minus_non_API_open_difference"] = None
    return result


def load_rows(cohort_path: Path, probes_path: Path, overrides_path: Path | None) -> tuple[dict, list[dict], int]:
    cohort = json.loads(cohort_path.read_text(encoding="utf-8"))
    matched = cohort["matched"]
    if len(matched) != 600 or len(matched) % 2:
        raise ValueError(f"Expected the frozen 600-note paired cohort, found {len(matched)}")
    probe_rows = {}
    for line in probes_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        note_id = str(row["note_id"])
        if note_id in probe_rows:
            raise ValueError(f"Duplicate probe note ID: {note_id}")
        probe_rows[note_id] = row
    ids = {str(row["note_id"]) for row in matched}
    if len(ids) != len(matched) or set(probe_rows) != ids:
        raise ValueError(f"Probe coverage mismatch: missing={len(ids-set(probe_rows))}, extra={len(set(probe_rows)-ids)}")
    overrides = json.loads(overrides_path.read_text(encoding="utf-8")) if overrides_path else {}
    if set(overrides) - ids:
        raise ValueError("An override note ID is outside the frozen cohort")
    snapshot_day = dt.date.fromisoformat(cohort["snapshot_date"])
    result = []
    for index in range(0, len(matched), 2):
        ai, non_api = matched[index:index + 2]
        if (ai["author_type"], non_api["author_type"]) != GROUPS or ai["month_utc"] != non_api["month_utc"]:
            raise ValueError(f"Pair {index//2} is not an AI/non-API creation-month pair")
        for source in (ai, non_api):
            note_id = str(source["note_id"])
            probe = probe_rows[note_id]
            if probe.get("url") != source["selected_url"]:
                raise ValueError(f"Probe URL mismatch or missing URL for note {note_id}")
            category = overrides.get(note_id, {}).get("final_category", probe["category"])
            if category not in ALLOWED:
                raise ValueError(f"Unknown category for note {note_id}: {category}")
            author_id = source.get("author_id")
            if not author_id:
                raise ValueError(f"Missing pseudonymous author ID for note {note_id}")
            host = (urlsplit(source["selected_url"]).hostname or "").lower()
            if not host:
                raise ValueError(f"Missing hostname for note {note_id}")
            created_day = dt.datetime.fromtimestamp(
                int(source["created_at_millis"]) / 1000, tz=dt.timezone.utc
            ).date()
            age_days = (snapshot_day - created_day).days
            if age_days < 0:
                raise ValueError(f"Note {note_id} was created after snapshot")
            result.append({
                "group": source["author_type"],
                "author": author_id,
                "month": source["month_utc"],
                "host": host,
                "domain_class": domain_class(host),
                "age_days": age_days,
                "age_band": age_band(age_days),
                "category": category,
                "open": int(category == "open_candidate"),
            })
    return cohort, result, len(overrides)


def author_sensitivity(rows: list[dict], draws: int, seed: int) -> dict:
    if draws < 100:
        raise ValueError("Use at least 100 resamples")
    clusters: dict[str, dict[str, list[int]]] = {group: collections.defaultdict(list) for group in GROUPS}
    for row in rows:
        clusters[row["group"]][row["author"]].append(row["open"])
    values = {group: list(clusters[group].values()) for group in GROUPS}
    author_counts = {group: len(values[group]) for group in GROUPS}
    max_notes = {group: max(map(len, values[group])) for group in GROUPS}
    observed_note_rates = {group: sum(map(sum, values[group])) / sum(map(len, values[group])) for group in GROUPS}
    author_equal_rates = {
        group: sum(sum(author) / len(author) for author in values[group]) / len(values[group])
        for group in GROUPS
    }
    leave_one_out = {}
    for group in GROUPS:
        total_open = sum(map(sum, values[group]))
        total_notes = sum(map(len, values[group]))
        differences = []
        for author in values[group]:
            remaining = (total_open - sum(author)) / (total_notes - len(author))
            if group == "AI_API":
                differences.append(remaining - observed_note_rates["non_API"])
            else:
                differences.append(observed_note_rates["AI_API"] - remaining)
        leave_one_out[group] = {
            "AI_minus_non_API_difference_range": [min(differences), max(differences)],
            "number_of_omissions_reversing_primary_sign": sum(
                difference * (observed_note_rates["AI_API"] - observed_note_rates["non_API"]) < 0
                for difference in differences
            ),
            "omissions_evaluated": len(differences),
        }
    rng = random.Random(seed)
    one_each: dict[str, list[float]] = {group: [] for group in GROUPS}
    cluster_note_weighted: dict[str, list[float]] = {group: [] for group in GROUPS}
    cluster_author_equal: dict[str, list[float]] = {group: [] for group in GROUPS}
    for _ in range(draws):
        for group in GROUPS:
            authors = values[group]
            one_each[group].append(sum(rng.choice(author) for author in authors) / len(authors))
            sampled_authors = [authors[rng.randrange(len(authors))] for _ in authors]
            cluster_note_weighted[group].append(
                sum(map(sum, sampled_authors)) / sum(map(len, sampled_authors))
            )
            cluster_author_equal[group].append(
                sum(sum(author) / len(author) for author in sampled_authors) / len(sampled_authors)
            )

    def summarize_replicates(replicates: dict[str, list[float]], point_rates: dict[str, float], label: str) -> dict:
        differences = [a - b for a, b in zip(replicates["AI_API"], replicates["non_API"])]
        return {
            "interpretation": label,
            "point_rates": point_rates,
            "point_AI_minus_non_API": point_rates["AI_API"] - point_rates["non_API"],
            "replicate_95_range_by_group": {group: interval(replicates[group]) for group in GROUPS},
            "replicate_95_range_difference": interval(differences),
        }

    return {
        "author_count": author_counts,
        "max_notes_per_author": max_notes,
        "top_three_author_note_share": {
            group: sum(sorted(map(len, values[group]), reverse=True)[:3]) / sum(map(len, values[group]))
            for group in GROUPS
        },
        "leave_one_author_out_note_weighted": leave_one_out,
        "one_note_per_fixed_author": summarize_replicates(
            one_each, author_equal_rates,
            "95% range across repeat random note choices for the observed authors; not a population confidence interval",
        ),
        "author_cluster_bootstrap_note_weighted": summarize_replicates(
            cluster_note_weighted, observed_note_rates,
            "95% percentile interval after resampling observed author clusters independently by group; not the primary matched-pair CI",
        ),
        "author_cluster_bootstrap_author_equal": summarize_replicates(
            cluster_author_equal, author_equal_rates,
            "95% percentile interval for equally weighted author-level open rates; not the primary matched-pair CI",
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--probes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overrides", type=Path, help="Same note-ID to final_category JSON used in primary analysis")
    parser.add_argument("--draws", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20261115)
    args = parser.parse_args()

    cohort, rows, override_count = load_rows(args.cohort, args.probes, args.overrides)
    by_group = {group: [row for row in rows if row["group"] == group] for group in GROUPS}
    hosts = {group: collections.Counter(row["host"] for row in by_group[group]) for group in GROUPS}
    shared_hosts = sorted(
        [host for host in set(hosts["AI_API"]) & set(hosts["non_API"])
         if hosts["AI_API"][host] >= 3 and hosts["non_API"][host] >= 3],
        key=lambda host: -(hosts["AI_API"][host] + hosts["non_API"][host]),
    )
    months = sorted({row["month"] for row in rows})
    domain_classes = ("social_or_video", "wiki_reference", "government_or_education", "other_public_web")
    bands = ("0-119_days", "120-239_days", "240_plus_days")
    report = {
        "analysis_kind": "secondary_descriptive_sensitivity_not_causal",
        "snapshot_date": cohort["snapshot_date"],
        "cohort_sha256": hashlib.sha256(args.cohort.read_bytes()).hexdigest(),
        "probes_sha256": hashlib.sha256(args.probes.read_bytes()).hexdigest(),
        "overrides_sha256": hashlib.sha256(args.overrides.read_bytes()).hexdigest() if args.overrides else None,
        "overrides_count": override_count,
        "resampling": {"draws": args.draws, "seed": args.seed},
        "overall": paired_stratum(rows),
        "author_sensitivity": author_sensitivity(rows, args.draws, args.seed),
        "domain_class_rates": {
            domain: paired_stratum([row for row in rows if row["domain_class"] == domain])
            for domain in domain_classes
        },
        "domain_composition": {
            group: {
                "unique_hosts": len(hosts[group]),
                "largest_host_note_count": max(hosts[group].values()),
                "top_five_host_share": sum(n for _, n in hosts[group].most_common(5)) / len(by_group[group]),
            }
            for group in GROUPS
        },
        "shared_exact_host_rates_min_three_each": {
            host: paired_stratum([row for row in rows if row["host"] == host]) for host in shared_hosts
        },
        "month_rates": {
            month: paired_stratum([row for row in rows if row["month"] == month]) for month in months
        },
        "predeclared_period_rates": {
            "before_2026_02": paired_stratum([row for row in rows if row["month"] < "2026-02"]),
            "2026_02_or_later": paired_stratum([row for row in rows if row["month"] >= "2026-02"]),
        },
        "age_band_rates": {
            band: paired_stratum([row for row in rows if row["age_band"] == band]) for band in bands
        },
        "age_definition": "UTC calendar days from note creation to the fixed dataset snapshot date; 0-119, 120-239, and 240+ day bands",
        "uncertain_outcome_bounds": {
            group: {
                "lower_confirmed_open_rate": sum(row["category"] == "open_candidate" for row in by_group[group]) / len(by_group[group]),
                "upper_if_all_uncertain_open_rate": sum(row["category"] in {"open_candidate", "transient_uncertain"} for row in by_group[group]) / len(by_group[group]),
            }
            for group in GROUPS
        },
        "caveats": [
            "AI_API notes in this cohort were produced by only 20 pseudonymous authors; note-level intervals can overstate independent information. Actual count is reported above.",
            "non_API means observed non-API enrolled states, not verified human authorship.",
            "One-per-author draws do not preserve creation-month matching and are a sensitivity check, not a replacement primary estimate.",
            "Author-cluster bootstrap treats observed authors as resampling units; the small AI author count makes its interval unstable and limits population generalization.",
            "Domain classes are coarse fixed host rules, not content categories; differences within domain strata remain observational and potentially sparse.",
            "Open/readable means machine-observable retrieval, not source reliability, factual truth, or claim relevance. Access barriers may hide valid sources.",
            "No multiple-comparison significance tests are performed; month, age, and domain results are descriptive.",
        ],
    }
    report["uncertain_outcome_bounds"]["AI_minus_non_API_possible_range"] = [
        report["uncertain_outcome_bounds"]["AI_API"]["lower_confirmed_open_rate"]
        - report["uncertain_outcome_bounds"]["non_API"]["upper_if_all_uncertain_open_rate"],
        report["uncertain_outcome_bounds"]["AI_API"]["upper_if_all_uncertain_open_rate"]
        - report["uncertain_outcome_bounds"]["non_API"]["lower_confirmed_open_rate"],
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}; {len(rows)} notes, {args.draws} resamples")


if __name__ == "__main__":
    main()
