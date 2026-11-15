"""Secondary reproduction from the anonymous numeric package only.

Standard library only; no private inputs or network. Never writes the package's
CSVs, manifest, primary reproducer, or primary results.
"""
from __future__ import annotations
import argparse
import collections
import csv
import hashlib
import json
import math
import statistics
from functools import lru_cache
from pathlib import Path

STRATA = ("both", "ai_only", "non_api_only", "neither")
GROUPS = (("AI_API", "ai"), ("non_API", "non"))
ALPHA_DENOMINATOR = 320

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_package(package):
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "newwave-public-numeric-v1"
    tables, hashes = {}, {"manifest.json": sha(package / "manifest.json")}
    for filename in ("data/machine_pairs_anonymous.csv", "data/browser_pairs_anonymous.csv"):
        path, expected = package / filename, manifest["files"][filename]
        hashes[filename] = sha(path)
        if hashes[filename] != expected["sha256"]:
            raise ValueError("CSV SHA-256 mismatch: " + filename)
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            assert reader.fieldnames == expected["columns"]
            rows = list(reader)
        assert len(rows) == expected["rows"]
        tables[filename] = rows
    frame = manifest["browser_population_strata"]
    assert set(frame) == set(STRATA)
    machine, browser = (tables["data/" + name + "_pairs_anonymous.csv"] for name in ("machine", "browser"))
    assert len(machine) == sum(frame[h]["population_pairs"] for h in STRATA)
    assert collections.Counter(r["stratum"] for r in browser) == {h: frame[h]["sampled_pairs"] for h in STRATA}
    for row in machine:
        for _, prefix in GROUPS:
            assert float(row[prefix + "_any_open"]) in (0., 1.)
    for row in browser:
        for _, prefix in GROUPS:
            lo, hi = (float(row[prefix + "_any_" + suffix]) for suffix in ("lower", "upper"))
            assert lo in (0., 1.) and hi in (0., 1.) and lo <= hi
    return frame, machine, browser, hashes

def estimate(records, field, frame):
    N = sum(frame[h]["population_pairs"] for h in STRATA)
    mean = variance = 0.
    for h in STRATA:
        Nh, nh = (frame[h][name] for name in ("population_pairs", "sampled_pairs"))
        values = [r[field] for r in records if r["stratum"] == h]
        assert len(values) == nh and 2 <= nh <= Nh
        mean += (Nh / N) * sum(values) / nh
        if nh < Nh:
            variance += (Nh / N) ** 2 * (1 - nh / Nh) * statistics.variance(values) / nh
    return {"estimate": mean, "design_se": math.sqrt(max(0., variance))}

def machine_any(stratum, prefix):
    return int(stratum == "both" or stratum == ("ai_only" if prefix == "ai" else "non_api_only"))

def disagreement(frame, machine, browser):
    N, results = len(machine), {}
    for group, prefix in GROUPS:
        positive_count = sum(int(float(r[prefix + "_any_open"])) for r in machine)
        assert positive_count == sum(frame[h]["population_pairs"] * machine_any(h, prefix) for h in STRATA)
        positive_probability, records = positive_count / N, []
        for row in browser:
            m = machine_any(row["stratum"], prefix)
            lo, hi = (float(row[prefix + "_any_" + suffix]) for suffix in ("lower", "upper"))
            records.append({"stratum": row["stratum"], "machine_positive": m, "browser_lower": lo, "browser_upper": hi,
                "machine_positive_browser_negative_lower": m * (1-hi), "machine_positive_browser_negative_upper": m * (1-lo),
                "machine_negative_browser_positive_lower": (1-m)*lo, "machine_negative_browser_positive_upper": (1-m)*hi,
                "browser_minus_machine_lower": lo-m, "browser_minus_machine_upper": hi-m})
        estimates = {f: estimate(records, f, frame) for f in records[0] if f != "stratum"}
        assert math.isclose(estimates["machine_positive"]["estimate"], positive_probability, abs_tol=1e-12)
        conditional = {}
        for name, stem, denominator in (
            ("browser_negative_among_machine_positive", "machine_positive_browser_negative", positive_probability),
            ("browser_positive_among_machine_negative", "machine_negative_browser_positive", 1-positive_probability)):
            assert denominator > 0
            conditional[name] = {"denominator_probability": denominator,
                "lower": estimates[stem+"_lower"]["estimate"]/denominator,
                "upper": estimates[stem+"_upper"]["estimate"]/denominator,
                "endpoint_design_se": [estimates[stem+"_lower"]["design_se"]/denominator, estimates[stem+"_upper"]["design_se"]/denominator]}
        results[group] = {"population_notes": N, "sampled_notes": len(records),
            "exact_census_machine_positive_notes": positive_count, "exact_census_machine_negative_notes": N-positive_count,
            "weighted_estimates": estimates, "conditional_fractions_using_exact_census_denominators": conditional}
    return results

def finite_sample_interval(frame, browser):
    records = [{"stratum": r["stratum"], "dL": int(float(r["ai_any_lower"]))-int(float(r["non_any_upper"])),
                "dU": int(float(r["ai_any_upper"]))-int(float(r["non_any_lower"]))} for r in browser]
    Ntotal = sum(frame[h]["population_pairs"] for h in STRATA)
    strata, lower_total, upper_total = {}, 0, 0
    for h in STRATA:
        N, n = (frame[h][name] for name in ("population_pairs", "sampled_pairs"))
        strata[h] = {"population_pairs": N, "sampled_pairs": n}
        for endpoint in ("dL", "dU"):
            values = [r[endpoint] for r in records if r["stratum"] == h]
            assert len(values) == n and set(values) <= {-1,0,1}
            counts = collections.Counter(values)
            plus, minus = count_interval(N,n,counts[1]), count_interval(N,n,counts[-1])
            strata[h][endpoint] = {"sample_counts": {"positive": counts[1], "zero": counts[0], "negative": counts[-1]},
                "population_positive_count_one_sided_bounds": list(plus), "population_negative_count_one_sided_bounds": list(minus)}
            if endpoint == "dL": lower_total += plus[0]-minus[1]
            else: upper_total += plus[1]-minus[0]
    lower, upper = estimate(records,"dL",frame), estimate(records,"dU",frame)
    z = 2.241402727604947
    return {"estimated_missing_content_bounds": [lower["estimate"],upper["estimate"]],
        "endpoint_design_se": [lower["design_se"],upper["design_se"]],
        "approx_normal_bonferroni_outer_interval": [max(-1.,lower["estimate"]-z*lower["design_se"]),min(1.,upper["estimate"]+z*upper["design_se"])],
        "strata": strata, "finite_sample_conservative_outer_interval": {"lower_total": lower_total,"upper_total": upper_total,"denominator": Ntotal,"bounds": [lower_total/Ntotal,upper_total/Ntotal]},
        "familywise_alpha": .05,"one_sided_tail_alpha": {"numerator": 1,"denominator": 320},"directional_tail_bounds_used": 16}

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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package",type=Path,default=Path(__file__).resolve().parents[1],help="Directory containing manifest.json and data/")
    parser.add_argument("--output",type=Path,help="Write a new JSON file; otherwise print JSON")
    parser.add_argument("--self-test",action="store_true",help="Exhaustively enumerate all sample states N=1..16")
    args = parser.parse_args()
    if args.output and args.output.exists(): raise FileExistsError("Refusing to overwrite: "+str(args.output))
    frame,machine,browser,hashes = read_package(args.package.resolve())
    result = {"schema":"newwave-secondary-public-reproduction-v1",
        "status":"Secondary analyses conceived after field results. Frozen primary analysis and labels are unchanged.",
        "units":{"population_post_pairs":len(machine),"sampled_post_pairs":len(browser),"population_notes_per_group":len(machine),"sampled_notes_per_group":len(browser)},
        "note_level_any_source":disagreement(frame,machine,browser),"finite_sample_sensitivity":finite_sample_interval(frame,browser),
        "interpretation":[
            "Machine open_candidate and AI-assisted browser-profile content are distinct measurement channels, not factual truth or human-verified classifier accuracy.",
            "Disagreement ranges are weighted estimated missing-content endpoints, not confidence intervals. Joint fractions use all notes as denominator; conditional diagnostics use exact census machine-positive/negative denominators.",
            "At least 95% finite-population design coverage follows from sixteen directional exact-tail count bounds at alpha=1/320 each and the union bound, conditional on fixed endpoints and random pair sampling. It excludes annotation error, changing pages and external generalization.",
            "The outer lower limit uses lower Kplus minus upper Kminus for dL; the outer upper uses upper Kplus minus lower Kminus for dU, summed over strata and divided by 1882. Both scalar limits are displayed, but joint coverage of every displayed limit is not asserted.",
            "The independently shuffled CSVs are never joined. Browser stratum defines each note's machine-any status. The 674 unique URLs are not a representative URL sample.",
            "Reference-level machine/browser matches are omitted from the public tables; within-note random-reference cross-channel disagreement cannot be reconstructed and is not attempted."],
        "input_sha256":hashes,"script_sha256":sha(Path(__file__))}
    if args.self_test: result["independent_exhaustive_small_state_verification"] = independently_verify()
    serialized = json.dumps(result,indent=2)+"\n"
    if args.output:
        args.output.write_text(serialized,encoding="utf-8")
        print(json.dumps({"output":str(args.output),"finite_sample_outer_interval":result["finite_sample_sensitivity"]["finite_sample_conservative_outer_interval"]["bounds"],"self_test":bool(args.self_test)}))
    else: print(serialized,end="")

if __name__ == "__main__": main()
