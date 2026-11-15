"""Post-result secondary machine/browser comparison; preserve frozen inputs.

Public output contains aggregate counts and estimates only. No URL, note, post,
account, or opaque per-case identifier is written. Each group has one note per
sampled pair. The optional reference experiment draws a note uniformly and then
one of that note's distinct network URLs uniformly, rather than drawing a URL
uniformly from the 674 observed unique URLs.
"""

from __future__ import annotations

import collections
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"
OUTPUT = R / "newwave_measurement_disagreement_secondary.json"
STRATA = ("both", "ai_only", "non_api_only", "neither")
GROUPS = ("AI_API", "non_API")
LOG_NAMES = ("newwave_browser_a_normalized.jsonl", "newwave_browser_b.jsonl", "newwave_browser_c_normalized.jsonl")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_inputs():
    freeze = json.loads((R / "newwave_browser_freeze.json").read_text(encoding="utf-8"))
    key = json.loads((R / "newwave_browser_key_PRIVATE.json").read_text(encoding="utf-8"))
    primary = json.loads((R / "newwave_browser_aggregate_with_recode.json").read_text(encoding="utf-8"))
    machine = json.loads((R / "newwave_machine_aggregate.json").read_text(encoding="utf-8"))
    assert digest(R / "newwave_browser_key_PRIVATE.json") == freeze["key"]["sha256"]
    labels = {}
    for name in LOG_NAMES:
        assert digest(R / name) == primary["input_sha256"]["logs"][name]
        for line in (R / name).read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            assert row["code"] not in labels
            assert row["outcome"] in {"accessible", "not_accessible", "unresolved"}
            labels[row["code"]] = row["outcome"]
    assert len(labels) == 674
    pairs = key["selected_pairs"]
    assert len(pairs) == 240
    assert collections.Counter(p["stratum"] for p in pairs) == {h: freeze["sampling"]["strata"][h]["sampled_pairs"] for h in STRATA}
    for pair in pairs:
        f = freeze["sampling"]["strata"][pair["stratum"]]
        assert math.isclose(pair["weight"], f["population_pairs"] / f["sampled_pairs"])
    return freeze, key, labels, primary, machine


def estimate(records, field, frame):
    N = sum(frame[h]["population_pairs"] for h in STRATA)
    value = variance = 0.0
    for h in STRATA:
        values = [r[field] for r in records if r["stratum"] == h]
        Nh, nh = frame[h]["population_pairs"], frame[h]["sampled_pairs"]
        assert len(values) == nh
        value += (Nh / N) * sum(values) / nh
        if nh < Nh:
            variance += (Nh / N) ** 2 * (1 - nh / Nh) * statistics.variance(values) / nh
    return {"estimate": value, "design_se": math.sqrt(variance)}


def comparison_metrics(m, lo, hi):
    assert m in (0, 1) and lo in (0, 1) and hi in (0, 1) and lo <= hi
    return {
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


def summarize(records, frame, exact_machine_rate, target_size):
    metrics = {field: estimate(records, field, frame) for field in records[0] if field != "stratum"}
    result = {
        "population_notes": target_size,
        "sampled_notes": len(records),
        "exact_census_machine_positive_probability": exact_machine_rate,
        "exact_census_machine_negative_probability": 1 - exact_machine_rate,
        "weighted_estimates": metrics,
        "conditional_fractions_using_exact_census_denominators": {},
        "browser_rate_minus_exact_census_machine_rate": {
            "lower": metrics["browser_lower"]["estimate"] - exact_machine_rate,
            "upper": metrics["browser_upper"]["estimate"] - exact_machine_rate,
            "note": "Subtracts the known census rate from the browser-rate estimator; for the note-level any endpoint this equals the directly paired contrast because M is constant within each sampling stratum.",
        },
    }
    for name, stem, denom in (
        ("browser_negative_among_machine_positive", "machine_positive_browser_negative", exact_machine_rate),
        ("browser_positive_among_machine_negative", "machine_negative_browser_positive", 1 - exact_machine_rate),
    ):
        assert denom > 0
        result["conditional_fractions_using_exact_census_denominators"][name] = {
            "denominator_probability": denom,
            "lower": metrics[stem + "_lower"]["estimate"] / denom,
            "upper": metrics[stem + "_upper"]["estimate"] / denom,
            "endpoint_design_se": [metrics[stem + "_lower"]["design_se"] / denom, metrics[stem + "_upper"]["design_se"] / denom],
        }
    return result


def main():
    assert not OUTPUT.exists(), "Secondary result already exists; do not overwrite it."
    freeze, key, labels, primary, machine = read_inputs()
    frame = freeze["sampling"]["strata"]
    N = sum(frame[h]["population_pairs"] for h in STRATA)
    output = {
        "analysis_kind": "post_result_secondary_design_weighted_machine_browser_disagreement",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "Conceived after the field results; secondary descriptive measurement comparison, not a replacement primary endpoint.",
        "sampling": {"population_post_pairs": N, "sampled_post_pairs": len(key["selected_pairs"]), "sampled_unique_urls": len(labels), "strata": frame},
        "interpretation": {
            "outcomes": "Machine open_candidate versus AI-assisted browser-profile substantive intended-content classification; neither is factual truth.",
            "bounds": "Unknown browser content is assigned adversely at each endpoint; these estimated bounds do not include sampling or annotation uncertainty.",
            "false_positive_wording": "Machine-positive/browser-negative joint fraction among all notes (or note-then-uniform-reference trials), not the conventional false-positive rate conditional on actual browser negativity.",
            "weights": "Each pair contributes N_h/n_h; group note averages are divided by 1882. The 674 unique URLs are not a representative URL sample.",
            "conditional_denominators": "Known full-frame machine-positive and machine-negative probabilities are used. Conditional bounds are ratios of weighted joint-fraction endpoint estimates to those exact denominators, not complete-case rates.",
            "reference_net_estimators": "For the note-then-uniform-reference endpoint, the directly paired browser-minus-machine estimate and browser estimate minus exact census machine rate need not coincide in this finite sample; both are design-unbiased endpoint estimators.",
            "uncertainty": "Endpoint design SEs use stratified SRS-without-replacement finite-population variance. No new confidence interval or simultaneous inferential claim is made for this secondary collection of outcomes.",
        },
        "note_level_any_source": {},
        "uniform_note_then_uniform_distinct_reference": {},
        "input_sha256": {name: digest(R / name) for name in ("newwave_browser_freeze.json", "newwave_browser_key_PRIVATE.json", "newwave_browser_aggregate_with_recode.json", "newwave_machine_aggregate.json", *LOG_NAMES)},
        "script_sha256": digest(Path(__file__)),
    }
    for group in GROUPS:
        any_records, ref_records = [], []
        total_sample_references = 0
        for pair in key["selected_pairs"]:
            row = pair["groups"][group]
            codes = row["network_url_codes"]
            assert codes and len(codes) == len(set(codes))
            total_sample_references += len(codes)
            m = [int(row["machine_categories"][c] == "open_candidate") for c in codes]
            lo = [int(labels[c] == "accessible") for c in codes]
            hi = [int(labels[c] != "not_accessible") for c in codes]
            any_records.append({"stratum": pair["stratum"], **comparison_metrics(int(any(m)), int(any(lo)), int(any(hi)))})
            per_reference = [comparison_metrics(*v) for v in zip(m, lo, hi)]
            ref_records.append({"stratum": pair["stratum"], **{f: sum(r[f] for r in per_reference) / len(codes) for f in per_reference[0]}})
        any_rate = machine["overall"]["means"][group]["any_open"]
        ref_rate = machine["overall"]["means"][group]["open_fraction"]
        any_result = summarize(any_records, frame, any_rate, N)
        assert math.isclose(any_result["weighted_estimates"]["machine_positive"]["estimate"], any_rate, abs_tol=1e-12)
        for endpoint, field in (("lower", "any_lower"), ("upper", "any_upper")):
            assert math.isclose(any_result["weighted_estimates"]["browser_" + endpoint]["estimate"], primary["group_note_outcome_rates"][group][field]["estimate"], abs_tol=1e-12)
        any_result["exact_census_machine_positive_notes"] = round(N * any_rate)
        any_result["exact_census_machine_negative_notes"] = N - round(N * any_rate)
        any_result["sampled_note_source_references"] = total_sample_references
        output["note_level_any_source"][group] = any_result
        ref_result = summarize(ref_records, frame, ref_rate, N)
        ref_result["sampled_note_source_references"] = total_sample_references
        ref_result["reference_weighting"] = "Within each note, divide by its number of distinct network URLs before averaging notes using pair sampling weights. No pooled-URL denominator."
        output["uniform_note_then_uniform_distinct_reference"][group] = ref_result
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "any_source": {g: {k: v["estimate"] for k, v in output["note_level_any_source"][g]["weighted_estimates"].items()} for g in GROUPS}}))


if __name__ == "__main__":
    main()
