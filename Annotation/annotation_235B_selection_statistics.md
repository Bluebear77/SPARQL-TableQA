# 235B Annotation Selection Statistics

This file summarizes the balanced 235B annotation outputs.

Public output columns:

```text
question,gold_answer,KG answer,taxonomy_label,confidence,source
```

## Cleaning Summary

| Metric | Count |
| --- | --- |
| Simple heuristics input rows | 1453 |
| LLM-as-a-judge input rows | 810 |
| Simple rows filtered by taxonomy_label | 810 |
| Rows removed by >10-row file_path filter | 95 |
| Duplicate question rows removed | 17 |
| Eligible rows after cleaning | 1341 |

## Top 300 Output

Rows written: 300

Method distribution:

| Method | Count |
| --- | --- |
| Simple heuristics | 150 |
| LLM-as-a-judge | 150 |

QA group distribution:

| QA Group | Count |
| --- | --- |
| SimpleQA | 150 |
| ComplexQA | 150 |

2x2 bucket distribution:

| QA Group | Method | Count |
| --- | --- | --- |
| SimpleQA | Simple heuristics | 75 |
| SimpleQA | LLM-as-a-judge | 75 |
| ComplexQA | Simple heuristics | 75 |
| ComplexQA | LLM-as-a-judge | 75 |

Taxonomy distribution:

| taxonomy_label | Count |
| --- | --- |
| Different answer | 127 |
| Higher accuracy in KG than in Table | 4 |
| Higher accuracy in Table than in KG | 16 |
| Same | 150 |
| Temporal changes | 3 |

## Second 10-Case Presentation Slice

Rows written: 10

Method distribution:

| Method | Count |
| --- | --- |
| Simple heuristics | 5 |
| LLM-as-a-judge | 5 |

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
| ComplexQA | Simple heuristics | 2 |
| ComplexQA | LLM-as-a-judge | 3 |

Taxonomy distribution:

| taxonomy_label | Count |
| --- | --- |
| Different answer | 3 |
| Higher accuracy in KG than in Table | 2 |
| Same | 5 |
