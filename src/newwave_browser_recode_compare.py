"""Compare frozen browser recode against primary URL labels without changing either."""

from __future__ import annotations

import collections
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"
OUT = R / "newwave_browser_recode_mismatches_PRIVATE.json"
LABELS = ("accessible", "not_accessible", "unresolved")


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not OUT.exists(), "Comparison already exists; inspect before rerun"
    originals = {r["code"]: r for letter in "abc" for r in rows(R / f"newwave_browser_{letter}.jsonl")}
    recode_path = R / "newwave_browser_recode.jsonl"
    recoded = {r["code"]: r for r in rows(recode_path)}
    assert len(originals) == 674 and len(recoded) == 87
    assert set(recoded) <= set(originals)
    assert all(originals[code]["url"] == row["url"] for code, row in recoded.items())
    matrix = {a: {b: 0 for b in LABELS} for a in LABELS}
    mismatches = []
    for code, second in recoded.items():
        first = originals[code]
        matrix[first["outcome"]][second["outcome"]] += 1
        if first["outcome"] != second["outcome"]:
            mismatches.append({
                "code": code,
                "url": first["url"],
                "primary": {k: first.get(k) for k in ("outcome", "reason", "title", "final_url", "evidence", "evidencebrief", "auth_visible", "one_hop_pdf") if k in first},
                "recode": {k: second.get(k) for k in ("outcome", "reason", "title", "final_url", "evidence", "auth_visible", "one_hop_pdf")},
            })
    n = len(recoded)
    correct = sum(matrix[label][label] for label in LABELS)
    p = correct / n
    z = 1.959963984540054
    d = 1 + z*z/n
    center = (p + z*z/(2*n)) / d
    half = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    expected = sum(sum(matrix[label].values()) * sum(matrix[a][label] for a in LABELS) for label in LABELS)/(n*n)
    result = {
        "n": n,
        "agreement_n": correct,
        "agreement_rate": p,
        "agreement_wilson_95_descriptive": [center-half, center+half],
        "cohen_kappa_descriptive": (p-expected)/(1-expected),
        "confusion_rows_primary_columns_frozen_recode": matrix,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "source_sha256": {"primary_logs": {letter: sha(R / f"newwave_browser_{letter}.jsonl") for letter in "abc"}, "recode": sha(recode_path)},
        "interpretation": "Repeated AI-assisted browser-profile observation at two times; agreement is not pure interannotator reliability or human-ground-truth accuracy. No relabeling follows this comparison.",
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("n", "agreement_n", "agreement_rate", "agreement_wilson_95_descriptive", "cohen_kappa_descriptive", "mismatch_count")}))


if __name__ == "__main__":
    main()
