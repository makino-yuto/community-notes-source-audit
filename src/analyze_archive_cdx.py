"""Analyze fixed Community Notes Wayback CDX metadata without claiming drift.

The CDX query uses calendar-day bounds and can return captures just outside
the intended UTC windows. This script applies the exact UTC bounds again.
It treats failed/capped queries as unknown, not as no archive. Indexed captures
are potential recovery leads; replay or source support is not verified here.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import random
import statistics
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
SAMPLE = RESULTS / "archive_sample_2026-11-14.json"
RAW = RESULTS / "archive_cdx_2026-11-14.jsonl"
PROBES = RESULTS / "probes_2026-11-15.jsonl"
JSON_OUT = RESULTS / "archive_analysis_2026-11-15.json"
MD_OUT = RESULTS / "archive_analysis_2026-11-15.md"
WINDOWS = ("creation_plus_minus_30d", "helpful_plus_minus_30d", "later_after_helpful_30d")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1_048_576), b""):
            h.update(block)
    return h.hexdigest()


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def capture_dt(value: str) -> datetime:
    return datetime.strptime(value[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


def wilson(k: int, n: int) -> list[float | None]:
    if n == 0:
        return [None, None]
    z = 1.959963984540054
    p = k / n
    denom = 1 + z*z/n
    center = (p + z*z/(2*n))/denom
    half = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/denom
    return [max(0.0, center-half), min(1.0, center+half)]


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def window_result(observation: dict | None) -> dict:
    if observation is None:
        return {"state": "missing_query", "captures": [], "cap_hit": False, "excluded_calendar_boundary": 0}
    if observation.get("not_yet_elapsed"):
        return {"state": "followup_not_elapsed", "captures": [], "cap_hit": False, "excluded_calendar_boundary": 0}
    if observation.get("http_status") != 200 or observation.get("curl_exit") != 0 or not isinstance(observation.get("captures"), list):
        return {"state": "query_error", "captures": [], "cap_hit": False, "excluded_calendar_boundary": 0}
    start, end = dt(observation["window_start_utc"]), dt(observation["window_end_utc"])
    captures = []
    excluded = 0
    for row in observation["captures"]:
        try:
            stamp = capture_dt(row["timestamp"])
        except (KeyError, ValueError, TypeError):
            excluded += 1
            continue
        if start <= stamp <= end and str(row.get("statuscode")) == "200":
            captures.append({"timestamp": stamp, "digest": row.get("digest"), "mimetype": row.get("mimetype"), "original": row.get("original")})
        else:
            excluded += 1
    cap_hit = bool(observation.get("result_cap_hit"))
    if captures:
        state = "capture_confirmed"
    elif cap_hit:
        state = "capped_unknown"
    else:
        state = "confirmed_none"
    return {"state": state, "captures": captures, "cap_hit": cap_hit, "excluded_calendar_boundary": excluded}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=Path, default=SAMPLE)
    parser.add_argument("--raw", type=Path, default=RAW)
    parser.add_argument("--probes", type=Path, default=PROBES)
    parser.add_argument("--json-output", type=Path, default=JSON_OUT)
    parser.add_argument("--md-output", type=Path, default=MD_OUT)
    args = parser.parse_args()

    document = json.loads(args.sample.read_text(encoding="utf-8"))
    sample = document["sample"]
    raw = read_jsonl(args.raw)
    probes = {str(row["note_id"]): row for row in read_jsonl(args.probes)}
    if len(sample) != 200 or len(raw) != 200:
        raise ValueError(f"Expected complete fixed 200-note archive sample: sample={len(sample)}, raw={len(raw)}")
    if len({row["note_id"] for row in sample}) != 200 or len({row["note_id"] for row in raw}) != 200:
        raise ValueError("Duplicate note IDs in archive sample or raw CDX records")
    if {row["note_id"] for row in sample} != {row["note_id"] for row in raw}:
        raise ValueError("CDX responses do not cover the fixed archive sample")
    if any(row["note_id"] not in probes for row in sample):
        raise ValueError("Missing primary probes for archive sample")
    if any(sample[i]["author_type"] != "AI_API" or sample[i+1]["author_type"] != "non_API" or sample[i]["month_utc"] != sample[i+1]["month_utc"] for i in range(0, 200, 2)):
        raise ValueError("Archive sample is not ordered as month-matched AI/non-API pairs")

    raw_by_id = {row["note_id"]: row for row in raw}
    cases = []
    query_http = collections.Counter()
    for note in sample:
        note_id = note["note_id"]
        response = raw_by_id[note_id]
        skipped = bool(response.get("skipped_sensitive_query"))
        windows = {}
        for name in WINDOWS:
            observation = response.get("windows", {}).get(name)
            windows[name] = window_result(observation)
            if observation is not None and "http_status" in observation:
                query_http[str(observation["http_status"])] += 1
        case = {
            "note_id": note_id,
            "group": note["author_type"],
            "month": note["month_utc"],
            "url": note["selected_url"],
            "anchor_kind": note["helpful_anchor_kind"],
            "primary_category": probes[note_id]["category"],
            "skipped_sensitive_query": skipped,
            "windows": windows,
        }
        cases.append(case)

    summary = {
        "analysis_kind": "CDX_200_capture_metadata_only_exact_UTC_window_filter",
        "sample_note_count": 200,
        "matched_pairs": 100,
        "input_sha256": {"sample": sha256(args.sample), "raw_cdx": sha256(args.raw), "primary_probes": sha256(args.probes)},
        "query_http_status_counts": dict(sorted(query_http.items())),
        "groups": {},
    }
    for group in ("AI_API", "non_API"):
        rows = [case for case in cases if case["group"] == group]
        if len(rows) != 100:
            raise ValueError(f"Expected 100 rows in {group}")
        counts = {}
        for name in WINDOWS:
            states = collections.Counter(case["windows"][name]["state"] for case in rows)
            states["excluded_calendar_boundary_rows"] = sum(case["windows"][name]["excluded_calendar_boundary"] for case in rows)
            states["cap_hit_queries"] = sum(case["windows"][name]["cap_hit"] for case in rows)
            counts[name] = dict(states)
        near = [case for case in rows if case["windows"]["helpful_plus_minus_30d"]["state"] == "capture_confirmed"]
        creation = [case for case in rows if case["windows"]["creation_plus_minus_30d"]["state"] == "capture_confirmed"]
        later = [case for case in rows if case["windows"]["later_after_helpful_30d"]["state"] == "capture_confirmed"]
        both = [case for case in rows if case in near and case in later]
        any_indexed = [case for case in rows if any(case["windows"][name]["state"] == "capture_confirmed" for name in WINDOWS)]
        non_open = [case for case in rows if case["primary_category"] != "open_candidate"]
        near_non_open = [case for case in non_open if case in near]
        any_non_open = [case for case in non_open if case in any_indexed]
        distinct_urls = len({case["url"] for case in rows})
        unique_any = len({case["url"] for case in any_indexed})
        anchor_kinds = collections.Counter(case["anchor_kind"] for case in rows)
        primary_categories = collections.Counter(case["primary_category"] for case in rows)
        near_by_category = collections.Counter(case["primary_category"] for case in near_non_open)
        any_by_category = collections.Counter(case["primary_category"] for case in any_non_open)
        month = collections.defaultdict(lambda: {"n": 0, "near": 0, "later": 0, "both": 0})
        for case in rows:
            m = month[case["month"]]
            m["n"] += 1
            m["near"] += case in near
            m["later"] += case in later
            m["both"] += case in both
        digest_pairs = []
        for case in both:
            early = case["windows"]["helpful_plus_minus_30d"]["captures"]
            late = case["windows"]["later_after_helpful_30d"]["captures"]
            # A nearest-to-anchor early capture is not necessarily before the
            # note's Helpful time. The latest later capture is ≥30 days later.
            anchor = datetime.fromtimestamp(int(next(n for n in sample if n["note_id"] == case["note_id"])["helpful_anchor_millis"])/1000, timezone.utc)
            early_one = min(early, key=lambda x: abs((x["timestamp"]-anchor).total_seconds()))
            late_one = max(late, key=lambda x: x["timestamp"])
            digest_pairs.append({"same": bool(early_one["digest"] and early_one["digest"] == late_one["digest"]), "has_both": bool(early_one["digest"] and late_one["digest"]), "mime_same": early_one["mimetype"] == late_one["mimetype"], "early_after_anchor": early_one["timestamp"] > anchor})
        summary["groups"][group] = {
            "n": len(rows),
            "distinct_selected_urls": distinct_urls,
            "repeated_selected_url_rows": len(rows)-distinct_urls,
            "distinct_urls_with_any_indexed_capture": unique_any,
            "anchor_kind_counts": dict(anchor_kinds),
            "primary_category_counts": dict(primary_categories),
            "window_states": counts,
            "creation_near_capture_notes": len(creation),
            "helpful_near_capture_notes": len(near),
            "helpful_near_wilson_95": wilson(len(near), len(rows)),
            "later_capture_notes": len(later),
            "both_helpful_near_and_later_notes": len(both),
            "both_wilson_95": wilson(len(both), len(rows)),
            "any_indexed_200_capture_notes": len(any_indexed),
            "primary_non_open_notes": len(non_open),
            "primary_non_open_with_helpful_near_indexed_200": len(near_non_open),
            "primary_non_open_with_any_indexed_200": len(any_non_open),
            "primary_non_open_near_by_category": dict(near_by_category),
            "primary_non_open_any_by_category": dict(any_by_category),
            "digest_pairs_with_early_and_later": len(digest_pairs),
            "digest_pairs_with_two_nonempty_digests": sum(pair["has_both"] for pair in digest_pairs),
            "selected_pair_same_digest": sum(pair["has_both"] and pair["same"] for pair in digest_pairs),
            "selected_pair_different_digest": sum(pair["has_both"] and not pair["same"] for pair in digest_pairs),
            "selected_pair_mime_differs": sum(not pair["mime_same"] for pair in digest_pairs),
            "selected_early_capture_after_anchor": sum(pair["early_after_anchor"] for pair in digest_pairs),
            "by_month": dict(sorted(month.items())),
        }

    # Pair bootstrap is descriptive only; shared URLs and author dependence
    # mean the nominal interval should not be interpreted as independent sites.
    rng = random.Random(20261118)
    pairs = [(cases[i], cases[i+1]) for i in range(0, 200, 2)]
    month_pairs = collections.defaultdict(list)
    for ai, human in pairs:
        month_pairs[ai["month"]].append((int(ai["windows"]["helpful_plus_minus_30d"]["state"] == "capture_confirmed"), int(human["windows"]["helpful_plus_minus_30d"]["state"] == "capture_confirmed")))
    diffs=[]
    for _ in range(10_000):
        total=0
        for values in month_pairs.values():
            for _ in values:
                ai_value, human_value = values[rng.randrange(len(values))]
                total += ai_value - human_value
        diffs.append(total/100)
    diffs.sort()
    summary["ai_minus_non_api_near_capture_difference"] = (summary["groups"]["AI_API"]["helpful_near_capture_notes"]-summary["groups"]["non_API"]["helpful_near_capture_notes"])/100
    summary["ai_minus_non_api_near_capture_bootstrap_95"] = [diffs[250], diffs[9750]]
    summary["caveats"] = [
        "CDX 200 capture metadata does not verify that a Wayback replay currently loads or supports the note's claim.",
        "A digest difference can reflect dynamic templates, ads, or navigation, and is not semantic evidence drift.",
        "All 200 selected anchors are first-non-NMR Helpful timestamps. The near-Helpful window is +/-30 days, and its selected capture may occur after Helpful.",
        "Calendar-day CDX query bounds were re-filtered to exact UTC windows here; capped queries without in-window captures remain unknown.",
        "The archive sample is 100 matched pairs from the 600-note primary sample, not a new independent population sample.",
    ]

    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    ai, hu = summary["groups"]["AI_API"], summary["groups"]["non_API"]
    lines = [
        "# Wayback CDX archive coverage: fixed 100 + 100 notes", "",
        "This report analyzes a seeded subsample of 100 month-matched AI API/non-API note pairs. It uses only CDX metadata for indexed HTTP-200 captures. It does **not** verify Wayback replay, source relevance, claim support, or semantic content drift.", "",
        f"Input SHA-256: archive sample `{summary['input_sha256']['sample']}`; CDX rows `{summary['input_sha256']['raw_cdx']}`; primary probes `{summary['input_sha256']['primary_probes']}`.", "",
        "| Measure | AI API | Non-API |", "| :-- | --: | --: |",
        f"| Distinct selected URLs | {ai['distinct_selected_urls']} | {hu['distinct_selected_urls']} |",
        f"| Indexed 200 capture within 30 days of creation | {ai['creation_near_capture_notes']}/100 | {hu['creation_near_capture_notes']}/100 |",
        f"| Indexed 200 capture within ±30 days of Helpful anchor | {ai['helpful_near_capture_notes']}/100 | {hu['helpful_near_capture_notes']}/100 |",
        f"| Indexed 200 capture ≥30 days later | {ai['later_capture_notes']}/100 | {hu['later_capture_notes']}/100 |",
        f"| Indexed captures in both near and later windows | {ai['both_helpful_near_and_later_notes']}/100 | {hu['both_helpful_near_and_later_notes']}/100 |",
        f"| Any indexed 200 capture in queried windows | {ai['any_indexed_200_capture_notes']}/100 | {hu['any_indexed_200_capture_notes']}/100 |",
        f"| Primary machine non-open notes | {ai['primary_non_open_notes']}/100 | {hu['primary_non_open_notes']}/100 |",
        f"| Non-open with near-Helpful archive index candidate | {ai['primary_non_open_with_helpful_near_indexed_200']} | {hu['primary_non_open_with_helpful_near_indexed_200']} |",
        f"| Non-open with any archive index candidate | {ai['primary_non_open_with_any_indexed_200']} | {hu['primary_non_open_with_any_indexed_200']} |",
        "", f"Near-Helpful capture difference (AI minus non-API): {100*summary['ai_minus_non_api_near_capture_difference']:+.1f} percentage points; month-stratified bootstrap 95% interval {100*summary['ai_minus_non_api_near_capture_bootstrap_95'][0]:+.1f} to {100*summary['ai_minus_non_api_near_capture_bootstrap_95'][1]:+.1f} points. This interval does not account for author or URL clustering.",
        "", "## Query completeness and timing", "",
    ]
    for group in ("AI_API", "non_API"):
        g=summary["groups"][group]
        lines += [f"### {group}", "", f"Helpful anchor kinds: {g['anchor_kind_counts']}.", ""]
        for name in WINDOWS:
            lines.append(f"- {name}: {g['window_states'][name]}")
        lines += ["", f"Among {g['digest_pairs_with_early_and_later']} notes with captures in both windows, {g['digest_pairs_with_two_nonempty_digests']} had two nonempty digests; {g['selected_pair_different_digest']} selected pairs differed and {g['selected_pair_same_digest']} matched. {g['selected_early_capture_after_anchor']} selected near captures were after the anchor. These are metadata counts, not content-drift verdicts.", ""]
    lines += ["## Interpretation", "", *[f"- {item}" for item in summary["caveats"]], "", "Potential archive rescue means only that CDX indexed a 200 capture for the URL. To claim a source was actually recoverable, replay and inspect the archived page, checking it is the intended content. Do not relabel primary URL results from this index alone.", ""]
    args.md_output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.md_output}")
    print(json.dumps({"AI_API": {k: ai[k] for k in ("helpful_near_capture_notes", "later_capture_notes", "both_helpful_near_and_later_notes", "primary_non_open_with_helpful_near_indexed_200")}, "non_API": {k: hu[k] for k in ("helpful_near_capture_notes", "later_capture_notes", "both_helpful_near_and_later_notes", "primary_non_open_with_helpful_near_indexed_200")}}, indent=2))


if __name__ == "__main__":
    main()
