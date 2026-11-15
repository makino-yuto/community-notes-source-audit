"""Freeze a cohort-blinded source-role audit sample without reading URL probes.

Run from any directory with Python 3.11+:
    python src/build_role_sample.py

The public-style blind packet contains note text and its preselected URL, but no
author ID, author type, or probe outcome. Keep the mapping key away from reviewers
until coding is complete. This script never fetches URLs.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COHORT = ROOT / "results" / "cohort_2026-11-14.json"
FROZEN = ROOT / "results" / "freeze_manifest.json"
BLIND = ROOT / "results" / "role_sample_blinded.jsonl"
KEY = ROOT / "results" / "role_sample_key.json"
MANIFEST = ROOT / "results" / "role_sample_freeze_manifest.json"
SEED = 20261116
PAIRS = 50
GROUPS = ("AI_API", "non_API")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_frozen_cohort() -> None:
    manifest = json.loads(FROZEN.read_text(encoding="utf-8"))
    reference = next(
        (item for item in manifest["files"] if item["path"].replace("\\", "/").endswith("results/cohort_2026-11-14.json")),
        None,
    )
    if reference is None:
        raise RuntimeError("Frozen cohort entry missing from manifest")
    observed = sha256_file(COHORT)
    if observed != reference["sha256"]:
        raise RuntimeError(f"Frozen cohort hash changed: {observed}")


def quota_by_month(rows: list[dict], n: int) -> dict[str, int]:
    counts = Counter(row["month_utc"] for row in rows if row["author_type"] == GROUPS[0])
    total = sum(counts.values())
    if total == 0:
        raise RuntimeError("No AI cohort rows")
    exact = {month: n * count / total for month, count in counts.items()}
    quota = {month: int(value) for month, value in exact.items()}
    remaining = n - sum(quota.values())
    for month in sorted(exact, key=lambda m: (-(exact[m] - quota[m]), m))[:remaining]:
        quota[month] += 1
    return dict(sorted(quota.items()))


def main() -> None:
    assert_frozen_cohort()
    if BLIND.exists() or KEY.exists() or MANIFEST.exists():
        raise RuntimeError("Role sample is already frozen; do not silently replace it")

    cohort = json.loads(COHORT.read_text(encoding="utf-8"))
    rows = cohort["matched"]
    if Counter(row["author_type"] for row in rows) != Counter({GROUPS[0]: 300, GROUPS[1]: 300}):
        raise RuntimeError("Unexpected matched cohort composition")
    if len({row["note_id"] for row in rows}) != len(rows):
        raise RuntimeError("Duplicate note IDs")

    rng = random.Random(SEED)
    by_group_month: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        by_group_month[row["author_type"], row["month_utc"]].append(row)

    quota = quota_by_month(rows, PAIRS)
    selected: list[dict] = []
    for month, take in quota.items():
        for group in GROUPS:
            candidates = sorted(by_group_month[group, month], key=lambda row: str(row["note_id"]))
            if take > len(candidates):
                raise RuntimeError(f"Insufficient {group} notes in {month}")
            rng.shuffle(candidates)
            selected.extend(candidates[:take])
    if len(selected) != 2 * PAIRS:
        raise RuntimeError("Wrong sample size")
    rng.shuffle(selected)

    blind_rows: list[dict] = []
    key_rows: list[dict] = []
    for index, row in enumerate(selected, 1):
        code = f"R{index:03d}"
        created = datetime.fromtimestamp(int(row["created_at_millis"]) / 1000, timezone.utc).date().isoformat()
        blind_rows.append(
            {
                "code": code,
                "note_created_utc": created,
                "note_summary": row["summary"],
                "selected_url": row["selected_url"],
            }
        )
        key_rows.append(
            {
                "code": code,
                "note_id": row["note_id"],
                "author_type": row["author_type"],
                "author_id": row["author_id"],
                "month_utc": row["month_utc"],
                "selected_url_sha256": hashlib.sha256(row["selected_url"].encode("utf-8")).hexdigest(),
            }
        )

    BLIND.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in blind_rows), encoding="utf-8")
    KEY.write_text(json.dumps({"seed": SEED, "quota_by_month": quota, "rows": key_rows}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    MANIFEST.write_text(
        json.dumps(
            {
                "purpose": "Source-role and citation-support construct-validity audit; no URL probe outcomes used",
                "cohort_sha256": sha256_file(COHORT),
                "script_sha256": sha256_file(Path(__file__)),
                "seed": SEED,
                "pairs": PAIRS,
                "quota_by_month": quota,
                "blinded_packet_sha256": sha256_file(BLIND),
                "mapping_key_sha256": sha256_file(KEY),
                "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Frozen {len(blind_rows)} notes across {len(quota)} creation months")
    print(f"Blind packet: {BLIND}")
    print(f"Mapping key: {KEY} (do not show to role coders)")


if __name__ == "__main__":
    main()
