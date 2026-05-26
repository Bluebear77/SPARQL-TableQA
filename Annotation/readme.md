# Annotation

This directory contains the selected balanced annotation sets used to manually inspect high-confidence modality-level consistency cases in KONTRAST.

## Purpose

After Simple-heuristics and LLM-as-a-judge labels are generated, KONTRAST selects a compact annotation set for validation. Each row compares:

```text
(question, table answer, KG answer)
```

and keeps the most confident classification cases after filtering duplicates and overlong KG outputs.

## Output Schema

Each annotation CSV uses the following columns:

| Column | Meaning |
|---|---|
| `question` | Original QA question. |
| `gold_answer` | Table answer used as the reference answer. |
| `KG answer` | Answer retrieved from the KG. |
| `taxonomy_label` | Cross-modal consistency label. |
| `confidence` | `similarity_score` for Simple-heuristics rows, or `difference_severity` for LLM-as-a-judge rows. |
| `source` | Complete dataset-relative JSON path. |

## Selection Rules

For each model, the script selects up to 310 cases while balancing:

- Simple-heuristics and LLM-as-a-judge methods;
- SimpleQA and ComplexQA sources.

Rows are sorted by confidence: higher `similarity_score` first for Simple-heuristics, and `major`, `moderate`, `minor`, `none` for LLM-as-a-judge.

## Contents

This directory includes:

- final annotation CSV files for different model outputs;
- removed-row audit files under `removed_files/`;
- `annotation_statistics.md` summarizing selection counts and balance.