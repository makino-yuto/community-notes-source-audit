# Anonymous numeric reproduction: same-post all-citation wave

This package accompanies “Can Readers Still Check the Source? A Time-Matched Audit of AI-API Community Notes.” It reproduces the main numeric machine-screening and browser-access results using the Python standard library:

    python src/reproduce_newwave_public.py --output reproduced.json

The script verifies the SHA-256 hash of each CSV against manifest.json, checks each row's arithmetic, and recomputes main paired machine contrasts, note-level browser bounds, finite-population design standard errors, the outer interval, and conservative access sensitivities. It makes no network requests. Time-gap, shared-link and host-diversity robustness results are supplied only as aggregate numbers in the manifest.

## Population and units

- data/machine_pairs_anonymous.csv: 1,882 post pairs; one eligible observed AI-API and one non-API currently Helpful note per post, selected as specified in the frozen protocol. Each row preserves the pair but carries no post, note, author or URL identifier.
- data/browser_pairs_anonymous.csv: 240 post pairs sampled without replacement, 60 from each machine any-open stratum. Each row gives anonymous note-level lower/upper access outcomes after all cited URLs were browser-inspected. The stratum population and sample counts in manifest.json reproduce the weights.
- AI-API identifies observed apiEarnedIn enrollment. Non-API is not verified human authorship. This is a conditional currently Helpful frame, not a causal AI-vs-human experiment.

Machine “open” is an automated transport/content screening category. Browser “accessible” requires visible substantive intended content in the study browser profile. Both are distinct from whether a source supports a note's claim. Unresolved browser outcomes remain interval bounds. The normal finite-population interval quantifies pair-sampling variation within the fixed frame; it does not quantify AI assessor error, changing web pages or generalization to other writers.

The machine table includes only URL counts and machine outcomes, not host counts, time gaps, shared-link flags, domains, exact times or links. Rows in the two CSVs were independently shuffled with a cryptographic random generator; their original order and correspondence across tables are unavailable. Author-cluster codes are omitted to reduce account-linkage risk. Some rare numeric combinations remain. This is not differential privacy and does not guarantee that rows cannot be linked with external data.

The manifest carries aggregate URL-label and repeated-browser counts only; the 87 repeated observations cannot be reconstructed case by case from this package. The separate 100-pair source-support diagnostic is reported in aggregate; its source texts and individual judgments are withheld.

This release permits numeric recomputation, not an independent historical audit of pages, videos, or model judgments. Rebuilding the frame from official Community Notes releases requires the broader repository's extraction code and frozen seeds. Re-observing live URLs later would measure a different date.
