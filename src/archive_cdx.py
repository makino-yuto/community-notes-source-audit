"""Internet Archive CDX coverage check on a fixed matched 100+100 cohort.

Run `--freeze-only` first, before looking up captures. The independent seed
selects 100 matched pairs from the already frozen 300+300 primary cohort,
without inspecting URL health or archive availability. `--run` then queries
only CDX capture metadata, at <= 1 request/second. A different CDX digest is
*not* evidence that a claim changed; a missing capture is *not* evidence that
the live page was absent. Captures may cover redirects, errors or unrelated
page revisions, and the Internet Archive has incomplete coverage.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import random
import subprocess
import time
import urllib.parse
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COHORT = ROOT / "results" / "cohort_2026-11-14.json"
STATUS_ZIP = ROOT / "data" / "noteStatusHistory-00000.zip"
FROZEN = ROOT / "results" / "archive_sample_2026-11-14.json"
RAW_OUT = ROOT / "results" / "archive_cdx_2026-11-14.jsonl"
CDX_ENDPOINT = "https://web.archive.org/cdx/search/cdx"
ARCHIVE_SEED = 20261116
ARCHIVE_PAIRS = 100
MAX_CAPTURE_ROWS = 100
SENSITIVE_QUERY_KEYS = {"access_token", "api_key", "apikey", "auth", "key", "password", "secret", "session", "sessionid", "sig", "signature", "token"}


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def utc_from_millis(value: str) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)


def cdx_date(value: datetime) -> str:
    return value.strftime("%Y%m%d")


def timestamp_datetime(value: str) -> datetime:
    return datetime.strptime(value[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


def status_anchors(note_ids: set[str]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    with zipfile.ZipFile(STATUS_ZIP) as archive:
        with archive.open("noteStatusHistory-00000.tsv") as raw:
            for row in csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8"), delimiter="\t"):
                if row["noteId"] not in note_ids:
                    continue
                first_status = row["firstNonNMRStatus"]
                if first_status == "CURRENTLY_RATED_HELPFUL" and row["timestampMillisOfFirstNonNMRStatus"]:
                    anchor = row["timestampMillisOfFirstNonNMRStatus"]
                    kind = "first_non_nmr_was_helpful"
                elif row["mostRecentNonNMRStatus"] == "CURRENTLY_RATED_HELPFUL" and row["timestampMillisOfLatestNonNMRStatus"]:
                    anchor = row["timestampMillisOfLatestNonNMRStatus"]
                    kind = "latest_helpful_proxy_not_first"
                else:
                    anchor = row["timestampMillisOfCurrentStatus"]
                    kind = "current_status_timestamp_proxy_not_first"
                found[row["noteId"]] = {
                    "first_non_nmr_status": first_status,
                    "helpful_anchor_millis": anchor,
                    "helpful_anchor_kind": kind,
                }
    if set(found) != note_ids:
        raise ValueError(f"Missing status rows for {len(note_ids - set(found))} selected notes")
    return found


def freeze_sample() -> dict:
    cohort = json.loads(COHORT.read_text(encoding="utf-8"))
    matched = cohort["matched"]
    if len(matched) != 600 or len({row["note_id"] for row in matched}) != 600:
        raise ValueError("Expected the frozen 600-note primary cohort")
    pairs = [matched[index:index + 2] for index in range(0, len(matched), 2)]
    if any(len(pair) != 2 or pair[0]["author_type"] != "AI_API" or pair[1]["author_type"] != "non_API" or pair[0]["month_utc"] != pair[1]["month_utc"] for pair in pairs):
        raise ValueError("Primary cohort no longer has 300 matched AI/non-API pairs")
    chosen_indices = sorted(random.Random(ARCHIVE_SEED).sample(range(len(pairs)), ARCHIVE_PAIRS))
    selected = [row for index in chosen_indices for row in pairs[index]]
    anchors = status_anchors({row["note_id"] for row in selected})
    sample = [
        {
            "note_id": row["note_id"],
            "author_type": row["author_type"],
            "month_utc": row["month_utc"],
            "selected_url": row["selected_url"],
            "created_at_millis": row["created_at_millis"],
            **anchors[row["note_id"]],
        }
        for row in selected
    ]
    document = {
        "parent_cohort_path": str(COHORT),
        "parent_cohort_sha256": file_sha256(COHORT),
        "archive_seed": ARCHIVE_SEED,
        "pairs": ARCHIVE_PAIRS,
        "selection_condition": "Uniform over 300 fixed month-matched pairs; no URL-health or archive-status filtering",
        "sample": sample,
    }
    if FROZEN.exists():
        existing = json.loads(FROZEN.read_text(encoding="utf-8"))
        if existing != document:
            raise ValueError("Frozen archive subsample differs from current inputs")
    else:
        FROZEN.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    return document


def safe_for_cdx(url: str) -> bool:
    parsed = urllib.parse.urlsplit(url)
    if parsed.username or parsed.password or len(url) > 2000:
        return False
    return not any(key.lower() in SENSITIVE_QUERY_KEYS for key, _ in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))


def query_cdx(url: str, start: datetime, end: datetime, *, latest: bool) -> dict:
    params = {
        "url": url,
        "matchType": "exact",
        "output": "json",
        "fl": "timestamp,original,mimetype,statuscode,digest,length",
        "filter": "statuscode:200",
        "from": cdx_date(start),
        "to": cdx_date(end),
        "limit": "-1" if latest else str(MAX_CAPTURE_ROWS),
    }
    if latest:
        params["fastLatest"] = "true"
    query_url = CDX_ENDPOINT + "?" + urllib.parse.urlencode(params)
    for retry in range(3):
        process = subprocess.run(
            ["curl.exe", "--silent", "--show-error", "--location", "--connect-timeout", "10", "--max-time", "30", "--write-out", "\n__HTTP_STATUS__=%{http_code}", query_url],
            capture_output=True, text=True, timeout=35,
        )
        payload, _, status = process.stdout.rpartition("\n__HTTP_STATUS__=")
        try:
            status_code = int(status)
        except ValueError:
            status_code = 0
        if status_code in (429, 500, 502, 503, 504) and retry < 2:
            time.sleep(2 ** (retry + 1))
            continue
        result = {
            "query_url": query_url,
            "http_status": status_code,
            "curl_exit": process.returncode,
            "queried_at_utc": datetime.now(timezone.utc).isoformat(),
            "window_start_utc": start.isoformat(),
            "window_end_utc": end.isoformat(),
        }
        if status_code == 200 and process.returncode == 0:
            try:
                rows = json.loads(payload)
                if rows:
                    header = rows[0]
                    captures = [dict(zip(header, row)) for row in rows[1:] if len(row) == len(header)]
                else:
                    captures = []
                result["captures"] = captures
                result["result_cap_hit"] = not latest and len(captures) >= MAX_CAPTURE_ROWS
            except (ValueError, TypeError):
                result["parse_error"] = True
        else:
            result["error_excerpt"] = process.stderr[:200]
        return result
    raise RuntimeError("Retry loop exited unexpectedly")


def run_queries(document: dict, max_notes: int | None) -> None:
    # One record per note. Existing records are reused on restart.
    done = set()
    if RAW_OUT.exists():
        for line in RAW_OUT.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["note_id"])
    selected = document["sample"][:max_notes] if max_notes else document["sample"]
    for note in selected:
        if note["note_id"] in done:
            continue
        if not safe_for_cdx(note["selected_url"]):
            row = {"note_id": note["note_id"], "skipped_sensitive_query": True}
        else:
            created = utc_from_millis(note["created_at_millis"])
            helpful = utc_from_millis(note["helpful_anchor_millis"])
            windows = {
                "creation_plus_minus_30d": (created - timedelta(days=30), created + timedelta(days=30), False),
                "helpful_plus_minus_30d": (helpful - timedelta(days=30), helpful + timedelta(days=30), False),
                "later_after_helpful_30d": (helpful + timedelta(days=30), datetime(2026, 11, 14, 23, 59, 59, tzinfo=timezone.utc), True),
            }
            observations = {}
            for name, (start, end, latest) in windows.items():
                if start > end:
                    observations[name] = {"not_yet_elapsed": True}
                    continue
                observations[name] = query_cdx(note["selected_url"], start, end, latest=latest)
                time.sleep(1.0)
            row = {"note_id": note["note_id"], "author_type": note["author_type"], "url": note["selected_url"], "helpful_anchor_kind": note["helpful_anchor_kind"], "windows": observations}
        with RAW_OUT.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-only", action="store_true", help="Freeze 100 matched pairs without CDX requests")
    parser.add_argument("--run", action="store_true", help="Query CDX for the frozen subsample")
    parser.add_argument("--max-notes", type=int, help="Optional bounded smoke run")
    args = parser.parse_args()
    if not args.freeze_only and not args.run:
        parser.error("Choose --freeze-only or --run")
    document = freeze_sample()
    print(f"Frozen {len(document['sample'])} notes from {document['pairs']} pairs at {FROZEN}")
    if args.run:
        run_queries(document, args.max_notes)
        print(f"CDX responses at {RAW_OUT}")


if __name__ == "__main__":
    main()
