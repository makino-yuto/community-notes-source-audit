# Can Readers Still Check the Source?

Reproduction package for a dated, descriptive audit of external source URLs in Helpful X Community Notes in the official 2026-11-14 snapshot. The report is titled *Can Readers Still Check the Source? A Time-Matched Audit of AI-API Community Notes*.

This study and its code were developed during the AI x Epistemics Sprint (November 13–15, 2026). No code from our earlier Swarm Alignment project was reused. A small feasibility pilot for this study also took place during this Sprint.

The primary question is whether an unauthenticated research client could retrieve one preselected external URL per note in the 2026-11-14 public snapshot. It does **not** measure whether the URL supported the note, whether the note was true, or the causal effect of AI authorship. We compare observed `apiEarnedIn` AI-API authors with observed non-API enrollment states, matched by note creation month; “non-API” is not proof of human authorship.

## What is included

- `protocol.md`: local plan frozen before primary URL probes; it is not an external preregistration. A small feasibility pilot preceded it.
- `results/source_manifest_2026-11-14.json`: official X download URLs, byte sizes, SHA-256 hashes, and snapshot date.
- `results/freeze_manifest.json` and `results/role_sample_freeze_manifest.json`: hashes proving the study's frozen inputs, code, and blinded source-role sample.
- `src/`: deterministic cohort selection, bounded URL probing, aggregate analysis and sensitivity scripts; secondary archive, source-role, survivor-selection, and URL-normalization analysis scripts. `analyze_anonymous_pairs.py` recomputes the frozen primary contrast from the released anonymous pair data.
- `results/anonymous_pairs.csv`: 300 month-matched category pairs, cryptographically shuffled so row order does not reproduce the deterministic cohort order. It contains month and four-category machine outcomes, without note IDs, author IDs, or selected URLs.
- `results/aggregate_results.json`: independently checked, group-level machine observations, with the primary result separated from a later two-case URL-correction sensitivity.
- `results/support_audit_aggregate.json`: AI-assisted source-role labels for a blinded 100-note sample and current-page support labels for a frozen 40-note subset. Only group-level counts are included.
- `results/archive_analysis_2026-11-15.json`: aggregate Wayback CDX indexed-capture metadata for 100 matched pairs, with query-state and timing caveats.
- `results/survivor_selection_2026-11-14.json`: aggregate count of currently Helpful status-history rows with and without a Notes row in the frozen snapshot.
- `source_role_questionnaire.md` and `related_work.md`: annotation rubric and nearest-work boundary.

The official ZIPs, matched note records, probe logs, note text, pseudonymous author IDs, URLs selected from notes, blinded packets and keys, manual page excerpts, and individual annotation rows are **not** in this folder. The `.gitignore` also protects new local outputs from accidental staging. No paid model API was used for the URL measurements. The anonymous pairs preserve month and outcome combinations; they should not be described as a differential-privacy release.

## Dated observations and limits

The frozen machine pass yielded 235/300 AI-API and 221/300 non-API `open_candidate` responses (78.3% and 73.7%). The AI-minus-non-API difference is +4.7 percentage points; the 10,000-replicate, within-month paired bootstrap 95% interval is −2.0 to +11.3 points. It crosses zero. The categories in the included JSON keep access barriers, transient/uncertain observations, and provisional “gone” results separate. A 2xx page can be a soft error, challenge, unrelated redirect or stale page; `open_candidate` therefore does not mean verified evidence.

Two syntax corrections were reviewed **after** the primary analysis. Applying only those two verified changes gives 235/300 versus 223/300 and a +4.0-point difference (95% paired bootstrap interval −2.7 to +10.7). This is a **post-hoc sensitivity**, not a replacement of the frozen primary result. The full candidate list and individual URLs remain private. Additional extraction artifacts may remain.

The AI-API sample contains 20 observed authors versus 291 non-API authors; the largest author contributes 45 AI-API notes. An equal-author sensitivity changes the point estimate to approximately −0.6 points and does not preserve the month-matched estimand. These facts, selection of surviving currently Helpful notes, source/domain composition, and changing web responses limit generalization.

In the separate, blinded source-role sample, AI-assisted coding labeled the selected URL as an intended `SUPPORT` source in 46/50 AI-API notes and 39/50 non-API notes. This label describes the URL's role in the note, not whether its content actually substantiated the claim. In a frozen subset of 20 `SUPPORT` cases per group, AI-assisted current-page coding found `FULL` support in 12/20 AI-API and 10/20 non-API cases; `PARTIAL` in 5/20 and 2/20; `NONE` in 1/20 each; and `UNASSESSABLE` in 2/20 and 7/20. Across the subset's 32 `open_candidate` machine outcomes, only 18 were coded `FULL` and 7 `PARTIAL`; 2 were `NONE` and 5 `UNASSESSABLE`. This demonstrates a construct gap between HTTP response and coded support in a selected sample. Coding was AI-assisted and **not independently human validated**. The two 20-case blocks used different reviewers and browser-escalation rates and were unevenly balanced by cohort; the group contrast is not interpretable as an AI-writing effect. These are current-page observations, not historical support, population rates, note truth, or evidence of change over time.

In a secondary 100-pair archive sample, a CDX-indexed HTTP-200 capture within ±30 days of the note's first Helpful timestamp was found for 61/100 AI-API and 48/100 non-API note-link rows: a +13-point difference (within-month paired bootstrap 95% interval 0 to +26 points). The 200 selected rows contain 199 distinct URLs because one non-API URL repeats. A capture could fall **after** the Helpful timestamp. Some queries errored or reached a result cap. CDX metadata alone establishes neither successful Wayback replay nor claim support; digest changes cannot establish semantic drift. The archive sample is a subset of the primary sample and has its own author concentration. In a separately frozen eight-case replay among CDX-positive, machine-non-open rows, five intended substantive bodies displayed; one current-404 page's archived fiction disclaimer supported a narrow correction. This 5/8 is conditional on the selected subset, not a general recovery rate. Individual replay URLs and note IDs remain private.

The frozen snapshot had 89,992 currently Helpful status-history rows created in the study window. Of those, 88,103 had a corresponding Notes row and 1,889 (2.1%) did not. This is a survivor-selection boundary: missing Notes content is **not a verified deletion count**, and a missing row cannot supply the source URL needed for this audit.

Recompute the dated primary category counts, difference, and within-month paired bootstrap interval without accessing the private probe log:

```powershell
.\.venv\Scripts\python src\analyze_anonymous_pairs.py
```

This reproduces the statistics from released category pairs, not the individual historical HTTP responses or the selected URLs.

## Reproduce the cohort and run a new measurement

Use Python 3.11 and the listed package versions. From the package root on Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python src\download_snapshot.py
.\.venv\Scripts\python src\build_cohort.py --since 2025-09 --through 2026-08 --target-per-group 300
.\.venv\Scripts\python src\probe_urls.py --cohort results\cohort_2026-11-14.json --output results\probes_rerun.jsonl --workers 6
.\.venv\Scripts\python src\analyze_probes.py --cohort results\cohort_2026-11-14.json --probes results\probes_rerun.jsonl --output results\analysis_rerun.json
.\.venv\Scripts\python src\sensitivity.py --cohort results\cohort_2026-11-14.json --probes results\probes_rerun.jsonl --output results\sensitivity_rerun.json
```

The download is roughly 800 MB. `download_snapshot.py` verifies every ZIP against the committed official manifest; `--verify-only` checks existing files without network access. After `build_cohort.py`, compare the cohort file's SHA-256 with `results/freeze_manifest.json`. On PowerShell:

```powershell
(Get-FileHash results\cohort_2026-11-14.json -Algorithm SHA256).Hash.ToLower()
```

The frozen cohort hash is `0cce905860faf3e2027ad49146a5f5c360da096b5708e8c3559496b6e85e06d0`. The original private probe-log hash is `607b56583ebd22b6000807405289a62e0cc59bf4b437f8629d2ca4fa09bcd6fe`. Rerunning live URLs later tests **the later web**, so its probe hash and counts are not expected to match the dated original. The original individual probe log is withheld to avoid publishing raw URLs and note-level observations. The released anonymous pairs permit recomputation of the dated category counts and primary contrast, but do not permit an independent audit of each historical HTTP classification. Cohort reconstruction, method inspection, and a current rerun remain possible.

To regenerate the blinded 100-note source-role sample locally after cohort reconstruction:

```powershell
.\.venv\Scripts\python src\build_role_sample.py
```

The command writes raw note summaries, selected URLs, and a private mapping key into `results/`. **Keep these files local.** The role rubric is in `source_role_questionnaire.md`. The original packet and annotation rows are intentionally withheld. `archive_cdx.py` and URL-normalization/reprobe scripts are optional secondary analyses; on Windows the archive script needs `curl.exe`. They create private URL-level outputs that must not be committed. Do not treat CDX digest changes alone as semantic drift, or a fixed URL as a primary result.

After downloading the official snapshot, the missing-Notes-row aggregate can be recomputed exactly. Archive CDX availability can be queried again after rebuilding the cohort, but the archive index may have changed since the dated analysis:

```powershell
.\.venv\Scripts\python src\survivor_selection.py --output results\survivor_selection_rerun.json
.\.venv\Scripts\python src\archive_cdx.py --freeze-only
.\.venv\Scripts\python src\archive_cdx.py --run
.\.venv\Scripts\python src\analyze_archive_cdx.py --json-output results\archive_analysis_rerun.json --md-output results\archive_analysis_rerun.md
```

The source-role and current-page support annotations require the withheld individual review packets, so their published aggregate cannot be independently regenerated from this package. `analyze_support_audit.py` exposes the aggregation method.

## Source and interpretation notes

X's [Community Notes data guide](https://communitynotes.x.com/guide/en/under-the-hood/download-data) describes the public cumulative files, delayed releases, and disappearance of deleted note content from later Notes files. Our source-role rubric and the frozen protocol document the selection rules. The relevant prior work is listed in `related_work.md`.

URL probes use bounded unauthenticated GET requests with redirect/body/time limits, no personal cookies, and a public-destination check. Respect source sites' access controls and rate limits; do not bypass challenges or logins. We do not publish individual problematic links, author rankings, or note text. The primary comparison is observational and cannot adjudicate note truth, source trustworthiness, or AI model quality.

## Validation performed for this package

All six entries in `freeze_manifest.json` matched their current files. The 600 matched note IDs and 600 probe IDs were unique and identical; each probe's group, month and selected URL matched its frozen note. Independently counted machine categories matched the saved analysis, and rerunning `analyze_probes.py` reproduced the entire primary JSON. Rerunning it with the two browser-reviewed correction overrides reproduced the entire corrected sensitivity JSON. The released anonymous pairs reproduce the frozen primary counts, difference, and interval. The 100 role labels and 40 current-page support labels were checked against their private frozen selections and the released aggregate. Archive input hashes and month totals, and survivor arithmetic and ZIP hashes, were checked against local originals. The package contents were inspected to exclude raw datasets and identifiers.

## Citation

If you use this package, cite the dated report and the official Community Notes snapshot rather than treating the live rerun as the 2026-11-15 observation. The report citation will be added after the final PDF is approved.
