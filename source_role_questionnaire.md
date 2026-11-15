# Blinded source-role and citation-support audit

Use the frozen `results/role_sample_blinded.jsonl` packet in its given randomized order. The packet has 100 notes: 50 from each cohort, sampled from the primary 600 notes with month-balanced quotas and seed `20261116`. The reviewer must not open `role_sample_key.json`, cohort labels, or URL-probe results before coding. AI style may still reveal author type, so the blind is imperfect.

This is a **construct-validity substudy**, separate from the primary URL-retrievability outcome. A working link is not necessarily evidence for a note's claim. No paid API or model calls are required. Each coded item should have a short rationale; source-support labels must cite a page title, paragraph/heading, or short excerpt locator, without copying long passages.

## Pass 1: source role, before opening the URL

Read the note summary, its selected URL, and the note creation date. Record exactly one role for that selected URL based only on the wording and surrounding context in the note:

* `SUPPORT`: presented as evidence for a factual claim made by the note (including a source explicitly introduced by “according to”, “shows”, “records”, “source”, or similar language).
* `SUBJECT`: the post, photo, video, statement, or account that the note is correcting or identifying, without being presented as independent support for the correction.
* `BACKGROUND`: related reading, attribution, navigation, or context that is not presented as direct evidence for the note's main correction.
* `AMBIGUOUS`: the role cannot be assigned from the note text, including genuine overlap between subject and support. Record why.

Do not inspect whether the URL works in this pass. Do not infer `SUPPORT` just because the note author's `trustworthySources` checkbox was selected; that checkbox is not in the blind packet. For notes with several URLs, code only the URL that was randomly selected before probing, and do not silently switch to a healthier citation.

Record `core_claim` as the shortest checkable factual proposition that the note uses the selected URL to support. Prefer the factual clause immediately preceding that URL; if the URL is at the end of a multi-clause note, use the first central corrective claim. Mark `NO_CHECKABLE_CLAIM` when none is identifiable, and `MULTIPLE_INSEPARABLE` when a single proposition cannot be chosen without cherry-picking. This record is made before visiting the source.

## Pass 2: source support, after reading the cited page

Only assess support for cases coded `SUPPORT` in Pass 1. Use an unauthenticated live page or PDF at the selected URL and record its title, access time, final URL, and exact section/paragraph used. Ignore source authority and judge only whether its content supports the preselected `core_claim` **with matching scope, date, population and quantifier**:

* `FULL`: source content directly entails the core claim at its stated scope.
* `PARTIAL`: source backs a narrower or incomplete version, but not every material element.
* `NONE`: the page is accessible and topically related, yet does not contain sufficient evidence for the claim.
* `CONTRADICTS`: the source directly gives an incompatible result or correction.
* `UNASSESSABLE`: login/block, missing content, unsupported language or media, no stable claim, or a source that has changed so far that original support cannot be inferred.

An `OPEN/READABLE` HTTP outcome cannot determine `FULL` by itself. A current `NONE` verdict does not prove that the source never supported the claim at note creation. If an Internet Archive capture within 30 days of the note's first Helpful date exists, code a separate historical-support verdict and keep capture date/URL; do not replace the current verdict. A changed CDX digest alone is insufficient for a semantic-drift claim.

## Reproducibility and reporting

Save one JSONL annotation row per code with fields `code`, `role`, `role_reason`, `core_claim`, `support_current`, `source_locator`, `source_checked_utc`, `historical_support` (if checked), `historical_capture_date` (if checked), and `confidence` (`high`, `medium`, `low`). No cohort label belongs in annotation rows.

For feasibility before the Nov 16 20:59 JST deadline, code Pass 1 for all 100 notes (roughly 1–2 hours). Then code Pass 2 for a **seeded subset of up to 40 `SUPPORT` cases**, at most 20 per cohort, drawn without seeing support outcomes. If a cohort has fewer than 20 `SUPPORT` cases, include all and report the smaller denominator. A reviewer other than the first coder should recode a seeded 20-case subset, blind to the first labels, to expose ambiguity; if only one reviewer is available, do not claim independent agreement. Calculate raw agreement and Cohen's kappa for source role; report disagreement cases and resolved labels. Model-to-model agreement is a consistency check, not human validation.

Report source-role counts by cohort with Wilson intervals (small-sample, descriptive), plus support-verdict counts **conditional on a selected `SUPPORT` URL that was inspectable**. Do not extrapolate the 40-case support audit to all 600 notes, equate note helpfulness with factual correctness, or infer a causal AI-vs-human difference. The 20 AI authors versus 291 human authors in the primary cohort create author-level dependence; mention this and avoid precise population claims from this small audit.

Do not republish note text, author identities, or a list of broken or manipulable URLs. A public artifact can show coded counts and redacted examples with enough explanation to reproduce the rubric.
