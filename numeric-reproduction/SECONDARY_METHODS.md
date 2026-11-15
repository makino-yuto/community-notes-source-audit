# Public reproduction of secondary measurement analyses

This add-on uses only the existing anonymous numeric package: `manifest.json`, `data/machine_pairs_anonymous.csv`, and `data/browser_pairs_anonymous.csv`. It uses the Python standard library, makes no network requests, and does not read private keys, source identifiers, observations, or page text. Both CSV hashes and row counts are checked against the unchanged manifest. Original CSVs, manifest, primary code and primary results are never written.

These analyses were conceived after field outcomes. They are secondary measurement comparisons and a conservative sampling sensitivity; they do not replace the frozen primary analysis or relabel observations.

When the new script is installed alongside the existing numeric package's `src/`, run from that package directory:

    python src/reproduce_newwave_secondary_public.py --self-test --output secondary_reproduced.json

While staged separately, supply the numeric-package directory:

    python path/to/add-on/src/reproduce_newwave_secondary_public.py --package path/to/numeric-reproduction --self-test --output secondary_reproduced.json

The output must be a new filename. Omitting `--output` prints JSON. The script does not depend on the staged example result or verification report.

## Weighted machine/browser disagreement

The machine table is a census of 1,882 pairs, with one note per group. The browser table contains 240 pairs, sampled without replacement: 60 from each machine-any stratum. For AI-API notes, machine-any `M=1` in `both` and `ai_only`; for non-API notes, `M=1` in `both` and `non_api_only`. Browser `[L,U]` is read directly from the group's `any_lower` and `any_upper` fields. The independently shuffled CSV rows are never matched or joined.

For each note:

- Joint machine-positive/browser-negative endpoints: `M(1-U)` and `M(1-L)`.
- Joint machine-negative/browser-positive endpoints: `(1-M)L` and `(1-M)U`.
- Browser-minus-machine endpoints: `L-M` and `U-M`.

Endpoints are averaged within stratum and combined using population shares `N_h/1882`. Endpoint design SEs use stratified SRS-without-replacement finite-population variance. Displayed ranges are estimated missing-content bounds, **not confidence intervals**. Joint fractions use all notes as denominator; the first is not the conventional false-positive rate conditional on actual browser negativity.

Exact machine-positive/negative counts are independently recomputed from the machine census CSV and checked against the stratum definitions: 1,701/181 AI-API notes and 1,532/350 non-API notes. The corresponding joint-fraction endpoints divided by these exact probabilities give the conditional diagnostics.

| Note-level estimated bound | AI-API | Non-API |
|---|---:|---:|
| Machine positive, browser negative; all notes | 3.01-5.79% | 2.88-8.31% |
| Machine negative, browser positive; all notes | 6.45-7.96% | 8.82-13.09% |
| Browser positive among machine-negative notes | 67.07-82.75% | 47.43-70.40% |
| Browser-minus-machine probability | +0.66 to +4.95 pp | +0.51 to +10.21 pp |

These measure channel disagreement, not human-verified classifier error or factual truth. Sampling uncertainty remains material. Browser profile, execution mode, and observation time differ from machine retrieval. The 674 unique URLs are not a representative URL sample and supply no population denominator here.

The optional within-note random-reference cross-channel analysis in the private-key aggregate cannot be reconstructed from these CSVs: they omit reference-level matches between machine and browser outcomes. This add-on reproduces only the note-level comparison identified by released fields.

## Conservative exact-tail sampling sensitivity

For each browser pair, `dL = ai_any_lower - non_any_upper` and `dU = ai_any_upper - non_any_lower`. Both belong to `{-1,0,+1}`. The positive and negative sampled counts for a stratum endpoint have hypergeometric marginals with unknown population counts `Kplus` and `Kminus`.

For observed count `k`, the lower count limit is the smallest integer `K` with inclusive tail `P_K(X >= k) > 1/320`. The upper is the largest `K` with `P_K(X <= k) > 1/320`. Tails are exact integer sums of `comb(K,x) comb(N-K,n-x)`, with denominator `comb(N,n)`. Binary search compares integer numerators multiplied by 320, avoiding floating probability rounding. Census strata recover observed counts exactly.

The outer lower limit uses lower `Kplus` minus upper `Kminus` for `dL`; the outer upper uses upper `Kplus` minus lower `Kminus` for `dU`. There are four required directional limits per stratum, sixteen total. Each has noncoverage at most `1/320`; Bonferroni's union bound gives joint coverage at least `1-16/320=95%`, without requiring count independence. Sum the selected count differences over strata and divide by 1,882. Both scalar limits are displayed for auditability, but simultaneous coverage of every displayed scalar limit is not asserted.

The public CSV reproduces **-13.66 to +26.94 pp**, exactly `[-257/1882, 507/1882]`. It also reproduces frozen missing-content bounds **-0.57 to +13.42 pp** and approximate normal outer interval **-4.87 to +19.17 pp**. The sensitivity does not demonstrate that the normal approximation undercovers; it supplies an alternative finite-sample guarantee under the stated assumptions.

Coverage is conditional on fixed endpoint states and random pair sampling. It excludes AI annotation error, page or browser-profile changes, and extrapolation to new posts or writers. Equal allocation over sixteen tails and separate marginal count limits make the interval deliberately conservative. Primary labels and estimands do not change.

With `--self-test`, distributions are independently built by enumerating every actual sample subset for all `N=1..16`, all sample sizes including zero and census, and every population positive count. These verify inclusive tails, binary inversion against an exhaustive search over `K`, scalar noncoverage and census collapse. There are 1,784 `N,n,K` configurations, including nonzero failure cases; maximum one-sided noncoverage is `1/330`, below `1/320`.

## Scope of reproduction

The staged `secondary_reproduced.json` uses only the numeric package. The separate verification report compares its aggregates against the private-key analyses. The add-on does not independently verify historical web-content classifications. Browser access remains an AI-assisted browser-profile endpoint, distinct from source support and factual truth.

The script was also run with its default package path in a minimal temporary directory containing only the unchanged manifest, two CSVs, and new script. With `--self-test`, its entire output exactly matched the staged result. `numeric_only_smoke_verification.json` records that portability check.

## Evidence-validator breakdown supplied as an aggregate

`support_validator_failure_breakdown.json` and the matching small Markdown table separately report failure categories from the frozen selected support executions. They are public-safe aggregate outputs, not inputs to the public numeric reproducer. Their original source packets and individual executions are withheld, so this breakdown cannot be independently rebuilt from the two numeric CSVs.

With 100 selected notes per group, exclusive counts are nonliteral-only 2/1, length-only 8/4, both 3/0, invalid execution 1/0, and no validation failure 86/95 (AI-API/non-API). The 13/5 evidence-positive validator failures reproduce the existing strict downgrades. The invalid execution was already UNASSESSABLE in both summaries and is not an additional positive-label downgrade. All 199 valid selected executions were independently revalidated against the frozen rule, with zero stored-error mismatches and unchanged raw/strict group label counts. Length-only failures measure output compliance, not proof of absent semantic support.
