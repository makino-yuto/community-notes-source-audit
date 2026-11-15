"""Uniform static content collection for all URLs in the fixed 100-pair packet.

Preparation joins the pre-probe semantic key to the frozen candidate frame,
then exports a URL-only shuffled packet and a separate private mapping. No
machine outcomes are read when selecting URLs. Collection uses one bounded,
unauthenticated GET per distinct defragmented network URL, after the all-URL
machine pass finishes. It stores content and provenance, never factual labels.

The complete private text may be supplied later to a separately frozen model
judgment pass, where the first 24,000 characters per URL are the uniform cap.
"""

from __future__ import annotations

import argparse
import hashlib
import io
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
import pypdf
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from probe_urls import (
    CONNECT_TIMEOUT,
    MAX_BODY_BYTES,
    MAX_REDIRECTS,
    READ_TIMEOUT,
    USER_AGENT,
    sha256_text,
    validate_public_url,
)


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
DEFAULT_KEY = RESULTS / "newwave_semantic_key_PRIVATE.json"
DEFAULT_CANDIDATES = RESULTS / "revision_samepost_candidates_v2_PRIVATE.jsonl"
DEFAULT_MANIFEST = RESULTS / "newwave_semantic_content_manifest_PRIVATE.json"
DEFAULT_MAPPING = RESULTS / "newwave_semantic_content_mapping_PRIVATE.jsonl"
DEFAULT_OUTPUT = RESULTS / "newwave_semantic_content_PRIVATE.jsonl"
DEFAULT_RUNLOG = RESULTS / "newwave_semantic_content_runlog_PRIVATE.jsonl"
DEFAULT_MACHINE_MANIFEST = RESULTS / "newwave_probe_manifest_PRIVATE.json"
DEFAULT_MACHINE_OUTPUT = RESULTS / "newwave_probe_PRIVATE.jsonl"
DEFAULT_MACHINE_RUNLOG = RESULTS / "newwave_probe_runlog_PRIVATE.jsonl"
SEED = 2026111510
EXPECTED_PAIRS = 100
MAX_WORKERS = 4
HOST_INTERVAL_SECONDS = 1.0
GLOBAL_INTERVAL_SECONDS = 0.20
MAX_SAVED_CHARS = 120_000
MAX_PDF_PAGES = 50
BODY_DEADLINE_SECONDS = 30.0
HEX_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
DROP_HTML_TAGS = ("script", "style", "noscript", "template", "svg", "nav", "header", "footer")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_text(text: str) -> str:
    return " ".join(text.split())


def compact_json(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(compact_json(row) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                raise ValueError(f"Blank JSONL record at {path}:{line_no}")
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Malformed JSONL at {path}:{line_no}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Non-object JSONL record at {path}:{line_no}")
            yield row


def fixed_pair_urls(key: Path, candidates: Path) -> tuple[list[dict], list[dict]]:
    """Resolve key notes to all citations without reading any probe outcomes."""
    semantic_pairs = json.loads(key.read_text(encoding="utf-8"))
    if not isinstance(semantic_pairs, list) or len(semantic_pairs) != EXPECTED_PAIRS:
        raise ValueError(f"Expected {EXPECTED_PAIRS} frozen semantic pairs")
    by_post = {}
    for pair in read_jsonl(candidates):
        post_id = str(pair.get("post_id", ""))
        if not post_id or post_id in by_post:
            raise ValueError("Missing or duplicate candidate post_id")
        by_post[post_id] = pair
    url_by_hash: dict[str, str] = {}
    mapping: list[dict] = []
    seen_codes: set[str] = set()
    for item in semantic_pairs:
        code = item.get("code")
        post_id = str(item.get("post_id", ""))
        if not isinstance(code, str) or code in seen_codes or post_id not in by_post:
            raise ValueError(f"Semantic key code/post mismatch: {code}")
        seen_codes.add(code)
        pair = by_post[post_id]
        sides = item.get("sides")
        groups = item.get("groups")
        if not isinstance(sides, dict) or not isinstance(groups, dict):
            raise ValueError(f"Missing side/group mapping for {code}")
        for side in ("A", "B"):
            group = groups.get(side)
            note_id = str(sides.get(side, ""))
            if group not in {"AI_API", "non_API"} or not note_id:
                raise ValueError(f"Invalid side mapping for {code}/{side}")
            note = pair["ai" if group == "AI_API" else "non_api"]
            if str(note.get("note_id", "")) != note_id:
                raise ValueError(f"Candidate/key note mismatch for {code}/{side}")
            citations = note.get("external_urls")
            if not isinstance(citations, list) or not citations:
                raise ValueError(f"No retained URL for {code}/{side}")
            for citation_index, citation in enumerate(citations):
                citation_url = citation.get("normalized_url") if isinstance(citation, dict) else None
                if not isinstance(citation_url, str):
                    raise ValueError(f"Invalid citation record for {code}/{side}")
                parsed = urlsplit(citation_url)
                if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                    raise ValueError(f"Malformed citation for {code}/{side}")
                network_url = urldefrag(citation_url).url
                url_hash = sha256_text(network_url)
                if url_hash in url_by_hash and url_by_hash[url_hash] != network_url:
                    raise ValueError("Network URL SHA-256 collision")
                url_by_hash[url_hash] = network_url
                mapping.append({
                    "pair_code": code,
                    "side": side,
                    "note_id": note_id,
                    "citation_index": citation_index,
                    "citation_url": citation_url,
                    "network_url_sha256": url_hash,
                })
    if len(seen_codes) != EXPECTED_PAIRS:
        raise ValueError("Semantic key pair count changed")
    urls = [{"url_sha256": digest, "url": url} for digest, url in url_by_hash.items()]
    urls.sort(key=lambda row: row["url"])
    random.Random(SEED).shuffle(urls)
    return urls, mapping


def prepare(key: Path, candidates: Path, manifest: Path, mapping_path: Path) -> None:
    if manifest.exists() or mapping_path.exists():
        raise FileExistsError("Manifest/mapping already exists; use new paths for a new frozen version")
    urls, mapping = fixed_pair_urls(key, candidates)
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    with mapping_path.open("x", encoding="utf-8", newline="\n") as stream:
        for row in mapping:
            stream.write(compact_json(row) + "\n")
    payload = {
        "schema": "samepost-semantic-content-manifest-v1",
        "prepared_utc": now_utc(),
        "fixed_semantic_pairs": EXPECTED_PAIRS,
        "key_file": key.name,
        "key_sha256": file_sha256(key),
        "candidate_file": candidates.name,
        "candidate_sha256": file_sha256(candidates),
        "mapping_file": mapping_path.name,
        "mapping_sha256": file_sha256(mapping_path),
        "script_sha256": file_sha256(Path(__file__)),
        "probe_urls_sha256": file_sha256(Path(probe_urls.__file__)),
        "python_version": sys.version.split()[0],
        "requests_version": requests.__version__,
        "bs4_version": bs4.__version__,
        "pypdf_version": pypdf.__version__,
        "seed": SEED,
        "unique_network_urls": len(urls),
        "citation_references": len(mapping),
        "policy": {
            "max_workers": MAX_WORKERS,
            "host_min_interval_seconds": HOST_INTERVAL_SECONDS,
            "global_min_interval_seconds": GLOBAL_INTERVAL_SECONDS,
            "max_redirects": MAX_REDIRECTS,
            "max_body_bytes": MAX_BODY_BYTES,
            "connect_timeout_seconds": CONNECT_TIMEOUT,
            "read_timeout_seconds": READ_TIMEOUT,
            "body_deadline_seconds": BODY_DEADLINE_SECONDS,
            "max_saved_chars_per_text_field": MAX_SAVED_CHARS,
            "max_pdf_pages": MAX_PDF_PAGES,
            "requests_per_network_url": 1,
            "no_health_based_retry_or_browser_escalation": True,
        },
        "urls": urls,
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(f"Prepared {EXPECTED_PAIRS} pairs; {len(mapping)} citations; {len(urls)} network URLs")
    print(f"Key SHA-256: {payload['key_sha256']}")
    print(f"Candidate SHA-256: {payload['candidate_sha256']}")
    print(f"Mapping SHA-256: {payload['mapping_sha256']}")
    print(f"Script SHA-256: {payload['script_sha256']}")
    print(f"Manifest SHA-256: {file_sha256(manifest)}")
    print("Preparation made no network requests.")


class RateLimiter:
    """Shared spacing across workers, including redirect hops."""

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
                current = time.monotonic()
                earliest = max(
                    self._host_last.get(host, -1e9) + HOST_INTERVAL_SECONDS,
                    self._global_last + GLOBAL_INTERVAL_SECONDS,
                )
                delay = earliest - current
                if delay <= 0:
                    self._host_last[host] = current
                    self._global_last = current
                    return
            time.sleep(min(delay, 0.25))


def read_body(response: requests.Response) -> tuple[bytes, bool, bool]:
    started = time.monotonic()
    chunks = []
    size = 0
    capped = False
    deadline = False
    for chunk in response.iter_content(chunk_size=65536):
        if time.monotonic() - started > BODY_DEADLINE_SECONDS:
            deadline = True
            break
        if not chunk:
            continue
        remaining = MAX_BODY_BYTES - size
        if len(chunk) > remaining:
            chunks.append(chunk[:remaining])
            size += remaining
            capped = True
            break
        chunks.append(chunk)
        size += len(chunk)
        if size >= MAX_BODY_BYTES:
            capped = True
            break
    return b"".join(chunks), capped, deadline


def text_field(text: str) -> dict:
    cleaned = normalized_text(text)
    return {
        "text": cleaned[:MAX_SAVED_CHARS],
        "chars_total": len(cleaned),
        "chars_saved": min(len(cleaned), MAX_SAVED_CHARS),
        "truncated": len(cleaned) > MAX_SAVED_CHARS,
        "sha256_full": sha256_text(cleaned) if cleaned else None,
        "sha256_saved": sha256_text(cleaned[:MAX_SAVED_CHARS]) if cleaned else None,
    }


def parse_html(raw: bytes) -> dict:
    soup = BeautifulSoup(raw, "html.parser")
    title = soup.title.get_text(" ", strip=True)[:250] if soup.title else ""
    for element in soup.find_all(DROP_HTML_TAGS):
        element.decompose()
    body = soup.body or soup
    body_text = body.get_text(" ", strip=True)
    selection = body
    selector = "body"
    for kind in ("article", "main"):
        candidates = body.find_all(kind)
        if not candidates:
            continue
        ranked = sorted(
            enumerate(candidates),
            key=lambda item: len(normalized_text(item[1].get_text(" ", strip=True))),
            reverse=True,
        )
        index, candidate = ranked[0]
        if len(normalized_text(candidate.get_text(" ", strip=True))) >= 80:
            selection = candidate
            selector = f"{kind}[index={index}]"
            break
    main_text = selection.get_text(" ", strip=True)
    return {
        "format": "html",
        "parse_status": "ok" if normalized_text(main_text) else "empty_text",
        "title": title,
        "main_selector": selector,
        "removed_tags": list(DROP_HTML_TAGS),
        "body_text": text_field(body_text),
        "main_text": text_field(main_text),
    }


def parse_pdf(raw: bytes) -> dict:
    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
        if reader.is_encrypted:
            return {
                "format": "pdf", "parse_status": "encrypted_unassessable",
                "page_count": None, "pages_extracted": 0, "main_selector": "pdf",
                "body_text": text_field(""), "main_text": text_field(""),
            }
        page_count = len(reader.pages)
        parts = []
        spans = []
        chars = 0
        for page_index in range(min(page_count, MAX_PDF_PAGES)):
            page_text = normalized_text(reader.pages[page_index].extract_text() or "")
            if page_text:
                start = chars
                parts.append(page_text)
                chars += len(page_text) + 1
                spans.append({
                    "page_1based": page_index + 1,
                    "start_char": start,
                    "end_char": start + len(page_text),
                    "page_text_sha256": sha256_text(page_text),
                })
            if chars >= MAX_SAVED_CHARS:
                break
        full_text = " ".join(parts)
        pages_extracted = page_index + 1 if page_count else 0
        status = "ok" if full_text else "empty_pdf_text_unassessable"
        return {
            "format": "pdf",
            "parse_status": status,
            "page_count": page_count,
            "pages_extracted": pages_extracted,
            "page_limit_reached": page_count > MAX_PDF_PAGES and pages_extracted >= MAX_PDF_PAGES,
            "text_limit_reached": chars >= MAX_SAVED_CHARS,
            "page_spans": spans,
            "main_selector": "pdf_extracted_pages",
            "body_text": text_field(full_text),
            "main_text": text_field(full_text),
        }
    except Exception as exc:
        return {
            "format": "pdf",
            "parse_status": "parse_error_unassessable",
            "parse_error": f"{type(exc).__name__}: {str(exc)[:250]}",
            "page_count": None,
            "pages_extracted": 0,
            "main_selector": "pdf",
            "body_text": text_field(""),
            "main_text": text_field(""),
        }


def parse_content(raw: bytes, content_type: str) -> dict:
    if raw.startswith(b"%PDF") or content_type == "application/pdf":
        return parse_pdf(raw)
    if "html" in content_type or raw[:1000].lower().find(b"<html") >= 0:
        try:
            return parse_html(raw)
        except Exception as exc:
            return {
                "format": "html", "parse_status": "parse_error_unassessable",
                "parse_error": f"{type(exc).__name__}: {str(exc)[:250]}",
                "body_text": text_field(""), "main_text": text_field(""),
            }
    if content_type.startswith("text/") or content_type in {"application/json", "application/xml"}:
        decoded = raw.decode("utf-8", errors="replace")
        field = text_field(decoded)
        return {
            "format": "plain_text", "parse_status": "ok" if field["chars_total"] else "empty_text",
            "main_selector": "entire_decoded_response",
            "body_text": field, "main_text": field,
        }
    return {
        "format": "unsupported", "parse_status": "unsupported_media_unassessable",
        "main_selector": None,
        "body_text": text_field(""), "main_text": text_field(""),
    }


def one_get(url: str, limiter: RateLimiter) -> dict:
    current = url
    started = time.monotonic()
    fetched_utc = now_utc()
    chain = []
    session = requests.Session()
    session.trust_env = False
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/pdf,text/plain,application/json,*/*;q=0.5",
    })
    try:
        for hop in range(MAX_REDIRECTS + 1):
            try:
                host = validate_public_url(current)
            except (LookupError, ValueError) as exc:
                return {
                    "fetch_status": "blocked_or_dns_error",
                    "reason": f"{type(exc).__name__}: {str(exc)[:250]}",
                    "chain": chain,
                    "fetched_at_utc": fetched_utc,
                    "elapsed_ms": round((time.monotonic() - started) * 1000),
                }
            with limiter.host_lock(host):
                limiter.wait_for_slot(host)
                with session.get(
                    current, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                    stream=True, allow_redirects=False,
                ) as response:
                    status = response.status_code
                    location = response.headers.get("Location")
                    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
                    chain.append({"url": current, "host": host, "status": status, "location": location})
                    if 300 <= status < 400 and location:
                        if hop == MAX_REDIRECTS:
                            return {
                                "fetch_status": "redirect_limit",
                                "chain": chain,
                                "fetched_at_utc": fetched_utc,
                                "elapsed_ms": round((time.monotonic() - started) * 1000),
                            }
                        current = urljoin(current, location)
                        continue
                    raw, body_capped, body_deadline = read_body(response)
            parsed = parse_content(raw, content_type)
            return {
                "fetch_status": "http_response",
                "chain": chain,
                "final_url": current,
                "status_code": status,
                "http_200_exact": status == 200,
                "content_type": content_type,
                "body_bytes_read": len(raw),
                "body_capped_2mb": body_capped,
                "body_deadline_exceeded": body_deadline,
                "body_sha256": hashlib.sha256(raw).hexdigest(),
                "parsed": parsed,
                "fetched_at_utc": fetched_utc,
                "elapsed_ms": round((time.monotonic() - started) * 1000),
            }
    except (requests.RequestException, OSError) as exc:
        return {
            "fetch_status": "request_error",
            "reason": f"{type(exc).__name__}: {str(exc)[:250]}",
            "chain": chain,
            "fetched_at_utc": fetched_utc,
            "elapsed_ms": round((time.monotonic() - started) * 1000),
        }
    finally:
        session.close()
    raise AssertionError("Redirect loop exhausted")


def verify_machine_pass(
    machine_manifest: Path, machine_output: Path, machine_runlog: Path
) -> dict:
    manifest = json.loads(machine_manifest.read_text(encoding="utf-8"))
    required = {row["url_sha256"] for row in manifest["urls"]}
    completed = set()
    for row in read_jsonl(machine_output):
        url_hash = row.get("url_sha256")
        if url_hash in completed:
            raise ValueError("Duplicate machine probe URL hash")
        completed.add(url_hash)
    if completed != required:
        raise ValueError(f"Machine pass incomplete: {len(completed)}/{len(required)} URLs")
    run_finished = any(
        row.get("event") == "run_completed" and row.get("total_records") == len(required)
        for row in read_jsonl(machine_runlog)
    )
    if not run_finished:
        raise ValueError("Machine pass has no completed runlog event")
    return {
        "manifest_sha256": file_sha256(machine_manifest),
        "output_sha256": file_sha256(machine_output),
        "runlog_sha256": file_sha256(machine_runlog),
        "completed_urls": len(required),
    }


def load_plan(
    key: Path, candidates: Path, manifest_path: Path, mapping_path: Path,
    approved_manifest_sha256: str,
) -> dict:
    if not HEX_SHA256.fullmatch(approved_manifest_sha256):
        raise ValueError("Supply the reviewed 64-character manifest SHA-256")
    if file_sha256(manifest_path) != approved_manifest_sha256:
        raise ValueError("Manifest has changed since approval")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "samepost-semantic-content-manifest-v1":
        raise ValueError("Unexpected semantic content manifest schema")
    expected = {
        "key_sha256": file_sha256(key),
        "candidate_sha256": file_sha256(candidates),
        "mapping_sha256": file_sha256(mapping_path),
        "script_sha256": file_sha256(Path(__file__)),
        "probe_urls_sha256": file_sha256(Path(probe_urls.__file__)),
        "python_version": sys.version.split()[0],
        "requests_version": requests.__version__,
        "bs4_version": bs4.__version__,
        "pypdf_version": pypdf.__version__,
    }
    if any(manifest.get(field) != value for field, value in expected.items()):
        raise ValueError("Frozen key, candidate, mapping, code, or runtime changed")
    if manifest.get("fixed_semantic_pairs") != EXPECTED_PAIRS or manifest.get("seed") != SEED:
        raise ValueError("Unexpected fixed pair count or seed")
    urls = manifest.get("urls")
    if not isinstance(urls, list) or len(urls) != manifest.get("unique_network_urls"):
        raise ValueError("Manifest URL count mismatch")
    seen = set()
    for row in urls:
        if row.get("url_sha256") != sha256_text(row.get("url", "")):
            raise ValueError("Manifest network URL hash mismatch")
        if row["url_sha256"] in seen:
            raise ValueError("Duplicate network URL in manifest")
        seen.add(row["url_sha256"])
    return manifest


def run(
    key: Path, candidates: Path, manifest_path: Path, mapping_path: Path,
    output: Path, runlog: Path, machine_manifest: Path, machine_output: Path,
    machine_runlog: Path, approved_manifest_sha256: str, workers: int,
) -> None:
    if not 1 <= workers <= MAX_WORKERS:
        raise ValueError(f"Workers must be 1–{MAX_WORKERS}")
    paths = (key, candidates, manifest_path, mapping_path, output, runlog,
             machine_manifest, machine_output, machine_runlog)
    if len({path.resolve() for path in paths}) != len(paths):
        raise ValueError("All input and output paths must be distinct")
    manifest = load_plan(key, candidates, manifest_path, mapping_path, approved_manifest_sha256)
    machine = verify_machine_pass(machine_manifest, machine_output, machine_runlog)
    if output.exists() and not runlog.exists():
        raise ValueError("Existing content output has no matching runlog")
    url_by_hash = {row["url_sha256"]: row["url"] for row in manifest["urls"]}
    completed = set()
    if output.exists():
        for row in read_jsonl(output):
            digest = row.get("url_sha256")
            if digest not in url_by_hash or row.get("url") != url_by_hash[digest] or digest in completed:
                raise ValueError("Invalid/duplicate URL in existing content output")
            completed.add(digest)
    prior_completed = len(completed)
    started = set()
    if runlog.exists():
        for row in read_jsonl(runlog):
            if row.get("manifest_sha256") != approved_manifest_sha256:
                raise ValueError("Runlog belongs to a different manifest")
            if row.get("event") == "url_started":
                started.add(row["url_sha256"])
    if not started.issubset(url_by_hash):
        raise ValueError("Runlog contains a URL outside the manifest")
    interrupted = started - completed
    for digest in sorted(interrupted):
        append_jsonl(output, {
            "url_sha256": digest,
            "url": url_by_hash[digest],
            "fetch_status": "interrupted_unassessable",
            "reason": "previous process stopped after write-ahead start; not re-fetched",
            "fetched_at_utc": now_utc(),
        })
        completed.add(digest)
    remaining = [row for row in manifest["urls"] if row["url_sha256"] not in completed]
    append_jsonl(runlog, {
        "event": "run_started", "utc": now_utc(),
        "manifest_sha256": approved_manifest_sha256,
        "machine_gate": machine,
        "prior_completed": prior_completed,
        "interrupted_marked_unassessable": len(interrupted),
        "remaining": len(remaining),
        "workers": workers,
    })
    limiter = RateLimiter()
    def submit_logged(pool: ThreadPoolExecutor, entry: dict):
        append_jsonl(runlog, {
            "event": "url_started", "utc": now_utc(),
            "manifest_sha256": approved_manifest_sha256,
            "url_sha256": entry["url_sha256"],
        })
        return pool.submit(one_get, entry["url"], limiter)
    new_count = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        iterator = iter(remaining)
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
                    result = future.result()
                except Exception as exc:
                    result = {
                        "fetch_status": "internal_error_unassessable",
                        "reason": f"{type(exc).__name__}: {str(exc)[:250]}",
                        "fetched_at_utc": now_utc(),
                    }
                append_jsonl(output, {
                    "url_sha256": entry["url_sha256"],
                    "url": entry["url"],
                    **result,
                })
                new_count += 1
                if new_count % 25 == 0:
                    print(f"New {new_count}/{len(remaining)}; total {len(completed)+new_count}/{len(manifest['urls'])}", flush=True)
                try:
                    next_entry = next(iterator)
                except StopIteration:
                    continue
                pending[submit_logged(pool, next_entry)] = next_entry
    append_jsonl(runlog, {
        "event": "run_completed", "utc": now_utc(),
        "manifest_sha256": approved_manifest_sha256,
        "new_records": new_count,
        "total_records": len(completed) + new_count,
        "expected_records": len(manifest["urls"]),
        "output_sha256": file_sha256(output) if output.exists() else None,
    })
    print(f"Content records: {len(completed)+new_count}/{len(manifest['urls'])}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true", help="Freeze URL-only packet/mapping; no network")
    mode.add_argument("--run", action="store_true", help="Collect static content after machine pass")
    parser.add_argument("--key", type=Path, default=DEFAULT_KEY)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runlog", type=Path, default=DEFAULT_RUNLOG)
    parser.add_argument("--machine-manifest", type=Path, default=DEFAULT_MACHINE_MANIFEST)
    parser.add_argument("--machine-output", type=Path, default=DEFAULT_MACHINE_OUTPUT)
    parser.add_argument("--machine-runlog", type=Path, default=DEFAULT_MACHINE_RUNLOG)
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    parser.add_argument("--approve-manifest-sha256")
    args = parser.parse_args()
    if args.prepare:
        prepare(args.key, args.candidates, args.manifest, args.mapping)
        return
    if not args.approve_manifest_sha256:
        parser.error("--run requires --approve-manifest-sha256 after amendment review")
    run(
        args.key, args.candidates, args.manifest, args.mapping,
        args.output, args.runlog, args.machine_manifest, args.machine_output,
        args.machine_runlog, args.approve_manifest_sha256, args.workers,
    )


if __name__ == "__main__":
    main()
