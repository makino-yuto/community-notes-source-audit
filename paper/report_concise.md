# Can Readers Still Check the Source? A Time-Matched Audit of AI-API Community Notes

**Yuto Makino**

The University of Electro-Communications, Japan

With Apart Research

## Abstract

Checking a Community Note requires more than a working link. We audited all citations in 1,882 same-post pairs from the official 14 November 2026 snapshot, covering 3,764 currently Helpful notes and 5,787 distinct URLs. Observed AI-API enrollment defined the groups; non-API does not verify human authorship. Automated screening found at least one open candidate in 90.4% of AI-API notes versus 81.4% of non-API notes. For one uniformly chosen citation, the expectations were 76.8% and 76.6%. AI-assisted browser inspection of 240 sampled pairs yielded conservative access-difference bounds from -0.6 to +13.4 percentage points; the approximate 95% outer design interval was -4.9 to +19.2. A separate 200-note support diagnostic and 60 synthetic controls exposed substantial unassessability and rubric ambiguity. We release frozen protocols and numeric data for recomputing the estimates. The audit separates citation redundancy, visible content and claim support. These dated, AI-only measurements establish neither note truth nor a causal authorship advantage; intervals exclude annotation error.

## 1. Introduction and related work

Link counts and HTTP success are tempting trust signals, but a correction is checkable only when readers can inspect relevant evidence. We combine an all-citation machine census, probability-sampled browser inspection and a separate fixed-claim diagnostic to distinguish **citation redundancy, current access and claim support**.

AI-writer source checks [1], same-post ratings and timing studies [2,4], fact-checking dependencies [3], higher AI citation counts [5], silent HTTP failures [6], and citation/support evaluations [8-10] already exist. Our contribution is a dated measurement of these distinct endpoints in deployed Community Notes, with unknown outcomes retained and publicly reproducible arithmetic.

## 2. Methods

### Population and machine screening

The official Notes, status-history and enrollment snapshot was retained and hashed [7]. Eligible notes were created September 2025-August 2026, currently Helpful, noncollaborative, available, externally linked, and had an enrollment state recorded by creation. From 57,506 eligible notes, we selected each group's earliest eligible note on every shared post: **1,882 pairs**. This selection preceded probing. API enrollment does not verify individual-note composition; same-post pairing does not ensure the same correction.

Every citation was screened using bounded GETs; fragments and within-note duplicates were collapsed. An open candidate was a 2xx PDF, or another 2xx response with at least 80 text characters and no detected login/challenge marker. We compared any-open with each note's expected open fraction for one uniformly chosen citation. Access was measured on 15 November 2026. The follow-up protocol was publicly frozen before its own probes, after an earlier exploratory audit.

### Browser access and source support

We sampled 60 pairs without replacement from each machine any-open stratum: both groups, AI-API only, non-API only and neither. AI assistants inspected every citation in these **240 pairs: 674 distinct URLs**. Packets omitted cohort labels, note text and machine outcomes. Access required substantive intended content or visible media; titles, teasers and empty players did not suffice. Unresolved pages and policy blocks remained unknown.

The primary endpoint was the paired difference in offering any intended source. Stratum weights and finite-population variance address pair sampling. Adverse unknown-content assignments yield conservative bounds; an approximate Bonferroni outer interval adds sampling uncertainty. The endpoint depends on the study browser profile and existing cookies. Intervals condition on AI classifications and exclude annotation error.

A separate seeded **100-pair diagnostic** fixed each note's main claim before source inspection. Tool-free `gpt-5.6-sol` trials judged capped source text as FULL, PARTIAL, NONE, CONTRADICTS or UNASSESSABLE; original posts/media were unavailable. Missing text could not establish absence. Positive judgments required literal quotations within a 20-word-per-source cap; failures became UNASSESSABLE in strict summaries. Separate AI recodes and synthetic fixtures assessed consistency and rubric behavior, without human gold validation.

## 3. Results

### More citations change the comparison

AI-API notes cited 2.05 URLs on average versus 1.45. Machine any-open rates were **90.4% versus 81.4%**, while the uniformly chosen citation expectations were **76.8% versus 76.6%** (Figure 1A). These are different estimands: multiple citations offer more chances to find one open candidate. The comparison does not establish independent corroboration or a causal benefit of AI authorship. Full machine and robustness tables are in the linked technical report.

[[FIGURE1]]

Figure 1. Citation screening and AI-assisted browser access in the same target population. A: the 1,882-pair machine census; diamonds show any-open rates and circles the uniform-citation expectation. B: design-weighted browser results from 240 sampled pairs. Thick segments are conservative unknown-content bounds; the thin contrast line adds approximate 95% outer design uncertainty. Intervals exclude AI annotation error. Neither endpoint establishes claim support.

### Intended-content access remains uncertain

Browser inspection gave primary paired bounds of **-0.6 to +13.4 percentage points** and an approximate 95% outer interval of **-4.9 to +19.2** (Figure 1B). A conservative post hoc exact-tail check was wider, **-13.7 to +26.9 points**. These results leave the direction unresolved. A second AI pass agreed on 73/87 URL classifications, measuring repeatability across assessors and browser states, not accuracy. Profile sensitivities and machine/browser disagreements appear in the appendix.

### Accessible content does not settle support

Strict AI FULL labels occurred in **16/100 AI-API and 13/100 non-API notes**; **89/200** remained UNASSESSABLE. Eighteen positive outputs failed quotation-format checks, which are distinct from factual errors. The independent AI recode agreed on 15/20 strict labels. These source-text judgments do not establish note truth.

In 60 synthetic fixtures, eight NONE/PARTIAL disagreements arose from crediting an entity match without the asserted event or date. The inclusive rubric makes these boundary disputes, not unequivocal semantic errors. Controls were frozen before their own calls but created after field judgments; they do not estimate field accuracy or justify relabeling.

## 4. Implications and limitations

A useful audit should report **what was checked**: dated transport, visible intended content, a fixed proposition, source quotations and an explicit unknown state. Citation counts and HTTP success alone do not supply this record. Whether such a record improves reader decisions remains untested.

The selected pairs cover 3.6% of eligible posts and are concentrated in 26 AI-API author accounts. This conditional population does not represent all notes or independent operators. Access depends on one date and browser profile; support judgments use capped current text and lack original target media. AI recodes are not human ground truth. Neither these comparisons nor the archival feasibility check establish causal authorship effects, historical decay or note correctness.

## Code and AI use

The [public repository](https://github.com/makino-yuto/community-notes-source-audit) provides protocols, code, aggregates, numeric pairs and the full technical report. Public files reproduce arithmetic, not historical page states. Individual identifiers, weak-link lists and source-text judgments remain private. Codex/ChatGPT assisted with design, code, writing, browsing and judgments; the author directed the project. Semantic and browser labels remain AI-only.

## References


1. Miller, B., Baxter, J., Chao, J., Coleman, K., Hilgard, S., and Ortiz, D. (2026). [Community-Driven API and AI Writer Design for Openly Scaling Community Notes](https://arxiv.org/abs/2609.40067). arXiv:2609.40067.
2. Li, H., and Bakker, M. A. (2026). [AI Fact-Checking in the Wild: A Field Evaluation of LLM-Written Community Notes on X](https://arxiv.org/abs/2604.02592). arXiv:2604.02592.
3. Borenstein, N., Warren, G., Elliott, D., and Augenstein, I. (2025). [Can Community Notes Replace Professional Fact-Checkers?](https://aclanthology.org/2025.acl-short.42/). ACL 2025.
4. Gong, Y., and Wu, S. (2026). [Characterizing AI Fact-Checkers and Their Contributions on Community Notes](https://arxiv.org/abs/2605.16566). arXiv:2605.16566.
5. Purnell, S. (2026). [AI Writers on Community Notes: An Evaluation of Seven Months of Data](https://www.rstreet.org/research/ai-writers-on-community-notes-an-evaluation-of-seven-months-of-data/). R Street Institute.
6. Zhang, S. (2026). [When 200 OK Is Not an Answer: Silent Fetch Failures in Agentic Web Content Acquisition](https://arxiv.org/abs/2611.00884). arXiv:2611.00884.
7. X Community Notes. [Downloading data](https://communitynotes.x.com/guide/en/under-the-hood/download-data) and [public data dictionary](https://github.com/twitter/communitynotes/blob/main/documentation/under-the-hood/download-data.md). Accessed 15 November 2026.

8. Singh, S., Wu, J., Churina, S., and Jaidka, K. (2025). [On the Limitations of LLM-Synthesized Social Media Misinformation Moderation](https://openreview.net/forum?id=ilz2ghLgzt). ICLR ICBINB Workshop.
9. Rao, D., Wong, E., and Callison-Burch, C. (2026). [Detecting and Correcting Reference Hallucinations in Commercial LLMs and Deep Research Agents](https://arxiv.org/abs/2604.03173). arXiv:2604.03173.
10. Wu, J., Fu, Z., Wang, H., Li, F., Guo, J., Nakov, P., and Kan, M.-Y. (2026). [Beyond the Crowd: LLM-Augmented Community Notes for Governing Health Misinformation](https://aclanthology.org/2026.acl-long.233/). ACL 2026, pp. 5152-5171.


## Appendix. Limitations and Dual-Use / Ethical Considerations

### Scope, assessment and ethics

This is a conditional population of available, currently Helpful notes with external citations and eligible enrollment histories. The paired posts represent 3.6% of eligible posts, not all Community Notes or future writers. `apiEarnedIn` records an account state; it verifies neither AI composition of an individual note nor human authorship in the comparison group. Accounts need not represent independent operators. Same-post pairing does not establish identical claims: the separate 100-pair diagnostic classified 43 corrections as the same, 36 overlapping, 20 different and one unassessable.

All browser and semantic judgments, including independent recodes, were AI assessments without human gold validation. The original target posts/media were unavailable to the support diagnostic. Access, claim support and external truth are separate endpoints. Current access depends on date, vantage and cookies; it cannot establish what a reader saw at publication. Sampling intervals exclude annotation error, profile changes and extrapolation beyond the fixed frame. Neither model-labeled contradiction was independently confirmed as a robust factual contradiction. No individual note or account is accused of misconduct.

Requests were bounded and host-paced, rejected non-public network addresses, and did not bypass authentication, challenges or certificate warnings. Policy-blocked sources remained unknown. Public files omit individual source/post/note/account identifiers, page bodies and weak-link lists to reduce targeting and unfair attribution. Rare numeric combinations remain: the release is not differentially private and cannot guarantee unlinkability.

### Frame and measurement details

The retained, hashed 14 November 2026 official releases supplied notes, status history and enrollment [7]. Eligibility required September 2025-August 2026 creation, current Helpful status, noncollaborative available text, external HTTP(S) citations, a post ID and an enrollment state recorded by creation. There were 57,506 eligible notes on 51,904 posts. Before probing, each of 1,882 shared posts contributed its earliest eligible note per group, with note ID breaking ties. The median creation gap was 1.00 hours; the maximum was 39.69 hours.

The follow-up was publicly frozen in commit `8fd3817` at 03:22:27 UTC on 15 November, before its first probe at 03:22:51; it followed the initial audit, rather than preregistering it retroactively. Conservative extraction preserved literal citations, handled entities/punctuation and collapsed fragments and within-note duplicates for retrieval. Every one of 5,787 network URLs was screened. An open candidate required a 2xx PDF, or another 2xx response with at least 80 extracted characters and no detected login/challenge marker.

### Browser sampling and uncertainty

The machine any-open paired strata contained 1,436 both-positive pairs, 265 AI-API-only, 96 non-API-only and 85 neither-positive pairs. Sampling 60 pairs without replacement in each stratum yielded 240 pairs and 674 unique URLs. URL-only packets omitted cohort, claim and machine outcome. Intended substantive content or visible media was required; metadata, teasers and empty players failed. Full cited abstract records and one obvious PDF hop were allowed and flagged. The AI labels were 486 accessible, 105 not accessible and 83 unresolved, including nine policy blocks.

For each pair, the lower difference is AI known-any access minus non-API possible-any access; the upper reverses known and possible. With stratum sizes `Nh`, samples `nh=60` and `N=1882`:

```text
estimate(d) = sum_h (Nh/N) * mean_h(d)
variance(d) = sum_h (Nh/N)^2 * (1 - nh/Nh) * s_h(d)^2/nh
outer95 = [estimate(dL)-2.2414*SE_L, estimate(dU)+2.2414*SE_U]
```

Unknown states stay in denominators. The primary bounds are conservative, allowing opposite assignments to a shared unresolved URL; they are not ordinary confidence intervals. The approximate Bonferroni outer interval covers sampling uncertainty conditional on fixed correct classifications. Shared authors/sources do not require independent fixed pair outcomes under this sampling design, but can produce correlated observation errors.

A post hoc exact-tail check bounded positive/negative endpoint counts by hypergeometric inversion: four one-sided limits per stratum, 16 total, each at alpha `1/320`. Their union bound gives at least 95% conditional design coverage and an outer interval of -13.66 to +26.94 percentage points (pp). It leaves the frozen approximate primary analysis unchanged. Recoding 53 signed-in-state successes as unknown widens primary bounds to -7.08 to +24.00 pp; sign-in does not prove login was necessary. The separate browser recode agreed on 73/87 labels (kappa 0.701), measuring repeatability, not accuracy.

Target-frame machine-negative counts were 181 AI-API and 350 non-API notes. Their estimated browser-access bounds were 67.07-82.75% and 47.43-70.40%, respectively. These are weighted endpoint estimates, not confidence intervals; differing clients, profiles and times prevent interpreting the disagreement as a causal rendering effect.

### Fixed-claim labels and controls

The separate seeded 100-pair diagnostic supplied 200 notes and 357 source slots from 319 URLs; it overlapped the browser sample by 13 posts and is not an independent replication. Claims were fixed before source inspection. Uniform static retrieval supplied coverage flags and at most 24,000 characters per source to isolated, tool-free `gpt-5.6-sol` trials without cohort labels. Missing/truncated text could not establish absence. Positive or contradictory labels required literal quotations totaling at most 20 whitespace-delimited words per source. Strict summaries changed noncompliant positive outputs to UNASSESSABLE.

**Table A1. AI source-support labels per 100 notes in each group, raw / strict.** These are observed-text judgments, not verified note truth.

| Label | AI-API raw / strict | Non-API raw / strict |
|---|---:|---:|
| FULL | 20 / 16 | 15 / 13 |
| PARTIAL | 39 / 30 | 33 / 30 |
| NONE | 5 / 5 | 15 / 15 |
| CONTRADICTS | 1 / 1 | 1 / 1 |
| UNASSESSABLE | 35 / 48 | 36 / 41 |

Eighteen positive outputs failed quotation/length checks (13 AI-API, five non-API); these are format failures, not factual errors. One repeated timeout remained unassessable; the selected outcomes included 199 valid executions. The strict FULL contrast was +3 pp (descriptive pair-bootstrap 95% -6 to +12); the strict 20-note recode agreed on 15/20 labels.

After field coding, 60 fictional controls were publicly frozen before their model calls. They matched the chosen labels in 52/60 trials. All eight disagreements credited entity identity as PARTIAL without the asserted event/date. This is a convention-sensitive rubric boundary, not eight unequivocal semantic errors. Synthetic repeated families do not calibrate field accuracy or justify relabeling field observations.

### Archival feasibility and reproducibility

A separately frozen 100-unit URL/first-Helpful-time panel yielded 31 parser-readable historical/current pairs, but only 18 across 18 notes had two substantively assessable AI labels. This failed the predeclared 30-unit/20-note comparison threshold. Twenty-five of 31 captures predated note creation. Independent AI review did not confirm source-support drift; missing bodies and invalid judgments remained unknown. No publication-time support or temporal trend is established.

The [complete technical record](https://github.com/makino-yuto/community-notes-source-audit/blob/b6a40a2a7dc413f6bed1c88e87041eb91f4f7de8/paper/Makino_Community_Notes_Source_Audit_Revised.pdf) retains full robustness tables, recode matrices, archive workflow and the separate preliminary wave. The repository pins snapshot/artifact hashes, seeds, protocols and amendments. Identifier-free numeric tables reproduce estimates from frozen outcomes, not historical web states. From `numeric-reproduction/`, with only the Python standard library:

```text
python src/reproduce_newwave_public.py --output reproduced.json
python src/reproduce_newwave_secondary_public.py --self-test --output secondary.json
```
