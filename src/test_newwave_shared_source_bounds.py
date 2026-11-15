"""Exhaustively check within-pair bounds for a three-URL universe."""

import itertools

from newwave_shared_source_bounds import pair_bounds

UNIVERSE = ("u0", "u1", "u2")
STATES = ("accessible", "not_accessible", "unresolved")
SUBSETS = [set(combo) for size in (1, 2, 3) for combo in itertools.combinations(UNIVERSE, size)]
checks = 0

for state_tuple in itertools.product(STATES, repeat=3):
    labels = dict(zip(UNIVERSE, state_tuple))
    unknown = [url for url in UNIVERSE if labels[url] == "unresolved"]
    for ai in SUBSETS:
        for non in SUBSETS:
            old_lo, old_hi, lo, hi = pair_bounds(ai, non, labels)
            actual = []
            for bits in itertools.product((0, 1), repeat=len(unknown)):
                completion = dict(zip(unknown, bits))
                ai_access = any(labels[url] == "accessible" or (labels[url] == "unresolved" and completion[url]) for url in ai)
                non_access = any(labels[url] == "accessible" or (labels[url] == "unresolved" and completion[url]) for url in non)
                actual.append(int(ai_access)-int(non_access))
            assert lo == min(actual) and hi == max(actual), (labels,ai,non,(lo,hi),actual)
            assert old_lo <= lo <= hi <= old_hi
            checks += 1

assert checks == 3**3 * 7 * 7 == 1323
print(f"Exhaustive three-URL logical test passed: {checks} state/subset cases")
