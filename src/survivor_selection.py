"""Count currently Helpful status rows lacking Notes content in one snapshot.

This measures an observable missing-content fraction, not a deletion rate:
other data-publication and join issues could also explain a missing Notes row.
No note IDs or content are written to the aggregate output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from build_cohort import rows_from_zip


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    start = int(datetime(2025, 9, 1, tzinfo=timezone.utc).timestamp() * 1000)
    end = int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp() * 1000)
    status_path = DATA / "noteStatusHistory-00000.zip"
    note_paths = sorted(DATA.glob("notes-*.zip"))
    if len(note_paths) != 5:
        raise ValueError(f"Expected five Notes shards, found {len(note_paths)}")

    helpful_ids: set[str] = set()
    status_rows_window = 0
    for row in rows_from_zip(status_path):
        created = int(row["createdAtMillis"])
        if start <= created < end:
            status_rows_window += 1
            if row["currentStatus"] == "CURRENTLY_RATED_HELPFUL":
                helpful_ids.add(row["noteId"])

    present_ids: set[str] = set()
    for path in note_paths:
        for row in rows_from_zip(path):
            note_id = row["noteId"]
            if note_id in helpful_ids:
                present_ids.add(note_id)

    n_helpful = len(helpful_ids)
    n_present = len(present_ids)
    report = {
        "snapshot_date": "2026-11-14",
        "creation_window_utc": ["2025-09-01", "2026-09-01_exclusive"],
        "status_rows_created_in_window": status_rows_window,
        "current_helpful_status_rows_created_in_window": n_helpful,
        "current_helpful_with_notes_row": n_present,
        "current_helpful_missing_notes_row": n_helpful - n_present,
        "missing_fraction_of_current_helpful_status_rows": (n_helpful - n_present) / n_helpful,
        "status_zip_sha256": hashlib.sha256(status_path.read_bytes()).hexdigest(),
        "notes_zip_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in note_paths},
        "interpretation": "Missing Notes content among currently Helpful status-history rows; not a verified deletion count and not correctable for absent URL text.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "status_rows_created_in_window", "current_helpful_status_rows_created_in_window",
        "current_helpful_with_notes_row", "current_helpful_missing_notes_row",
        "missing_fraction_of_current_helpful_status_rows",
    )}, indent=2))


if __name__ == "__main__":
    main()
