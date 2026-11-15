# Evidence-link durability in AI and human Community Notes: pre-analysis protocol

Version: 2026-11-15, after a separate small feasibility pilot and before the primary sample is drawn or probed. This is a local study plan, not an externally registered preregistration. Freeze this file and the code revision before running the primary analysis. The pilot, deviations, and their reasons belong in the final report.

## Question and estimand

Can an independent reader or research agent still retrieve the external evidence linked by a currently Helpful Community Note? Compare notes written through X's AI Note Writer API with human-authored notes from the same creation months. The primary estimand is the **descriptive difference in confirmed machine-retrievable source URLs**, AI minus human, in the eligible population defined below. It is not a causal effect of AI authorship, a judgment of claim truth, or a measure of note helpfulness.

The public data and its limits are specified by [X's Community Notes data dictionary](https://github.com/twitter/communitynotes/blob/main/documentation/under-the-hood/download-data.md). X says `apiEarnedIn` identifies AI API writers, `isCollaborativeNote` identifies hybrid notes, and deleted note content disappears from the daily Notes file while status metadata remains. X's [Community Writer design](https://github.com/twitter/communitynotes/blob/main/documentation/api/community-writer.md) explicitly uses a deletion model. These facts make survivor selection an important limit.

## Frozen source and eligibility

1. Use one dated official [Community Notes snapshot](https://communitynotes.x.com/guide/en/under-the-hood/download-data), recording exact source URLs, HTTP retrieval time, file size, and SHA-256 of Notes, Note Status History, and User Enrollment ZIP files. Do not mix snapshot dates. X says releases are daily on a best-effort basis and lag up to 48 hours.
2. Join Notes to Note Status History on `noteId`; join the note-author participant ID to User Enrollment `participantId`. Restrict to notes created from 2025-09-01 through 2026-08-31 inclusive, at least roughly two months before this study. Require snapshot `currentStatus == CURRENTLY_RATED_HELPFUL`, an available Notes row, nonempty summary, and at least one explicit `http://` or `https://` URL whose registrable domain is outside X/Twitter. Exclude ambiguous or malformed URLs, retaining counts.
3. AI cohort: `enrollmentState == apiEarnedIn`. Human cohort: all other writer-eligible human enrollment states. Exclude `isCollaborativeNote == true` from both. If `timestampOfLastStateChange` is later than note creation, exclude the author from the primary cohort because the snapshot cannot prove historical enrollment state. Report these exclusions. Do not treat missing enrollment rows as human.
4. Select at most one URL per note using a seeded random draw among explicit external URLs. This prevents a multi-citation note from receiving more weight. Record all-URL note-level results as a secondary analysis only if collection time permits. Do not choose a URL based on its apparent health.
5. Match AI and human notes by creation month. Aim for 300 notes per group across months with both cohorts; draw equal numbers within each month up to availability, using seed `20261115`, then allocate unused slots proportionally across remaining eligible months. Fix the selected note IDs and URLs before any URL probes. Report the source population and realized sample by month. If fewer than 300 matched pairs exist, use all available and disclose the smaller sample.

## URL measurement and adjudication

The probe uses an ordinary unauthenticated HTTPS/HTTP GET with a documented user agent, five-redirect cap, 15-second timeout, and response-body cap. Record UTC time, original URL hash, final URL/domain, redirect chain, status, content type, response length, and normalized text hash where readable. Never transmit credentials or personal cookies. A HEAD response alone does not determine health. Run one repeat GET for errors, blocks, and timeouts; record both observations. A site may vary by region or block automation, so do not call a 403/429 a dead source.

Assign one mutually exclusive outcome to each URL:

* **Open/readable:** a 2xx final response yields a substantive article/document body or a readable PDF without login or anti-bot challenge. A 2xx login page does not qualify.
* **Access barrier:** authentication, paywall, CAPTCHA, robots/anti-bot interstitial, HTTP 401/403/429, or a 2xx challenge/login page. The source may still exist.
* **Gone:** confirmed HTTP 404/410, DNS NXDOMAIN, or a redirect to a generic missing/deleted page on repeat checks.
* **Transient/uncertain:** timeout, connection/TLS failure, 5xx, unstable outcomes, unsupported media type, or parser uncertainty after repeat checks.

Keep the redirect outcome as separate metadata: same registrable domain, cross-domain, or URL shortener. Review every `gone` and `access barrier` case manually in a normal browser, and a seeded 10% sample of `open/readable` cases, before reporting final classifications. If resources limit full adjudication, record exactly which cases were reviewed and retain the machine-only result separately. A second pass with another network vantage point, if available, is a sensitivity check, not a reason to silently relabel failures.

The **primary outcome** is the fraction classified `open/readable`. Report `access barrier`, `gone`, and `transient/uncertain` separately. The primary comparison treats uncertainty as not confirmed accessible; a sensitivity interval counts uncertain cases first as accessible, then inaccessible. Excluding uncertain cases is an additional sensitivity analysis, not the main estimate.

## Archive and content-drift substudy

For a seeded subset of at most 100 URLs per cohort, query the [Internet Archive CDX index](https://github.com/internetarchive/wayback/blob/master/wayback-cdx-server/README.md) for an archived capture within 30 days of the note's first Helpful timestamp (or creation if first-Helpful is unavailable), and a later capture at least 30 days after that. Record capture coverage, timestamps, HTTP status and CDX digest. A different digest is **possible change**, not evidence that the cited claim changed: site navigation, advertising and dynamic templates can alter the digest. For pairs with captures, extract main-text content and inspect a seeded, fixed number of changed cases manually for substantive page or claim-level drift. Report the fraction with adequate archive coverage separately; never infer that URLs without captures stayed stable.

## Analysis and uncertainty

The primary result is the AI-minus-human percentage-point difference in `open/readable`, with each creation month given weight proportional to its eligible matched-pair population. Estimate a 95% confidence interval by resampling matched AI/human pairs within month (10,000 bootstrap replicates, fixed seed). Report raw counts and Wilson intervals by cohort, month, source-domain class, and age band. Domain- and author-cluster sensitivity analyses matter because repeated links from the same host and repeated notes by one writer can understate uncertainty. If confidence intervals are wide or cross zero, say so; do not convert a null result into evidence of equivalence.

Predeclared checks: (i) remove X/Twitter links and generic homepages (already primary eligibility); (ii) separate exact 404/410/NXDOMAIN from all other failures; (iii) exclude notes whose author state may have changed after note creation; (iv) compare post-2026-02 and pre-2026-02 cohorts; (v) quantify how many candidate Notes rows are absent despite status-history metadata (deleted-content survivor selection). The last check cannot recover missing text or URLs, so it does not correct selection bias.

## Interpretation, dual use and privacy

Availability is only a prerequisite for verification. A live URL may be false, irrelevant, altered, or malicious; a blocked URL may be valid to a human visitor. Current Helpful status reflects contributor ratings, not independent factual certification. AI and human notes differ in post selection, recency, topics, and domains, so the cohort comparison is descriptive. No causal AI-vs-human claim follows.

The study uses public, pseudonymous data. Do not deanonymize authors, profile individual writers, republish misleading note text at scale, or publish an actionable list of vulnerable source URLs. Release aggregate metrics, code, input file hashes, and a small redacted audit sample. URL probes should obey reasonable rate limits and avoid login or bypassing site controls. The evidence-preservation tool, if built, must not amplify false or harmful source material.
