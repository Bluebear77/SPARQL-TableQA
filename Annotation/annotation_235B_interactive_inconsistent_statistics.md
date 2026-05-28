# 235B Interactive Inconsistent Annotation Selection Statistics

This file summarizes the balanced 235B inconsistent-case annotation outputs.

Rows whose normalized `taxonomy_label` is `Same` are excluded before selection.

Public output columns:

```text
question,gold_answer,KG answer,taxonomy_label,sparql,confidence,source
```

## Selection Mode

- Requested target size: 300
- Actual main selection size: 296
- Mode: perfect

The main set is exactly balanced across the four source/method buckets.

## Cleaning Summary

| Metric | Count |
| --- | --- |
| Simple heuristics input rows | 1453 |
| LLM-as-a-judge input rows | 810 |
| Simple rows filtered by different_unclassified | 810 |
| Simple rows filtered because taxonomy_label is Same | 422 |
| LLM rows filtered because taxonomy_label is Same | 100 |
| Rows removed by >10-row file_path filter | 95 |
| Duplicate question rows removed | 11 |
| Eligible inconsistent rows after cleaning | 825 |

## Selection Notes

- ComplexQA: filled 2 row(s) from LLM-as-a-judge because the preferred method bucket was short.

## Main Inconsistent Output

Rows written: 296

Method distribution:

| Method | Count |
| --- | --- |
| Simple heuristics | 148 |
| LLM-as-a-judge | 148 |

QA group distribution:

| QA Group | Count |
| --- | --- |
| SimpleQA | 148 |
| ComplexQA | 148 |

2x2 bucket distribution:

| QA Group | Method | Count |
| --- | --- | --- |
| SimpleQA | Simple heuristics | 74 |
| SimpleQA | LLM-as-a-judge | 74 |
| ComplexQA | Simple heuristics | 74 |
| ComplexQA | LLM-as-a-judge | 74 |

Taxonomy distribution:

| taxonomy_label | Count |
| --- | --- |
| Different answer | 148 |
| Higher accuracy in KG than in Table | 105 |
| Higher accuracy in Table than in KG | 40 |
| Temporal changes | 3 |

## Second 10-Case Inconsistent Presentation Slice

Rows written: 10

Method distribution:

| Method | Count |
| --- | --- |
| Simple heuristics | 3 |
| LLM-as-a-judge | 7 |

QA group distribution:

| QA Group | Count |
| --- | --- |
| SimpleQA | 5 |
| ComplexQA | 5 |

2x2 bucket distribution:

| QA Group | Method | Count |
| --- | --- | --- |
| SimpleQA | Simple heuristics | 3 |
| SimpleQA | LLM-as-a-judge | 2 |
| ComplexQA | Simple heuristics | 0 |
| ComplexQA | LLM-as-a-judge | 5 |

Taxonomy distribution:

| taxonomy_label | Count |
| --- | --- |
| Different answer | 6 |
| Higher accuracy in KG than in Table | 4 |
