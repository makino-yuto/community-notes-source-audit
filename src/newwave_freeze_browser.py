"""Freeze a stratified, all-citation browser-validation packet before viewing pages.

The machine-probe log must already be complete. The three public-to-reviewer
packets contain only opaque URL codes and network URLs. Pair identities, group
labels, machine classes, strata, and weights remain in a private key.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from urllib.parse import urldefrag

from newwave_analyze_machine import digest_file, digest_text, load_inputs


ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"
CANDIDATES = R / "revision_samepost_candidates_v2_PRIVATE.jsonl"
PROBE_MANIFEST = R / "newwave_probe_manifest_PRIVATE.json"
PROBES = R / "newwave_probe_PRIVATE.jsonl"
PROTOCOL = R / "newwave_protocol_frozen.json"
OUT_MANIFEST = R / "newwave_browser_freeze.json"
KEY = R / "newwave_browser_key_PRIVATE.json"
PACKETS = [R / f"newwave_browser_packet_{letter}.json" for letter in "abc"]
RECODE_PACKET = R / "newwave_browser_recode_packet.json"
STRATA = ("both", "ai_only", "non_api_only", "neither")
SAMPLE_SEED = 2026111508
PACKET_SEED = 2026111511
RECODE_SEED = 2026111512
PER_STRATUM = 60


def unique_network_urls(note: dict) -> list[str]:
    return sorted({urldefrag(link["normalized_url"]).url for link in note["external_urls"]})


def machine_any(note: dict, probes: dict[str, dict]) -> bool:
    return any(probes[digest_text(url)]["category"] == "open_candidate" for url in unique_network_urls(note))


def write_exclusive(path: Path, payload: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidates", type=Path, default=CANDIDATES)
    ap.add_argument("--probe-manifest", type=Path, default=PROBE_MANIFEST)
    ap.add_argument("--probes", type=Path, default=PROBES)
    ap.add_argument("--protocol", type=Path, default=PROTOCOL)
    args = ap.parse_args()
    outputs = [OUT_MANIFEST, KEY, RECODE_PACKET, *PACKETS]
    if any(path.exists() for path in outputs):
        raise FileExistsError("A browser freeze output already exists; inspect before retrying")
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    expected = protocol["input_sha256"].get("results\\revision_samepost_candidates_v2_PRIVATE.jsonl")
    if expected != digest_file(args.candidates):
        raise ValueError("Candidate file does not match final research protocol")
    candidates, probes, probe_manifest = load_inputs(args.candidates, args.probe_manifest, args.probes)
    if len(candidates) != protocol["sampling_frame"]["pairs"]:
        raise ValueError("Pair frame size does not match final research protocol")
    frame = defaultdict(list)
    for pair in candidates:
        ai = machine_any(pair["ai"], probes)
        non = machine_any(pair["non_api"], probes)
        stratum = "both" if ai and non else "ai_only" if ai else "non_api_only" if non else "neither"
        frame[stratum].append(pair)
    rng = random.Random(SAMPLE_SEED)
    chosen = []
    stratum_sizes = {}
    for stratum in STRATA:
        ordered = sorted(frame[stratum], key=lambda p: str(p["post_id"]))
        count = min(PER_STRATUM, len(ordered))
        sample = rng.sample(ordered, count)
        stratum_sizes[stratum] = {"population_pairs": len(ordered), "sampled_pairs": count}
        for pair in sample:
            chosen.append((stratum, pair))
    chosen.sort(key=lambda item: str(item[1]["post_id"]))
    if not chosen:
        raise ValueError("No browser pairs selected")
    if len({str(pair["post_id"]) for _, pair in chosen}) != len(chosen):
        raise ValueError("Duplicate browser post pair")

    all_urls = sorted({url for _, pair in chosen for group in ("ai", "non_api") for url in unique_network_urls(pair[group])})
    url_rng = random.Random(PACKET_SEED)
    url_rng.shuffle(all_urls)
    url_code = {url: f"W{index:04d}" for index, url in enumerate(all_urls, 1)}
    packets: list[list[dict]] = [[], [], []]
    for index, url in enumerate(all_urls):
        packets[index % 3].append({"code": url_code[url], "url": url})
    for packet in packets:
        packet.sort(key=lambda row: row["code"])

    selected_pairs = []
    for index, (stratum, pair) in enumerate(chosen, 1):
        groups = {}
        for group, name in (("AI_API", "ai"), ("non_API", "non_api")):
            note = pair[name]
            urls = unique_network_urls(note)
            groups[group] = {
                "note_id": str(note["note_id"]),
                "author_id": str(note["author_id"]),
                "network_url_codes": [url_code[url] for url in urls],
                "citation_variant_count": len(note["external_urls"]),
                "machine_categories": {url_code[url]: probes[digest_text(url)]["category"] for url in urls},
            }
        selected_pairs.append({
            "pair_code": f"B{index:04d}",
            "post_id": str(pair["post_id"]),
            "stratum": stratum,
            "weight": stratum_sizes[stratum]["population_pairs"] / stratum_sizes[stratum]["sampled_pairs"],
            "groups": groups,
        })
    recode_rng = random.Random(RECODE_SEED)
    recode_pairs = sorted(recode_rng.sample(selected_pairs, min(30, len(selected_pairs))), key=lambda pair: pair["pair_code"])
    recode_codes = {
        code for pair in recode_pairs for group in ("AI_API", "non_API")
        for code in pair["groups"][group]["network_url_codes"]
    }
    recode_packet = sorted(({"code": url_code[url], "url": url} for url in all_urls if url_code[url] in recode_codes), key=lambda row: row["code"])
    key = {
        "schema": "newwave-browser-key-v1",
        "selected_pairs": selected_pairs,
        "recode_pair_codes": [pair["pair_code"] for pair in recode_pairs],
        "url_lookup": sorted(({"code": url_code[url], "url": url, "url_sha256": digest_text(url)} for url in all_urls), key=lambda row: row["code"]),
    }
    for path, payload in zip(PACKETS, packets):
        write_exclusive(path, payload)
    write_exclusive(RECODE_PACKET, recode_packet)
    write_exclusive(KEY, key)
    freeze = {
        "schema": "newwave-browser-freeze-v1",
        "protocol_sha256": digest_file(args.protocol),
        "candidate_sha256": digest_file(args.candidates),
        "probe_manifest_sha256": digest_file(args.probe_manifest),
        "probe_log_sha256": digest_file(args.probes),
        "freeze_script_sha256": digest_file(Path(__file__)),
        "analysis_script_sha256": digest_file(ROOT / "src" / "newwave_analyze_browser.py"),
        "sampling": {
            "unit": "post_pair",
            "strata": stratum_sizes,
            "seed": SAMPLE_SEED,
            "per_stratum_cap": PER_STRATUM,
            "sampled_post_pairs": len(selected_pairs),
            "distinct_network_urls": len(all_urls),
            "rules": "Within each predeclared paired machine-any-open stratum, sort original post IDs and draw min(60,N_h) with one seeded Python Random instance in fixed stratum order; inspect every defragmented external network URL in both selected notes; globally deduplicate URLs.",
        },
        "packets": {path.name: {"count": len(packet), "sha256": digest_file(path)} for path, packet in zip(PACKETS, packets)},
        "key": {"name": KEY.name, "sha256": digest_file(KEY)},
        "recode": {"pair_sample_seed": RECODE_SEED, "selected_pairs": len(recode_pairs), "packet_name": RECODE_PACKET.name, "packet_count": len(recode_packet), "packet_sha256": digest_file(RECODE_PACKET)},
        "browser_label_schema": {
            "required": ["code", "url", "outcome", "reason", "title", "final_url", "utc", "evidence", "auth_visible", "one_hop_pdf"],
            "outcome_values": ["accessible", "not_accessible", "unresolved"],
            "criterion": "Visible substantive intended article, document, media or structured data; title, metadata, teaser, wrong target, unavailable video and challenge are not accessible. One obvious linked full-report PDF may be opened and flagged. One normal retry for blank/error. No login, challenge bypass or story-view notification.",
        },
        "interpretation": "Study-browser-profile access, possibly affected by cookies; not general anonymous human access or evidence support.",
    }
    write_exclusive(OUT_MANIFEST, freeze)
    print(json.dumps({"pairs": len(selected_pairs), "urls": len(all_urls), "packets": [len(p) for p in packets], "recode_urls": len(recode_packet), "manifest": str(OUT_MANIFEST)}))


if __name__ == "__main__":
    main()
