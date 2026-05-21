# Taxonomy Merge Statistics

This file summarizes the merged taxonomy-labeled QA CSV outputs.

Each count is shown as:

```text
count (percentage within model)
```

## Total Rows by Model

| Metric | Qwen3-4B-Instruct | Qwen3-30B-Thinking | Qwen3-235B-Thinking |
| --- | --- | --- | --- |
| Total | 1165 | 1278 | 1453 |

## Taxonomy Distribution by Model

| taxonomy_label | Qwen3-4B-Instruct | Qwen3-30B-Thinking | Qwen3-235B-Thinking |
| --- | --- | --- | --- |
| Different answer | 638 (54.76%) | 546 (42.72%) | 600 (41.29%) |
| Higher accuracy in KG than in Table | 139 (11.93%) | 147 (11.50%) | 164 (11.29%) |
| Higher accuracy in Table than in KG | 87 (7.47%) | 125 (9.78%) | 139 (9.57%) |
| Same | 288 (24.72%) | 427 (33.41%) | 522 (35.93%) |
| Temporal changes | 13 (1.12%) | 33 (2.58%) | 28 (1.93%) |
| Total | 1165 (100.00%) | 1278 (100.00%) | 1453 (100.00%) |

## Method Distribution by Model

| method | Qwen3-4B-Instruct | Qwen3-30B-Thinking | Qwen3-235B-Thinking |
| --- | --- | --- | --- |
| LLM-as-a-judge | 743 (63.78%) | 720 (56.34%) | 810 (55.75%) |
| Simple heuristics | 422 (36.22%) | 558 (43.66%) | 643 (44.25%) |
| Total | 1165 (100.00%) | 1278 (100.00%) | 1453 (100.00%) |

## Skipped Pairs

None.
