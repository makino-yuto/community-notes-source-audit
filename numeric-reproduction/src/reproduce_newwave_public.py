"""Recompute the published new-wave numeric results from anonymous pair tables.

Usage: python src/reproduce_newwave_public.py [--output result.json]
Requires only the Python standard library and this package's CSV/manifest files.
No private keys, original posts, URLs, internet requests or model API are used.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
Z = 1.959963984540054
Z_BONF = 2.241402727604947
STRATA = ("both", "ai_only", "non_api_only", "neither")
PREFIXES = ("ai", "non")
VARIANTS = ("baseline", "auth_unknown", "abstract_unknown", "pdf_unknown", "all_three_unknown")


def read_csv(path: Path, metadata: dict) -> list[dict]:
    assert hashlib.sha256(path.read_bytes()).hexdigest() == metadata["sha256"], path
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames == metadata["columns"], path
        result = list(reader)
    assert len(result) == metadata["rows"], path
    return result


def proportion(value: str) -> float:
    result = float(value)
    assert math.isfinite(result) and 0 <= result <= 1
    return result


def bit(value: str) -> int:
    assert value in ("0", "1")
    return int(value)


def estimate(values: dict[str, list[float]], frame: dict) -> dict:
    """Stratified finite-population mean and design SE from pair-level sums."""
    N_total = sum(frame[h]["population_pairs"] for h in STRATA)
    mean = variance = 0.0
    for h in STRATA:
        N_h = frame[h]["population_pairs"]
        n_h = frame[h]["sampled_pairs"]
        observed = values[h]
        assert len(observed) == n_h and 2 <= n_h <= N_h
        sx = sum(observed)
        sx2 = sum(x*x for x in observed)
        mean += (N_h/N_total) * (sx/n_h)
        variance += (N_h/N_total)**2 * (1 - n_h/N_h) * (sx2 - sx*sx/n_h)/(n_h*(n_h-1))
    se = math.sqrt(max(0.0, variance))
    return {"estimate": mean, "design_se": se, "normal_95": [mean-Z*se, mean+Z*se]}


def from_pairs(rows: list[dict], frame: dict, fn) -> dict:
    return estimate({h: [fn(row) for row in rows if row["stratum"] == h] for h in STRATA}, frame)


def analyze_machine(rows: list[dict]) -> dict:
    assert len(rows) == 1882
    normalized = []
    for raw in rows:
        row = {}
        for p in PREFIXES:
            row[f"{p}_urls"] = int(raw[f"{p}_urls"])
            for name in ("any_open", "all_open", "fixed_single_open"):
                row[f"{p}_{name}"] = bit(raw[f"{p}_{name}"])
            for name in ("open_fraction", "redundancy_random_single"):
                row[f"{p}_{name}"] = proportion(raw[f"{p}_{name}"])
            n = row[f"{p}_urls"]
            fraction = row[f"{p}_open_fraction"]
            assert n >= 1
            assert math.isclose(fraction*n, round(fraction*n), abs_tol=1e-12)
            k = round(fraction*n)
            assert 0 <= k <= n
            assert row[f"{p}_any_open"] == int(k > 0)
            assert row[f"{p}_all_open"] == int(k == n)
            assert math.isclose(row[f"{p}_redundancy_random_single"], int(k > 0)-fraction, abs_tol=1e-14)
        normalized.append(row)

    def summary(subset):
        n = len(subset)
        assert n > 0
        metrics = ("urls", "any_open", "all_open", "open_fraction", "fixed_single_open", "redundancy_random_single")
        means = {p: {m: sum(row[f"{p}_{m}"] for row in subset)/n for m in metrics} for p in PREFIXES}
        differences = {m: means["ai"][m]-means["non"][m] for m in metrics}
        cells = collections.Counter((r["ai_any_open"], r["non_any_open"]) for r in subset)
        return {
            "pairs": n, "means": means, "AI_API_minus_non_API": differences,
            "any_open_pair_cells": {"both": cells[1,1], "ai_only": cells[1,0], "non_api_only": cells[0,1], "neither": cells[0,0]},
        }

    return {
        "overall": summary(normalized),
        "url_count_pair_cells": {
            "AI_more": sum(r["ai_urls"] > r["non_urls"] for r in normalized),
            "equal": sum(r["ai_urls"] == r["non_urls"] for r in normalized),
            "non_API_more": sum(r["ai_urls"] < r["non_urls"] for r in normalized),
        },
        "note": "Complete fixed same-post frame; machine open is a transport/content proxy, not substantive browser access or claim support.",
    }


def analyze_browser(rows: list[dict], frame: dict) -> dict:
    assert len(rows) == 240
    assert collections.Counter(r["stratum"] for r in rows) == {h: frame[h]["sampled_pairs"] for h in STRATA}
    for row in rows:
        for p in PREFIXES:
            for name in ("any", "all", "fraction"):
                lower = proportion(row[f"{p}_{name}_lower"])
                upper = proportion(row[f"{p}_{name}_upper"])
                assert lower <= upper
            for variant in VARIANTS[1:]:
                lo = proportion(row[f"{p}_any_lower_{variant}"])
                hi = proportion(row[f"{p}_any_upper_{variant}"])
                assert lo <= hi

    def metric(row, prefix, name, side, variant):
        suffix = "" if variant == "baseline" else f"_{variant}"
        return float(row[f"{prefix}_{name}_{side}{suffix}"])

    def paired(name, variant="baseline"):
        lower = from_pairs(rows, frame, lambda r: metric(r,"ai",name,"lower",variant)-metric(r,"non",name,"upper",variant))
        upper = from_pairs(rows, frame, lambda r: metric(r,"ai",name,"upper",variant)-metric(r,"non",name,"lower",variant))
        point = from_pairs(rows, frame, lambda r: metric(r,"ai",name,"lower",variant)-metric(r,"non",name,"lower",variant))
        assert lower["estimate"] <= upper["estimate"]
        return {
            "identified_lower": lower,
            "identified_upper": upper,
            "unresolved_as_inaccessible": point,
            "approx_bonferroni_95_outer_interval": [
                max(-1.0, lower["estimate"]-Z_BONF*lower["design_se"]),
                min(1.0, upper["estimate"]+Z_BONF*upper["design_se"]),
            ],
        }

    group = {
        p: {name: {side: from_pairs(rows, frame, lambda r,p=p,name=name,side=side: metric(r,p,name,side,"baseline"))
                    for side in ("lower","upper")} for name in ("any","all","fraction")}
        for p in PREFIXES
    }
    known = {
        "both": from_pairs(rows,frame,lambda r:int(r["ai_any_lower"]=="1" and r["non_any_lower"]=="1")),
        "ai_only": from_pairs(rows,frame,lambda r:int(r["ai_any_lower"]=="1" and r["non_any_upper"]=="0")),
        "non_api_only": from_pairs(rows,frame,lambda r:int(r["ai_any_upper"]=="0" and r["non_any_lower"]=="1")),
        "neither": from_pairs(rows,frame,lambda r:int(r["ai_any_upper"]=="0" and r["non_any_upper"]=="0")),
    }
    known["undetermined_estimate"] = 1-sum(known[h]["estimate"] for h in ("both","ai_only","non_api_only","neither"))
    return {
        "sampled_pairs": 240,
        "target_pairs": sum(frame[h]["population_pairs"] for h in STRATA),
        "group_rates": group,
        "paired_any_source": paired("any"),
        "paired_all_sources": paired("all"),
        "paired_source_fraction": paired("fraction"),
        "known_pair_cells": known,
        "sensitivities": {variant: paired("any",variant) for variant in VARIANTS[1:]},
        "note": "Stratum-weighted pair sampling with finite-population variance. Unresolved citations bound access; intervals omit AI judgment error, network time change, and generalization beyond the fixed frame.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional JSON output path; stdout otherwise")
    args = parser.parse_args()
    manifest = json.loads((BASE/"manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "newwave-public-numeric-v1"
    files = manifest["files"]
    machine_rows = read_csv(BASE/"data/machine_pairs_anonymous.csv", files["data/machine_pairs_anonymous.csv"])
    browser_rows = read_csv(BASE/"data/browser_pairs_anonymous.csv", files["data/browser_pairs_anonymous.csv"])
    result = {
        "analysis_kind": "newwave_anonymous_numeric_reproduction",
        "source_file_sha256": {name: meta["sha256"] for name,meta in files.items()},
        "machine": analyze_machine(machine_rows),
        "browser": analyze_browser(browser_rows, manifest["browser_population_strata"]),
        "browser_url_label_counts_aggregate_only": manifest["browser_url_label_counts_aggregate_only"],
        "browser_recode_aggregate_only": manifest["browser_recode_aggregate_only"],
        "machine_robustness_aggregate_only": manifest["machine_robustness_aggregate_only"],
        "scope": "These anonymous pair tables reproduce numeric results. They do not expose source URLs, texts or historical page bodies, so they cannot independently re-audit source semantics or browser accessibility.",
    }
    text = json.dumps(result, indent=2, ensure_ascii=False)+"\n"
    if args.output:
        assert not args.output.exists(), "Refusing to overwrite existing output"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
