"""Run frozen, independent source-to-claim judgments for archive versions."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from newwave_judge_support import PROMPT as BASE_PROMPT, SCHEMA, validate_result
from newwave_model_trials import CLI, DISABLE

HERE = Path(__file__).resolve()
PUBLIC = HERE.parents[1]
PRIVATE = PUBLIC.parent / "results"
TMP = PUBLIC.parent / "tmp" / "newwave_longitudinal_judge_trials"
DEFAULT_PACKET = PRIVATE / "newwave_longitudinal_judge_packet_PRIVATE.json"
DEFAULT_PROTOCOL = PUBLIC / "protocols" / "2026-11-15-longitudinal-judge.json"
DEFAULT_RESULTS = PRIVATE / "newwave_longitudinal_judgments_PRIVATE.jsonl"
BASE_JUDGE_SHA256 = "8165cd69de668d0bd01c500ef16f9a14bf97bb0cb636f49d67bc599cfec690a5"
PROMPT = (
    BASE_PROMPT.replace(
        "Consider ALL supplied sources.",
        "Consider the one supplied source. Its historical/current version is hidden."
    ).replace(
        "Do not infer cohort/author identity.",
        "Do not infer cohort, author identity, or source version. "
        "The source may include temporal clues; still judge only the observed text. "
        "If it is an Archive error/wrapper rather than the intended source, use UNASSESSABLE."
    )
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def assess_one(row: dict, schema_path: Path) -> dict:
    code = row["code"]
    case_dir = TMP / code
    case_dir.mkdir(parents=True, exist_ok=True)
    response_path = case_dir / "response.json"
    if response_path.exists():
        raise FileExistsError(response_path)
    prompt = PROMPT + json.dumps(row, ensure_ascii=False, separators=(",", ":"))
    (case_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    args = [str(CLI), "exec", "--ignore-user-config", "--ephemeral",
            "--skip-git-repo-check", "--sandbox", "read-only", "--color", "never",
            "--output-schema", str(schema_path), "--output-last-message", str(response_path)]
    for feature in DISABLE:
        args.extend(["--disable", feature])
    args.append("-")
    env = os.environ.copy()
    for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL"):
        env.pop(key, None)
    started = utc()
    try:
        run = subprocess.run(args, input=prompt, text=True, encoding="utf-8",
                             errors="replace", capture_output=True,
                             cwd=case_dir, env=env, timeout=240, check=False)
        (case_dir / "stdout.txt").write_text(run.stdout, encoding="utf-8")
        (case_dir / "stderr.txt").write_text(run.stderr, encoding="utf-8")
        response = json.loads(response_path.read_text(encoding="utf-8")) if response_path.exists() else None
        model = re.search(r"^model:\s*(.+)$", run.stderr, re.M)
        unexpected_tool = bool(re.search(r"^(?:exec|web|apply_patch|mcp|tool)\b", run.stderr, re.M))
        errors = validate_result(response, row) if response else ["missing_response"]
        if response and row["source_quality_warning"] and response["main_claim_verdict"] != "UNASSESSABLE":
            errors.append("archive_wrapper_not_unassessable")
        return {
            "code": code, "started_utc": started, "finished_utc": utc(),
            "response": response, "return_code": run.returncode,
            "model_advertised": model.group(1).strip() if model else None,
            "unexpected_tool_trace": unexpected_tool,
            "quote_validation_errors": errors,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "packet_row_sha256": hashlib.sha256(
                json.dumps(row, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")).hexdigest(),
            "valid_execution": (run.returncode == 0 and model is not None and
                                response is not None and not unexpected_tool and not errors),
        }
    except Exception as exc:
        return {"code": code, "started_utc": started, "finished_utc": utc(),
                "valid_execution": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}


def run(packet_path: Path, protocol_path: Path, output_path: Path, workers: int,
        limit: int | None) -> None:
    if not 1 <= workers <= 2:
        raise ValueError("At most two independent workers")
    plan = json.loads(protocol_path.read_text(encoding="utf-8"))
    if (sha(packet_path) != plan["inputs"]["packet_sha256"] or
        sha(HERE) != plan["inputs"]["judge_script_sha256"] or
        sha(PUBLIC / "src" / "newwave_judge_support.py") != BASE_JUDGE_SHA256):
        raise ValueError("Frozen packet, judge, or base prompt changed")
    rows = json.loads(packet_path.read_text(encoding="utf-8"))
    if len(rows) != 62 or len({row["code"] for row in rows}) != 62:
        raise ValueError("Expected 62 opaque items")
    if any(set(row) != {"code", "main_claim", "sources", "source_quality_warning"} or
           len(row["sources"]) != 1 or row["sources"][0]["source_id"] != "S1"
           for row in rows):
        raise ValueError("Packet includes unexpected fields")
    TMP.mkdir(parents=True, exist_ok=True)
    schema_path = TMP / "schema.json"
    schema_path.write_text(json.dumps(SCHEMA, indent=2) + "\n", encoding="utf-8")
    done = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()] if output_path.exists() else []
    if len({row["code"] for row in done}) != len(done) or any(not row.get("valid_execution") for row in done):
        raise ValueError("Prior trial log invalid; no automatic retry")
    pending = [row for row in rows if row["code"] not in {d["code"] for d in done}]
    if limit is not None:
        pending = pending[:limit]
    metadata = {
        "utc": utc(), "packet_sha256": sha(packet_path),
        "protocol_sha256": sha(protocol_path),
        "schema_sha256": sha(schema_path), "judge_script_sha256": sha(HERE),
        "base_prompt_script_sha256": BASE_JUDGE_SHA256,
        "cli_sha256": sha(CLI), "cases_requested": len(pending),
        "workers": workers, "text_cap_per_source": 24_000,
    }
    (TMP / f"run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool, output_path.open(
        "a", encoding="utf-8", newline="\n"
    ) as stream:
        for result in pool.map(lambda row: assess_one(row, schema_path), pending):
            stream.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            print(result["code"], result.get("model_advertised"),
                  (result.get("response") or {}).get("main_claim_verdict"),
                  result.get("quote_validation_errors"), flush=True)
            if not result["valid_execution"]:
                raise RuntimeError("Invalid frozen judgment; inspect log, no automatic retry")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    p.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    p.add_argument("--output", type=Path, default=DEFAULT_RESULTS)
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--limit", type=int)
    a = p.parse_args()
    run(a.packet, a.protocol, a.output, a.workers, a.limit)


if __name__ == "__main__":
    main()
