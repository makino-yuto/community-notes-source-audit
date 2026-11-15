# Fixed-claim source-support diagnostic

This secondary diagnostic covers 100 randomly selected same-post pairs: 100 notes from the observed AI-API cohort and 100 from the observed non-API cohort. All 200 notes remain in every primary support denominator. The cited material comprises 357 note-source slots drawn from 319 distinct network URLs. This diagnostic is separate from the browser-profile source-access endpoint.

The main corrective propositions were fixed in the preceding blinded alignment pass. A uniform static content pass retrieved the selected citations without outcome-conditioned browser escalation. Each supplied source included its provenance and extraction coverage, with at most the first 24,000 main-text characters. Empty responses, access barriers, boilerplate, truncation and one policy-censored source were retained. The original social-media posts and media were unavailable.

Fresh isolated official Codex CLI trials used the existing ChatGPT authentication, no API keys or model override, an ephemeral read-only configuration, and disabled tools. All 199 technically valid executions advertised the same default model, `gpt-5.6-sol`. Assessors were instructed to treat retrieved text as untrusted quoted data and judge source support for the fixed proposition while retaining entity, quantity, time, negation, modality and attribution. The categories were FULL, PARTIAL, NONE, CONTRADICTS and UNASSESSABLE. Missing or truncated text could not establish absence; observed positive evidence could support FULL despite later truncation. This evaluates observed source-to-claim support, not the truth of a note or the authority of its source.

## Technical interruption and prospective completion

The original ordered executor journal contains 185 valid executions and one 240-second timeout. Fourteen later tasks completed response/log artifacts but were not written to the journal after iteration aborted. Those unjournaled outputs were preserved and were not silently accepted. A separate technical-completion amendment and adapter were [committed and pushed](https://github.com/makino-yuto/community-notes-source-audit/commit/d1b316a64c0412868e7a4cb653e32b9f35807c3c) before any retry.

All 15 cases without valid original journal records were retried exactly once, using the same packet, fixed claims, prompt, schema, validator, default CLI settings, two-worker cap and 240-second limit. Separate directories and a separate journal retain every retry. Fourteen retries were valid; the repeated timeout is UNASSESSABLE in both summaries. No second retry was attempted. The original journal and all 57 original artifacts associated with the 15 cases still match their pre-retry hashes. Private inventories retain selection and artifact hashes; public outputs contain only aggregates.

## Raw results and predeclared strict validation

The raw summary retains the model's semantic categories for valid executions. The strict summary applies the previously declared rule: evidence or source-coverage validation failures become UNASSESSABLE, with the original output preserved. For every supplied quote, code checked source identity, exact literal occurrence in supplied main_text, and the cumulative limit of 20 whitespace-delimited words per source. Evidence-positive labels required evidence, and source observations had to cover every supplied source.

All 200 selected executions were rechecked, including all 109 FULL, PARTIAL or CONTRADICTS cases. Eighteen evidence-positive cases failed validation: six nonliteral-quote events and 15 word-limit events, with overlap. Every affected case was flagged and downgraded. The repeated timeout accounts for one additional invalid-execution case. There were no differences between stored and recomputed validation errors. Both CONTRADICTS cases passed technical evidence checks.

A separate independent AI review examined both complete contradiction packets and established no robust factual contradiction in either. Partial positive background information coexisted with incomplete support for the core propositions; logical scope, unavailable media, incomplete source coverage, internal source inconsistency and temporal reference limited the contradiction inference. The public aggregate records two packets reviewed and zero independently confirmed contradictions. Private opaque-case notes retain the detailed reasons. Both original raw and strict model CONTRADICTS labels remain unchanged, and the review changes no group counts or agreement calculations. Model contradiction labels must not be interpreted as confirmed false notes.

| Category | Raw AI-API | Raw non-API | Strict AI-API | Strict non-API |
|---|---:|---:|---:|---:|
| FULL | 20 | 15 | 16 | 13 |
| PARTIAL | 39 | 33 | 30 | 30 |
| NONE | 5 | 15 | 5 | 15 |
| CONTRADICTS | 1 | 1 | 1 | 1 |
| UNASSESSABLE | 35 | 36 | 48 | 41 |
| Total | 100 | 100 | 100 | 100 |

Raw FULL-or-PARTIAL support was 59% versus 48%, an 11-point paired difference. After strict validation it was 46% versus 43%, a 3-point difference. Strict FULL alone was 16% versus 13%, also a 3-point difference. These are descriptive cohort associations. The strict FULL-or-PARTIAL paired cells were 27 both positive, 19 AI-API only, 16 non-API only and 38 neither positive.

Descriptive percentile bootstrap intervals resample 100 post pairs together, using 10,000 draws and seed 2026111514. The interval for the strict FULL-or-PARTIAL difference was -9 to +15 percentage points; for strict FULL it was -6 to +12 points. These intervals describe post-pair resampling sensitivity. They do not resolve model error, observation censoring, source selection or account dependence and are not the primary browser endpoint's design-based interval. Equal-AI-account and leave-one-AI-account-out summaries are provided separately in the aggregate.

## Source roles, coverage and blinded recoding

The AI-API notes supplied 210 source slots and the non-API notes 147. Main text was empty in 30 and 24 slots, respectively; 20 and 10 slots were truncated at the supplied-text limit. Seven AI-API notes and 10 non-API notes had all source text empty. One policy-censored source remains in the denominator. The aggregate preserves these extraction flags independently of the model's substantive-content judgments.

Source-role observations cover 354 slots from technically valid executions; three slots belong to the repeated-timeout case and have no model role annotation. The AI-API slot labels were SUPPORT 82, SUBJECT 22, BACKGROUND 47 and AMBIGUOUS 56. The non-API labels were SUPPORT 53, SUBJECT 13, BACKGROUND 41 and AMBIGUOUS 40. These are diagnostic model descriptions of citation roles, not independent source-quality ratings or factual certifications.

A uniform random 20-note recode subset was fixed before support outputs were inspected. Its second AI assessor read only the blind packet, with no primary labels, key, other study files, network or external facts. The recode was hash-frozen before comparison. Exact raw-label agreement was 17/20 (85%; Cohen's kappa 0.775); agreement with strict primary labels was 15/20 (75%; kappa 0.631). Full confusion matrices and descriptive Wilson intervals appear in the aggregate. Strict agreement is lower because two otherwise agreeing primary PARTIAL labels failed technical quote checks. This is AI-versus-AI consistency, not human gold-standard validation; correlated errors remain possible.

The selected sample contains 13 observed AI-API accounts (effective inverse-HHI count 7.81) and 96 non-API accounts. The largest AI-API account supplies 18% of these notes. Same-post pairing does not ensure matching corrective propositions: the alignment pass labeled 43 pairs same-main-correction, 36 overlapping, 20 different and one unassessable, and its own blinded recode agreement was limited. Alignment-stratum counts are diagnostic only; no pair is dropped from the overall results.

## Interpretation and reproducibility

The main result is sensitive to evidence validation: the raw 11-point FULL-or-PARTIAL difference falls to 3 points under the predeclared strict rule, while many notes remain unassessable. Literal quotation is a necessary technical check, not proof that the quoted text entails every fixed material claim. General background about synthetic media cannot identify an unavailable target video, and a specific caption disclosure has a different evidentiary role from a general detection article.

The sample is conditional on currently Helpful notes from both observed enrollment cohorts on the same post. Observed API enrollment does not prove AI composition, and non-API enrollment does not verify human authorship. These results establish neither a causal authorship effect nor current note truth, historical support or semantic drift. The public analysis script and aggregate expose the calculations, counts, validation outcomes and input hashes. Withheld individual packets and raw CLI records prevent independent regeneration from the public package alone.

Independent recode SHA-256: `fccd7efa1dd5a901cc9c0687ff7fc2554de4cdd1b11fda5216c58c54defbf5b5`.
