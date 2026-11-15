"""V2 feasibility census with an auditable syntax-corrected URL extractor.

This reuses the primary study's strict eligibility but keeps every external
URL and the underlying tweetId for design analysis. No network probes are run.
The private candidate file contains public note text, IDs, and URLs and must
not be published without separate privacy/dual-use review.
"""

from __future__ import annotations

import collections
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import build_cohort as bc
import revision_extract_urls as ex


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
PUBLIC = RESULTS / "revision_samepost_feasibility_v2.json"
PRIVATE = RESULTS / "revision_samepost_candidates_v2_PRIVATE.jsonl"
GROUPS = ("AI_API", "non_API")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pct(values: list[int], p: float) -> int | None:
    if not values:
        return None
    x = sorted(values)
    return x[round(p * (len(x) - 1))]


def main() -> None:
    enrollment = {}
    for row in bc.rows_from_zip(bc.DATA / "userEnrollment-00000.zip"):
        enrollment[row["participantId"]] = (
            row["enrollmentState"],
            int(row["timestampOfLastStateChange"] or 0),
        )
    helpful = set()
    for row in bc.rows_from_zip(bc.DATA / "noteStatusHistory-00000.zip"):
        if row["currentStatus"] == "CURRENTLY_RATED_HELPFUL" and "2025-09" <= bc.month_from_millis(row["createdAtMillis"]) <= "2026-08":
            helpful.add(row["noteId"])

    by_post: dict[str, dict[str, list[dict]]] = collections.defaultdict(lambda: {g: [] for g in GROUPS})
    seen = set()
    n = collections.Counter()
    flag_counts = collections.Counter()
    rejection_counts = collections.Counter()
    for path in sorted(bc.DATA.glob("notes-*.zip")):
        for row in bc.rows_from_zip(path):
            note_id = row["noteId"]
            if note_id not in helpful or note_id in seen:
                continue
            seen.add(note_id)
            if row.get("isCollaborativeNote", "0") == "1":
                continue
            links, rejected = ex.extract_urls(row["summary"])
            if not links:
                continue
            author_id = row["noteAuthorParticipantId"]
            state = enrollment.get(author_id)
            if state is None or state[1] > int(row["createdAtMillis"]):
                continue
            flag_counts.update(flag for link in links for flag in link["flags"])
            rejection_counts.update(link["rejection_reason"] for link in rejected)
            group = "AI_API" if state[0] == "apiEarnedIn" else "non_API"
            post_id = row["tweetId"]
            if not post_id:
                continue
            n[group] += 1
            by_post[post_id][group].append({
                "note_id": note_id,
                "post_id": post_id,
                "group": group,
                "author_id": author_id,
                "created_at_millis": int(row["createdAtMillis"]),
                "month_utc": bc.month_from_millis(row["createdAtMillis"]),
                "external_urls": links,
                "rejected_url_candidates": rejected,
                "summary": row["summary"],
                "classification": row.get("classification"),
                "is_media_note": row.get("isMediaNote") == "1",
            })

    both = {p: g for p, g in by_post.items() if g["AI_API"] and g["non_API"]}
    note_count_on_both = {g: sum(len(v[g]) for v in both.values()) for g in GROUPS}
    pairs = []
    all_pairs_count = 0
    for post_id, groups in sorted(both.items()):
        ais = sorted(groups["AI_API"], key=lambda r: (r["created_at_millis"], r["note_id"]))
        nons = sorted(groups["non_API"], key=lambda r: (r["created_at_millis"], r["note_id"]))
        all_pairs_count += len(ais) * len(nons)
        # Design-only deterministic pair, fixed without inspecting URLs or
        # outcomes: first created note from each group on this post.
        ai, non = ais[0], nons[0]
        hosts = [{(urlsplit(u["normalized_url"]).hostname or "").lower().removeprefix("www.") for u in r["external_urls"]} for r in (ai, non)]
        pairs.append({
            "post_id": post_id,
            "ai": ai,
            "non_api": non,
            "all_helpful_note_counts_on_post": {g: len(groups[g]) for g in GROUPS},
            "absolute_creation_gap_hours": abs(ai["created_at_millis"] - non["created_at_millis"]) / 3_600_000,
            "url_overlap_exact": bool({u["normalized_url"] for u in ai["external_urls"]} & {u["normalized_url"] for u in non["external_urls"]}),
            "host_overlap_exact": bool(hosts[0] & hosts[1]),
        })
    PRIVATE.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in pairs), encoding="utf-8")
    gaps = [int(round(row["absolute_creation_gap_hours"])) for row in pairs]
    result = {
        "analysis_kind": "same_post_design_feasibility_no_live_probes",
        "snapshot_date": bc.SNAPSHOT,
        "eligibility": "Same non-URL eligibility as build_cohort.py: current Helpful, Sep2025-Aug2026, available noncollaborative note text, observed enrollment not changed after creation; at least one external URL under the revised parser.",
        "source_manifest_sha256": digest(RESULTS / "source_manifest_2026-11-14.json"),
        "extractor_sha256": digest(ROOT / "src" / "revision_extract_urls.py"),
        "script_sha256": digest(Path(__file__)),
        "private_candidates_sha256": digest(PRIVATE),
        "eligible_notes_with_nonempty_post_id": dict(n),
        "url_normalization_flags_among_eligible_notes": dict(flag_counts),
        "rejected_url_reasons_among_eligible_notes": dict(rejection_counts),
        "eligible_posts_with_any_note": len(by_post),
        "eligible_posts_with_both_groups": len(both),
        "all_cross_group_note_pairs_on_both_posts": all_pairs_count,
        "eligible_helpful_notes_on_both_posts": note_count_on_both,
        "deterministic_first_each_pair_count": len(pairs),
        "first_each_pair_creation_gap_hours": {"median": pct(gaps, .5), "p90": pct(gaps, .9), "max": max(gaps) if gaps else None},
        "first_each_pair_url_count": {
            g: dict(collections.Counter(len(row["ai" if g == "AI_API" else "non_api"]["external_urls"]) for row in pairs))
            for g in GROUPS
        },
        "first_each_pair_exact_url_overlap_posts": sum(row["url_overlap_exact"] for row in pairs),
        "first_each_pair_exact_host_overlap_posts": sum(row["host_overlap_exact"] for row in pairs),
        "first_each_pair_distinct_authors": {
            "AI_API": len({row["ai"]["author_id"] for row in pairs}),
            "non_API": len({row["non_api"]["author_id"] for row in pairs}),
        },
        "first_each_pair_same_month": sum(row["ai"]["month_utc"] == row["non_api"]["month_utc"] for row in pairs),
        "private_candidate_file": PRIVATE.name,
        "caveats": [
            "Matching the post controls its identifier, not note proposition, timing, source role, author/operator, or selection into Helpful status.",
            "Selecting first in each group is determined before any retrieval outcomes but can differ in note ages.",
            "URL extraction fixes known syntax errors but its punctuation heuristic remains ambiguous; raw spans and flags are preserved for review.",
            "One URL may be non-evidentiary, and neither a link count nor same-host count establishes independent evidentiary support.",
            "No claim that non_API means human-written; no causal AI effect follows.",
        ],
    }
    PUBLIC.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
