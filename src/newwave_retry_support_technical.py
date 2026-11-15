"""One prospective technical-completion retry; never salvage unjournaled trials.

Raw per-case prompts and results remain private. The adapter imports the frozen
support prompt, schema, CLI settings and validator without changing them.
"""
import concurrent.futures
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import newwave_judge_support as base

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'results'
T = ROOT / 'tmp' / 'newwave_support_technical_retry'
AMENDMENT = R / 'newwave_support_retry_amendment_PRIVATE.json'
OUT = R / 'newwave_support_retry_trials_PRIVATE.jsonl'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_capture(path, value):
    if isinstance(value, bytes):
        value = value.decode('utf-8', errors='replace')
    path.write_text(value or '', encoding='utf-8')


def run_one(row, schema):
    d = T / row['code']
    d.mkdir(exist_ok=False)
    output = d / 'response.json'
    prompt = base.PROMPT + json.dumps(row, ensure_ascii=False)
    prompt_path = d / 'prompt.txt'
    prompt_path.write_text(prompt, encoding='utf-8')
    original_prompt = ROOT / 'tmp' / 'newwave_support_trials' / row['code'] / 'prompt.txt'
    assert prompt_path.read_bytes() == original_prompt.read_bytes()
    args = [str(base.CLI), 'exec', '--ignore-user-config', '--ephemeral',
            '--skip-git-repo-check', '--sandbox', 'read-only', '--color', 'never',
            '--output-schema', str(schema), '--output-last-message', str(output)]
    for feature in base.DISABLE:
        args += ['--disable', feature]
    args += ['-']
    env = os.environ.copy()
    for name in ['OPENAI_API_KEY', 'OPENAI_BASE_URL']:
        env.pop(name, None)
    result = {'code': row['code'], 'attempt': 'technical_retry_once',
              'started_utc': base.utc(), 'prompt_sha256': sha(prompt_path),
              'packet_row_sha256': hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
              'raw_directory': str(d.relative_to(ROOT))}
    try:
        p = subprocess.run(args, input=prompt, text=True, encoding='utf-8',
                           errors='replace', capture_output=True, cwd=d, env=env,
                           timeout=240)
        save_capture(d / 'stdout.txt', p.stdout)
        save_capture(d / 'stderr.txt', p.stderr)
        model = re.search(r'^model:\s*(.+)$', p.stderr, re.M)
        response = json.loads(output.read_text(encoding='utf-8')) if output.exists() else None
        tool_trace = bool(re.search(r'^(?:exec|web|apply_patch|mcp|tool)\b', p.stderr, re.M))
        errors = base.validate_result(response, row) if response else ['no_response']
        result.update(return_code=p.returncode,
                      model_advertised=model.group(1).strip() if model else None,
                      unexpected_tool_trace=tool_trace, response=response,
                      quote_validation_errors=errors,
                      valid_execution=p.returncode == 0 and model is not None and response is not None and not tool_trace)
    except subprocess.TimeoutExpired as exc:
        save_capture(d / 'stdout.txt', exc.stdout)
        save_capture(d / 'stderr.txt', exc.stderr)
        result.update(valid_execution=False, error='TimeoutExpired: 240-second technical retry limit')
    except Exception as exc:
        result.update(valid_execution=False, error=type(exc).__name__ + ': ' + str(exc)[:300])
    result['ended_utc'] = base.utc()
    (d / 'execution_record.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    amendment = json.loads(AMENDMENT.read_text(encoding='utf-8'))
    for rel, expected in amendment['frozen_inputs_sha256'].items():
        assert sha(ROOT / rel) == expected, rel
    original = [json.loads(line) for line in (R / 'newwave_support_trials_PRIVATE.jsonl').read_text(encoding='utf-8').splitlines()]
    packet = json.loads((R / 'newwave_support_packet_blind.json').read_text(encoding='utf-8'))
    valid_codes = {r['code'] for r in original if r['valid_execution']}
    eligible = [r['code'] for r in packet if r['code'] not in valid_codes]
    assert eligible == amendment['retry_codes'] and len(eligible) == 15
    assert not T.exists() and not OUT.exists(), 'At most one retry; no overwrite or automatic resume.'
    for rel, expected in amendment['original_retry_artifacts_sha256'].items():
        assert sha(ROOT / rel) == expected, rel
    T.mkdir()
    schema = T / 'support_schema.json'
    schema.write_text(json.dumps(base.SCHEMA, indent=2) + '\n', encoding='utf-8')
    assert sha(schema) == sha(ROOT / 'tmp' / 'newwave_support_trials' / 'support_schema.json')
    manifest = {'started_utc': base.utc(), 'amendment_sha256': sha(AMENDMENT),
                'script_sha256': sha(Path(__file__)), 'schema_sha256': sha(schema),
                'cli_sha256': sha(base.CLI), 'workers': 2, 'cases_requested': 15,
                'timeout_seconds': 240, 'same_prompt_schema_content': True,
                'public_protocol_commit': amendment['public_protocol_commit'],
                'selection': 'all cases without a valid original journal record; no semantic selection'}
    (T / 'run_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    rows = [row for row in packet if row['code'] in set(eligible)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor, OUT.open('x', encoding='utf-8') as handle:
        jobs = [executor.submit(run_one, row, schema) for row in rows]
        for future in concurrent.futures.as_completed(jobs):
            result = future.result()
            handle.write(json.dumps(result, ensure_ascii=False) + '\n')
            handle.flush()
            print(result['code'], result['valid_execution'], result.get('model_advertised'), flush=True)
    assert len(OUT.read_text(encoding='utf-8').splitlines()) == 15
    for rel, expected in amendment['original_retry_artifacts_sha256'].items():
        assert sha(ROOT / rel) == expected, rel


if __name__ == '__main__':
    main()
