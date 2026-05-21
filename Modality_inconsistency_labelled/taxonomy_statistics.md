# Taxonomy Merge Statistics

This file summarizes the cleaned, merged taxonomy-labeled QA CSV outputs.

Cleaning steps applied before writing each output CSV:
1. Remove rows whose `file_path` appears in `Output_GRASP/script/large_results_report.txt`.
2. Remove duplicate `question` rows inside each model output, keeping the first occurrence.
3. Save removed rows to `Modality_inconsistency_labelled/removed_files/`, with a `cause` column.

Each distribution count is shown as:

```text
count (percentage within model)
```

## Total Rows by Model

| Metric | Qwen3-4B-Instruct | Qwen3-30B-Thinking | Qwen3-235B-Thinking |
| --- | --- | --- | --- |
| Total | 902 | 1167 | 1341 |

## Rows Removed by Cleaning Step

| Model | Rows removed by >10-row file_path filter | Rows removed as duplicate questions | Total removed by these two steps | Removed rows CSV |
| --- | --- | --- | --- | --- |
| Qwen3-4B-Instruct | 251 | 12 | 263 | /KONTRAST/Modality_inconsistency_labelled/removed_files/removed_rows_4B.csv |
| Qwen3-30B-Thinking | 97 | 14 | 111 | /KONTRAST/Modality_inconsistency_labelled/removed_files/removed_rows_30B.csv |
| Qwen3-235B-Thinking | 95 | 17 | 112 | /KONTRAST/Modality_inconsistency_labelled/removed_files/removed_rows_235B.csv |
| Total | 443 | 43 | 486 |  |

## Taxonomy Distribution by Model

| taxonomy_label | Qwen3-4B-Instruct | Qwen3-30B-Thinking | Qwen3-235B-Thinking |
| --- | --- | --- | --- |
| Different answer | 416 (46.12%) | 477 (40.87%) | 519 (38.70%) |
| Higher accuracy in KG than in Table | 122 (13.53%) | 135 (11.57%) | 151 (11.26%) |
| Higher accuracy in Table than in KG | 66 (7.32%) | 101 (8.65%) | 126 (9.40%) |
| Same | 285 (31.60%) | 423 (36.25%) | 518 (38.63%) |
| Temporal changes | 13 (1.44%) | 31 (2.66%) | 27 (2.01%) |
| Total | 902 (100.00%) | 1167 (100.00%) | 1341 (100.00%) |

## Method Distribution by Model

| method | Qwen3-4B-Instruct | Qwen3-30B-Thinking | Qwen3-235B-Thinking |
| --- | --- | --- | --- |
| LLM-as-a-judge | 495 (54.88%) | 625 (53.56%) | 713 (53.17%) |
| Simple heuristics | 407 (45.12%) | 542 (46.44%) | 628 (46.83%) |
| Total | 902 (100.00%) | 1167 (100.00%) | 1341 (100.00%) |

## Skipped Pairs

None.
