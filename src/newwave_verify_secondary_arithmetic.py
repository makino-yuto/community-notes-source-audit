"""Independent Fraction-based check of the new secondary aggregate arithmetic.

Does not import either secondary analyzer. Reads frozen observations and writes
only a new identifier-free verification result.
"""

from __future__ import annotations

import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"
OUTPUT = R / "newwave_secondary_arithmetic_verification.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert not OUTPUT.exists(), "Verification output exists; do not overwrite."
    read = lambda name: json.loads((R / name).read_text(encoding="utf-8"))
    freeze = read("newwave_browser_freeze.json")
    key = read("newwave_browser_key_PRIVATE.json")
    primary = read("newwave_browser_aggregate_with_recode.json")
    disagreement = read("newwave_measurement_disagreement_secondary.json")
    exact = read("newwave_finite_sample_bounds_secondary.json")
    assert digest(R / "newwave_browser_freeze.json") == primary["input_sha256"]["freeze"]
    assert digest(R / "newwave_browser_key_PRIVATE.json") == primary["input_sha256"]["key"]
    assert digest(ROOT / "src/newwave_measurement_disagreement_secondary.py") == disagreement["script_sha256"]
    assert digest(ROOT / "src/newwave_finite_sample_bounds_secondary.py") == exact["script_sha256"]
    labels = {}
    for name in ("newwave_browser_a_normalized.jsonl", "newwave_browser_b.jsonl", "newwave_browser_c_normalized.jsonl"):
        assert digest(R / name) == primary["input_sha256"]["logs"][name]
        for line in (R / name).read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            assert row["code"] not in labels
            labels[row["code"]] = row["outcome"]
    frame = freeze["sampling"]["strata"]
    N = sum(s["population_pairs"] for s in frame.values())
    checked = 0
    for group in ("AI_API", "non_API"):
        sums = {experiment: {} for experiment in ("note_level_any_source", "uniform_note_then_uniform_distinct_reference")}
        for pair in key["selected_pairs"]:
            h = frame[pair["stratum"]]
            weight = Fraction(h["population_pairs"], h["sampled_pairs"] * N)
            row = pair["groups"][group]
            codes = row["network_url_codes"]
            # This verifier uses exact rational weighted sums, not per-stratum means.
            observations = [(int(row["machine_categories"][c] == "open_candidate"), int(labels[c] == "accessible"), int(labels[c] != "not_accessible")) for c in codes]
            any_observation = tuple(int(any(v[j] for v in observations)) for j in range(3))
            for experiment, trials in (("note_level_any_source", [any_observation]), ("uniform_note_then_uniform_distinct_reference", observations)):
                for m, lo, hi in trials:
                    contributions = {
                        "machine_positive": m,
                        "browser_lower": lo,
                        "browser_upper": hi,
                        "machine_positive_browser_negative_lower": m * (1 - hi),
                        "machine_positive_browser_negative_upper": m * (1 - lo),
                        "machine_negative_browser_positive_lower": (1 - m) * lo,
                        "machine_negative_browser_positive_upper": (1 - m) * hi,
                        "browser_minus_machine_lower": lo - m,
                        "browser_minus_machine_upper": hi - m,
                    }
                    for field, value in contributions.items():
                        sums[experiment][field] = sums[experiment].get(field, Fraction()) + weight * Fraction(value, len(trials))
        for experiment, totals in sums.items():
            for field, value in totals.items():
                assert math.isclose(float(value), disagreement[experiment][group]["weighted_estimates"][field]["estimate"], abs_tol=1e-12)
                checked += 1
            assert totals["browser_minus_machine_lower"] == totals["machine_negative_browser_positive_lower"] - totals["machine_positive_browser_negative_upper"]
            assert totals["browser_minus_machine_upper"] == totals["machine_negative_browser_positive_upper"] - totals["machine_positive_browser_negative_lower"]
    # Check the reported exact-count limits against their defining tail inequalities
    # at each boundary and its adjacent integer, independently of binary search.
    boundary_checks = 0
    for h, result in exact["strata"].items():
        Nh, nh = result["population_pairs"], result["sampled_pairs"]
        denominator = math.comb(Nh, nh)
        for endpoint in ("dL", "dU"):
            for category, noun in (("positive", "positive"), ("negative", "negative")):
                observed = result[endpoint]["sample_counts"][category]
                lower, upper = result[endpoint]["population_" + noun + "_count_one_sided_bounds"]
                def numerator(K, ge):
                    return sum(math.comb(K, x) * math.comb(Nh - K, nh - x) for x in range(nh + 1) if x <= K and nh - x <= Nh - K and (x >= observed if ge else x <= observed))
                assert numerator(lower, True) * 320 > denominator
                assert lower == 0 or numerator(lower - 1, True) * 320 <= denominator
                assert numerator(upper, False) * 320 > denominator
                assert upper == Nh or numerator(upper + 1, False) * 320 <= denominator
                boundary_checks += 4
    lower_total = sum(s["dL"]["population_positive_count_one_sided_bounds"][0] - s["dL"]["population_negative_count_one_sided_bounds"][1] for s in exact["strata"].values())
    upper_total = sum(s["dU"]["population_positive_count_one_sided_bounds"][1] - s["dU"]["population_negative_count_one_sided_bounds"][0] for s in exact["strata"].values())
    assert [lower_total, upper_total] == [-257, 507]
    assert exact["finite_sample_conservative_outer_interval"]["bounds"] == [lower_total / N, upper_total / N]
    output = {
        "analysis_kind": "independent_secondary_arithmetic_verification",
        "weighted_estimates_independently_checked_with_exact_rational_sums": checked,
        "joint_fraction_net_difference_identities_checked": 8,
        "exact_hypergeometric_boundary_and_neighbor_inequalities_checked": boundary_checks,
        "exact_global_endpoint_totals_reproduced": [lower_total, upper_total],
        "frozen_primary_input_hashes_match": True,
        "new_result_script_hashes_match": True,
        "limitations": "Arithmetic verification is not independent source-label adjudication or empirical validation of the hypothetical fixed-page-state sampling model.",
        "input_sha256": {name: digest(R / name) for name in ("newwave_measurement_disagreement_secondary.json", "newwave_finite_sample_bounds_secondary.json", "newwave_browser_aggregate_with_recode.json")},
        "script_sha256": digest(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output))


if __name__ == "__main__":
    main()
