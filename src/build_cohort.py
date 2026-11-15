"""Build month-matched public Community Notes AI/human source-link cohorts.

Source: X Community Notes cumulative 2026-11-14 snapshot. This script reads
the official ZIP files without extracting them, preserving original IDs and
timestamps. `apiEarnedIn` in the official User Enrollment table identifies AI
Note Writer API accounts; other observed enrollment states are classified as
non-API for this operational comparison. This does not prove human authorship.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import json
import random
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RESULTS = ROOT / "results"
SNAPSHOT = "2026-11-14"
BASE_URL = "https://ton.twimg.com/birdwatch-public-data/2026/11/14"
SEED = 20261115
URL_RE = re.compile(r"https?://[^\s<>\]\[\(\)\"']+")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def rows_from_zip(path: Path):
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.endswith(".tsv")]
        if len(members) != 1:
            raise ValueError(f"Expected one TSV in {path}")
        with archive.open(members[0]) as raw:
            yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8"), delimiter="\t")


def month_from_millis(value: str) -> str:
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).strftime("%Y-%m")


def urls(value: str) -> list[str]:
    return [item.rstrip(".,;!?") for item in URL_RE.findall(value)]


def external_evidence_urls(value: str) -> tuple[list[str], collections.Counter]:
    kept = []
    excluded = collections.Counter()
    for item in urls(value):
        try:
            parsed = urlsplit(item)
            host = (parsed.hostname or "").lower().rstrip(".")
            ascii_host = host.encode("idna").decode("ascii")
            labels = ascii_host.split(".")
            if (
                parsed.scheme not in ("http", "https")
                or parsed.username is not None
                or len(labels) < 2
                or any(not re.fullmatch(r"[a-z0-9-]{1,63}", label) or label.startswith("-") or label.endswith("-") for label in labels)
            ):
                excluded["malformed"] += 1
                continue
            if (
                ascii_host in {"x.com", "twitter.com", "t.co", "twimg.com", "localhost"}
                or ascii_host.endswith((".x.com", ".twitter.com", ".twimg.com", ".local", ".internal", ".test", ".example"))
            ):
                excluded["platform_or_internal"] += 1
                continue
            if all(label.isdigit() for label in labels):
                excluded["ip_address"] += 1
                continue
            kept.append(item)
        except (UnicodeError, ValueError):
            excluded["malformed"] += 1
    return kept, excluded


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2025-09", help="Inclusive UTC month, YYYY-MM")
    parser.add_argument("--through", default="2026-08", help="Inclusive UTC month, YYYY-MM")
    parser.add_argument("--target-per-group", type=int, default=300)
    args = parser.parse_args()

    enrollment_path = DATA / "userEnrollment-00000.zip"
    status_path = DATA / "noteStatusHistory-00000.zip"
    note_paths = sorted(DATA.glob("notes-*.zip"))
    if not note_paths:
        raise FileNotFoundError("No official notes ZIP files found")

    enrollment: dict[str, tuple[str, int]] = {}
    enrollment_states = collections.Counter()
    for row in rows_from_zip(enrollment_path):
        enrollment_states[row["enrollmentState"]] += 1
        last_change = int(row["timestampOfLastStateChange"]) if row["timestampOfLastStateChange"] else 0
        enrollment[row["participantId"]] = (row["enrollmentState"], last_change)

    notes: dict[str, dict] = {}
    all_note_rows = 0
    excluded_collab = 0
    excluded_missing_enrollment = 0
    excluded_later_state_change = 0
    excluded_no_external_url = 0
    excluded_url_reasons = collections.Counter()
    for path in note_paths:
        for row in rows_from_zip(path):
            all_note_rows += 1
            month = month_from_millis(row["createdAtMillis"])
            if not args.since <= month <= args.through:
                continue
            if row.get("isCollaborativeNote", "0") == "1":
                excluded_collab += 1
                continue
            found, url_exclusions = external_evidence_urls(row["summary"])
            excluded_url_reasons.update(url_exclusions)
            if not found:
                excluded_no_external_url += 1
                continue
            author_id = row["noteAuthorParticipantId"]
            author_enrollment = enrollment.get(author_id)
            if author_enrollment is None:
                excluded_missing_enrollment += 1
                continue
            author_state, last_change = author_enrollment
            if last_change > int(row["createdAtMillis"]):
                excluded_later_state_change += 1
                continue
            # Select exactly one link per note, independent of shard/row order.
            selector = hashlib.sha256(f"{SEED}:{row['noteId']}".encode()).digest()
            chosen = found[int.from_bytes(selector, "big") % len(found)]
            notes[row["noteId"]] = {
                "note_id": row["noteId"],
                "author_id": author_id,
                "author_enrollment_state": author_state,
                "author_last_state_change_millis": last_change,
                "created_at_millis": row["createdAtMillis"],
                "month_utc": month,
                "selected_url": chosen,
                "external_url_count": len(found),
                "raw_url_count": len(urls(row["summary"])),
                "trustworthy_sources_self_report": row.get("trustworthySources", ""),
                "summary": row["summary"],
                "note_shard": path.name,
            }

    scored = 0
    helpful = []
    for row in rows_from_zip(status_path):
        note = notes.get(row["noteId"])
        if note is None:
            continue
        scored += 1
        if row["currentStatus"] != "CURRENTLY_RATED_HELPFUL":
            continue
        note = dict(note)
        note["current_status"] = row["currentStatus"]
        note["status_at_millis"] = row["timestampMillisOfCurrentStatus"]
        note["author_type"] = "AI_API" if note["author_enrollment_state"] == "apiEarnedIn" else "non_API"
        helpful.append(note)

    grouped = collections.defaultdict(lambda: {"AI_API": [], "non_API": []})
    for note in helpful:
        grouped[note["month_utc"]][note["author_type"]].append(note)

    rng = random.Random(SEED)
    month_pairs = []
    counts = {}
    for month in sorted(grouped):
        ai = sorted(grouped[month]["AI_API"], key=lambda row: row["note_id"])
        human = sorted(grouped[month]["non_API"], key=lambda row: row["note_id"])
        take = min(len(ai), len(human))
        if take:
            selected_ai = rng.sample(ai, take)
            selected_human = rng.sample(human, take)
            month_pairs.extend(zip(selected_ai, selected_human))
        counts[month] = {"AI_API": len(ai), "non_API": len(human), "possible_pairs": take}
    selected_pairs = rng.sample(month_pairs, min(args.target_per_group, len(month_pairs)))
    matched = [row for pair in selected_pairs for row in pair]
    selected_by_month = collections.Counter(pair[0]["month_utc"] for pair in selected_pairs)
    for month in counts:
        counts[month]["selected_pairs"] = selected_by_month[month]

    manifest = {
        "source": "X Community Notes public cumulative data",
        "documentation_url": "https://github.com/twitter/communitynotes/blob/main/documentation/under-the-hood/download-data.md",
        "snapshot_date": SNAPSHOT,
        "files": [
            {"name": path.name, "url": f"{BASE_URL}/{path.name.split('-')[0]}/{path.name}", "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in [*note_paths, status_path, enrollment_path]
        ],
        "user_enrollment_ai_definition": "enrollmentState == apiEarnedIn (current snapshot state)",
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "source_manifest_2026-11-14.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    cohort = {
        "snapshot_date": SNAPSHOT,
        "since_month_utc": args.since,
        "through_month_utc": args.through,
        "seed": SEED,
        "target_per_group": args.target_per_group,
        "notes_shards": [path.name for path in note_paths],
        "all_note_rows_in_shards": all_note_rows,
        "excluded_collaborative_recent": excluded_collab,
        "excluded_no_external_url_recent": excluded_no_external_url,
        "excluded_url_reasons_recent": dict(excluded_url_reasons),
        "recent_noncollaborative_with_url": len(notes),
        "recent_scored_with_url": scored,
        "current_helpful_with_url": len(helpful),
        "ai_api_author_count": sum(state == "apiEarnedIn" for state, _ in enrollment.values()),
        "enrollment_states": dict(enrollment_states),
        "excluded_missing_enrollment_recent": excluded_missing_enrollment,
        "excluded_later_state_change_recent": excluded_later_state_change,
        "by_month": counts,
        "matched_size": len(matched),
        "matched": matched,
    }
    (RESULTS / "cohort_2026-11-14.json").write_text(json.dumps(cohort, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in cohort.items() if k != "matched"}, indent=2))


if __name__ == "__main__":
    main()
