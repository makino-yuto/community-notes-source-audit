"""Aggregate the preselected source-role and claim-support review packets."""

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"


def jsonl(name):
    return [json.loads(line) for line in (RES / name).read_text(encoding="utf-8").splitlines() if line]


def main():
    key = json.loads((RES / "role_sample_key.json").read_text(encoding="utf-8"))
    group = {row["code"]: row["author_type"] for row in key["rows"]}
    assert len(group) == 100 and Counter(group.values()) == {"AI_API": 50, "non_API": 50}
    roles = jsonl("role_labels_blind.jsonl")
    assert len(roles) == 100 and {r["code"] for r in roles} == set(group)
    selected = json.loads((RES / "support_sample_40.json").read_text(encoding="utf-8"))["codes"]
    assert len(selected) == len(set(selected)) == 40
    labels = jsonl("support_audit_agent_first20.jsonl") + jsonl("support_audit_root_last20.jsonl")
    assert len(labels) == 40 and {r["code"] for r in labels} == set(selected)
    assert all(next(x for x in roles if x["code"] == r["code"])["role"] == "SUPPORT" for r in labels)
    role_by_group = defaultdict(Counter)
    for r in roles:
        role_by_group[group[r["code"]]][r["role"]] += 1
    support_by_group = defaultdict(Counter)
    for r in labels:
        support_by_group[group[r["code"]]][r["support_current"]] += 1
    note_for_code = {row["code"]: row["note_id"] for row in key["rows"]}
    probe_category = {row["note_id"]: row["category"] for row in jsonl("probes_2026-11-15.jsonl")}
    support_by_machine = defaultdict(Counter)
    for r in labels:
        support_by_machine[probe_category[note_for_code[r["code"]]]][r["support_current"]] += 1
    out = {
        "role_sample": {"n": 100, "by_group": {g: dict(role_by_group[g]) for g in sorted(role_by_group)}, "overall": dict(Counter(r["role"] for r in roles))},
        "support_subsample": {"n": 40, "by_group": {g: dict(support_by_group[g]) for g in sorted(support_by_group)}, "by_machine_category": {c: dict(support_by_machine[c]) for c in sorted(support_by_machine)}, "overall": dict(Counter(r["support_current"] for r in labels))},
        "interpretation": "AI-assisted source-role and current-page support coding; not human validated, not note truth, not historic source support.",
    }
    (RES / "support_audit_aggregate.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
