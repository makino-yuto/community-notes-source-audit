"""Frozen, bounded, unauthenticated all-URL probes for the same-post study.

Prepare a private URL-only manifest before looking at URL health. Running
requires the caller to provide that manifest's SHA-256, so a reviewed, frozen
plan cannot be silently changed. The script never assesses factual support.

Each distinct normalized URL is fetched at most once, plus one repeat when
the first machine result is not open. Redirect hops are counted separately.
All output, including URL queries and extracted text, is private.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit

import bs4
import probe_urls
import requests

from probe_urls import (
    CHALLENGE_MARKERS,
    CONNECT_TIMEOUT,
    MAX_BODY_BYTES,
    MAX_REDIRECTS,
    READ_TIMEOUT,
    USER_AGENT,
    extract_visible_text,
    sha256_text,
    validate_public_url,
)


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
DEFAULT_CANDIDATES = RESULTS / "revision_samepost_candidates_v2_PRIVATE.jsonl"
DEFAULT_MANIFEST = RESULTS / "newwave_probe_manifest_PRIVATE.json"
DEFAULT_OUTPUT = RESULTS / "newwave_probe_PRIVATE.jsonl"
DEFAULT_RUNLOG = RESULTS / "newwave_probe_runlog_PRIVATE.jsonl"
SEED = 2026111506
MAX_WORKERS = 6
HOST_INTERVAL_SECONDS = 1.0
GLOBAL_INTERVAL_SECONDS = 0.15
MAX_EXTRACTED_TEXT_CHARS = 120_000
BODY_DEADLINE_SECONDS = 30
REVIEW_FLAGS = frozenset({"unicode_path_query_or_fragment_review", "nonstandard_port"})
EXTRA_CHALLENGE_MARKERS = (
    "are you a robot?",
    "complete the captcha",
    "security verification",
    "datadome device check",
    "one more step",
)
HEX_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def append_jsonl(path: Path, obj: dict) -> None:
    """Append and sync one complete record; never rewrite an earlier record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(canonical_json(obj) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                raise ValueError(f"Blank JSONL line at {path}:{line_number}")
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Malformed JSONL at {path}:{line_number}; inspect before resuming") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Expected object at {path}:{line_number}")
            rows.append(row)
    return rows


def parse_candidates(path: Path, expected_pairs: int) -> tuple[list[dict], int, int]:
    """Extract only normalized URL data; never feed cohort labels to workers."""
    pairs = read_jsonl(path)
    if expected_pairs < 1 or len(pairs) != expected_pairs:
        raise ValueError(f"Expected {expected_pairs} frozen pairs, found {len(pairs)}")
    seen_posts: set[str] = set()
    urls: dict[str, dict] = {}
    references = 0
    for index, pair in enumerate(pairs, 1):
        post_id = str(pair.get("post_id", ""))
        if not post_id or post_id in seen_posts:
            raise ValueError(f"Missing or duplicate post_id in pair {index}")
        seen_posts.add(post_id)
        for side in ("ai", "non_api"):
            note = pair.get(side)
            if not isinstance(note, dict):
                raise ValueError(f"Missing {side} note in pair {index}")
            links = note.get("external_urls")
            if not isinstance(links, list) or not links:
                raise ValueError(f"Missing normalized external_urls in {side} note of pair {index}")
            seen_in_note: set[str] = set()
            for link in links:
                if not isinstance(link, dict):
                    raise ValueError(f"Expected URL record dict in {side} note of pair {index}")
                citation_url = link.get("normalized_url")
                if not isinstance(citation_url, str) or not citation_url:
                    raise ValueError(f"Missing normalized_url in {side} note of pair {index}")
                parsed = urlsplit(citation_url)
                if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                    raise ValueError(f"Invalid normalized URL in pair {index}")
                flags = link.get("flags", [])
                if not isinstance(flags, list) or any(not isinstance(flag, str) for flag in flags):
                    raise ValueError(f"Invalid URL flags in pair {index}")
                if citation_url in seen_in_note:
                    raise ValueError(f"Duplicate normalized URL within {side} note of pair {index}")
                seen_in_note.add(citation_url)
                references += 1
                # Fragment text is a citation locator, not part of an HTTP GET.
                # Probe the network URL once and retain exact citation variants.
                url = urldefrag(citation_url).url
                url_hash = sha256_text(url)
                if url_hash in urls and urls[url_hash]["url"] != url:
                    raise ValueError("SHA-256 URL collision")
                record = urls.setdefault(url_hash, {
                    "url_sha256": url_hash, "url": url, "flags": set(),
                    "references": 0, "citation_urls": set(),
                })
                record["flags"].update(flags)
                record["references"] += 1
                record["citation_urls"].add(citation_url)
    ordered = []
    for record in urls.values():
        ordered.append({
            "url_sha256": record["url_sha256"],
            "url": record["url"],
            "flags": sorted(record["flags"]),
            "references": record["references"],
            "citation_urls": sorted(record["citation_urls"]),
        })
    ordered.sort(key=lambda row: row["url"])
    random.Random(SEED).shuffle(ordered)
    return ordered, len(pairs), references


def prepare_manifest(candidates: Path, manifest: Path, expected_pairs: int) -> None:
    urls, pair_count, references = parse_candidates(candidates, expected_pairs)
    needs_review = [
        row["url_sha256"] for row in urls if REVIEW_FLAGS.intersection(row["flags"])
    ]
    payload = {
        "schema": "samepost-allurl-probe-manifest-v1",
        "prepared_utc": utc_now(),
        "candidate_file": candidates.name,
        "candidate_sha256": file_sha256(candidates),
        "script_sha256": file_sha256(Path(__file__)),
        "probe_urls_sha256": file_sha256(Path(probe_urls.__file__)),
        "python_version": sys.version.split()[0],
        "requests_version": requests.__version__,
        "bs4_version": bs4.__version__,
        "seed": SEED,
        "pair_count": pair_count,
        "url_references": references,
        "unique_url_count": len(urls),
        "review_flags": sorted(REVIEW_FLAGS),
        "review_required_url_sha256": needs_review,
        "policy": {
            "max_workers": MAX_WORKERS,
            "max_redirects": MAX_REDIRECTS,
            "max_body_bytes": MAX_BODY_BYTES,
            "connect_timeout_seconds": CONNECT_TIMEOUT,
            "read_timeout_seconds": READ_TIMEOUT,
            "body_deadline_seconds": BODY_DEADLINE_SECONDS,
            "host_min_interval_seconds": HOST_INTERVAL_SECONDS,
            "global_min_interval_seconds": GLOBAL_INTERVAL_SECONDS,
            "max_saved_text_chars": MAX_EXTRACTED_TEXT_CHARS,
            "repeat": "exactly once if first category is not open_candidate; no repeat of unsafe-target block",
            "method": "unauthenticated GET, no script execution or challenge solving",
        },
        "urls": urls,
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(f"Prepared {manifest}: {len(urls)} unique URLs from {references} note-URL references")
    print(f"Candidate SHA-256: {payload['candidate_sha256']}")
    print(f"Script SHA-256: {payload['script_sha256']}")
    print(f"Probe dependency SHA-256: {payload['probe_urls_sha256']}")
    print(f"Manifest SHA-256: {file_sha256(manifest)}")
    print(f"URLs requiring normalization flag review: {len(needs_review)}")
    print("Preparation made no network requests.")


class RateLimiter:
    """One shared limiter across every worker and every redirect/retry hop."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._host_locks: dict[str, threading.Lock] = {}
        self._host_last: dict[str, float] = {}
        self._global_last = -1e9

    def host_lock(self, host: str) -> threading.Lock:
        with self._guard:
            return self._host_locks.setdefault(host, threading.Lock())

    def wait_for_slot(self, host: str) -> None:
        while True:
            with self._guard:
                now = time.monotonic()
                earliest = max(
                    self._host_last.get(host, -1e9) + HOST_INTERVAL_SECONDS,
                    self._global_last + GLOBAL_INTERVAL_SECONDS,
                )
                delay = earliest - now
                if delay <= 0:
                    self._host_last[host] = now
                    self._global_last = now
                    return
            time.sleep(min(delay, 0.25))


def read_body(response: requests.Response, started: float) -> tuple[bytes, bool, bool]:
    chunks: list[bytes] = []
    size = 0
    truncated = False
    timed_out = False
    for chunk in response.iter_content(chunk_size=65536):
        if time.monotonic() - started > BODY_DEADLINE_SECONDS:
            timed_out = True
            break
        if not chunk:
            continue
        remaining = MAX_BODY_BYTES - size
        if len(chunk) > remaining:
            chunks.append(chunk[:remaining])
            size += remaining
            truncated = True
            break
        chunks.append(chunk)
        size += len(chunk)
        if size >= MAX_BODY_BYTES:
            truncated = True
            break
    return b"".join(chunks), truncated, timed_out


def one_get(url: str, limiter: RateLimiter) -> dict:
    current = url
    chain: list[dict] = []
    started = time.monotonic()
    fetched_at_utc = utc_now()
    session = requests.Session()
    session.trust_env = False
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/pdf,text/plain,*/*;q=0.5",
    })
    try:
        for hop in range(MAX_REDIRECTS + 1):
            try:
                host = validate_public_url(current)
            except LookupError as exc:
                return {
                    "category": "gone_candidate", "reason": "dns_lookup_failed",
                    "legacy_category": "gone_candidate", "legacy_reason": "dns_lookup_failed",
                    "error": str(exc)[:350], "chain": chain,
                    "fetched_at_utc": fetched_at_utc,
                    "elapsed_ms": round((time.monotonic() - started) * 1000),
                }
            except ValueError as exc:
                return {
                    "category": "transient_uncertain", "reason": "blocked_unsafe_target",
                    "legacy_category": "transient_uncertain", "legacy_reason": "blocked_unsafe_target",
                    "error": str(exc)[:350], "chain": chain,
                    "fetched_at_utc": fetched_at_utc,
                    "elapsed_ms": round((time.monotonic() - started) * 1000),
                }
            # Holding this host lock through response headers prevents a second
            # worker from starting the same-host request inside the one-second
            # interval. The shared global limiter spaces requests across hosts.
            with limiter.host_lock(host):
                limiter.wait_for_slot(host)
                with session.get(
                    current,
                    timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                    stream=True,
                    allow_redirects=False,
                ) as response:
                    status = response.status_code
                    location = response.headers.get("Location")
                    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
                    chain.append({"url": current, "host": host, "status": status, "location": location})
                    if 300 <= status < 400 and location:
                        if hop == MAX_REDIRECTS:
                            return {
                                "category": "transient_uncertain", "reason": "redirect_limit",
                                "legacy_category": "transient_uncertain", "legacy_reason": "redirect_limit",
                                "chain": chain, "fetched_at_utc": fetched_at_utc,
                                "elapsed_ms": round((time.monotonic() - started) * 1000),
                            }
                        current = urljoin(current, location)
                        continue
                    raw, body_truncated, body_timed_out = read_body(response, time.monotonic())
            title, visible = extract_visible_text(raw, content_type)
            normalized = " ".join(visible.split())
            lower = (title + " " + normalized[:1000]).lower()
            old_hits = [marker for marker in CHALLENGE_MARKERS if marker in lower]
            extra_hits = [marker for marker in EXTRA_CHALLENGE_MARKERS if marker in lower]
            if status in {401, 403, 429}:
                legacy_category, legacy_reason = "access_barrier", f"http_{status}"
            elif status in {404, 410}:
                legacy_category, legacy_reason = "gone_candidate", f"http_{status}"
            elif status < 200 or status >= 400:
                legacy_category, legacy_reason = "transient_uncertain", f"http_{status}"
            elif old_hits:
                legacy_category, legacy_reason = "access_barrier", "challenge_or_login_text"
            elif content_type == "application/pdf" and raw.startswith(b"%PDF"):
                legacy_category, legacy_reason = "open_candidate", "readable_pdf"
            elif len(normalized) >= 80:
                legacy_category, legacy_reason = "open_candidate", "readable_text"
            else:
                legacy_category, legacy_reason = "transient_uncertain", "no_readable_text_or_unsupported_media"
            category, reason = legacy_category, legacy_reason
            if extra_hits and category == "open_candidate":
                category, reason = "access_barrier", "extra_challenge_marker"
            if body_timed_out:
                category, reason = "transient_uncertain", "body_deadline"
                legacy_category, legacy_reason = "transient_uncertain", "body_deadline"
            return {
                "category": category,
                "reason": reason,
                "legacy_category": legacy_category,
                "legacy_reason": legacy_reason,
                "challenge_markers_old": old_hits,
                "challenge_markers_extra": extra_hits,
                "chain": chain,
                "final_url": current,
                "status_code": status,
                "http_200_exact": status == 200,
                "content_type": content_type,
                "body_bytes_read": len(raw),
                "body_truncated": body_truncated,
                "body_deadline_exceeded": body_timed_out,
                "body_sha256": hashlib.sha256(raw).hexdigest(),
                "visible_text_len": len(normalized),
                "visible_text_sha256": sha256_text(normalized) if normalized else None,
                "visible_text_saved_chars": min(len(normalized), MAX_EXTRACTED_TEXT_CHARS),
                "visible_text_truncated": len(normalized) > MAX_EXTRACTED_TEXT_CHARS,
                "visible_text": normalized[:MAX_EXTRACTED_TEXT_CHARS],
                "title": title,
                "fetched_at_utc": fetched_at_utc,
                "elapsed_ms": round((time.monotonic() - started) * 1000),
            }
    except (requests.RequestException, OSError) as exc:
        return {
            "category": "transient_uncertain",
            "reason": type(exc).__name__,
            "legacy_category": "transient_uncertain",
            "legacy_reason": type(exc).__name__,
            "error": str(exc)[:350],
            "chain": chain,
            "fetched_at_utc": fetched_at_utc,
            "elapsed_ms": round((time.monotonic() - started) * 1000),
        }
    finally:
        session.close()
    raise AssertionError("redirect loop exhausted without a result")


def probe_url(entry: dict, limiter: RateLimiter) -> dict:
    first = one_get(entry["url"], limiter)
    repeat = None
    if first["category"] != "open_candidate" and first["reason"] != "blocked_unsafe_target":
        repeat = one_get(entry["url"], limiter)
    if repeat and (first["category"], first["reason"]) != (repeat["category"], repeat["reason"]):
        category = "transient_uncertain"
        reason = "first_repeat_disagree"
    elif repeat:
        category, reason = repeat["category"], repeat["reason"]
    else:
        category, reason = first["category"], first["reason"]
    if first["legacy_category"] == "open_candidate" or not repeat:
        legacy_category, legacy_reason = first["legacy_category"], first["legacy_reason"]
    elif (first["legacy_category"], first["legacy_reason"]) != (repeat["legacy_category"], repeat["legacy_reason"]):
        legacy_category, legacy_reason = "transient_uncertain", "first_repeat_disagree"
    else:
        legacy_category, legacy_reason = repeat["legacy_category"], repeat["legacy_reason"]
    return {
        "url_sha256": entry["url_sha256"],
        "url": entry["url"],
        "category": category,
        "reason": reason,
        "legacy_category": legacy_category,
        "legacy_reason": legacy_reason,
        "first": first,
        "repeat": repeat,
        "probed_at_utc": utc_now(),
    }


def load_manifest(path: Path, candidates: Path, expected_hash: str) -> dict:
    if not HEX_SHA256.fullmatch(expected_hash):
        raise ValueError("--approve-manifest-sha256 must be a 64-character lowercase SHA-256")
    actual_hash = file_sha256(path)
    if actual_hash != expected_hash:
        raise ValueError("Manifest hash differs from reviewed hash")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "samepost-allurl-probe-manifest-v1":
        raise ValueError("Unexpected manifest schema")
    if manifest.get("candidate_sha256") != file_sha256(candidates):
        raise ValueError("Candidate input differs from frozen manifest")
    if manifest.get("script_sha256") != file_sha256(Path(__file__)):
        raise ValueError("Runner code differs from frozen manifest")
    if manifest.get("probe_urls_sha256") != file_sha256(Path(probe_urls.__file__)):
        raise ValueError("Probe dependency differs from frozen manifest")
    if (manifest.get("python_version"), manifest.get("requests_version"), manifest.get("bs4_version")) != (
        sys.version.split()[0], requests.__version__, bs4.__version__
    ):
        raise ValueError("Probe runtime versions differ from frozen manifest")
    if manifest.get("seed") != SEED or not isinstance(manifest.get("pair_count"), int) or manifest["pair_count"] < 1:
        raise ValueError("Unexpected manifest seed or pair count")
    if len(read_jsonl(candidates)) != manifest["pair_count"]:
        raise ValueError("Manifest pair count differs from frozen candidate file")
    urls = manifest.get("urls")
    if not isinstance(urls, list) or len(urls) != manifest.get("unique_url_count"):
        raise ValueError("Manifest URL count mismatch")
    seen = set()
    for row in urls:
        url_hash = row.get("url_sha256")
        if not isinstance(row.get("url"), str) or url_hash != sha256_text(row["url"]):
            raise ValueError("Manifest URL hash mismatch")
        citation_urls = row.get("citation_urls")
        if not isinstance(citation_urls, list) or not citation_urls or any(
            not isinstance(value, str) or urldefrag(value).url != row["url"]
            for value in citation_urls
        ):
            raise ValueError("Manifest citation variant does not map to network URL")
        if url_hash in seen:
            raise ValueError("Duplicate URL hash in manifest")
        seen.add(url_hash)
    expected_review = {
        row["url_sha256"] for row in urls if REVIEW_FLAGS.intersection(row.get("flags", []))
    }
    if set(manifest.get("review_required_url_sha256", [])) != expected_review:
        raise ValueError("Manifest normalization-review list mismatch")
    return manifest


def read_approved_flags(path: Path | None, required: set[str]) -> str | None:
    if not required:
        return None
    if path is None:
        raise ValueError(
            f"{len(required)} normalized URLs have review flags; provide a manually "
            "reviewed JSON list of approved URL SHA-256 values with --approved-flags-file"
        )
    approved = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(approved, list) or any(not isinstance(value, str) for value in approved):
        raise ValueError("Approved-flags file must be a JSON list of URL SHA-256 values")
    if set(approved) != required:
        raise ValueError("Approved-flags file must contain exactly the flagged URL hashes")
    return file_sha256(path)


def load_completed(output: Path, manifest: dict) -> set[str]:
    if not output.exists():
        return set()
    url_by_hash = {row["url_sha256"]: row["url"] for row in manifest["urls"]}
    completed: set[str] = set()
    for row in read_jsonl(output):
        url_hash = row.get("url_sha256")
        if url_hash not in url_by_hash or row.get("url") != url_by_hash[url_hash]:
            raise ValueError("Existing result URL is not in the frozen manifest")
        if url_hash in completed:
            raise ValueError("Duplicate URL hash in existing results; inspect before resuming")
        completed.add(url_hash)
    return completed


def run(
    candidates: Path,
    manifest_path: Path,
    output: Path,
    runlog: Path,
    reviewed_hash: str,
    approved_flags: Path | None,
    workers: int,
) -> None:
    if not 1 <= workers <= MAX_WORKERS:
        raise ValueError(f"Workers must be between 1 and {MAX_WORKERS}")
    if len({p.resolve() for p in (candidates, manifest_path, output, runlog)}) != 4:
        raise ValueError("Candidate, manifest, output, and runlog paths must be distinct")
    manifest = load_manifest(manifest_path, candidates, reviewed_hash)
    required = set(manifest["review_required_url_sha256"])
    approval_file_sha256 = read_approved_flags(approved_flags, required)
    if output.exists() and not runlog.exists():
        raise ValueError("Existing probe output has no matching runlog; inspect before resuming")
    completed = load_completed(output, manifest)
    prior_completed = len(completed)
    started: set[str] = set()
    if runlog.exists():
        for row in read_jsonl(runlog):
            if row.get("manifest_sha256") != reviewed_hash:
                raise ValueError("Existing runlog belongs to a different manifest")
            if row.get("event") == "url_started":
                started.add(row["url_sha256"])
    url_by_hash = {row["url_sha256"]: row["url"] for row in manifest["urls"]}
    if not started.issubset(url_by_hash):
        raise ValueError("Runlog contains URL hash outside frozen manifest")
    interrupted = started - completed
    for url_hash in sorted(interrupted):
        # A prior process may have made one or two HTTP requests before dying.
        # Do not silently issue more attempts on resume; preserve uncertainty.
        append_jsonl(output, {
            "url_sha256": url_hash,
            "url": url_by_hash[url_hash],
            "category": "transient_uncertain",
            "reason": "interrupted_before_result",
            "legacy_category": "transient_uncertain",
            "legacy_reason": "interrupted_before_result",
            "first": None,
            "repeat": None,
            "probed_at_utc": utc_now(),
        })
        completed.add(url_hash)
    pending_urls = [row for row in manifest["urls"] if row["url_sha256"] not in completed]
    append_jsonl(runlog, {
        "event": "run_started",
        "utc": utc_now(),
        "manifest_sha256": reviewed_hash,
        "candidate_sha256": manifest["candidate_sha256"],
        "script_sha256": manifest["script_sha256"],
        "approval_file_sha256": approval_file_sha256,
        "workers": workers,
        "already_completed": prior_completed,
        "interrupted_recovered_as_unresolved": len(interrupted),
        "remaining": len(pending_urls),
    })
    limiter = RateLimiter()
    new_count = 0
    def submit_logged(pool: ThreadPoolExecutor, entry: dict):
        append_jsonl(runlog, {
            "event": "url_started",
            "utc": utc_now(),
            "manifest_sha256": reviewed_hash,
            "url_sha256": entry["url_sha256"],
        })
        return pool.submit(probe_url, entry, limiter)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        iterator = iter(pending_urls)
        pending = {}
        for _ in range(workers):
            try:
                entry = next(iterator)
            except StopIteration:
                break
            pending[submit_logged(pool, entry)] = entry
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                entry = pending.pop(future)
                try:
                    row = future.result()
                except Exception as exc:
                    row = {
                        "url_sha256": entry["url_sha256"],
                        "url": entry["url"],
                        "category": "transient_uncertain",
                        "reason": "internal_error",
                        "first": None,
                        "repeat": None,
                        "internal_error": repr(exc)[:350],
                        "probed_at_utc": utc_now(),
                    }
                append_jsonl(output, row)
                new_count += 1
                if new_count % 50 == 0:
                    print(f"New {new_count}/{len(pending_urls)}; total {len(completed) + new_count}/{len(manifest['urls'])}", flush=True)
                try:
                    next_entry = next(iterator)
                except StopIteration:
                    continue
                pending[submit_logged(pool, next_entry)] = next_entry
    append_jsonl(runlog, {
        "event": "run_completed",
        "utc": utc_now(),
        "manifest_sha256": reviewed_hash,
        "new_records": new_count,
        "total_records": len(completed) + new_count,
        "expected_records": len(manifest["urls"]),
        "output_sha256": file_sha256(output) if output.exists() else None,
    })
    print(f"Completed {len(completed) + new_count}/{len(manifest['urls'])} URL records in {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true", help="Write frozen URL-only manifest; no network")
    mode.add_argument("--run", action="store_true", help="Probe a reviewed frozen manifest")
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runlog", type=Path, default=DEFAULT_RUNLOG)
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    parser.add_argument("--expected-pairs", type=int, help="Required for --prepare; freezes candidate frame size")
    parser.add_argument("--approve-manifest-sha256")
    parser.add_argument("--approved-flags-file", type=Path)
    args = parser.parse_args()
    if args.prepare:
        if args.expected_pairs is None:
            parser.error("--prepare requires --expected-pairs from the reviewed candidate frame")
        prepare_manifest(args.candidates, args.manifest, args.expected_pairs)
        return
    if not args.approve_manifest_sha256:
        parser.error("--run requires --approve-manifest-sha256 after review")
    run(
        args.candidates,
        args.manifest,
        args.output,
        args.runlog,
        args.approve_manifest_sha256,
        args.approved_flags_file,
        args.workers,
    )


if __name__ == "__main__":
    main()
