"""Transparent no-retry continuation after one quote-cap validation failure.

The original frozen prompt, packet and 20-word quote cap remain unchanged.
J003 stays invalid. Two concurrently launched cases (J004/J005) have raw
outputs but no committed trial rows; both are mechanically salvaged regardless
of their labels. Subsequent invalid cases are retained and do not stop the
unconditional 62-case run.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import newwave_longitudinal_judge as base
from newwave_judge_support import validate_result

HERE = Path(__file__).resolve()
PUBLIC = HERE.parents[1]
PRIVATE = PUBLIC.parent / "results"
V1_PROTOCOL = PUBLIC / "protocols" / "2026-11-15-longitudinal-judge.json"
V2_PROTOCOL = PUBLIC / "protocols" / "2026-11-15-longitudinal-judge-v2.json"
PACKET = PRIVATE / "newwave_longitudinal_judge_packet_PRIVATE.json"
V1_LOG = PRIVATE / "newwave_longitudinal_judgments_PRIVATE.jsonl"
V2_LOG = PRIVATE / "newwave_longitudinal_judgments_v2_PRIVATE.jsonl"
V1_LOG_SHA = "d7441ccd4df7b09aa96a392596ada098500159589d50468de87c5c9902c1dc33"
RAW_FILENAMES = ("prompt.txt", "stdout.txt", "stderr.txt", "response.json")
SALVAGE_CODES = ("J004", "J005")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def verify_fixed(packet_path: Path, v1_protocol: Path, v1_log: Path) -> list[dict]:
    plan = json.loads(v1_protocol.read_text(encoding="utf-8"))
    if sha(packet_path) != plan["inputs"]["packet_sha256"]:
        raise ValueError("Frozen packet changed")
    if sha(Path(base.__file__)) != plan["inputs"]["judge_script_sha256"]:
        raise ValueError("Original frozen judge changed")
    if sha(v1_log) != V1_LOG_SHA:
        raise ValueError("First three-row trial log changed")
    previous = read_rows(v1_log)
    if [r["code"] for r in previous] != ["J001", "J002", "J003"]:
        raise ValueError("Unexpected original trial code sequence")
    if [r["valid_execution"] for r in previous] != [True, True, False]:
        raise ValueError("Original trial failure pattern differs")
    if previous[-1]["quote_validation_errors"] != ["quote_word_limit"]:
        raise ValueError("Original halt was not the documented quote-cap failure")
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    if len(packet) != 62 or [r["code"] for r in packet] != [
        f"J{i:03d}" for i in range(1, 63)
    ]:
        raise ValueError("Packet changed from fixed 62-case order")
    return packet


def raw_hashes(code: str) -> dict[str, str]:
    directory = base.TMP / code
    return {name: sha(directory / name) for name in RAW_FILENAMES}


def prepare(path: Path, packet_path: Path, v1_protocol: Path, v1_log: Path,
            output_path: Path) -> dict:
    if path.exists() or output_path.exists():
        raise FileExistsError("V2 protocol or output already exists")
    verify_fixed(packet_path, v1_protocol, v1_log)
    raw = {code: raw_hashes(code) for code in SALVAGE_CODES}
    plan = {
        "schema": "newwave-longitudinal-judge-no-retry-continuation-v2",
        "status": "FROZEN BEFORE ANY V2 CONTINUATION MODEL CALL",
        "prepared_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reason": "Original J003 response exceeded the frozen 20-word literal quotation cap by one word; the original runner halted after logging J001–J003. Concurrent workers had already materialized J004/J005 raw outputs.",
        "rules": {
            "fixed_sample": "All 62 opaque packet items remain; J003 is invalid/unknown in analysis.",
            "salvage": "Mechanically validate both J004/J005 raw responses and prompt/log provenance regardless of labels, without re-calling either. Missing return codes are disclosed; schema/quote/tool checks still apply.",
            "continuation": "Run only J006–J062 under the identical frozen prompt, packet, schema, and quote rule. Record every outcome, including invalid results, and never stop or retry based on labels or validation status.",
            "interruption": "If a future worker materializes raw output before its row is appended, mechanically salvage it; partial raw output becomes invalid/unknown without retry.",
            "denominators": "Retain all 62 judgment items and all 100 archive panel units. Invalid trial is unknown, never NONE.",
        },
        "inputs": {
            "v1_protocol_sha256": sha(v1_protocol),
            "v1_log_sha256": sha(v1_log),
            "packet_sha256": sha(packet_path),
            "v1_judge_script_sha256": sha(Path(base.__file__)),
            "base_prompt_script_sha256": sha(PUBLIC / "src" / "newwave_judge_support.py"),
            "cli_sha256": sha(base.CLI),
            "v2_script_sha256": sha(HERE),
            "preexisting_raw_outputs_sha256": raw,
        },
        "new_model_calls_at_freeze": 0,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    return {"protocol_sha256": sha(path), "salvage_codes": list(SALVAGE_CODES),
            "continuation_codes": "J006-J062"}


def salvage(row: dict) -> dict:
    code = row["code"]
    directory = base.TMP / code
    expected_prompt = base.PROMPT + json.dumps(row, ensure_ascii=False, separators=(",", ":"))
    existing = [name for name in RAW_FILENAMES if (directory / name).exists()]
    record = {
        "code": code,
        "provenance_class": "preexisting_raw_salvage",
        "raw_file_sha256": {name: sha(directory / name) for name in existing},
        "return_code_recorded": False,
        "started_utc": None,
        "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    errors = []
    if set(existing) != set(RAW_FILENAMES):
        errors.append("incomplete_raw_output")
    if "prompt.txt" in existing:
        # Path.write_text on Windows translates LF to CRLF; compare the
        # frozen prompt using that exact recorded write transformation.
        if (directory / "prompt.txt").read_bytes() != expected_prompt.replace("\n", "\r\n").encode("utf-8"):
            errors.append("prompt_mismatch")
    response = None
    if "response.json" in existing:
        try:
            response = json.loads((directory / "response.json").read_text(encoding="utf-8"))
            errors.extend(validate_result(response, row))
            if row["source_quality_warning"] and response["main_claim_verdict"] != "UNASSESSABLE":
                errors.append("archive_wrapper_not_unassessable")
        except Exception as exc:
            errors.append("invalid_response:" + type(exc).__name__)
    stderr = (directory / "stderr.txt").read_text(encoding="utf-8") if "stderr.txt" in existing else ""
    model = re.search(r"^model:\s*(.+)$", stderr, re.M)
    unexpected_tool = bool(re.search(r"^(?:exec|web|apply_patch|mcp|tool)\b", stderr, re.M))
    if model is None:
        errors.append("missing_model_marker")
    if unexpected_tool:
        errors.append("unexpected_tool_trace")
    record.update({
        "response": response,
        "model_advertised": model.group(1).strip() if model else None,
        "unexpected_tool_trace": unexpected_tool,
        "quote_validation_errors": errors,
        "packet_row_sha256": hashlib.sha256(
            json.dumps(row, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")).encode("utf-8")).hexdigest(),
        "prompt_sha256": hashlib.sha256(expected_prompt.encode("utf-8")).hexdigest(),
        "valid_execution": not errors,
    })
    return record


def run(protocol_path: Path, packet_path: Path, v1_protocol: Path,
        v1_log: Path, output_path: Path, workers: int) -> None:
    if workers != 2:
        raise ValueError("Frozen continuation uses exactly two workers")
    packet = verify_fixed(packet_path, v1_protocol, v1_log)
    plan = json.loads(protocol_path.read_text(encoding="utf-8"))
    if (sha(HERE) != plan["inputs"]["v2_script_sha256"] or
        sha(v1_protocol) != plan["inputs"]["v1_protocol_sha256"] or
        sha(packet_path) != plan["inputs"]["packet_sha256"] or
        sha(base.CLI) != plan["inputs"]["cli_sha256"] or
        sha(PUBLIC / "src" / "newwave_judge_support.py") !=
        plan["inputs"]["base_prompt_script_sha256"]):
        raise ValueError("V2 frozen code/protocol/input mismatch")
    for code in SALVAGE_CODES:
        if raw_hashes(code) != plan["inputs"]["preexisting_raw_outputs_sha256"][code]:
            raise ValueError("Preexisting J004/J005 raw output changed")
    prior = read_rows(output_path) if output_path.exists() else []
    done = {row["code"] for row in prior}
    if len(done) != len(prior) or any(code not in [f"J{i:03d}" for i in range(4, 63)] for code in done):
        raise ValueError("Unexpected V2 continuation log")
    pending = [row for row in packet[3:] if row["code"] not in done]
    schema_path = base.TMP / "schema.json"
    if not schema_path.exists():
        schema_path.write_text(json.dumps(base.SCHEMA, indent=2) + "\n", encoding="utf-8")
    if schema_path.read_text(encoding="utf-8") != json.dumps(base.SCHEMA, indent=2) + "\n":
        raise ValueError("Original frozen output schema changed")
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool, output_path.open(
        "a", encoding="utf-8", newline="\n"
    ) as stream:
        def one(row: dict) -> dict:
            if any((base.TMP / row["code"] / name).exists() for name in RAW_FILENAMES):
                return salvage(row)
            return base.assess_one(row, schema_path)
        for result in pool.map(one, pending):
            stream.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            print(result["code"], result.get("model_advertised"),
                  (result.get("response") or {}).get("main_claim_verdict"),
                  result.get("quote_validation_errors"), flush=True)
    final = read_rows(output_path)
    if len(final) != 59 or [row["code"] for row in final] != [
        f"J{i:03d}" for i in range(4, 63)
    ]:
        raise ValueError("V2 continuation did not record all 59 items")
    print(json.dumps({"recorded": len(final),
                      "valid": sum(row.get("valid_execution") is True for row in final),
                      "invalid": sum(row.get("valid_execution") is not True for row in final),
                      "results_sha256": sha(output_path)}), flush=True)


def main() -> None:
    p = argparse.ArgumentParser()
    action = p.add_mutually_exclusive_group(required=True)
    action.add_argument("--prepare", action="store_true")
    action.add_argument("--collect", action="store_true")
    p.add_argument("--protocol", type=Path, default=V2_PROTOCOL)
    p.add_argument("--packet", type=Path, default=PACKET)
    p.add_argument("--v1-protocol", type=Path, default=V1_PROTOCOL)
    p.add_argument("--v1-log", type=Path, default=V1_LOG)
    p.add_argument("--output", type=Path, default=V2_LOG)
    p.add_argument("--workers", type=int, default=2)
    a = p.parse_args()
    if a.prepare:
        print(json.dumps(prepare(a.protocol, a.packet, a.v1_protocol, a.v1_log, a.output)), flush=True)
    else:
        run(a.protocol, a.packet, a.v1_protocol, a.v1_log, a.output, a.workers)


if __name__ == "__main__":
    main()
