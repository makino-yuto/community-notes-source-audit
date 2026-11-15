"""Design-weighted browser audit of the frozen same-post all-citation sample.

All browser labels refer to visible substantive intended content in the study
browser profile. Unresolved labels produce partial-identification bounds; no
complete-case deletion or factual-support inference is made. Output is
aggregate only, without post IDs, note IDs, author IDs, or source URLs.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import statistics
from pathlib import Path

from newwave_analyze_machine import digest_file, read_jsonl


ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"
FREEZE = R / "newwave_browser_freeze.json"
KEY = R / "newwave_browser_key_PRIVATE.json"
LOGS = [R / f"newwave_browser_{letter}.jsonl" for letter in "abc"]
RECODE = R / "newwave_browser_recode.jsonl"
OUTPUT = R / "newwave_browser_aggregate.json"
OUTCOMES = {"accessible", "not_accessible", "unresolved"}
GROUPS = ("AI_API", "non_API")
STRATA = ("both", "ai_only", "non_api_only", "neither")
REQUIRED = ("code", "url", "outcome", "reason", "title", "final_url", "utc", "evidence", "auth_visible", "one_hop_pdf")
Z = 1.959963984540054
Z_BONFERRONI = 2.241402727604947


def verify_freeze(freeze_path: Path, key_path: Path) -> tuple[dict, dict, dict[str, str]]:
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if freeze.get("schema") != "newwave-browser-freeze-v1":
        raise ValueError("Unexpected browser freeze schema")
    if freeze.get("analysis_script_sha256") != digest_file(Path(__file__)):
        raise ValueError("Analysis script changed after browser freeze")
    if freeze["key"]["sha256"] != digest_file(key_path):
        raise ValueError("Private browser key changed after freeze")
    if freeze["protocol_sha256"] != digest_file(R / "newwave_protocol_frozen.json"):
        raise ValueError("Research protocol changed after browser freeze")
    if freeze["candidate_sha256"] != digest_file(R / "revision_samepost_candidates_v2_PRIVATE.jsonl"):
        raise ValueError("Pair candidate file changed after browser freeze")
    if freeze["probe_manifest_sha256"] != digest_file(R / "newwave_probe_manifest_PRIVATE.json"):
        raise ValueError("Machine probe manifest changed after browser freeze")
    if freeze["probe_log_sha256"] != digest_file(R / "newwave_probe_PRIVATE.jsonl"):
        raise ValueError("Machine probe log changed after browser freeze")
    key = json.loads(key_path.read_text(encoding="utf-8"))
    if key.get("schema") != "newwave-browser-key-v1":
        raise ValueError("Unexpected browser key schema")
    expected = {}
    for packet_name, packet_meta in freeze["packets"].items():
        path = R / packet_name
        if digest_file(path) != packet_meta["sha256"]:
            raise ValueError("Browser packet changed after freeze")
        packet = json.loads(path.read_text(encoding="utf-8"))
        if len(packet) != packet_meta["count"]:
            raise ValueError("Browser packet length differs from freeze")
        for row in packet:
            code, url = row["code"], row["url"]
            if code in expected:
                raise ValueError("Duplicate URL code across browser packets")
            expected[code] = url
    lookup = {row["code"]: row["url"] for row in key["url_lookup"]}
    if lookup != expected:
        raise ValueError("Private key and browser packets disagree on URL coverage")
    if len(expected) != freeze["sampling"]["distinct_network_urls"]:
        raise ValueError("Distinct browser URL count differs from freeze")
    recode_path = R / freeze["recode"]["packet_name"]
    if digest_file(recode_path) != freeze["recode"]["packet_sha256"]:
        raise ValueError("Blind recode packet changed after freeze")
    recode_packet = json.loads(recode_path.read_text(encoding="utf-8"))
    if len(recode_packet) != freeze["recode"]["packet_count"]:
        raise ValueError("Blind recode packet count differs from freeze")
    if any(expected.get(row["code"]) != row["url"] for row in recode_packet):
        raise ValueError("Blind recode packet contains unknown code or URL")
    recode_pairs = set(key["recode_pair_codes"])
    if len(recode_pairs) != freeze["recode"]["selected_pairs"]:
        raise ValueError("Blind recode pair count differs from freeze")
    recode_expected_codes = {
        code for pair in key["selected_pairs"] if pair["pair_code"] in recode_pairs
        for group in GROUPS for code in pair["groups"][group]["network_url_codes"]
    }
    if {row["code"] for row in recode_packet} != recode_expected_codes:
        raise ValueError("Blind recode URLs do not cover exactly the selected pairs")
    return freeze, key, expected


def load_labels(paths: list[Path], expected: dict[str, str]) -> dict[str, dict]:
    labels = {}
    for path in paths:
        for row in read_jsonl(path):
            for field in REQUIRED:
                if field not in row:
                    raise ValueError(f"Missing {field} in {path.name}")
            code = row["code"]
            if code not in expected or row["url"] != expected[code]:
                raise ValueError("Browser label code or URL does not match frozen packet")
            if code in labels:
                raise ValueError("Duplicate browser URL label")
            if row["outcome"] not in OUTCOMES:
                raise ValueError("Unexpected browser access label")
            if any(not isinstance(row[field], str) for field in ("reason", "title", "final_url", "utc", "evidence")):
                raise ValueError("Browser observation text fields must be strings")
            if any(not isinstance(row[field], bool) for field in ("auth_visible", "one_hop_pdf")):
                raise ValueError("Browser observation flags must be booleans")
            labels[code] = row
    if set(labels) != set(expected):
        raise ValueError(f"Incomplete browser label coverage: {len(labels)}/{len(expected)}")
    return labels


def note_metrics(codes: list[str], labels: dict[str, dict]) -> dict[str, float]:
    if not codes or len(codes) != len(set(codes)):
        raise ValueError("Empty or duplicate network URL codes within a note")
    outcomes = [labels[code]["outcome"] for code in codes]
    n = len(outcomes)
    accessible = outcomes.count("accessible")
    unresolved = outcomes.count("unresolved")
    not_accessible = outcomes.count("not_accessible")
    if accessible + unresolved + not_accessible != n:
        raise ValueError("Invalid browser outcome")
    return {
        "any_lower": float(accessible > 0),
        "any_upper": float(accessible > 0 or unresolved > 0),
        "all_lower": float(accessible == n),
        "all_upper": float(not_accessible == 0),
        "fraction_lower": accessible / n,
        "fraction_upper": (accessible + unresolved) / n,
        "unresolved_fraction": unresolved / n,
    }


def estimate(values_by_stratum: dict[str, list[float]], freeze: dict) -> dict:
    """Stratified pair HT mean and without-replacement finite-population SE."""
    N = sum(freeze["sampling"]["strata"][h]["population_pairs"] for h in STRATA)
    if N <= 0:
        raise ValueError("Empty target population")
    mean = 0.0
    variance = 0.0
    for h in STRATA:
        N_h = freeze["sampling"]["strata"][h]["population_pairs"]
        n_h = freeze["sampling"]["strata"][h]["sampled_pairs"]
        values = values_by_stratum.get(h, [])
        if len(values) != n_h:
            raise ValueError("Observed pair count differs from frozen stratum sample")
        if not N_h:
            continue
        mean_h = sum(values) / n_h
        weight = N_h / N
        mean += weight * mean_h
        if n_h < N_h:
            if n_h < 2:
                raise ValueError("Cannot estimate variance from a one-pair noncensus stratum")
            variance += weight * weight * (1 - n_h / N_h) * statistics.variance(values) / n_h
    se = math.sqrt(max(0.0, variance))
    return {"estimate": mean, "design_se": se, "normal_95": [mean - Z * se, mean + Z * se]}


def estimate_field(records: list[dict], freeze: dict, field: str) -> dict:
    by = collections.defaultdict(list)
    for record in records:
        by[record["stratum"]].append(record[field])
    return estimate(by, freeze)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--freeze", type=Path, default=FREEZE)
    ap.add_argument("--key", type=Path, default=KEY)
    ap.add_argument("--logs", nargs=3, type=Path, default=LOGS)
    ap.add_argument("--recode", type=Path, help="Optional independently blinded second-pass JSONL")
    ap.add_argument("--output", type=Path, default=OUTPUT)
    args = ap.parse_args()
    if args.output.exists():
        raise FileExistsError("Aggregate output exists; inspect it before any rerun")
    freeze, key, expected = verify_freeze(args.freeze, args.key)
    labels = load_labels(args.logs, expected)
    selected = key["selected_pairs"]
    if len(selected) != freeze["sampling"]["sampled_post_pairs"]:
        raise ValueError("Selected pair count differs from browser freeze")
    stratum_counter = collections.Counter(pair["stratum"] for pair in selected)
    for h in STRATA:
        if stratum_counter[h] != freeze["sampling"]["strata"][h]["sampled_pairs"]:
            raise ValueError("Selected pair stratum count differs from browser freeze")
    records = []
    for pair in selected:
        group_metrics = {group: note_metrics(pair["groups"][group]["network_url_codes"], labels) for group in GROUPS}
        ai, non = group_metrics["AI_API"], group_metrics["non_API"]
        records.append({
            "stratum": pair["stratum"],
            "author_id": pair["groups"]["AI_API"]["author_id"],
            "ai": ai,
            "non": non,
            "any_lower_assumption_difference": ai["any_lower"] - non["any_lower"],
            "any_identified_lower": ai["any_lower"] - non["any_upper"],
            "any_identified_upper": ai["any_upper"] - non["any_lower"],
            "all_identified_lower": ai["all_lower"] - non["all_upper"],
            "all_identified_upper": ai["all_upper"] - non["all_lower"],
            "fraction_identified_lower": ai["fraction_lower"] - non["fraction_upper"],
            "fraction_identified_upper": ai["fraction_upper"] - non["fraction_lower"],
            "known_both": float(ai["any_lower"] == 1 and non["any_lower"] == 1),
            "known_ai_only": float(ai["any_lower"] == 1 and non["any_upper"] == 0),
            "known_non_api_only": float(ai["any_upper"] == 0 and non["any_lower"] == 1),
            "known_neither": float(ai["any_upper"] == 0 and non["any_upper"] == 0),
        })
    primary_assumption = estimate_field(records, freeze, "any_lower_assumption_difference")
    primary_lower = estimate_field(records, freeze, "any_identified_lower")
    primary_upper = estimate_field(records, freeze, "any_identified_upper")
    if primary_lower["estimate"] > primary_upper["estimate"] + 1e-12:
        raise ValueError("Partial-identification bounds inverted")
    group_rates = {
        group: {
            metric: estimate(
                {h: [record["ai" if group == "AI_API" else "non"][metric] for record in records if record["stratum"] == h] for h in STRATA},
                freeze,
            )
            for metric in ("any_lower", "any_upper", "all_lower", "all_upper", "fraction_lower", "fraction_upper", "unresolved_fraction")
        }
        for group in GROUPS
    }
    secondary = {
        name: {
            "lower": estimate_field(records, freeze, f"{name}_identified_lower"),
            "upper": estimate_field(records, freeze, f"{name}_identified_upper"),
        }
        for name in ("all", "fraction")
    }
    known_cells = {name: estimate_field(records, freeze, name) for name in ("known_both", "known_ai_only", "known_non_api_only", "known_neither")}
    known_sum = sum(value["estimate"] for value in known_cells.values())
    weighted_unknown_share = max(0.0, 1 - known_sum)
    outcome_counts = collections.Counter(row["outcome"] for row in labels.values())
    auth_counts = collections.Counter(row["outcome"] for row in labels.values() if row["auth_visible"])
    one_hop_counts = collections.Counter(row["outcome"] for row in labels.values() if row["one_hop_pdf"])
    packet_outcomes = {
        path.name: dict(collections.Counter(row["outcome"] for row in read_jsonl(path)))
        for path in args.logs
    }

    recode_result = None
    if args.recode:
        recode_packet = json.loads((R / freeze["recode"]["packet_name"]).read_text(encoding="utf-8"))
        recode_expected = {row["code"]: row["url"] for row in recode_packet}
        recoded = load_labels([args.recode], recode_expected)
        confusion = collections.Counter((labels[code]["outcome"], row["outcome"]) for code, row in recoded.items())
        recode_result = {
            "url_count": len(recoded),
            "exact_outcome_agreement": sum(labels[code]["outcome"] == row["outcome"] for code, row in recoded.items()) / len(recoded),
            "confusion": {f"primary_{a}__recode_{b}": n for (a, b), n in sorted(confusion.items())},
            "note": "Two AI-assisted browser passes; agreement is not human-ground-truth accuracy. Primary labels are not replaced by recode labels.",
        }
    result = {
        "analysis_kind": "newwave_stratified_samepost_browser_validation",
        "input_sha256": {
            "freeze": digest_file(args.freeze),
            "key": digest_file(args.key),
            "logs": {path.name: digest_file(path) for path in args.logs},
            "recode": digest_file(args.recode) if args.recode else None,
            "analysis_script": digest_file(Path(__file__)),
        },
        "target_population_pairs": sum(freeze["sampling"]["strata"][h]["population_pairs"] for h in STRATA),
        "sampled_pairs": len(selected),
        "sampled_distinct_network_urls": len(labels),
        "strata": freeze["sampling"]["strata"],
        "browser_profile_caveat": "Visible study-browser-profile content, potentially with existing cookies; not anonymous-reader or independent factual-support validation.",
        "url_labels": {
            "outcomes": dict(outcome_counts),
            "by_reviewer_packet": packet_outcomes,
            "auth_visible_by_outcome": dict(auth_counts),
            "one_hop_pdf_by_outcome": dict(one_hop_counts),
        },
        "primary_any_source": {
            "unresolved_as_inaccessible_pair_difference": primary_assumption,
            "partial_identification_lower": primary_lower,
            "partial_identification_upper": primary_upper,
            "approx_bonferroni_95_outer_interval_for_identified_set": [
                max(-1.0, primary_lower["estimate"] - Z_BONFERRONI * primary_lower["design_se"]),
                min(1.0, primary_upper["estimate"] + Z_BONFERRONI * primary_upper["design_se"]),
            ],
            "method": "Within each machine-defined paired-any-open stratum, sample pairs without replacement; use N_h/n_h weights and finite-population design variance. Unknown URL content yields worst-case endpoint bounds rather than complete-case deletion.",
        },
        "group_note_outcome_rates": group_rates,
        "secondary_paired_differences": secondary,
        "pair_discordance_definitely_known_weighted_shares": {
            **{name: row["estimate"] for name, row in known_cells.items()},
            "undetermined": weighted_unknown_share,
        },
        "recode": recode_result,
        "limitations": [
            "Same-post current-Helpful selection is a conditional population, not a causal AI-versus-human experiment.",
            "The design-based SE captures sampling of post pairs; it does not capture browser-judge error, temporal site change, or AI-writer dependence.",
            "No intended-content label proves that a citation supports the note's proposition.",
            "Unresolved outcomes remain bounds; complete cases are not treated as a random sample.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "sampled_pairs": len(selected), "urls": len(labels), "point_lower_assumption": primary_assumption["estimate"], "identified_bounds": [primary_lower["estimate"], primary_upper["estimate"]]}))


if __name__ == "__main__":
    main()
