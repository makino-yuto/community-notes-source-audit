"""Recompute the frozen primary contrast from the released anonymous pairs.

This reproduces the dated descriptive statistics, not historical URL responses.
"""

import csv
import random
from collections import Counter, defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "results" / "anonymous_pairs.csv"
ALLOWED = {"open_candidate", "access_barrier", "transient_uncertain", "gone_candidate"}


def quantile(sorted_values, p):
    pos = (len(sorted_values) - 1) * p
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def main():
    with DATA.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 300
    months = defaultdict(list)
    ai_counts, non_counts = Counter(), Counter()
    for i, row in enumerate(rows, 1):
        assert int(row["pair_index"]) == i
        a, b = row["ai_api_category"], row["non_api_category"]
        assert a in ALLOWED and b in ALLOWED
        ai_counts[a] += 1
        non_counts[b] += 1
        months[row["month_utc"]].append((a == "open_candidate", b == "open_candidate"))
    diff = (ai_counts["open_candidate"] - non_counts["open_candidate"]) / 300
    rng = random.Random(20261115)
    vals = []
    for _ in range(10000):
        total = 0
        for month_pairs in months.values():
            for _ in range(len(month_pairs)):
                a, b = month_pairs[rng.randrange(len(month_pairs))]
                total += a - b
        vals.append(total / 300)
    vals.sort()
    print("AI_API", dict(ai_counts))
    print("non_API", dict(non_counts))
    print("difference", round(diff, 8))
    print("within-month paired bootstrap 95%", [round(quantile(vals, .025), 8), round(quantile(vals, .975), 8)])


if __name__ == "__main__":
    main()
