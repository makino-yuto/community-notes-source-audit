"""Deterministically copy pre-source first-correction claims for archive judging.

This performs no network or source-body reads. The AI-generated claims were
already logged before the uniform current-content pass. Their limitations are
retained; this script must not revise claims based on source outcomes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve()
PROJECT = HERE.parents[1]
PRIVATE = PROJECT.parent / "results"
ALIGNMENT_SHA256 = "282fbde3e1cfe8100d2baa9798fdb0c0aa169d349a4bfd91893d18b1e096d8b1"
KEY_SHA256 = "8246f299b02fe7feb4a6dd8cef29e9861e22517e16c5aa5a8ac568b2b5ef3e4f"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze(alignment_path: Path, key_path: Path, output_path: Path) -> dict:
    if output_path.exists():
        raise FileExistsError("Claims-only freeze already exists")
    if sha(alignment_path) != ALIGNMENT_SHA256 or sha(key_path) != KEY_SHA256:
        raise ValueError("Pre-source claim log or key hash changed")
    trials = [json.loads(line) for line in alignment_path.read_text(encoding="utf-8").splitlines()]
    key = json.loads(key_path.read_text(encoding="utf-8"))
    if len(trials) != 100 or len(key) != 100:
        raise ValueError("Expected exactly 100 frozen pair records")
    by_code = {row["code"]: row for row in key}
    if len(by_code) != 100 or len({row["code"] for row in trials}) != 100:
        raise ValueError("Duplicate pair code")
    if set(by_code) != {row["code"] for row in trials}:
        raise ValueError("Claim log and key differ in pair set")
    lines = []
    note_ids = set()
    for trial in sorted(trials, key=lambda row: row["code"]):
        if trial.get("valid") is not True:
            raise ValueError(f"Invalid frozen claim response for {trial['code']}")
        response = trial["response"]
        item = by_code[trial["code"]]
        for side in ("A", "B"):
            note_id = item["sides"][side]
            claim = response[f"main_claim_{side.lower()}"]
            if not isinstance(claim, str) or not claim.strip() or note_id in note_ids:
                raise ValueError("Blank claim or duplicate note ID")
            note_ids.add(note_id)
            other = response.get(f"other_material_claims_{side.lower()}", [])
            if not isinstance(other, list) or not all(isinstance(x, str) for x in other):
                raise ValueError("Malformed secondary claims")
            lines.append({
                "pair_code": trial["code"], "side": side, "note_id": note_id,
                "main_claim": claim, "other_material_claims": other,
                "source_trial_prompt_sha256": trial["prompt_sha256"],
                "source_alignment_sha256": ALIGNMENT_SHA256,
                "source_key_sha256": KEY_SHA256,
            })
    if len(lines) != 200 or len(note_ids) != 200:
        raise ValueError("Frozen claim count differs from 200 notes")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8", newline="\n") as stream:
        for row in lines:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    return {"claims": len(lines), "sha256": sha(output_path),
            "alignment_sha256": ALIGNMENT_SHA256, "key_sha256": KEY_SHA256}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alignment", type=Path, default=PRIVATE / "newwave_alignment_trials_PRIVATE.jsonl")
    parser.add_argument("--key", type=Path, default=PRIVATE / "newwave_semantic_key_PRIVATE.json")
    parser.add_argument("--output", type=Path, default=PRIVATE / "newwave_longitudinal_claims_PRIVATE.jsonl")
    args = parser.parse_args()
    print(json.dumps(freeze(args.alignment, args.key, args.output)), flush=True)


if __name__ == "__main__":
    main()
