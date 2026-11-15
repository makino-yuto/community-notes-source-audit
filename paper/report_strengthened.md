# Can Readers Still Check the Source? A Time-Matched Audit of AI-API Community Notes

**Yuto Makino**

The University of Electro-Communications, Japan

With Apart Research

## Abstract

An inspectable citation is a prerequisite for checking a correction, but link count, HTTP success and factual support measure different things. We audited the official 14 November 2026 Community Notes snapshot. A frozen follow-up covered all 1,882 eligible posts with both an observed AI-API and a non-API currently Helpful note: 3,764 notes and 5,787 distinct network URLs. Machine screening found an open candidate among any citation in 90.4% versus 81.4% of notes; the expected open fraction for one uniformly chosen citation was 76.8% versus 76.6%. AI-assisted browser-profile classifications of all citations in a stratified 240-pair probability sample bounded the paired intended-source-access difference between -0.6 and +13.4 percentage points; an approximate 95% outer design interval was -4.9 to +19.2. These intervals condition on AI classifications and exclude annotation error. In a separate 200-note diagnostic, strict AI-assisted FULL-support labels occurred in 16% versus 13%; missing evidence remained unassessable. Sixty synthetic fixtures exposed ambiguity in partial support for entity matching. We release publicly reproducible arithmetic and estimates from frozen outcomes, separating citation redundancy, current access and support. This establishes neither a causal AI-authorship advantage nor note truth.

## 1. Introduction

Checking a Community Note requires a resolving request, visible intended content and support for its correction. Multiple links can improve access without independent corroboration; account counts also contextualize AI-API output.

Existing source checks [1] cannot establish later access. We contribute an all-citation machine census in a fixed same-post population, probability-sampled AI-assisted browser bounds retaining unknown content, and a separate fixed-claim diagnostic with synthetic rubric controls. We publicly froze the follow-up before its network measurements, after the initial audit.

## 2. Related work

Miller et al. describe the Community Writer's scale, multiple accounts and drafting pipeline [1]. Li and Bakker compare notes on the same posts through ratings [2]; Borenstein et al. examine professional fact-checking dependencies [3]; Gong and Wu study AI writers, timing and ratings [4]. Purnell reports higher AI citation counts [5], and Zhang shows that HTTP 200 can conceal missing main content [6]. Synthetic-note citation failures, citation-health and archive tools, and source-support evaluations also exist [8-10]. Our contribution is a dated measurement of intended-source access across all citations in a deployed same-post population.

## 3. Methods

### Population and all-citation screening

The official 14 November 2026 Notes, status-history and enrollment releases were retained and hashed [7]. Eligibility required September 2025-August 2026 creation, current Helpful status, non-collaborative and available text, explicit external links, a nonempty post ID, and an enrollment state recorded no later than creation. The revised parser yielded 57,506 eligible notes on 51,904 posts. Observed `apiEarnedIn` defines AI-API; other enrollment states define non-API. Neither verifies individual-note authorship.

Selecting each group's earliest eligible note per post before probing yielded 1,882 pairs, 3,764 notes and 5,787 distinct defragmented network URLs. Same-post pairing need not align corrections or submission times. Access was observed on 15 November 2026 without a publication-time baseline; these data do not estimate decay or persistence. Selection and freeze details appear in Appendix B.

Bounded GETs recorded every citation without outcome-based repairs; fragments and repeated paths within notes counted once. An open candidate was a 2xx PDF, or another 2xx response with at least 80 extracted text characters and no detected login/challenge marker. This proxy was compared with a fixed-hash one-link choice and the expected open fraction for one uniformly chosen citation. Any-open minus that expectation measures observed redundancy, not a causal benefit of adding links.

### Primary browser endpoint

We sampled 60 pairs without replacement from each machine-defined paired any-open stratum: both, AI only, non-API only and neither. URL-only packets omitted cohort labels, note text and machine outcomes. AI assistants classified every citation in both notes: 240 pairs and 674 distinct URLs. Access required substantive intended content or visible media, including a full cited abstract record; titles, teasers, unrelated redirects and empty players failed. Blank/error pages after one normal retry and policy blocks remained unresolved.

The primary estimand is the paired difference in offering any visible intended source. Stratum weights and finite-population variance address pair sampling. Adverse unknown-content assignments yield conservative bounds; a Bonferroni outer interval adds design uncertainty, conditional on frozen AI classifications and excluding annotation error. Existing cookies restrict the endpoint to this browser profile. Sensitivities recode signed-in, abstract-only and one-hop-PDF successes as unknown. A separately frozen second AI pass assesses repeatability (Appendix C).

### Fixed-claim diagnostic

A separate seeded 100-pair sample fixed each note's main corrective proposition before source inspection. Its 200 notes supplied 357 source slots from 319 URLs. Uniform static retrieval supplied coverage flags and at most 24,000 characters per source; original posts/media were unavailable. Isolated, tool-free trials advertised `gpt-5.6-sol` and saw no cohort key.

The rubric distinguished FULL, PARTIAL, NONE, CONTRADICTS and UNASSESSABLE. Missing or truncated text could not establish absence. FULL/PARTIAL/CONTRADICTS required exact quotations, checked for literal occurrence, an observation for each source and a 20-word-per-source limit. Noncompliant outputs remained raw but became UNASSESSABLE in strict summaries; a repeated timeout also remained in the denominator. A frozen 20-note AI recode and 60 synthetic fixtures examine consistency and rubric behavior; neither supplies human gold (Appendix D).

## 4. Results

### Citation redundancy and intended-content access

The paired frame represents 3.6% of eligible posts and contains 26 AI-API versus 1,648 non-API author accounts; concentration details are in Appendix C. Mean network URLs per note were 2.05 versus 1.45. Machine any-open rates were 90.4% versus 81.4%, a +9.0-point contrast, while the uniformly chosen one-link expectations were 76.8% versus 76.6%, only +0.2 points. All-open reverses the comparison: 61.8% versus 70.8%. Gains over one uniformly chosen link were 13.6 versus 4.8 points. These describe the observed citation sets, not independent evidence.

The any-open contrast was +2.6 points among 536 equal-URL-count pairs and +8.9 among 1,671 pairs created within six hours. Different claims and source choices remain possible. Full machine tables and account/time sensitivities are in Appendix C.

[[FIGURE1]]

Figure 1. Two channels in the same 1,882-pair target population. A: machine census; circles show uniformly chosen citation expectations and diamonds any-link rates. B: design-weighted AI-assisted browser-profile classifications from 240 sampled pairs. Thick segments show conservative unknown-content bounds; the thin contrast line adds approximate 95% outer design uncertainty. Intervals condition on AI classifications and exclude annotation error. Bounds are not ordinary confidence intervals; neither channel establishes claim support or a causal authorship effect.

AI browser assessors classified 486/674 URLs accessible, 105 not accessible and 83 unresolved. Weighted any-source bounds were 91.0-95.3% for AI-API and 81.9-91.6% for non-API. Primary conservative paired bounds are **-0.6 to +13.4 points**, with an approximate simultaneous 95% outer interval of **-4.9 to +19.2**. Shared-URL consistency tightens them slightly (Appendix C). A post hoc finite-sample check using conservative exact hypergeometric count bounds gives a wider outer interval, -13.7 to +26.9 points, without the sparse-stratum normal approximation. Assuming unresolved URLs inaccessible gives +9.1 points (ordinary design 95% +2.9 to +15.4), an assumption-dependent result.

Reclassifying 53 signed-in-state successes as unknown widens bounds to -7.1 to +24.0 points; observed sign-in does not prove login necessary. Abstract/PDF recodings had smaller effects. Recode agreement was 73/87 (83.9%; kappa 0.70), measuring repeatability across browser states and AI assessors, not accuracy. Primary labels remained unchanged.

A secondary weighted channel comparison clarifies what browser measurement adds. Among machine-negative notes, the estimated bounds for any browser-accessible intended source were 67.1-82.8% for AI-API (181 target notes) and 47.4-70.4% for non-API (350). Machine-positive/browser-negative joint fractions among all notes were 3.0-5.8% and 2.9-8.3%. These endpoint estimates are neither confidence intervals nor evidence of vanished sources; they compare channels within the target note frame (Appendix C).

### Support and rubric fragility

Strict FULL support occurred in 16/100 AI-API and 13/100 non-API notes; 89/200 remained UNASSESSABLE. Eighteen positive outputs failed quotation-compliance checks, a technical distinction from factual error. The independent AI recode agreed with 15/20 strict labels. Raw/strict category tables and positive contrasts appear in Appendix D. Neither model-labeled contradiction was independently confirmed as a robust factual contradiction. Unavailable target media also prevents identifying a particular video through a background article.

Synthetic fixtures matched their planned labels in 52/60 technically valid trials. All eight disagreements were convention-dependent NONE-to-PARTIAL cases: a directory named the fictional target without the asserted event or date. Independent review found a real rubric-boundary ambiguity. PARTIAL can therefore reward entity matching without grounding the core correction. Controls were created after field judgments and frozen publicly before their own calls; they neither estimate field accuracy nor justify field relabeling (Appendix D).

## 5. Discussion and conclusion

Audit records should retain account provenance, literal/final URLs, dated transport and intended-content observations, fixed propositions, source locators and an unassessable state. Our reproducible numeric record distinguishes redundancy, access and support; improved reader judgment remains untested.

This is a conditional population of surviving, currently Helpful notes with eligible URLs and enrollment histories. It does not represent all Community Notes, verified AI-versus-human writing or independent operators. Browser access depends on one date, vantage and profile; static retrieval is a separate channel. Design uncertainty covers sampling within the fixed population. Annotation error, changing observations and generalization beyond this population remain outside those intervals. Support coding uses capped current text and AI-only assessment; it cannot establish historical support, semantic drift or note truth.

The audit separates citation redundancy, current access and fallible support judgments. These descriptive comparisons do not establish a causal authorship advantage.

## Code and data

The [public repository](https://github.com/makino-yuto/community-notes-source-audit) provides protocols, source hashes, code, aggregates and shuffled numeric pairs. These reproduce arithmetic, not historical page states. Raw identifiers, weak-link lists, source-text prompts and detailed browser observations remain private.

## LLM usage statement

Codex/ChatGPT assisted with design, code, writing, browser inspection and blinded judgments. Separate AI sessions supplied recodes; none is human gold. The author directed and reviewed the project but did not personally adjudicate every source. Arithmetic was independently checked; semantic labels remain AI-only.

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

## Appendix A. Limitations and Dual-Use / Ethical Considerations

The target is a **conditional, surviving-note population**: notes currently rated Helpful in one official snapshot, written in the date window, carrying explicit external links, and with an enrollment state observed no later than creation. It excludes notes without links, unavailable enrollment histories, collaborative notes, and notes that were Helpful historically but not at snapshot time. The 1,882 same-post pairs represent only 3.6% of eligible posts. Results should not be generalized to all Community Notes or to future writers. `apiEarnedIn` is an observed account state, not proof that any particular note was generated by AI; the comparison state is not proof of human authorship. Account IDs need not identify distinct operators.

Pairing by post controls the target post but does not ensure identical factual propositions. In the separate 100-pair diagnostic, only 43 pairs had the same main correction, 36 had overlapping corrections, 20 had different corrections, and one could not be classified. Notes could also have been written hours apart. Current link behavior cannot establish what a reader or writer saw at publication. Source edits, redirects, paywalls, geographic restrictions, browser profile and cookies, and temporary failures all affect observed access. The design-based intervals account for sampling of pairs within the fixed frame; they do **not** account for mistakes in AI labels, model rubric ambiguity, changing observations, or extrapolation to a new population. Under fixed-frame design inference, shared authors or sources do not require independent pair outcomes; they still limit generalization and can cause correlated observation error.

All semantic support and browser assessments were AI-assisted; the independent passes were further AI assessments, not human ground truth. The 60 fictitious controls stress-tested a chosen rubric convention, but they do not calibrate accuracy on real notes. The original posts and media were unavailable to the fixed-claim diagnostic. An accessible citation may be irrelevant to the claim, and a model's CONTRADICTS label is not a finding that a note is false. The two model-labeled contradictions were separately reviewed; neither was independently confirmed as a robust factual contradiction. No individual note or account is accused of misconduct.

The public materials omit post, note, author and source identifiers, retrieved page text, individual weak-link lists, and detailed browser traces. This limits reproducibility of a historical page-body judgment while reducing the risk of targeted exploitation or unfair attribution. The anonymous numeric release is **not** differentially private and cannot guarantee unlinkability. The audit made bounded requests to public citations, used at most six machine workers with at least one second between requests to a host, rejected non-public network addresses, and did not log in anew, bypass challenges or certificate interstitials, send messages, change source pages, purchase domains, or seek viewing notifications. Browser-policy blocks remained unresolved rather than being reinterpreted as website failures.

## Appendix B. Frame construction and measurement sequence

Inputs were the official 14 November 2026 Notes, Note Status History and User Enrollment releases [7]. The conservative parser kept literal and normalized HTTP(S) citations separate, decoded HTML entities, handled unmatched terminal punctuation/parentheses, rejected invalid/non-public hosts, and did not guess broken publisher URLs. Retrieval collapsed fragments and within-note duplicates; literal variants remain private. Its 1,719 HTML-entity and 161 unmatched-closing-parenthesis flags concern eligible notes, not extra notes/outcomes.

**Table A1. Revised additional-wave frame.**

| Stage or property | Count |
|---|---:|
| Eligible notes after date, current-Helpful, noncollaborative, text, external-URL, enrollment-time and nonempty-post-ID rules | 57,506 |
| Eligible AI-API / non-API notes | 25,530 / 31,976 |
| Posts containing eligible notes | 51,904 |
| Posts containing at least one note in each group | 1,882 |
| Selected post pairs / notes, earliest eligible note per group | 1,882 / 3,764 |
| Distinct normalized citation variants / defragmented network URLs in selected notes | 5,802 / 5,787 |
| Selected pairs created within six hours / same calendar month | 1,671 / 1,874 |

Before probing, each post contributed one pair: the earliest eligible note per enrollment group, ties broken by note ID. This yielded 1,882 pairs from 2,260 possible cross-group combinations. Creation gaps were median 1.00 hours, nearest-order 90th percentile 6.48, maximum 39.69 (the feasibility file rounded hours). The earlier exploratory parser census had **57,494 notes**: 25,530 AI-API and 31,964 non-API; the 12-note difference reflects extraction/eligibility changes. Its account/URL summaries are not additional-wave denominators or pooled with the revised frame.

The protocol was frozen locally at **03:21:20 UTC, 15 November 2026**, publicly committed as `8fd3817` at **03:22:27 UTC**, then first probed at **03:22:51 UTC**. Designed after the initial study, this prospective follow-up did not preregister that study. Retrieval covered all 5,787 defragmented network URLs. The all-citation browser plan was fixed between machine results and browser observations. The separate seeded 100-pair support sample overlapped the 240-pair browser sample by 13 posts; results were neither pooled nor treated as independent replication.

Bounded, unauthenticated public GETs used redirect/content limits, host pacing and a frozen randomized order. An **open candidate** was a 2xx PDF, or another 2xx response with at least 80 extracted text characters and no detected login/challenge marker. This establishes neither browser display of intended content nor claim support. Each note's fixed-hash citation was set before probing; the uniformly random single-citation expectation is the fraction of its citations screening open.

## Appendix C. All-citation and browser results

**Table A2. Machine census in all 1,882 revised pairs.** The difference column is AI-API minus non-API; it is descriptive for this conditional frame.

| Endpoint | AI-API | Non-API | Difference |
|---|---:|---:|---:|
| Mean network URLs per selected note | 2.047 | 1.453 | +0.595 |
| Mean distinct hosts per note | 1.939 | 1.377 | +0.562 |
| At least one open candidate | 90.38% | 81.40% | +8.98 pp |
| Every citation open candidate | 61.80% | 70.78% | -8.98 pp |
| Expected uniformly chosen single citation open | 76.83% | 76.59% | +0.24 pp |
| Fixed-hash single citation open | 75.82% | 76.20% | -0.37 pp |
| Any-open minus uniformly chosen single | 13.56 pp | 4.82 pp | +8.74 pp |

The pair-level any-open cells were 1,436 both, 265 AI-API only, 96 non-API only and 85 neither. AI-API cited more URLs in 1,123 pairs, non-API in 223, and the URL counts were equal in 536. This makes a higher probability of **at least one** open link arithmetically plausible even when the expected one-link rate is similar; it does not imply multiple independent corroborating sources. Of all network citations, the machine categories were AI-API 2,956 open, 563 barrier, 282 uncertain, 52 gone (3,853 total); non-API 2,093 open, 325 barrier, 261 uncertain, 55 gone (2,734 total). These labels are automated screen outputs.

**Table A3. Prespecified descriptive machine robustness.** Subsets and author weighting change the target or its composition; they are not independent confirmations of a causal effect.

| Analysis | Scope | AI-API minus non-API any-open |
|---|---:|---:|
| Selected pairs, primary machine frame | 1,882 pairs | +8.98 pp |
| Creation gap at most six hours | 1,671 pairs | +8.86 pp |
| Same defragmented network URL in both notes | 475 pairs | +4.84 pp |
| Equal numbers of cited network URLs | 536 pairs | +2.61 pp |
| Mean of account-specific AI-API paired differences | 26 AI-API author accounts | +7.86 pp |
| Leave one AI-API author account out | 26 recalculations | +8.67 to +9.47 pp |

The selected AI-API notes came from 26 author accounts and the non-API notes from 1,648. Their top-ten account shares were 94.00% and 5.58%; inverse-Herfindahl account diversities were 8.78 and 797.01. These measure account concentration in the selected frame, not the number of independent people or models. Earlier work already describes multiple-account AI-API operation [1].

Browser validation sampled 60 pairs without replacement in each of the four **machine-defined paired any-open** strata: both (population 1,436), AI-API only (265), non-API only (96), and neither (85). The resulting 240 pairs supplied 674 distinct cited URLs across both notes; every citation in each sampled note was reviewed. URL-only packets concealed cohort, post and claim. An accessible result required substantive intended article/document/structured-record content or visible media frames/transcript. A full cited PubMed abstract counted as a substantive abstract record, not as access to an entire paper. Title, metadata, teaser, blank player, unrelated redirect, login/challenge page, or empty shell did not suffice. One obvious full-report PDF hop was permitted and flagged. Normal retries could leave a result unresolved. The URL labels were 486 accessible, 105 not accessible and 83 unresolved; nine of the latter were browser-policy blocks, not website-failure findings.

Let N_h be population pairs and n_h=60 sampled pairs in stratum h, with N=1,882. For each pair, dL is AI known-any access minus non-API possible-any access; dU reverses known and possible. The fixed design estimator and variance are:

```text
estimate(d) = sum_h (N_h / N) * mean_h(d)
variance(d) = sum_h (N_h / N)^2 * (1 - n_h / N_h) * s_h(d)^2 / n_h
outer95 = [estimate(dL) - 2.2414 * SE(dL),
           estimate(dU) + 2.2414 * SE(dU)]
```

The outer interval uses Bonferroni protection for both estimated endpoints. Unknown source states remain in denominators; no complete-case deletion is used. Primary bounds are conservative because they initially allow opposite assignments to a shared unknown URL in the two notes. The sensitivity below adds that logical constraint. These intervals address pair sampling, not annotation or source-observation error.

**Table A4. Browser pair outcomes and fixed-denominator sensitivities.** Rates/bounds are design weighted. Sensitivity rows turn the stated accessible URL type into unknown and do not relabel the frozen primary observations.

| Endpoint | AI-API | Non-API | Paired difference or outer interval |
|---|---:|---:|---:|
| Any intended source, known-to-possible | 91.04%<br/>to 95.33% | 81.91%<br/>to 91.61% | -0.57 to +13.42 pp |
| Approximate 95% Bonferroni outer interval | - | - | -4.87 to +19.17 pp |
| Unknown assumed inaccessible, point estimate | - | - | +9.13 pp; ordinary design 95% +2.88 to +15.37 |
| Every citation accessible, lower-to-upper | - | - | -23.95 to +10.36 pp |
| Fraction of citations accessible, lower-to-upper | - | - | -11.21 to +12.16 pp |
| 53 access observations in signed-in browser state → unknown | - | - | -7.08 to +24.00 pp |
| Two substantive abstract records → unknown | - | - | -0.57 to +13.42 pp |
| One followed PDF → unknown | - | - | -0.57 to +14.69 pp |
| All three above → unknown | - | - | -7.08 to +25.27 pp |

The design-weighted pair cells whose status was definite were both accessible 77.73%, AI-API only 4.22%, non-API only 0.59%, and neither 4.09%; 13.38% of pair status was undetermined. The bounds, not the unknown-as-inaccessible point estimate, are the primary access result. All-source and fraction contrasts are secondary endpoints.

The frozen second AI-assisted browser pass revisited 87 unique URLs and agreed on 73 outcomes (83.9%; Cohen's kappa=0.701). The row-by-column confusion counts (primary → recode) were: accessible → accessible 47, not accessible 5, unresolved 3; not accessible → not accessible 21, unresolved 1; unresolved → accessible 4, not accessible 1, unresolved 5. A second pass at a later time and possibly different profile state measures repeatability, not human inter-rater accuracy. Primary labels were not edited after comparison. For analysis, separate normalized copies converted six null titles to empty strings in packet A, renamed C's `evidencebrief` field to `evidence`, and converted one recode row's null title/final URL to empty strings. Original browser logs were preserved; these were schema-only transformations.

**Post hoc logical shared-URL sensitivity.** Eight sampled pairs shared an unresolved URL; six in the machine-neither stratum had bounds tightened. When neither note has known access, a positive difference requires an AI-only unresolved URL, and a negative difference requires a non-API-only unresolved URL. Otherwise retain the primary bounds. Using the same weights gives -0.12 to +13.04 pp and an approximate 95% outer interval -4.41 to +18.79 pp. This post hoc rule does not jointly optimize URL states across different pairs and leaves the primary result unchanged. Exhaustive enumeration passed 1,323 small-state cases.

### Secondary comparison of measurement channels

Table A5 reports design-weighted note-level joint fractions, estimated from all citations in the 240 sampled pairs. Each cohort targets 1,882 notes. The known full-frame machine-positive/negative counts are 1,701/181 for AI-API and 1,532/350 for non-API. The conditional row divides estimated joint fractions by the machine-negative probabilities 181/1,882 or 350/1,882, equivalently estimated population counts by 181 or 350. Unknown browser labels generate endpoint bounds; the table does not report confidence intervals. The channels differ in client, profile and time, so this is not a causal rendering-effect estimate.

**Table A5. Note-level machine/browser disagreement, secondary analysis.** Percentages average over notes, not the 674 unique sampled URLs. Browser outcomes are AI-assisted classifications.

| Estimated endpoint bounds | AI-API | Non-API |
|---|---:|---:|
| Machine-positive and browser-negative, all notes |3.01-5.79%|2.88-8.31%|
| Machine-negative and browser-positive, all notes |6.45-7.96%|8.82-13.09%|
| Browser-positive among machine-negative notes |67.07-82.75%|47.43-70.40%|
| Browser-minus-machine any-source probability |+0.66 to +4.95 pp|+0.51 to +10.21 pp|

### Secondary finite-sample uncertainty check

Sparse discordances in the dominant stratum make normal coverage approximate. A post hoc conservative check inverts exact hypergeometric tails for positive and negative endpoint counts in each stratum. For the lower endpoint it combines a lower positive-count bound with an upper negative-count bound; for the upper endpoint it reverses those directions. Four one-sided bounds per stratum, 16 total, use tail alpha 1/320; Bonferroni gives at least 95% joint design coverage conditional on fixed correct classifications. Integer arithmetic checks each tail against the exact combinatorial denominator. Summing the count bounds and dividing by 1,882 gives **-257/1882 to 507/1882**, or **-13.66 to +26.94 pp**. This wider conservative outer interval does not cover annotation error or changing pages and does not replace the predeclared approximate interval. Exhaustive small-population subset tests covered 1,784 configurations, including census recovery. Public numeric-only code reproduces this check.

## Appendix D. Fixed-claim support diagnostic

A separate seeded 100-pair sample provided 200 notes and 357 note-source slots (319 distinct network URLs). Each note's main corrective claim was fixed from its note text **before** inspecting retrieved source text. The static-GET pipeline was uniform, with no selective browser rescue. Collection retained up to 120,000 private text characters; grader inputs were capped at 24,000 per source with explicit coverage flags. Of 319 query units, 318 were requested and one was policy-censored without a request. The original target post and media were unavailable. The isolated CLI trials had no network tools or cohort key and advertised `gpt-5.6-sol`. A positive FULL/PARTIAL or CONTRADICTS judgment required an exact source quotation no longer than 20 whitespace-delimited words per source. A quote had to occur literally in the retained main text. Missing, capped or truncated source text could not justify a claim that evidence was absent. `UNASSESSABLE` was retained in denominators.

**Table A6. AI-assisted fixed-claim labels; 100 notes per group.** “Strict” downgrades positive labels failing the fixed evidence validator to UNASSESSABLE. These are model judgments on saved source text, not verified note truth.

| Label | AI-API raw | Non-API raw | AI-API strict | Non-API strict |
|---|---:|---:|---:|---:|
| FULL | 20 | 15 | 16 | 13 |
| PARTIAL | 39 | 33 | 30 | 30 |
| NONE | 5 | 15 | 5 | 15 |
| CONTRADICTS, model label only | 1 | 1 | 1 | 1 |
| UNASSESSABLE | 35 | 36 | 48 | 41 |
| FULL or PARTIAL | 59 | 48 | 46 | 43 |

The raw FULL-or-PARTIAL paired difference was +11 pp (descriptive pair-bootstrap 95% 0 to +22); strict was +3 pp (-9 to +15). For FULL alone, strict counts were 16 and 13, +3 pp (-6 to +12). These are uncertainty summaries for the diagnostic sample, not performance estimates of an intervention. Validation found six nonliteral quote cases and 15 quote-length cases, overlapping in three cases; 18 positive labels were downgraded (13 AI-API, five non-API). These are literal-quotation and word-limit compliance failures, not a measurement that the claims are false or semantically unsupported. One trial timed out again on the prespecified technical retry and remained UNASSESSABLE. The separate review of both CONTRADICTS packets confirmed **zero** robust factual contradictions; the raw model labels remain visible for auditability.

**Table A7. Evidence-validator outcomes, exclusive categories; 100 selected notes per group.** The 199 valid selected executions were independently revalidated without changing labels; all stored validation outcomes matched. Invalid execution is separate from the 18 positive-label downgrades.

| Outcome | AI-API | Non-API |
|---|---:|---:|
| Nonliteral quotation only | 2 | 1 |
| Word limit only | 8 | 4 |
| Both quotation and word limit | 3 | 0 |
| Invalid execution | 1 | 0 |
| No validation failure | 86 | 95 |

Of 357 source slots, 354 obtained a model source-role observation; three belonged to the repeated timeout. AI-API had 210 slots, including 30 empty main-text slots and 20 input-truncated slots; non-API had 147 slots, including 24 empty and 10 input-truncated. Seven AI-API notes and ten non-API notes had all source main texts empty. In the 354 observed slots, source roles were SUPPORT 82/53, SUBJECT 22/13, BACKGROUND 47/41, and AMBIGUOUS 56/40 (AI-API/non-API). A source can discuss the subject without substantiating the correction, and the role tags are themselves AI judgments.

A separate 20-note recode was frozen before comparison. Raw labels agreed on 17/20 (85%; κ=0.775); strict labels agreed on 15/20 (75%; κ=0.631). For raw primary → independent AI, the nonzero cells were FULL→FULL 2; PARTIAL→FULL 1, PARTIAL 8, NONE 2; NONE→NONE 1; UNASSESSABLE→UNASSESSABLE 6. For strict primary → independent AI, they were FULL→FULL 2; PARTIAL→FULL 1, PARTIAL 6, NONE 2; NONE→NONE 1; UNASSESSABLE→PARTIAL 2, UNASSESSABLE 6. Another 20-pair correction-alignment recode agreed exactly on 11/20 (κ=0.291). The full 100-pair alignment distribution was 43 same main correction, 36 overlapping, 20 different, one unassessable; no pair was removed post hoc.

After field coding, a 60-case fictitious known-transformation control set was publicly frozen before control-model calls (`f3cd9bb`). Ten fictional families each had six conditions, with English, Japanese and Spanish cases; the 60 outputs were technically valid. Raw and strict labels matched the chosen gold convention in **52/60**: FULL 10/10, PARTIAL 10/10, CONTRADICTS 10/10, UNASSESSABLE 20/20, and NONE 2/10. The eight disagreements were chosen-gold NONE → model PARTIAL on complete directories naming the fictitious target protocol without its relevant date or enablement. Because the rubric also allows PARTIAL for some positive entity/type evidence, these eight are **boundary disputes under a chosen convention**, not unequivocal semantic errors. Repeated families, synthetic content, and creation after the field results prevent using 52/60 as an estimate of field-label accuracy.

## Appendix E. Reproducibility and provenance

Public identifier-free pair tables were independently cryptographically shuffled: 1,882 machine pairs (12 columns: URL counts and numeric any/all/fraction/single-link/redundancy outcomes per group), and 240 browser pairs (29: stratum, lower/upper pair outcomes, fixed-denominator auth/abstract/PDF sensitivities). They omit post/note/account/domain/URL IDs, text, exact dates, host/creation-gap indicators and author cluster codes. Time/shared-link/account checks are aggregate-only. A self-contained standard-library reproducer computes census contrasts, weighted browser bounds, finite-population SEs and the outer interval; private verification matched 84 values/counts to frozen aggregates. A numeric-only add-on reconstructs channel comparisons and the conservative finite-sample interval; 153 values matched private-key analyses within 1e-12. Both ran in minimal directories with only public numeric files/code. This reproduces arithmetic, **not** historical source-body observations.

**Table A8. Key immutable checksums and amendment points.** SHA-256 values below are 16-character prefixes; full byte hashes are in the release manifests. Git hashes identify public protocol/amendment commits.

| Artifact | Hash or commit |
|---|---|
| Public follow-up protocol commit, before first probe | `8fd3817` |
| Frozen protocol JSON SHA-256 | `e0120c8a1fc6f05a` |
| Revised paired candidate file SHA-256 | `fb2eb694f1d8bac7` |
| Machine probe log SHA-256 | `57fd958d45c6a2a8` |
| Frozen machine aggregate SHA-256 | `4254f9f3e8fb19c2` |
| Frozen browser aggregate SHA-256 | `d94d0ddb3898b244` |
| Original browser packet C log SHA-256 | `ec2ae9ae6e0b3c27` |
| Frozen 87-URL browser recode SHA-256 | `4d7599e27edbad0d` |
| Machine anonymous CSV SHA-256 | `2d89ae33aef8902f` |
| Browser anonymous CSV SHA-256 | `1c83f60ac7da4c44` |
| Public technical-retry amendment commit | `d1b316a64c0412868e7a4cb653e32b9f35807c3c` |
| Public synthetic-control freeze commit | `f3cd9bb` |

The support journal had 185 valid trials and 14 completed unjournaled artifacts, preserved but excluded. A public technical amendment preceded 15 isolated retries: 14 valid, one repeated timeout; thus 199 valid model trials and one UNASSESSABLE technical case. Only execution completeness changed, not selected cases, prompt rubric or denominator. The parser, pair-selection seeds and code permit deterministic rebuilding from the **same official snapshot bytes**. Git newline normalization was corrected without changing parsed JSON/CSV values. Later retrieval or numeric reruns cannot independently verify the historical pages.

## Appendix F. Exploratory checks and earlier study

An offline source-priority benchmark was defined **after** browser observations and is exploratory. For a note with machine-open candidates it chooses the candidate with the smallest frozen hash; otherwise it falls back to the prespecified fixed-hash citation. It uses no fitted parameter and no browser outcome to select a URL. Compared with a uniformly chosen single citation in the probability sample, the sharp gain bounds were **-4.23 to +5.41 pp** for AI-API and **-0.81 to +2.25 pp** for non-API. Treating unresolved citations as inaccessible gave point differences of -0.49 and +0.82 pp. The data therefore do not demonstrate an improvement from this priority rule, and no reader-facing intervention was tested.

The earlier exploratory study used a different URL parser and sampling/measurement units. It included 300 month-matched notes per group (600 total): machine-open 235/300 AI-API versus 221/300 non-API, difference +4.7 pp with descriptive pair-bootstrap 95% -2.0 to +11.3. Its browser expansion comprised 204 note-link observations, selected from all 144 machine-nonopen links plus 60 sampled machine-open links; weighted accessible-rate bounds were 76.9-84.5% versus 69.7-82.8%. A separate 40-case support recode yielded FULL 17, PARTIAL 7, NONE 2 and UNASSESSABLE 14; among 33 exact HTTP-200 links, seven remained UNASSESSABLE. The old/new recode agreed in 32/40 cases (κ=0.694). Eight selected historical-archive replays in that study yielded five substantive intended pages, one homepage and two shells, illustrating historical variability but not estimating a population rate. None of these 600/204/40/8 denominators is pooled with the revised 1,882-pair machine census, 240-pair browser sample or 100-pair support diagnostic.

## Appendix G. Archival follow-up and temporal limits

This secondary study tested whether a cited page version could be inspected before its Community Note first became Helpful, and whether archived and current versions supported the **same fixed corrective claim**. It used the separate 100-pair diagnostic: 200 notes with 357 citation references to 354 distinct exact-URL/first-Helpful-time query units. The 200 claims came from an alignment log fixed before this wave's source-content pass. Before archive querying, an unconditional hash-ranked 100-unit body-replay panel was selected. All 100 remain in the denominator, including failures and unavailable captures. The comparison concerns observed source-to-claim support, not note truth or the page a user actually saw.

The Internet Archive CDX search used a 30-day window before each first Helpful timestamp. A candidate required an exact original URL, archived HTTP 200, a permitted text/PDF MIME type, and a one-second capture interval wholly before the timestamp. A faster first pass was stopped after sustained HTTP 429 and connection failures; its unattempted units were unknown, and its outcomes did not select v2 units. The slower whole-frame v2 method was publicly frozen before requests (commit `96cc399`) with one worker and at least ten seconds between starts. It completed all 354 units: 345 valid exhausted index results and nine HTTP 403 errors (unknown). Of the valid results, 141 contained an eligible exact-original body candidate, 26 had a retained but ineligible capture, and 178 had no retained capture **in that window**. CDX metadata does not establish that a page body can be replayed or that it supports a claim.

**Table A9. Unconditional 100-unit panel and bounded body replay.** This is a source-unit availability funnel, not a note-level support rate.

| Stage or outcome | Units |
|---|---:|
| Frozen panel | 100 |
| Eligible exact-original pre-Helpful capture | 41 |
| No eligible capture in valid CDX result | 58 |
| CDX error; candidate status unknown | 1 |
| Historical and current text parser-readable | 31 |
| Historical replay transport failure | 9 |
| Historical body above 2 MB cap | 1 |
| Both versions substantively assessable by AI | 18 |

The nearest eligible capture and one fallback were frozen before any v2 panel body request (commit `22fc8c1`). Raw replay stayed on `web.archive.org`, rejected changed original URLs/timestamps and live-source redirects, and never fetched subresources or archived bodies from browser-policy-blocked hosts. One successful body used its preselected fallback. All 31 parser-readable historical bodies returned HTTP 200 with `Memento-Datetime` matching the selected capture; the corresponding 31 current pages also parsed. These 31 units span 29 notes on 25 posts, but parser-readable text can still be a teaser, wrong page or irrelevant article.

The 62 version-hidden, shuffled source judgments used the same previously fixed claim, a 24,000-character cap, and unchanged FULL/PARTIAL/NONE/CONTRADICTS/UNASSESSABLE rules. Eight quote-validation failures stayed **unknown**, with no retry or looser cap; 54 executions were valid. Only **18 source units across 18 notes** had two substantively assessable labels, below the predeclared 30-unit/20-note threshold for descriptive paired comparison. Four of those pairs had different labels. Separate label-hidden AI review did not confirm material source-support drift: two had unchanged claim-relevant passages, one identical extracted main text, and one an unrelated historical listing. On the proportion scale, the frozen 100-unit current-minus-historical FULL-support bound is **[-0.76, +0.79]**; post hoc censoring the listing's historical label changes assessable units **18→17** and the bound to **[-0.77, +0.79]**. Neither supports a directional claim.

The actual successful capture-to-first-Helpful lag was median 2.35 days (range 0.006-26.06 days). **Twenty-five of 31** successful captures preceded note creation; only six followed creation, and just **two** of those had two substantively assessable labels. Even an independently reviewed source-version difference would not establish what the citation said when the note was written. Archive selection, HTTP 403s, replay failures, page identity and AI label error further limit this feasibility study. No case-level source-drift claim is made.
