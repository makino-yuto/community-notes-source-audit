"""Analyze the frozen same-post, all-external-citation machine-probe wave.

The input is a census of selected AI-API/non-API currently Helpful note pairs,
not a randomized AI-writing experiment. HTTP categories are provisional and
cannot establish intended-page access or support. This script emits aggregate
results only; note text, URLs, author IDs, and pair-level outcomes remain local.

Run only after the pair frame, probe manifest, and complete probe log are frozen.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import random
from pathlib import Path
from urllib.parse import urldefrag, urlsplit


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
CANDIDATES = RESULTS / "revision_samepost_candidates_v2_PRIVATE.jsonl"
MANIFEST = RESULTS / "newwave_probe_manifest_PRIVATE.json"
PROBES = RESULTS / "newwave_probe_PRIVATE.jsonl"
OUTPUT = RESULTS / "newwave_machine_aggregate.json"
CATEGORIES = {"open_candidate", "access_barrier", "gone_candidate", "transient_uncertain"}
GROUPS = ("AI_API", "non_API")
METRICS = ("any_open", "all_open", "open_fraction", "fixed_single_open", "redundancy_vs_random_single", "redundancy_vs_fixed_single")
SINGLE_SEED = "2026111509"
BOOTSTRAP_SEED = 2026111510


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    out = []
    with path.open(encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                raise ValueError(f"Empty JSONL line: {path.name}:{line_no}")
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError(f"Non-object JSONL line: {path.name}:{line_no}")
            out.append(item)
    return out


def percentile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("Empty percentile")
    ordered = sorted(values)
    k = (len(ordered) - 1) * probability
    lo = math.floor(k)
    hi = math.ceil(k)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def fixed_single_url(note_id: str, network_urls: list[str]) -> str:
    """Select a fixed one-link baseline independently of probe outcomes.

    The URL with minimum SHA-256 of UTF-8 text
    ``2026111509|<note_id>|<defragmented_network_url>`` wins. The network URL
    breaks a hypothetical digest tie. Citation fragments do not create extra
    independent HTTP paths, and repeated references within a note count once.
    """
    return min(network_urls, key=lambda url: (digest_text(f"{SINGLE_SEED}|{note_id}|{url}"), url))


def load_inputs(candidate_path: Path, manifest_path: Path, probe_path: Path) -> tuple[list[dict], dict[str, dict], dict]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "samepost-allurl-probe-manifest-v1":
        raise ValueError("Unexpected probe manifest schema")
    if manifest.get("candidate_sha256") != digest_file(candidate_path):
        raise ValueError("Candidate file changed after probe manifest freeze")
    candidates = read_jsonl(candidate_path)
    if len(candidates) != manifest.get("pair_count"):
        raise ValueError("Pair count differs from frozen probe manifest")
    manifest_rows = manifest.get("urls")
    if not isinstance(manifest_rows, list) or len(manifest_rows) != manifest.get("unique_url_count"):
        raise ValueError("Malformed probe manifest URL list")
    url_by_hash = {}
    for row in manifest_rows:
        url = row.get("url")
        url_hash = row.get("url_sha256")
        if not isinstance(url, str) or url_hash != digest_text(url):
            raise ValueError("Malformed probe manifest URL hash")
        if url_hash in url_by_hash:
            raise ValueError("Duplicate URL hash in probe manifest")
        url_by_hash[url_hash] = url

    probes = {}
    for row in read_jsonl(probe_path):
        url_hash = row.get("url_sha256")
        url = row.get("url")
        if url_hash not in url_by_hash or url != url_by_hash[url_hash]:
            raise ValueError("Probe row is outside frozen URL manifest")
        if url_hash in probes:
            raise ValueError("Duplicate URL probe")
        if row.get("category") not in CATEGORIES:
            raise ValueError("Unexpected machine category")
        probes[url_hash] = row
    if set(probes) != set(url_by_hash):
        raise ValueError(f"Incomplete URL probe coverage: {len(probes)}/{len(url_by_hash)}")
    return candidates, probes, manifest


def note_record(note: dict, probes: dict[str, dict]) -> dict:
    links = note.get("external_urls")
    if not isinstance(links, list) or not links:
        raise ValueError("Eligible note lacks external citations")
    citation_urls = []
    for link in links:
        citation = link.get("normalized_url")
        if not isinstance(citation, str) or not citation:
            raise ValueError("Malformed citation URL")
        citation_urls.append(citation)
    if len(citation_urls) != len(set(citation_urls)):
        raise ValueError("Duplicate normalized citation in a note")
    network_urls = sorted({urldefrag(url).url for url in citation_urls})
    if any(not url for url in network_urls):
        raise ValueError("Empty defragmented network URL")
    categories = [probes[digest_text(url)]["category"] for url in network_urls]
    opened = [int(category == "open_candidate") for category in categories]
    open_count = sum(opened)
    network_count = len(network_urls)
    chosen = fixed_single_url(str(note["note_id"]), network_urls)
    single_open = int(probes[digest_text(chosen)]["category"] == "open_candidate")
    any_open = int(open_count > 0)
    fraction = open_count / network_count
    hosts = {(urlsplit(url).hostname or "").lower().removeprefix("www.") for url in network_urls}
    return {
        "citation_variant_count": len(citation_urls),
        "network_url_count": network_count,
        "network_urls": set(network_urls),
        "distinct_host_count": len(hosts),
        "category_counts": collections.Counter(categories),
        "author_id": str(note["author_id"]),
        "metrics": {
            "any_open": any_open,
            "all_open": int(open_count == network_count),
            "open_fraction": fraction,
            "fixed_single_open": single_open,
            "redundancy_vs_random_single": any_open - fraction,
            "redundancy_vs_fixed_single": any_open - single_open,
        },
    }


def paired_summary(pairs: list[dict]) -> dict:
    n = len(pairs)
    if not n:
        return {"pairs": 0}
    means = {
        group: {metric: sum(pair[group]["metrics"][metric] for pair in pairs) / n for metric in METRICS}
        for group in GROUPS
    }
    difference = {metric: means["AI_API"][metric] - means["non_API"][metric] for metric in METRICS}
    cells = collections.Counter(
        (pair["AI_API"]["metrics"]["any_open"], pair["non_API"]["metrics"]["any_open"])
        for pair in pairs
    )
    return {
        "pairs": n,
        "means": means,
        "ai_minus_non_api": difference,
        "any_open_discordance": {
            "both_open": cells[(1, 1)],
            "ai_only_open": cells[(1, 0)],
            "non_api_only_open": cells[(0, 1)],
            "neither_open": cells[(0, 0)],
        },
    }


def pair_bootstrap(pairs: list[dict], draws: int) -> dict:
    """Exploratory post bootstrap; the observed eligible frame is itself a census."""
    if draws < 100:
        raise ValueError("At least 100 bootstrap draws are required")
    n = len(pairs)
    rng = random.Random(BOOTSTRAP_SEED)
    ds = {metric: [pair["AI_API"]["metrics"][metric] - pair["non_API"]["metrics"][metric] for pair in pairs] for metric in METRICS}
    samples = {metric: [] for metric in METRICS}
    for _ in range(draws):
        indices = [rng.randrange(n) for _ in range(n)]
        for metric in METRICS:
            samples[metric].append(sum(ds[metric][i] for i in indices) / n)
    return {metric: [percentile(values, .025), percentile(values, .975)] for metric, values in samples.items()}


def author_sensitivity(pairs: list[dict]) -> dict:
    by_author = collections.defaultdict(list)
    for pair in pairs:
        by_author[pair["AI_API"]["author_id"]].append(pair)
    author_diffs = {}
    for author, subset in by_author.items():
        author_diffs[author] = {
            metric: sum(p["AI_API"]["metrics"][metric] - p["non_API"]["metrics"][metric] for p in subset) / len(subset)
            for metric in METRICS
        }
    author_equal = {
        metric: sum(row[metric] for row in author_diffs.values()) / len(author_diffs)
        for metric in METRICS
    }
    total_n = len(pairs)
    total_d = {metric: sum(p["AI_API"]["metrics"][metric] - p["non_API"]["metrics"][metric] for p in pairs) for metric in METRICS}
    loo = {metric: [] for metric in METRICS}
    for subset in by_author.values():
        count = len(subset)
        if count == total_n:
            continue
        for metric in METRICS:
            removed = sum(p["AI_API"]["metrics"][metric] - p["non_API"]["metrics"][metric] for p in subset)
            loo[metric].append((total_d[metric] - removed) / (total_n - count))
    counts = sorted((len(subset) for subset in by_author.values()), reverse=True)
    return {
        "distinct_ai_authors": len(by_author),
        "top_1_share": counts[0] / total_n,
        "top_10_share": sum(counts[:10]) / total_n,
        "effective_ai_authors_inverse_hhi": 1 / sum((count / total_n) ** 2 for count in counts),
        "equal_ai_author_average_paired_difference": author_equal,
        "leave_one_ai_author_out_range": {metric: [min(values), max(values)] for metric, values in loo.items()},
        "note": "Equal-author and leave-one-author-out summaries change or perturb the post-weighted estimand; pseudonymous author IDs are intentionally omitted.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--probes", type=Path, default=PROBES)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--bootstrap", type=int, default=2000)
    args = parser.parse_args()
    if args.output.resolve() in {args.candidates.resolve(), args.manifest.resolve(), args.probes.resolve()}:
        raise ValueError("Aggregate output may not overwrite a private input")
    candidates, probes, manifest = load_inputs(args.candidates, args.manifest, args.probes)
    pairs = []
    seen_posts = set()
    used_network_hashes = set()
    for row in candidates:
        post_id = str(row.get("post_id", ""))
        if not post_id or post_id in seen_posts:
            raise ValueError("Missing or duplicate post identifier")
        seen_posts.add(post_id)
        ai = row["ai"]
        non = row["non_api"]
        if ai["group"] != "AI_API" or non["group"] != "non_API":
            raise ValueError("Unexpected cohort label")
        if str(ai["post_id"]) != post_id or str(non["post_id"]) != post_id:
            raise ValueError("Notes are not about the same post")
        ai_record = note_record(ai, probes)
        non_record = note_record(non, probes)
        used_network_hashes.update(digest_text(url) for url in ai_record["network_urls"] | non_record["network_urls"])
        pairs.append({
            "AI_API": ai_record,
            "non_API": non_record,
            "gap_hours": abs(int(ai["created_at_millis"]) - int(non["created_at_millis"])) / 3_600_000,
            "shared_network_url": bool(ai_record["network_urls"] & non_record["network_urls"]),
        })
    if used_network_hashes != set(probes):
        raise ValueError("Candidate citations do not match complete frozen URL manifest")

    overall = paired_summary(pairs)
    close = paired_summary([p for p in pairs if p["gap_hours"] <= 6])
    shared = paired_summary([p for p in pairs if p["shared_network_url"]])
    equal_count = paired_summary([p for p in pairs if p["AI_API"]["network_url_count"] == p["non_API"]["network_url_count"]])
    equal_count_by_size = {
        str(size): paired_summary([p for p in pairs if p["AI_API"]["network_url_count"] == p["non_API"]["network_url_count"] == size])
        for size in sorted({p["AI_API"]["network_url_count"] for p in pairs if p["AI_API"]["network_url_count"] == p["non_API"]["network_url_count"]})
    }
    citation_stats = {}
    for group in GROUPS:
        variants = [p[group]["citation_variant_count"] for p in pairs]
        networks = [p[group]["network_url_count"] for p in pairs]
        hosts = [p[group]["distinct_host_count"] for p in pairs]
        categories = sum((p[group]["category_counts"] for p in pairs), collections.Counter())
        citation_stats[group] = {
            "total_citation_variants": sum(variants),
            "total_note_network_url_references": sum(networks),
            "mean_citation_variants_per_note": sum(variants) / len(pairs),
            "mean_distinct_network_urls_per_note": sum(networks) / len(pairs),
            "mean_distinct_hosts_per_note": sum(hosts) / len(pairs),
            "network_url_count_distribution": dict(sorted(collections.Counter(networks).items())),
            "machine_category_counts_per_note_network_reference": dict(categories),
        }
    comparison = collections.Counter(
        "AI_more" if p["AI_API"]["network_url_count"] > p["non_API"]["network_url_count"]
        else "non_API_more" if p["AI_API"]["network_url_count"] < p["non_API"]["network_url_count"]
        else "equal"
        for p in pairs
    )
    result = {
        "analysis_kind": "newwave_samepost_all_external_citation_machine_proxy_census",
        "snapshot_date": "2026-11-14",
        "input_sha256": {
            "candidates": digest_file(args.candidates),
            "probe_manifest": digest_file(args.manifest),
            "probe_log": digest_file(args.probes),
            "analysis_script": digest_file(Path(__file__)),
        },
        "frame": {
            "selected_post_pairs": len(pairs),
            "selected_notes": 2 * len(pairs),
            "distinct_probed_network_urls": len(probes),
            "manifest_url_references": manifest["url_references"],
            "post_condition": "Both strictly eligible groups have a currently Helpful note on the same post; earliest created note per group selected before URL probes.",
        },
        "machine_proxy": {
            "positive": "open_candidate",
            "other_categories": sorted(CATEGORIES - {"open_candidate"}),
            "interpretation": "Open candidates are not verified intended pages or supporting evidence; non-open candidates include browser-readable barriers and unresolved requests.",
        },
        "single_url_baseline": {
            "fixed_hash_rule": f"minimum SHA-256 of UTF-8 '{SINGLE_SEED}|<note_id>|<defragmented_network_url>', URL tie-break",
            "random_single_expectation": "Within-note open fraction is the expected machine-open probability for one uniformly selected distinct network URL; redundancy_vs_random_single = any_open - open_fraction.",
        },
        "overall": overall,
        "exploratory_post_bootstrap_95": pair_bootstrap(pairs, args.bootstrap),
        "bootstrap_draws": args.bootstrap,
        "subgroups": {
            "created_within_6_hours": close,
            "shared_exact_network_url": shared,
            "equal_network_url_count": equal_count,
            "equal_network_url_count_by_size": equal_count_by_size,
        },
        "citations": citation_stats,
        "paired_network_url_count_comparison": dict(comparison),
        "ai_author_sensitivity": author_sensitivity(pairs),
        "limitations": [
            "Descriptive currently Helpful same-post cohort; not a causal effect of AI authorship or of adding citations.",
            "non_API is not verified human-written; observed API enrollment is a snapshot-constrained proxy.",
            "Machine-open status does not imply intended content, correct source role, semantic support, or current note truth.",
            "Same-post pairing does not align note propositions; authors and source choices remain different.",
            "The post bootstrap is exploratory superpopulation sensitivity; the eligible frame itself is a census.",
            "Citation fragments are retained as variants but collapse to one HTTP network path within a note.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "pairs": len(pairs), "unique_urls": len(probes), "any_open_difference": overall["ai_minus_non_api"]["any_open"]}))


if __name__ == "__main__":
    main()
