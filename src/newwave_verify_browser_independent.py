"""Independent arithmetic check and conservative browser-label sensitivities.

This is a post-freeze verification script. It does not alter the frozen analysis
or any original browser observations. All output is aggregate, with no IDs or URLs.
"""

from __future__ import annotations

import collections
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urldefrag


ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"
STRATA = ("both", "ai_only", "non_api_only", "neither")
GROUPS = ("AI_API", "non_API")
OUT = R / "newwave_browser_independent_verification.json"


def lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def estimate(values: dict[str, list[float]], frame: dict) -> dict:
    """Direct sums/squared sums, separate from the frozen analyzer implementation."""
    total = sum(frame[h]["population_pairs"] for h in STRATA)
    estimate_sum = variance_sum = 0.0
    for h in STRATA:
        N = frame[h]["population_pairs"]
        n = frame[h]["sampled_pairs"]
        x = values[h]
        assert len(x) == n and n >= 2 and N >= n
        sx = sum(x)
        sx2 = sum(value * value for value in x)
        estimate_sum += (N / total) * (sx / n)
        variance_sum += (N / total) ** 2 * (1 - n / N) * (sx2 - sx * sx / n) / (n * (n - 1))
    return {"estimate": estimate_sum, "design_se": math.sqrt(max(0.0, variance_sum))}


def note_state(codes: list[str], labels: dict[str, str]) -> tuple[int, int]:
    assert codes and len(codes) == len(set(codes))
    states = [labels[code] for code in codes]
    definite = int("accessible" in states)
    possible = int(definite or "unresolved" in states)
    return definite, possible


def paired_bounds(selected: list[dict], labels: dict[str, str], frame: dict) -> dict:
    lower = {h: [] for h in STRATA}
    upper = {h: [] for h in STRATA}
    point = {h: [] for h in STRATA}
    for pair in selected:
        h = pair["stratum"]
        a = note_state(pair["groups"]["AI_API"]["network_url_codes"], labels)
        b = note_state(pair["groups"]["non_API"]["network_url_codes"], labels)
        lower[h].append(a[0] - b[1])
        upper[h].append(a[1] - b[0])
        point[h].append(a[0] - b[0])
    result = {"identified_lower": estimate(lower, frame), "identified_upper": estimate(upper, frame), "unresolved_as_inaccessible": estimate(point, frame)}
    assert result["identified_lower"]["estimate"] <= result["identified_upper"]["estimate"]
    z = 2.241402727604947
    result["approx_bonferroni_95_outer_interval"] = [
        max(-1.0, result["identified_lower"]["estimate"] - z * result["identified_lower"]["design_se"]),
        min(1.0, result["identified_upper"]["estimate"] + z * result["identified_upper"]["design_se"]),
    ]
    return result


def main() -> None:
    assert not OUT.exists(), "Verification output already exists; inspect before rerun"
    freeze = json.loads((R / "newwave_browser_freeze.json").read_text(encoding="utf-8"))
    key = json.loads((R / "newwave_browser_key_PRIVATE.json").read_text(encoding="utf-8"))
    primary = json.loads((R / "newwave_browser_aggregate.json").read_text(encoding="utf-8"))
    frame = freeze["sampling"]["strata"]
    selected = key["selected_pairs"]
    assert len(selected) == 240 and len({p["post_id"] for p in selected}) == 240
    assert collections.Counter(p["stratum"] for p in selected) == {h: frame[h]["sampled_pairs"] for h in STRATA}
    for pair in selected:
        h = pair["stratum"]
        assert math.isclose(float(pair["weight"]), frame[h]["population_pairs"] / frame[h]["sampled_pairs"])

    packet = [item for letter in "abc" for item in json.loads((R / f"newwave_browser_packet_{letter}.json").read_text(encoding="utf-8"))]
    observed = [item for letter in "abc" for item in lines(R / f"newwave_browser_{letter}.jsonl")]
    assert len(packet) == len(observed) == 674
    expected = {item["code"]: item["url"] for item in packet}
    assert len(expected) == 674
    assert {item["code"]: item["url"] for item in observed} == expected
    assert len({item["code"] for item in observed}) == 674
    by_code = {item["code"]: item for item in observed}
    baseline = {code: item["outcome"] for code, item in by_code.items()}
    assert set(baseline.values()) <= {"accessible", "not_accessible", "unresolved"}
    variants = {
        "baseline": lambda row: False,
        "authenticated_access_to_unknown": lambda row: row["auth_visible"],
        "abstract_only_to_unknown": lambda row: row.get("abstract_only", False),
        "one_hop_pdf_to_unknown": lambda row: row["one_hop_pdf"],
        "all_three_to_unknown": lambda row: row["auth_visible"] or row.get("abstract_only", False) or row["one_hop_pdf"],
    }
    sensitivity = {}
    for name, trigger in variants.items():
        recoded = {code: ("unresolved" if item["outcome"] == "accessible" and trigger(item) else item["outcome"]) for code, item in by_code.items()}
        sensitivity[name] = {
            "newly_unknown_urls": sum(recoded[code] != baseline[code] for code in baseline),
            "paired_any_source_difference": paired_bounds(selected, recoded, frame),
        }

    p = primary["primary_any_source"]
    b = sensitivity["baseline"]["paired_any_source_difference"]
    checks = {
        "target_population_matches": sum(frame[h]["population_pairs"] for h in STRATA) == primary["target_population_pairs"],
        "sample_size_matches": len(selected) == primary["sampled_pairs"],
        "url_count_matches": len(observed) == primary["sampled_distinct_network_urls"],
        "baseline_point_matches": math.isclose(b["unresolved_as_inaccessible"]["estimate"], p["unresolved_as_inaccessible_pair_difference"]["estimate"], abs_tol=1e-12),
        "baseline_lower_matches": math.isclose(b["identified_lower"]["estimate"], p["partial_identification_lower"]["estimate"], abs_tol=1e-12),
        "baseline_upper_matches": math.isclose(b["identified_upper"]["estimate"], p["partial_identification_upper"]["estimate"], abs_tol=1e-12),
        "baseline_point_se_matches": math.isclose(b["unresolved_as_inaccessible"]["design_se"], p["unresolved_as_inaccessible_pair_difference"]["design_se"], abs_tol=1e-12),
        "baseline_lower_se_matches": math.isclose(b["identified_lower"]["design_se"], p["partial_identification_lower"]["design_se"], abs_tol=1e-12),
        "baseline_upper_se_matches": math.isclose(b["identified_upper"]["design_se"], p["partial_identification_upper"]["design_se"], abs_tol=1e-12),
        "outer_interval_matches": all(math.isclose(x,y,abs_tol=1e-12) for x,y in zip(b["approx_bonferroni_95_outer_interval"], p["approx_bonferroni_95_outer_interval_for_identified_set"])),
    }
    assert all(checks.values()), checks

    # Independently check the full machine census and the random-one-link algebra.
    candidates = lines(R / "revision_samepost_candidates_v2_PRIVATE.jsonl")
    probes = {item["url_sha256"]: item for item in lines(R / "newwave_probe_PRIVATE.jsonl")}
    machine = json.loads((R / "newwave_machine_aggregate.json").read_text(encoding="utf-8"))
    assert len(candidates) == 1882
    raw_strata = collections.Counter()
    redundant_note_count = collections.Counter()
    random_one_gain = collections.defaultdict(float)
    any_rates = collections.defaultdict(float)
    open_fractions = collections.defaultdict(float)
    notes_count = collections.Counter()
    for pair in candidates:
        state = {}
        for group, field in (("AI_API", "ai"), ("non_API", "non_api")):
            urls = {urldefrag(link["normalized_url"]).url for link in pair[field]["external_urls"]}
            cats = [probes[hashlib.sha256(url.encode("utf-8")).hexdigest()]["category"] for url in urls]
            k, m = cats.count("open_candidate"), len(cats)
            assert m >= 1
            state[group] = k > 0
            notes_count[group] += 1
            random_one_gain[group] += int(k > 0) - k/m
            any_rates[group] += int(k > 0)
            open_fractions[group] += k/m
            redundant_note_count[group] += int(0 < k < m)
        raw_strata[("both" if state["AI_API"] and state["non_API"] else "ai_only" if state["AI_API"] else "non_api_only" if state["non_API"] else "neither")] += 1
    assert all(raw_strata[h] == frame[h]["population_pairs"] for h in STRATA)
    for group in GROUPS:
        metrics = machine["overall"]["means"][group]
        n = notes_count[group]
        assert n == 1882
        assert math.isclose(random_one_gain[group] / n, metrics["redundancy_vs_random_single"], abs_tol=1e-12)
        assert math.isclose(any_rates[group] / n, metrics["any_open"], abs_tol=1e-12)
        assert math.isclose(open_fractions[group] / n, metrics["open_fraction"], abs_tol=1e-12)
        assert math.isclose(metrics["any_open"] - metrics["open_fraction"], metrics["redundancy_vs_random_single"], abs_tol=1e-12)

    result = {
        "analysis_kind": "independent_browser_and_machine_arithmetic_verification",
        "input_sha256": {
            "browser_c_original": hashlib.sha256((R / "newwave_browser_c.jsonl").read_bytes()).hexdigest(),
            "browser_aggregate": hashlib.sha256((R / "newwave_browser_aggregate.json").read_bytes()).hexdigest(),
            "machine_aggregate": hashlib.sha256((R / "newwave_machine_aggregate.json").read_bytes()).hexdigest(),
        },
        "checks": checks,
        "frame_strata_independently_match_machine_census": True,
        "machine_redundancy_algebra_independently_matches": True,
        "machine_mixed_open_and_non_open_note_counts": dict(redundant_note_count),
        "url_label_counts": dict(collections.Counter(baseline.values())),
        "policy_not_observed_urls": sum(item["reason"] == "policy_not_observed" for item in observed),
        "sensitivity": sensitivity,
        "interpretation": "Sensitivity turns profile-authenticated, abstract-only, or one-hop-PDF accessible content into unresolved, not inaccessible. Denominators and post-pair design weights remain fixed. Normal finite-population intervals cover only random sampling of pairs within four machine-defined strata; they do not cover browser annotation error, site changes, or dependence among URLs and authors.",
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Independent browser arithmetic, machine strata, and redundancy checks passed; aggregate sensitivity written.")


if __name__ == "__main__":
    main()
