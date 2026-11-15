"""Conservative, auditable external-URL extraction for a second-pass study.

This fixes known syntax defects in the first study's regex without making
content-specific repairs. In particular, a BBC ``.amp`` path is left as
written; it is a source URL, not a parser defect. Every retained URL carries
the literal text span and normalization flags. Ambiguous cases are flagged
for review rather than silently rewritten.

No network activity occurs here. Any later probe must separately resolve DNS
and verify that *every* redirect target is a public address.
"""

from __future__ import annotations

import html
import ipaddress
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit


START = re.compile(r"https?://", re.IGNORECASE)
STOP = set(" \t\r\n\v\f<>\"'`[]")
TRAILING = set(".,;!?。、，．；！？：:）】」』〉》〕〗〙〛»”’}\u3000")
MATCHED_CJK_CLOSERS = {"）": "（", "】": "【", "」": "「", "』": "『", "〉": "〈", "》": "《", "〕": "〔", "〗": "〖", "〙": "〘", "〛": "〚"}
PRIVATE_SUFFIXES = (".localhost", ".local", ".internal", ".test", ".example", ".invalid")
EXCLUDED_PLATFORM = {"x.com", "twitter.com", "t.co", "twimg.com"}
VALID_LABEL = re.compile(r"[a-z0-9-]{1,63}\Z")
VALID_TLD = re.compile(r"(?:[a-z]{2,63}|xn--[a-z0-9-]{2,59})\Z")
BAD_PERCENT = re.compile(r"%(?![a-fA-F0-9]{2})")
CJK = re.compile(r"[\u3000-\u30ff\u3400-\u9fff]")
EXPLICIT_HTML_ENTITY = re.compile(r"&(?:amp|quot|apos|lt|gt|#[0-9]+|#x[0-9a-f]+);", re.IGNORECASE)


def _trim(raw: str) -> tuple[str, list[str]]:
    flags = []
    value = raw
    while value:
        c = value[-1]
        if c == ")":
            if value.count(")") > value.count("("):
                value = value[:-1]
                if "unmatched_closing_parenthesis_trimmed" not in flags:
                    flags.append("unmatched_closing_parenthesis_trimmed")
                continue
            break
        if c in MATCHED_CJK_CLOSERS:
            if value.count(c) > value.count(MATCHED_CJK_CLOSERS[c]):
                value = value[:-1]
                flags.append("unmatched_cjk_closing_trimmed")
                continue
            break
        if c in TRAILING:
            value = value[:-1]
            flag = "cjk_closing_punctuation_trimmed" if c in "）】」』〉》〕〗〙〛" else "terminal_punctuation_trimmed"
            if flag not in flags:
                flags.append(flag)
            continue
        if c == "(" and value.count("(") > value.count(")"):
            value = value[:-1]
            flags.append("unmatched_opening_parenthesis_trimmed")
            continue
        break
    return value, flags


def _validate(value: str) -> tuple[str | None, str | None, list[str]]:
    flags = []
    if BAD_PERCENT.search(value):
        # A literal percent is legal as displayed text (notably in text
        # fragments). Keep the URL with a review flag; the browser/client may
        # percent-encode it during navigation.
        flags.append("noncanonical_percent_encoding_review")
    if any(ord(c) < 33 or ord(c) == 127 or c.isspace() for c in value):
        return None, "space_or_control", flags
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port  # also validates the numeric range
    except ValueError:
        return None, "urlsplit_or_port_error", flags
    if parsed.scheme.lower() not in ("http", "https") or not host or parsed.username is not None or parsed.password is not None:
        return None, "malformed_or_userinfo", flags
    try:
        ipaddress.ip_address(host)
        return None, "ip_address", flags
    except ValueError:
        pass
    try:
        ascii_host = host.encode("idna").decode("ascii").lower()
    except UnicodeError:
        return None, "invalid_idna_host", flags
    labels = ascii_host.split(".")
    if len(labels) < 2 or any(not VALID_LABEL.fullmatch(label) or label.startswith("-") or label.endswith("-") for label in labels) or not VALID_TLD.fullmatch(labels[-1]):
        return None, "invalid_hostname", flags
    if ascii_host == "localhost" or ascii_host.endswith(PRIVATE_SUFFIXES):
        return None, "private_or_reserved_host", flags
    if ascii_host in EXCLUDED_PLATFORM or any(ascii_host.endswith("." + d) for d in EXCLUDED_PLATFORM):
        return None, "platform_host", flags
    if ascii_host != host:
        flags.append("idna_hostname")
    if port not in (None, 80, 443):
        flags.append("nonstandard_port")
    if CJK.search(parsed.path + parsed.query + parsed.fragment):
        flags.append("unicode_path_query_or_fragment_review")
    netloc = ascii_host + (f":{port}" if port is not None else "")
    normalized = urlunsplit((parsed.scheme.lower(), netloc, parsed.path, parsed.query, parsed.fragment))
    return normalized, None, flags


def extract_urls(text: str) -> tuple[list[dict], list[dict]]:
    """Return de-duplicated external URLs and rejected candidates with reasons.

    ``span_start`` and ``span_end`` index the original unescaped note summary.
    The raw literal retains HTML entities; ``normalized_url`` unescapes them,
    trims only terminal punctuation/unmatched closing parentheses, lowercases
    the scheme/host, and IDNA-encodes the host. Equal normalized URLs retain
    the first occurrence and add ``duplicate_occurrences``.
    """
    kept = []
    rejected = []
    seen = {}
    for match in START.finditer(text):
        start = match.start()
        # Avoid treating an inner https:// in an already captured query as a
        # second independent citation (common with redirect parameters).
        if any(item["span_start"] <= start < item["span_end"] for item in kept + rejected):
            continue
        end = match.end()
        while end < len(text) and text[end] not in STOP and not text[end].isspace() and unicodedata.category(text[end]) not in {"Cc", "Cf"}:
            closer = text[end]
            if closer in MATCHED_CJK_CLOSERS:
                consumed = text[start:end]
                if consumed.count(MATCHED_CJK_CLOSERS[closer]) <= consumed.count(closer):
                    break
            end += 1
        raw_literal = text[start:end]
        # Require a semicolon so a literal query such as ``&not=1`` is not
        # accidentally interpreted as an HTML character entity.
        unescaped = EXPLICIT_HTML_ENTITY.sub(lambda m: html.unescape(m.group()), raw_literal)
        candidate, flags = _trim(unescaped)
        if end < len(text) and (text[end].isspace() or unicodedata.category(text[end]) == "Cf") and text[end] not in STOP:
            flags.append("unicode_whitespace_or_format_delimiter_stop")
        if end < len(text) and text[end] in "）】」』〉》〕〗〙〛":
            flags.append("cjk_closing_delimiter_stop")
        if unescaped != raw_literal:
            flags.insert(0, "html_entity_unescaped")
        normalized, reason, more_flags = _validate(candidate)
        flags.extend(more_flags)
        record = {
            "raw_literal": raw_literal,
            "span_start": start,
            "span_end": end,
            "normalized_url": normalized,
            "flags": sorted(set(flags)),
        }
        if reason:
            record["rejection_reason"] = reason
            rejected.append(record)
            continue
        assert normalized is not None
        if normalized in seen:
            seen[normalized]["duplicate_occurrences"] += 1
            continue
        record["duplicate_occurrences"] = 1
        seen[normalized] = record
        kept.append(record)
    return kept, rejected


if __name__ == "__main__":
    fixtures = [
        ("https://en.wikipedia.org/wiki/The_Breadwinner_(film)", "https://en.wikipedia.org/wiki/The_Breadwinner_(film)"),
        ("（https://togetter.com/li/948152）および関連X投稿。", "https://togetter.com/li/948152"),
        ("https://www.eia.gov/a?f=W&amp;n=PET", "https://www.eia.gov/a?f=W&n=PET"),
        ("https://www.bbc.com/portuguese/articles/cq52lg1g8980.amp", "https://www.bbc.com/portuguese/articles/cq52lg1g8980.amp"),
        ("https://ja.wikipedia.org/wiki/東京", "https://ja.wikipedia.org/wiki/東京"),
        ("https://ja.wikipedia.org/wiki/東京（映画）", "https://ja.wikipedia.org/wiki/東京（映画）"),
        ("https://en.wikipedia.org/wiki/A_(B)).", "https://en.wikipedia.org/wiki/A_(B)"),
        ("https://decopy.ai/a#:~:text=100%", "https://decopy.ai/a#:~:text=100%"),
        ("https://example.org/path\u200a\u200a", "https://example.org/path"),
    ]
    for source, expected in fixtures:
        found, _ = extract_urls(source)
        assert len(found) == 1 and found[0]["normalized_url"] == expected, (source, found)
    for bad in ("http://127.0.0.1/", "http://metadata.google.internal/", "http://x.com/a", "https://example.test/path", "http://user:pass@example.org/"):
        found, rejected = extract_urls(bad)
        assert not found and rejected, bad
    print("revision_extract_urls fixtures passed")
