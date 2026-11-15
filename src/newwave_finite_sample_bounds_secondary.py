"""Conservative post-result design interval by exact hypergeometric inversion.

Only new aggregate output is written. Primary scripts, source labels, and results
are read without alteration. Integer comparisons avoid floating tail error.
"""

from __future__ import annotations

import collections
import hashlib
import json
import math
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"
OUTPUT = R / "newwave_finite_sample_bounds_secondary.json"
STRATA = ("both", "ai_only", "non_api_only", "neither")
ALPHA_DENOMINATOR = 320
LOG_NAMES = ("newwave_browser_a_normalized.jsonl", "newwave_browser_b.jsonl", "newwave_browser_c_normalized.jsonl")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=None)
def tail_numerator(N, n, K, k, side):
    """Unnormalized exact hypergeometric inclusive tail, denominator comb(N,n)."""
    assert 0 <= n <= N and 0 <= K <= N and 0 <= k <= n
    low, high = max(0, n - (N - K)), min(n, K)
    if side == "ge":
        low = max(low, k)
    elif side == "le":
        high = min(high, k)
    else:
        raise ValueError("Unknown tail")
    return sum(math.comb(K, x) * math.comb(N - K, n - x) for x in range(low, high + 1))


@lru_cache(maxsize=None)
def count_interval(N, n, observed):
    """Two separately one-sided bounds, each failing with probability <= 1/320.

    Lower: smallest K with P_K(X >= observed) > alpha.
    Upper: largest K with P_K(X <= observed) > alpha.
    The strict comparison includes discrete tail ties in the rejection region.
    """
    assert 0 <= observed <= n <= N
    denominator = math.comb(N, n)
    left, right = 0, N
    while left < right:
        mid = (left + right) // 2
        if ALPHA_DENOMINATOR * tail_numerator(N, n, mid, observed, "ge") > denominator:
            right = mid
        else:
            left = mid + 1
    lower = left
    left, right = 0, N
    while left < right:
        mid = (left + right + 1) // 2
        if ALPHA_DENOMINATOR * tail_numerator(N, n, mid, observed, "le") > denominator:
            left = mid
        else:
            right = mid - 1
    upper = left
    assert 0 <= lower <= upper <= N
    if n == N:
        assert lower == upper == observed
    return lower, upper


def independently_verify(max_N=16):
    """Enumerate every actual sample subset, without using hypergeometric PMFs.

    First K units are positive. For every population size, sample size and K,
    enumerate all bitmask samples and tabulate the observed success counts.
    Verify tails, binary inversions, one-sided noncoverage and census collapse.
    """
    configurations = tails_checked = inversion_checks = census_checks = 0
    largest_lower_failure = largest_upper_failure = (0, 1)
    nonzero_failures = 0
    for N in range(1, max_N + 1):
        counts = {(n, K): collections.Counter() for n in range(N + 1) for K in range(N + 1)}
        for sample_mask in range(1 << N):
            n = sample_mask.bit_count()
            observed = 0
            for K in range(N + 1):
                counts[n, K][observed] += 1
                observed += (sample_mask >> K) & 1
        for n in range(N + 1):
            denominator = math.comb(N, n)
            for k in range(n + 1):
                feasible_lower = [K for K in range(N + 1) if ALPHA_DENOMINATOR * sum(v for x, v in counts[n, K].items() if x >= k) > denominator]
                feasible_upper = [K for K in range(N + 1) if ALPHA_DENOMINATOR * sum(v for x, v in counts[n, K].items() if x <= k) > denominator]
                interval = count_interval(N, n, k)
                assert interval == (min(feasible_lower), max(feasible_upper))
                inversion_checks += 1
                if n == N:
                    assert interval == (k, k)
                    census_checks += 1
            for K in range(N + 1):
                distribution = counts[n, K]
                assert sum(distribution.values()) == denominator
                bad_lower = bad_upper = 0
                for k in range(n + 1):
                    assert tail_numerator(N, n, K, k, "ge") == sum(v for x, v in distribution.items() if x >= k)
                    assert tail_numerator(N, n, K, k, "le") == sum(v for x, v in distribution.items() if x <= k)
                    tails_checked += 2
                    lo, hi = count_interval(N, n, k)
                    bad_lower += distribution[k] * (lo > K)
                    bad_upper += distribution[k] * (hi < K)
                assert ALPHA_DENOMINATOR * bad_lower <= denominator
                assert ALPHA_DENOMINATOR * bad_upper <= denominator
                if bad_lower or bad_upper:
                    nonzero_failures += 1
                if bad_lower * largest_lower_failure[1] > largest_lower_failure[0] * denominator:
                    largest_lower_failure = bad_lower, denominator
                if bad_upper * largest_upper_failure[1] > largest_upper_failure[0] * denominator:
                    largest_upper_failure = bad_upper, denominator
                configurations += 1
    return {
        "independent_method": "Exhaustively enumerated every sample subset as a bitmask; no hypergeometric PMF was used to form the verification distributions. Compared inclusive tails and exhaustive K scans with integer-sum tails and binary inversions.",
        "population_sizes": [1, max_N],
        "all_sample_sizes_including_zero_and_census": True,
        "all_population_positive_counts": True,
        "N_n_K_configurations": configurations,
        "tail_comparisons": tails_checked,
        "binary_inversion_vs_exhaustive_scan_checks": inversion_checks,
        "census_collapse_checks": census_checks,
        "configurations_with_nonzero_scalar_noncoverage": nonzero_failures,
        "maximum_lower_bound_noncoverage": {"numerator": largest_lower_failure[0], "denominator": largest_lower_failure[1], "probability": largest_lower_failure[0] / largest_lower_failure[1]},
        "maximum_upper_bound_noncoverage": {"numerator": largest_upper_failure[0], "denominator": largest_upper_failure[1], "probability": largest_upper_failure[0] / largest_upper_failure[1]},
        "every_one_sided_failure_probability_at_most_1_over_320": True,
    }


def main():
    assert not OUTPUT.exists(), "Secondary result already exists; do not overwrite it."
    freeze = json.loads((R / "newwave_browser_freeze.json").read_text(encoding="utf-8"))
    key = json.loads((R / "newwave_browser_key_PRIVATE.json").read_text(encoding="utf-8"))
    primary = json.loads((R / "newwave_browser_aggregate_with_recode.json").read_text(encoding="utf-8"))
    assert digest(R / "newwave_browser_key_PRIVATE.json") == freeze["key"]["sha256"]
    labels = {}
    for name in LOG_NAMES:
        assert digest(R / name) == primary["input_sha256"]["logs"][name]
        for line in (R / name).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            assert r["code"] not in labels
            labels[r["code"]] = r["outcome"]
    assert len(labels) == 674
    by = {h: {"dL": [], "dU": []} for h in STRATA}
    for pair in key["selected_pairs"]:
        states = []
        for group in ("AI_API", "non_API"):
            outcomes = [labels[c] for c in pair["groups"][group]["network_url_codes"]]
            states.append((int("accessible" in outcomes), int("accessible" in outcomes or "unresolved" in outcomes)))
        a, b = states
        by[pair["stratum"]]["dL"].append(a[0] - b[1])
        by[pair["stratum"]]["dU"].append(a[1] - b[0])
    strata = {}
    global_lower_count = global_upper_count = 0
    estimated_lower = estimated_upper = 0.0
    Ntotal = sum(freeze["sampling"]["strata"][h]["population_pairs"] for h in STRATA)
    for h in STRATA:
        N, n = (freeze["sampling"]["strata"][h][f] for f in ("population_pairs", "sampled_pairs"))
        strata[h] = {"population_pairs": N, "sampled_pairs": n}
        for endpoint in ("dL", "dU"):
            values = by[h][endpoint]
            assert len(values) == n and set(values) <= {-1, 0, 1}
            counts = collections.Counter(values)
            plus = count_interval(N, n, counts[1])
            minus = count_interval(N, n, counts[-1])
            strata[h][endpoint] = {
                "sample_counts": {"positive": counts[1], "zero": counts[0], "negative": counts[-1]},
                "population_positive_count_one_sided_bounds": list(plus),
                "population_negative_count_one_sided_bounds": list(minus),
                "sample_endpoint_mean": sum(values) / n,
            }
            if endpoint == "dL":
                chosen = plus[0] - minus[1]
                strata[h][endpoint]["conservative_population_endpoint_total_lower"] = chosen
                global_lower_count += chosen
                estimated_lower += (N / Ntotal) * sum(values) / n
            else:
                chosen = plus[1] - minus[0]
                strata[h][endpoint]["conservative_population_endpoint_total_upper"] = chosen
                global_upper_count += chosen
                estimated_upper += (N / Ntotal) * sum(values) / n
    p = primary["primary_any_source"]
    assert math.isclose(estimated_lower, p["partial_identification_lower"]["estimate"], abs_tol=1e-12)
    assert math.isclose(estimated_upper, p["partial_identification_upper"]["estimate"], abs_tol=1e-12)
    verified = independently_verify()
    output = {
        "analysis_kind": "post_result_secondary_conservative_finite_sample_design_outer_interval",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "Conceived after outcomes; a secondary sensitivity, not a primary-analysis substitution or new label collection.",
        "population_post_pairs": Ntotal,
        "sampled_post_pairs": len(key["selected_pairs"]),
        "familywise_alpha": 0.05,
        "one_sided_tail_alpha": {"numerator": 1, "denominator": ALPHA_DENOMINATOR},
        "tail_bounds_used_for_simultaneous_claim": 16,
        "coverage_argument": "Each stratum is sampled by SRS without replacement. For fixed endpoint d in {-1,0,+1}, its positive-count and negative-count marginals are hypergeometric. Inclusive exact-tail inversion bounds each required count one-sided with noncoverage <=1/320. Four required tails per stratum (lower dL plus, upper dL minus, upper dU plus, lower dU minus) across four strata give at least 95% joint coverage by the union bound, with no independence assumption between categories or strata required for that bound. Summing count differences and dividing by 1882 yields an outer interval for both finite-population missing-content endpoints simultaneously.",
        "unused_scalar_bounds": "Both scalar one-sided limits are displayed for auditability, but only the specified 16 directional limits enter the familywise claim; simultaneous coverage of every displayed scalar limit is not asserted.",
        "integer_comparison": "Tail numerator multiplied by 320 is compared strictly with comb(N,n); integer arithmetic avoids numerical tail-threshold error.",
        "strata": strata,
        "frozen_primary_reproduced": {"estimated_missing_content_bounds": [estimated_lower, estimated_upper], "approx_normal_bonferroni_outer_interval": p["approx_bonferroni_95_outer_interval_for_identified_set"]},
        "finite_sample_conservative_outer_interval": {"lower_total": global_lower_count, "upper_total": global_upper_count, "denominator": Ntotal, "bounds": [global_lower_count / Ntotal, global_upper_count / Ntotal]},
        "independent_exhaustive_small_state_verification": verified,
        "limitations": [
            "Coverage is conditional on the fixed target population, random pair-sampling design, and fixed correct AI-assisted browser observations/endpoint states; it does not cover AI classification error, changing pages, browser-profile differences, or generalization to new authors/posts.",
            "The interval is conservative because 16 tails receive equal Bonferroni allocation, count-category feasibility is not jointly optimized, and primary unknown-content bounds can themselves be conservative for shared URLs.",
            "The point estimates and unknown-content bounds remain those of the frozen primary analysis. This sensitivity changes only the sampling-uncertainty calculation.",
        ],
        "input_sha256": {name: digest(R / name) for name in ("newwave_browser_freeze.json", "newwave_browser_key_PRIVATE.json", "newwave_browser_aggregate_with_recode.json", *LOG_NAMES)},
        "script_sha256": digest(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "finite_sample_outer_interval": output["finite_sample_conservative_outer_interval"], "verification": verified}))


if __name__ == "__main__":
    main()
