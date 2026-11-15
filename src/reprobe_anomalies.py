"""Post-hoc GET re-probe of only frozen-sample URL syntax corrections.

The frozen cohort and primary probe JSONL are read-only inputs. This sidecar
keeps both URLs and both categories. A successful GET does not prove that the
page is the intended evidence; manual content review remains necessary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from probe_urls import probe


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATES = ROOT / "results" / "url_normalization_candidates.jsonl"
DEFAULT_OUTPUT = ROOT / "results" / "reprobed_anomalies_2026-11-15.jsonl"
KINDS = {
    "html_unescape",
    "restore_parenthesis",
    "bbc_remove_amp_suffix",
    "trim_cjk_trailing_prose",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    candidates = [json.loads(line) for line in args.candidates.read_text(encoding="utf-8").splitlines() if line.strip()]
    selected = [row for row in candidates if row.get("candidate_kind") in KINDS and row.get("candidate_url")]
    if len({row["note_id"] for row in selected}) != len(selected):
        raise ValueError("Duplicate note IDs among correction candidates")
    candidate_file_hash = sha256(args.candidates)

    # One GET sequence per distinct corrected URL, then attach the observation
    # to all notes that had selected the same original URL (e.g., BBC AMP).
    corrected_results = {}
    for index, corrected_url in enumerate(dict.fromkeys(row["candidate_url"] for row in selected), 1):
        corrected_results[corrected_url] = probe({"selected_url": corrected_url, "note_id": "shared_candidate"})
        print(f"Re-probed {index}/{len(set(row['candidate_url'] for row in selected))} distinct corrections", flush=True)
        time.sleep(0.5)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        for row in selected:
            corrected_probe = corrected_results[row["candidate_url"]]
            record = {
                "study_phase": "post_hoc_syntax_correction_sensitivity",
                "candidate_file_sha256": candidate_file_hash,
                "note_id": row["note_id"],
                "group": row["group"],
                "correction_kind": row["candidate_kind"],
                "original_url": row["original_url"],
                "original_primary_category": row["baseline_category"],
                "corrected_url": row["candidate_url"],
                "corrected_category": corrected_probe["category"],
                "corrected_probe": {k: v for k, v in corrected_probe.items() if k != "note_id"},
                "same_corrected_url_shared_by_notes": [x["note_id"] for x in selected if x["candidate_url"] == row["candidate_url"]],
                "semantic_validity_reviewed": False,
            }
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"Wrote {args.output} ({len(selected)} note-level rows)")


if __name__ == "__main__":
    main()
