# Modality_inconsistency_labelled

This directory contains the final labeled modality-level inconsistency files used for KONTRAST analysis.

It is the final analysis layer of the repository. It consolidates valid cases from the Text-to-SPARQL / KG-answer generation stage with heuristic and LLM-based taxonomy labels, then applies additional cleaning before producing the final CSV files.

## Purpose

Use this directory to inspect the final cross-modal inconsistency annotations between table-grounded answers and KG answers generated from Wikidata.

The final merged CSV files are used for:

- reporting taxonomy distributions;
- comparing model settings;
- analyzing modality-level disagreement patterns;
- identifying cases that may need human review;
- tracking removed rows caused by duplicate questions or overly long KG answers.

## Main files

| File / directory | Description |
|---|---|
| `merged_taxonomy_answers_4B.csv` | Final cleaned taxonomy-labeled output for `Qwen3-4B-Instruct`. |
| `merged_taxonomy_answers_30B.csv` | Final cleaned taxonomy-labeled output for `Qwen3-30B-Thinking`. |
| `merged_taxonomy_answers_235B.csv` | Final cleaned taxonomy-labeled output for `Qwen3-235B-Thinking`. |
| `taxonomy_statistics.md` | Summary statistics for the final merged files, including taxonomy distribution, method distribution, and row-removal counts. |
| `removed_files/` | Stores rows removed during cleaning, with one CSV per model setting. |
| `count.py` | Utility script for counting or inspecting the labeled outputs. |
| `readme.md` | This documentation file. |

## Final merged CSV files

Each final merged CSV contains rows in the following schema:

| Column | Description |
|---|---|
| `question` | Input natural-language question. |
| `gold_answer` | Gold/reference answer from the table-based QA data. |
| `KG answer` | Answer generated from the KG/Wikidata pipeline. |
| `taxonomy_label` | Label describing the relationship between the table answer and KG answer. |
| `method` | Labeling method, either heuristic-based or LLM-as-a-judge. |
| `source` | Dataset/source category inferred from the original file path. |

## Taxonomy labels

Each row receives a taxonomy label such as:

- `Same`
- `Higher accuracy in KG than in Table`
- `Higher accuracy in Table than in KG`
- `Different answer`
- `Temporal changes`

These labels describe how the table-grounded answer compares with the KG answer.

## Cleaning rules

Before the final merged files are written, two cleaning steps are applied.

### 1. Duplicate-question removal

Within each final output CSV, duplicate rows with the same `question` are removed.

Only the first occurrence of each question is kept, so every final output file contains unique questions.

Removed duplicate rows are saved in the corresponding CSV under:

```text
removed_files/