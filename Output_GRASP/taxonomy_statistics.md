# Taxonomy Merge Statistics

This file summarizes the merged taxonomy-labeled QA CSV outputs.

Simple heuristics rows from `all_valid_cases_with_taxonomy.csv` exclude `different_unclassified`.

The taxonomy label `same` is normalized to `Same`.

Each count is shown as:

```text
count (percentage within model)
```

## Total Rows by Model

| Metric | Qwen3-4B-Instruct | Qwen3-235B-Thinking |
| --- | --- | --- |
| Total | 1165 | 1453 |

## Taxonomy Distribution by Model

| taxonomy_label | Qwen3-4B-Instruct | Qwen3-235B-Thinking |
| --- | --- | --- |
| Different answer | 648 (55.62%) | 607 (41.78%) |
| Higher accuracy in KG than in Table | 104 (8.93%) | 144 (9.91%) |
| Higher accuracy in Table than in KG | 80 (6.87%) | 130 (8.95%) |
| Same | 320 (27.47%) | 538 (37.03%) |
| Temporal changes | 13 (1.12%) | 34 (2.34%) |

## Method Distribution by Model

| method | Qwen3-4B-Instruct | Qwen3-235B-Thinking |
| --- | --- | --- |
| LLM-as-a-judge | 804 (69.01%) | 931 (64.07%) |
| Simple heuristics | 361 (30.99%) | 522 (35.93%) |

## Skipped Pairs

| Pair | Model | Reason | Missing Files |
| --- | --- | --- | --- |
| 30B | Qwen3-30B-Thinking | missing file(s) | /home/user/Documents/EURECOM/PhD2/SPARQL-TableQA/LLM-as-Judge/30B_judged.csv |
