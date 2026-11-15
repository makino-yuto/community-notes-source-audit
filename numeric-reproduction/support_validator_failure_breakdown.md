# Evidence-validator failure breakdown

**Exclusive categories; 100 selected notes per group.** Counts reproduce the frozen selection of 185 valid original journal records plus all 15 technical retries.

| Selected-case category | AI-API | Non-API |
|---|---:|---:|
| Nonliteral quotation only | 2 | 1 |
| Quote length only | 8 | 4 |
| Both nonliteral and length | 3 | 0 |
| Other validation failure | 0 | 0 |
| Invalid execution | 1 | 0 |
| No validation failure | 86 | 95 |
| Total | 100 | 100 |

Thirteen AI-API and five non-API evidence-positive judgments failed the frozen validator and became UNASSESSABLE in the existing strict summary. Across groups, six cases had a nonliteral-quote failure and 15 had a quote-length failure, overlapping in three cases. The one invalid execution was already UNASSESSABLE in both summaries and is not an additional positive-label downgrade. All 199 valid selected executions were independently revalidated; their errors and the raw/strict group label counts exactly matched the frozen analysis. No labels changed.

These categories measure technical evidence-format compliance, not semantic accuracy. In particular, a length-only failure does not imply that the cited source lacks support. The validator's source-coverage check verifies records for every supplied source; it does not certify semantic coverage.
