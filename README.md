# Can Readers Still Check the Source?

Companion materials for **Can Readers Still Check the Source? A Time-Matched Audit of AI-API Community Notes**, by Yuto Makino, AI x Epistemics Research Sprint, November 2026.

This revision audits current source access in a fixed, conditional population. It does not establish note truth, source independence, historical link decay, or a causal advantage of AI authorship. Primary browser and semantic labels are AI-assisted, without human gold validation.

[Read the revised paper](paper/Makino_Community_Notes_Source_Audit_Revised.pdf) | [Manuscript](paper/report_strengthened.md)

## Main measurements

- **1,882 same-post pairs, 3,764 notes, 5,787 distinct network URLs.** Machine any-open rates were 90.4% versus 81.4%; the expected open fraction of one uniformly chosen citation was 76.8% versus 76.6%. This contrasts citation redundancy with average per-link access.
- **240 probability-sampled post pairs, all 674 cited URLs inspected in one browser profile.** Weighted any-source difference bounds were -0.57 to +13.42 percentage points. The approximate outer 95% design interval was -4.87 to +19.17. These are conditional on the AI classifications and exclude observation/annotation error. A deliberately conservative secondary exact-tail interval is -13.66 to +26.94 pp; it does not replace the frozen primary analysis.
- **200-note fixed-claim diagnostic.** Labels passing the evidence-format validator were FULL in 16/100 versus 13/100 notes; 89/200 remained UNASSESSABLE. PARTIAL is an inclusive rubric label, not a certificate that the core correction is grounded.
- **60 synthetic fixtures.** 52/60 matched planned labels. Eight NONE/PARTIAL disagreements exposed entity-matching convention ambiguity; this is not an estimate of real-source accuracy.

AI-API denotes recorded `apiEarnedIn` enrollment; non-API does not prove human composition. The frame covers only currently Helpful, available, externally linked, noncollaborative notes satisfying the recorded enrollment-time rule. Same-post selection covers 3.6% of eligible posts and can pair different corrections.

A prospective 100-unit archival panel failed its predeclared semantic-assessability gate. Appendix G reports timing limits, unknown-inclusive bounds and a separate AI review; it establishes no temporal source-support trend.

## Reproduce the arithmetic without network access

```powershell
python numeric-reproduction/src/reproduce_newwave_public.py --output reproduced.json
python numeric-reproduction/src/reproduce_newwave_secondary_public.py --self-test --output secondary_reproduced.json
```

The standard-library script verifies committed CSV hashes, then recomputes the complete-frame machine contrasts, weighted browser bounds, finite-population standard errors and sensitivities. The package was independently checked against 84 numeric values/counts and executed successfully from an archive of committed Git bytes. A separate numeric-only add-on reconstructs secondary machine/browser disagreement and the exact-tail interval; 153 numeric values matched independent private-key analyses. See `numeric-reproduction/SECONDARY_METHODS.md` for assumptions and limits. A later whitespace-only byte-preservation correction restored frozen local JSON/CSV bytes after Git newline normalization; all affected parsed values were independently checked unchanged. `.gitattributes` now preserves exact artifact bytes across operating systems.

The shuffled numeric release omits individual source URLs, note/post/account IDs, source bodies, exact dates and author-cluster codes. Some rare numeric combinations remain; this is not differential privacy or guaranteed unlinkability. It reproduces estimates from frozen observations, not historical pages or their semantic judgments.

## Protocol and provenance

The follow-up plan was frozen locally 15 November at 03:21:20 UTC and [publicly committed](https://github.com/makino-yuto/community-notes-source-audit/commit/8fd3817) at 03:22:27 UTC, before the first new probe at 03:22:51. It followed an initial 600-note study; it is not a retroactive preregistration. Each later amendment states its timing and scope. The initial study and follow-up were conducted during this sprint; third-party data, libraries and fonts are preexisting.

`protocols/` contains prospective plans and amendments. `results/source_manifest_2026-11-14.json` pins the official snapshot. `src/` contains extraction, bounded collection, blinded-model and analysis code. `numeric-reproduction/` is the self-contained public arithmetic release. The report separates primary observations, secondary analyses, synthetic fixtures and the preliminary 600-note wave; their denominators are not pooled.

Rebuilding the frame requires the exact official snapshot bytes, roughly 800 MB. A later URL rerun measures the later web. The current study used ordinary HTTP and browser observation plus the official Codex CLI with an existing ChatGPT login; the numeric reproducer needs no model service or API key. Do not bypass site controls or use raw note/source data to target individual authors.

## Rebuild the figure and PDF

Use the recorded optional report environment (`pip install -r requirements-report.txt`), then run:

```powershell
python src/newwave_figures.py --output-dir output/figures
python src/render_newwave_report.py --sourceMD paper/report_strengthened.md --outputPDF rebuilt.pdf --main-pages 5
```

The bundled Old Standard TT fonts retain their OFL license. Re-rendering can change PDF metadata bytes. The published PDF and full artifact hashes are pinned in `release_manifest.json`.
