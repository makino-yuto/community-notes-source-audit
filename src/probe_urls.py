"""Bounded, unauthenticated URL probes for the Community Notes study.

This records what a research client can retrieve. It does not decide whether a
source supports a note, and it never executes page scripts or bypasses access
controls. Input is the frozen, preselected cohort from build_cohort.py.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import random
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


MAX_REDIRECTS = 5
MAX_BODY_BYTES = 2_000_000
CONNECT_TIMEOUT = 5
READ_TIMEOUT = 12
USER_AGENT = "EvidenceDurabilityStudy/0.1 (+https://github.com/makino-yuto)"
CHALLENGE_MARKERS = (
    "just a moment",
    "checking your browser",
    "verify you are human",
    "access denied",
    "enable javascript",
    "please log in",
    "sign in to continue",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_public_url(url: str) -> str:
    """Reject local/network-control destinations before every redirect hop."""
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("unsupported URL scheme or missing host")
    if parsed.username or parsed.password:
        raise ValueError("URL contains credentials")
    host = parsed.hostname.rstrip(".")
    if host.lower() in {"localhost", "localhost.localdomain"} or host.lower().endswith(".local"):
        raise ValueError("local hostname")
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            records = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise LookupError(f"DNS lookup failed: {exc}") from exc
        addresses = [ipaddress.ip_address(item[4][0]) for item in records]
    if not addresses or any(not addr.is_global for addr in addresses):
        raise ValueError("non-public network destination")
    return host.lower()


def extract_visible_text(raw: bytes, content_type: str) -> tuple[str, str]:
    if "html" in content_type:
        soup = BeautifulSoup(raw, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        for tag in soup(["script", "style", "noscript", "template", "svg"]):
            tag.decompose()
        return title[:250], " ".join(soup.stripped_strings)
    if any(token in content_type for token in ("text/plain", "application/json", "text/xml", "application/xml")):
        return "", raw.decode("utf-8", errors="replace")
    return "", ""


def one_get(url: str) -> dict:
    original = url
    chain: list[dict] = []
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf,text/plain,*/*;q=0.5"})
    try:
        for hop in range(MAX_REDIRECTS + 1):
            host = validate_public_url(url)
            with session.get(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT), stream=True, allow_redirects=False) as response:
                status = response.status_code
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
                chain.append({"url": url, "host": host, "status": status})
                if 300 <= status < 400 and response.headers.get("Location"):
                    if hop == MAX_REDIRECTS:
                        return {"category": "transient_uncertain", "reason": "redirect_limit", "chain": chain}
                    url = urljoin(url, response.headers["Location"])
                    continue
                if status in {401, 403, 429}:
                    return {"category": "access_barrier", "reason": f"http_{status}", "chain": chain, "final_url": url}
                if status in {404, 410}:
                    return {"category": "gone_candidate", "reason": f"http_{status}", "chain": chain, "final_url": url}
                if status >= 500 or status < 200:
                    return {"category": "transient_uncertain", "reason": f"http_{status}", "chain": chain, "final_url": url}
                if status >= 400:
                    return {"category": "transient_uncertain", "reason": f"http_{status}", "chain": chain, "final_url": url}

                chunks: list[bytes] = []
                size = 0
                truncated = False
                for chunk in response.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    allowed = MAX_BODY_BYTES - size
                    if len(chunk) > allowed:
                        chunks.append(chunk[:allowed])
                        size += allowed
                        truncated = True
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                    if size >= MAX_BODY_BYTES:
                        truncated = True
                        break
                raw = b"".join(chunks)
                title, visible = extract_visible_text(raw, content_type)
                normalized = " ".join(visible.split())
                lower = (title + " " + normalized[:1000]).lower()
                if any(marker in lower for marker in CHALLENGE_MARKERS):
                    category, reason = "access_barrier", "challenge_or_login_text"
                elif content_type == "application/pdf" and raw.startswith(b"%PDF"):
                    category, reason = "open_candidate", "readable_pdf"
                elif normalized and len(normalized) >= 80:
                    category, reason = "open_candidate", "readable_text"
                else:
                    category, reason = "transient_uncertain", "no_readable_text_or_unsupported_media"
                return {
                    "category": category,
                    "reason": reason,
                    "chain": chain,
                    "final_url": url,
                    "content_type": content_type,
                    "body_bytes_read": size,
                    "body_truncated": truncated,
                    "body_sha256": hashlib.sha256(raw).hexdigest(),
                    "visible_text_len": len(normalized),
                    "visible_text_sha256": sha256_text(normalized) if normalized else None,
                    "title": title,
                    "text_preview": normalized[:400],
                }
    except LookupError as exc:
        return {"category": "gone_candidate", "reason": "dns_lookup_failed", "error": str(exc), "chain": chain}
    except (ValueError, requests.RequestException, OSError) as exc:
        return {"category": "transient_uncertain", "reason": type(exc).__name__, "error": str(exc)[:350], "chain": chain}
    finally:
        session.close()


def probe(record: dict, repeat_errors: bool = True) -> dict:
    url = record.get("selected_url") or record.get("url")
    if not isinstance(url, str) or not url:
        raise ValueError(f"Missing preselected URL for note {record.get('note_id')}")
    first = one_get(url)
    second = None
    if repeat_errors and first["category"] != "open_candidate":
        time.sleep(0.4)
        second = one_get(url)
    if second and (first["category"], first.get("reason")) != (second["category"], second.get("reason")):
        final_category = "transient_uncertain"
    elif second:
        final_category = second["category"]
    else:
        final_category = first["category"]
    return {
        "note_id": record.get("note_id"),
        "author_type": record.get("author_type"),
        "month_utc": record.get("month_utc"),
        "created_at_millis": record.get("created_at_millis"),
        "url": url,
        "url_sha256": sha256_text(url),
        "probed_at_utc": now_utc(),
        "category": final_category,
        "first": first,
        "repeat": second,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    records = json.loads(args.cohort.read_text(encoding="utf-8"))
    if isinstance(records, dict):
        records = records["matched"]
    if args.limit:
        records = records[: args.limit]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    completed: dict[int, dict] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(probe, record): index for index, record in enumerate(records)}
        for future in as_completed(futures):
            index = futures[future]
            try:
                completed[index] = future.result()
            except Exception as exc:
                completed[index] = {"note_id": records[index].get("note_id"), "category": "transient_uncertain", "internal_error": repr(exc)}
            print(f"{len(completed)}/{len(records)}", end="\r", flush=True)
    with args.output.open("w", encoding="utf-8") as stream:
        for index in range(len(records)):
            stream.write(json.dumps(completed[index], ensure_ascii=False) + "\n")
    print(f"\nWrote {args.output} ({len(records)} records)")


if __name__ == "__main__":
    main()
