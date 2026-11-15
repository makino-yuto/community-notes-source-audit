"""Download and verify the dated official Community Notes ZIPs.

The ZIPs remain in local ``data/`` and are excluded from the public package.
Only the source URLs and SHA-256 hashes in the committed manifest are trusted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "results" / "source_manifest_2026-11-14.json"
DATA = ROOT / "data"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="Check existing ZIPs without network requests")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["snapshot_date"] != "2026-11-14":
        raise ValueError("Unexpected snapshot date")
    DATA.mkdir(exist_ok=True)
    for source in manifest["files"]:
        if Path(source["name"]).name != source["name"] or not source["url"].startswith(
            "https://ton.twimg.com/birdwatch-public-data/2026/11/14/"
        ):
            raise ValueError("Unexpected source path or URL")
        target = DATA / source["name"]
        if not target.exists():
            if args.verify_only:
                raise FileNotFoundError(target)
            partial = DATA / (source["name"] + ".partial")
            request = urllib.request.Request(source["url"], headers={"User-Agent": "EvidenceDurabilityStudy/0.1"})
            with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as output:
                total = 0
                for chunk in iter(lambda: response.read(1 << 20), b""):
                    total += len(chunk)
                    if total > source["bytes"]:
                        raise ValueError("Download exceeds manifest size")
                    output.write(chunk)
            if partial.stat().st_size != source["bytes"] or sha256(partial) != source["sha256"]:
                raise ValueError(f"Hash or size mismatch for {source['name']}; partial file retained for inspection")
            partial.replace(target)
        if target.stat().st_size != source["bytes"] or sha256(target) != source["sha256"]:
            raise ValueError(f"Existing file does not match manifest: {source['name']}")
        print(f"verified {source['name']} ({source['bytes']} bytes)")


if __name__ == "__main__":
    main()
