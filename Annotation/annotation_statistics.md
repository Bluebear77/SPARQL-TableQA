# Annotation Selection Statistics

This file summarizes the final balanced annotation CSV outputs.

Public output columns:

```text
question,gold_answer,KG answer,taxonomy_label,confidence,source
```

Confidence column meaning:
- Simple heuristics: `similarity_score`.
- LLM-as-a-judge: `difference_severity`, exactly one of `none`, `minor`, `moderate`, `major`.

Selection target:
- 300 cases per model.
- Balanced across SimpleQA and ComplexQA.
- Balanced across Simple heuristics and LLM-as-a-judge.

## Total Selected Rows

| Metric | Qwen3-4B-Instruct | Qwen3-30B-Thinking | Qwen3-235B-Thinking |
| --- | --- | --- | --- |
| Total selected | 300 | 300 | 300 |

## Method Distribution

| Method | Qwen3-4B-Instruct | Qwen3-30B-Thinking | Qwen3-235B-Thinking |
| --- | --- | --- | --- |
| Simple heuristics | 150 | 150 | 150 |
| LLM-as-a-judge | 150 | 150 | 150 |

## QA Group Distribution

| QA Group | Qwen3-4B-Instruct | Qwen3-30B-Thinking | Qwen3-235B-Thinking |
| --- | --- | --- | --- |
| SimpleQA | 150 | 150 | 150 |
| ComplexQA | 150 | 150 | 150 |

## 2x2 Bucket Distribution

| QA Group | Method | Qwen3-4B-Instruct | Qwen3-30B-Thinking | Qwen3-235B-Thinking |
| --- | --- | --- | --- | --- |
| SimpleQA | Simple heuristics | 75 | 75 | 75 |
| SimpleQA | LLM-as-a-judge | 75 | 75 | 75 |
| ComplexQA | Simple heuristics | 75 | 75 | 75 |
| ComplexQA | LLM-as-a-judge | 75 | 75 | 75 |

## Taxonomy Distribution

| taxonomy_label | Qwen3-4B-Instruct | Qwen3-30B-Thinking | Qwen3-235B-Thinking |
| --- | --- | --- | --- |
| Different answer | 141 | 128 | 129 |
| Higher accuracy in KG than in Table | 0 | 3 | 3 |
| Higher accuracy in Table than in KG | 9 | 14 | 15 |
| Same | 150 | 150 | 150 |
| Temporal changes | 0 | 5 | 3 |

## Rows Removed Before Selection

| Model | Simple rows filtered by label | Rows removed by >10-row file_path filter | Duplicate questions removed | Removed rows CSV |
| --- | --- | --- | --- | --- |
| Qwen3-4B-Instruct | 743 | 0 | 14 | /workspaces/KONTRAST/Annotation/removed_files/removed_rows_4B.csv |
| Qwen3-30B-Thinking | 720 | 0 | 17 | /workspaces/KONTRAST/Annotation/removed_files/removed_rows_30B.csv |
| Qwen3-235B-Thinking | 810 | 0 | 19 | /workspaces/KONTRAST/Annotation/removed_files/removed_rows_235B.csv |

## Selection Warnings

None.

## Skipped Pairs

None.
