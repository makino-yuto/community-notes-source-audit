"""Post hoc logical bounds respecting a shared unresolved URL within each pair.

The frozen primary analysis treats each note's unresolved cited URL as
separately favorable/unfavorable. If both notes cite the same unknown URL,
its accessibility state must be the same for both. This script tightens that
logical range without changing any frozen primary label or estimate.
"""

from __future__ import annotations

import collections
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"
OUT = R / "newwave_shared_source_bounds.json"
STRATA = ("both", "ai_only", "non_api_only", "neither")
Z_BONF = 2.241402727604947


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def pair_bounds(ai_codes: set[str], non_codes: set[str], labels: dict[str, str]) -> tuple[int, int, int, int]:
    """Return old lower/upper and shared-URL logical lower/upper for one pair."""
    assert ai_codes and non_codes
    ai_known = any(labels[code] == "accessible" for code in ai_codes)
    non_known = any(labels[code] == "accessible" for code in non_codes)
    ua = {code for code in ai_codes if labels[code] == "unresolved"}
    un = {code for code in non_codes if labels[code] == "unresolved"}
    old_lower = int(ai_known) - int(non_known or bool(un))
    old_upper = int(ai_known or bool(ua)) - int(non_known)
    if not ai_known and not non_known:
        lower = -int(bool(un - ua))
        upper = int(bool(ua - un))
    else:
        lower, upper = old_lower, old_upper
    assert old_lower <= lower <= upper <= old_upper
    return old_lower, old_upper, lower, upper


def estimate(values: dict[str, list[int]], frame: dict) -> dict:
    total = sum(frame[h]["population_pairs"] for h in STRATA)
    mean = variance = 0.0
    for h in STRATA:
        N = frame[h]["population_pairs"]
        n = frame[h]["sampled_pairs"]
        x = values[h]
        assert len(x) == n and 2 <= n <= N
        sx = sum(x)
        sx2 = sum(v*v for v in x)
        mean += (N/total) * sx/n
        variance += (N/total)**2 * (1-n/N) * (sx2-sx*sx/n)/(n*(n-1))
    return {"estimate": mean, "design_se": math.sqrt(max(0.0,variance))}


def main() -> None:
    assert not OUT.exists(), "Output exists; inspect before rerun"
    freeze_path = R / "newwave_browser_freeze.json"
    key_path = R / "newwave_browser_key_PRIVATE.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    key = json.loads(key_path.read_text(encoding="utf-8"))
    assert sha(key_path) == freeze["key"]["sha256"]
    frame = freeze["sampling"]["strata"]
    primary = json.loads((R / "newwave_browser_aggregate_with_recode.json").read_text(encoding="utf-8"))
    logs = [R / f"newwave_browser_{letter}.jsonl" for letter in "abc"]
    labels = {}
    for path in logs:
        for row in jsonl(path):
            assert row["code"] not in labels
            assert row["outcome"] in ("accessible", "not_accessible", "unresolved")
            labels[row["code"]] = row["outcome"]
    assert len(labels) == freeze["sampling"]["distinct_network_urls"] == 674

    by_stratum = {name: {h: [] for h in STRATA} for name in ("old_lower", "old_upper", "new_lower", "new_upper")}
    changed = collections.Counter()
    for pair in key["selected_pairs"]:
        h = pair["stratum"]
        ai = set(pair["groups"]["AI_API"]["network_url_codes"])
        non = set(pair["groups"]["non_API"]["network_url_codes"])
        assert ai <= labels.keys() and non <= labels.keys()
        old_lo, old_hi, new_lo, new_hi = pair_bounds(ai, non, labels)
        for name, value in (("old_lower", old_lo), ("old_upper", old_hi), ("new_lower", new_lo), ("new_upper", new_hi)):
            by_stratum[name][h].append(value)
        changed["sampled_pairs"] += 1
        changed["lower_tightened_pairs"] += int(new_lo > old_lo)
        changed["upper_tightened_pairs"] += int(new_hi < old_hi)
        changed["either_tightened_pairs"] += int(new_lo > old_lo or new_hi < old_hi)
        changed[f"either_tightened_{h}"] += int(new_lo > old_lo or new_hi < old_hi)
        changed["shared_unresolved_pairs"] += int(bool(
            {code for code in ai if labels[code] == "unresolved"} &
            {code for code in non if labels[code] == "unresolved"}
        ))
    assert changed["sampled_pairs"] == 240
    old_lo = estimate(by_stratum["old_lower"], frame)
    old_hi = estimate(by_stratum["old_upper"], frame)
    expected = primary["primary_any_source"]
    for got, target in ((old_lo, expected["partial_identification_lower"]), (old_hi, expected["partial_identification_upper"])):
        assert math.isclose(got["estimate"], target["estimate"], abs_tol=1e-12)
        assert math.isclose(got["design_se"], target["design_se"], abs_tol=1e-12)
    new_lo = estimate(by_stratum["new_lower"], frame)
    new_hi = estimate(by_stratum["new_upper"], frame)
    outer = [
        max(-1.0, new_lo["estimate"] - Z_BONF*new_lo["design_se"]),
        min(1.0, new_hi["estimate"] + Z_BONF*new_hi["design_se"]),
    ]
    result = {
        "analysis_kind": "posthoc_within_pair_shared_unknown_url_logical_bounds",
        "target_population_pairs": sum(frame[h]["population_pairs"] for h in STRATA),
        "sampled_pairs": 240,
        "counts": dict(changed),
        "frozen_primary_bounds_reproduced": {"lower": old_lo, "upper": old_hi},
        "shared_url_logical_bounds": {"lower": new_lo, "upper": new_hi,
                                      "approx_bonferroni_95_outer_interval": outer},
        "input_sha256": {
            "browser_freeze": sha(freeze_path),
            "private_key": sha(key_path),
            "original_browser_logs": {path.name: sha(path) for path in logs},
            "frozen_browser_aggregate": sha(R / "newwave_browser_aggregate_with_recode.json"),
            "script": sha(Path(__file__)),
        },
        "interpretation": "Post hoc logical sensitivity, not a replacement primary analysis. The same URL code has one unknown state within a post pair. Pairwise extrema are weighted with the original frozen design and finite-population SE. Cross-pair shared URLs are not jointly optimized, so bounds can remain conservative globally. No new source observations or outcome-based relabeling.",
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps({"tightened_pairs":changed["either_tightened_pairs"],
                      "bounds":[new_lo["estimate"],new_hi["estimate"]],
                      "outer":outer}))


if __name__ == "__main__":
    main()
