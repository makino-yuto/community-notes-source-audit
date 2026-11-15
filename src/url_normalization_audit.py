"""Post-hoc audit of syntax defects in the frozen Community Notes URL sample.

This script never changes the cohort or primary probes. Candidate URLs are
hypotheses for a separate re-probe, not corrected primary observations.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import html
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COHORT = ROOT / "results" / "cohort_2026-11-14.json"
DEFAULT_PROBES = ROOT / "results" / "probes_2026-11-15.jsonl"
DEFAULT_CANDIDATES = ROOT / "results" / "url_normalization_candidates.jsonl"
DEFAULT_REPORT = ROOT / "results" / "url_normalization_audit.md"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact_url(url: str) -> str:
    """Hide query values in the human-readable report."""
    parsed = urlsplit(url)
    path = parsed.path
    if len(path) > 70:
        path = path[:67] + "..."
    return parsed.netloc + path + ("?[query]" if parsed.query else "")


def load_probes(path: Path) -> dict[str, dict]:
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            key = str(row["note_id"])
            if key in rows:
                raise ValueError(f"Duplicate probe note_id: {key}")
            rows[key] = row
    return rows


def candidate_for(note: dict) -> tuple[list[str], str | None, str | None]:
    url = note["selected_url"]
    flags: list[str] = []
    candidate = None
    candidate_kind = None

    if re.search(r"&(?:amp|lt|gt|quot|apos|#[0-9]+|#x[0-9a-f]+);", url, re.I):
        flags.append("html_entity")
        candidate = html.unescape(url)
        candidate_kind = "html_unescape"

    # The extraction regex excludes parentheses. Recover only an immediately
    # adjacent balanced parenthetical present in the original note summary.
    suffix = note["summary"].split(url, 1)[1] if url in note["summary"] else ""
    match = re.match(r"\([^()\s<>]{1,100}\)", suffix)
    if match:
        flags.append("truncated_parenthesis")
        candidate = url + match.group()
        candidate_kind = "restore_parenthesis"

    # The BBC AMP links repeat in this frozen sample. Removing .amp is only a
    # canonicalization hypothesis; the replacement must be directly re-probed.
    parsed = urlsplit(url)
    if parsed.hostname in {"www.bbc.com", "bbc.com"} and parsed.path.endswith(".amp"):
        flags.append("bbc_amp_suffix")
        candidate = urlunsplit(parsed._replace(path=parsed.path[:-4]))
        candidate_kind = "bbc_remove_amp_suffix"

    # A full-width closing parenthesis followed by Japanese prose was captured
    # as URL text in one sample row. Keep this conservative and reviewable.
    fullwidth_close = url.find("）")
    if fullwidth_close != -1:
        flags.append("cjk_trailing_prose")
        candidate = url[:fullwidth_close]
        candidate_kind = "trim_cjk_trailing_prose"

    if re.search(r"%(?![0-9a-fA-F]{2})", url):
        flags.append("invalid_percent_escape")
    if "\ufffd" in url:
        flags.append("replacement_character")
    if any(ord(c) < 32 for c in url):
        flags.append("control_character")
    if parsed.path in {"", "/"} and not parsed.query:
        flags.append("generic_homepage_candidate")

    if candidate == url:
        candidate = None
        candidate_kind = None
    return flags, candidate, candidate_kind


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--probes", type=Path, default=DEFAULT_PROBES)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    cohort = json.loads(args.cohort.read_text(encoding="utf-8"))
    notes = cohort["matched"]
    probes = load_probes(args.probes)
    if {str(n["note_id"]) for n in notes} != set(probes):
        raise ValueError("Cohort/probe note IDs differ")

    rows = []
    by_url = collections.defaultdict(list)
    for note in notes:
        note_id = str(note["note_id"])
        probe = probes[note_id]
        url = note["selected_url"]
        if probe.get("url") != url:
            raise ValueError(f"Frozen URL/probe mismatch for {note_id}")
        by_url[url].append(note_id)
        flags, candidate, candidate_kind = candidate_for(note)
        if flags:
            rows.append({
                "note_id": note_id,
                "group": note["author_type"],
                "flags": flags,
                "baseline_category": probe["category"],
                "original_url": url,
                "candidate_url": candidate,
                "candidate_kind": candidate_kind,
                "requires_reprobe": candidate is not None,
            })

    args.candidates.parent.mkdir(parents=True, exist_ok=True)
    with args.candidates.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")

    defects = [r for r in rows if r["candidate_url"]]
    flag_counts = collections.Counter((r["group"], flag) for r in rows for flag in r["flags"])
    duplicate_families = [(url, ids) for url, ids in by_url.items() if len(ids) > 1]
    duplicate_families.sort(key=lambda item: (-len(item[1]), item[0]))
    ai_open = sum(probes[str(n["note_id"])]["category"] == "open_candidate" for n in notes if n["author_type"] == "AI_API")
    human_open = sum(probes[str(n["note_id"])]["category"] == "open_candidate" for n in notes if n["author_type"] == "non_API")
    potentially_changed = collections.Counter(r["group"] for r in defects if r["baseline_category"] != "open_candidate")
    md = [
        "# Post-hoc URL normalization audit",
        "",
        f"Frozen cohort SHA-256: `{sha256(args.cohort)}`. Primary probes SHA-256: `{sha256(args.probes)}`.",
        "",
        "This audit was performed after primary probing. Original observations remain the primary result. A candidate is not an observed successful URL until directly re-probed and reviewed for intended content.",
        "",
        f"Primary machine-only open counts: AI API {ai_open}/300; non-API {human_open}/300; difference {(ai_open-human_open)/3:.2f} percentage points.",
        f"Syntax-correction candidates: {len(defects)} notes ({len({r['candidate_url'] for r in defects})} distinct corrected URLs). Defect rows currently not open: AI API {potentially_changed['AI_API']}; non-API {potentially_changed['non_API']}.",
        "",
        "## Flag counts",
        "",
        "| Group | Flag | Notes |",
        "| :-- | :-- | --: |",
    ]
    md += [f"| {group} | {flag} | {count} |" for (group, flag), count in sorted(flag_counts.items())]
    md += ["", "## Affected notes", "", "| Note ID | Group | Flag(s) | Frozen result | Original host/path | Candidate host/path |", "| :-- | :-- | :-- | :-- | :-- | :-- |"]
    for row in rows:
        md.append("| " + " | ".join((
            row["note_id"], row["group"], ", ".join(row["flags"]), row["baseline_category"],
            compact_url(row["original_url"]), compact_url(row["candidate_url"]) if row["candidate_url"] else "—",
        )) + " |")
    md += ["", "## Exact repeated URLs", "", "| Notes | URL host/path | Note IDs and groups | Frozen results |", "| --: | :-- | :-- | :-- |"]
    for url, ids in duplicate_families:
        groups = [next(n["author_type"] for n in notes if str(n["note_id"]) == note_id) for note_id in ids]
        outcomes = [probes[note_id]["category"] for note_id in ids]
        md.append(f"| {len(ids)} | {compact_url(url)} | {', '.join(f'{id_} ({g})' for id_, g in zip(ids, groups))} | {', '.join(outcomes)} |")
    md += [
        "", "## Sensitivity plan", "",
        "1. Re-probe only syntax-correction candidates with the same GET classifier. Keep original URL, original result, corrected URL, corrected result, timestamps, and reason side by side. Never overwrite frozen records.",
        "2. Manually verify that any corrected 2xx response is the intended article/page, not a generic homepage, soft 404, challenge page, or unrelated redirect. Keep unresolved cases uncertain.",
        "3. Report the frozen primary contrast, then a clearly post-hoc corrected contrast using only verified corrections. Also report bounds: if every currently non-open correction candidate became open, the contrast would shift by the group-specific candidate counts above divided by 300.",
        "4. Report exact-URL duplicate families and a unique-URL sensitivity, while retaining the note-weighted primary estimand. The repeated BBC `.amp` link contributes three non-API notes, so a single URL failure must not be described as three independent source failures.",
        "5. Separately inspect source role and soft-404 outcomes in a blinded sample, and use author-cluster sensitivity because AI API notes are concentrated in a few writers.",
        "",
    ]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {args.candidates} ({len(rows)} flagged rows, {len(defects)} candidates)")
    print(f"Wrote {args.report} ({len(duplicate_families)} duplicate URL families)")


if __name__ == "__main__":
    main()
