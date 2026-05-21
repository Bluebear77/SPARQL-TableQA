# KONTRAST: Cross-Modal Knowledge Inconsistency Detection

This repository contains the experimental record for **KONTRAST**, a framework for detecting and categorizing knowledge inconsistencies across **tables**, **text**, and **knowledge graphs**.

Wikipedia and Wikidata are central open knowledge resources for search, question answering, LLM training, and retrieval-augmented generation. Their knowledge is connected, but distributed across different modalities. KONTRAST studies when these modalities agree, when they disagree, and how such disagreements can become actionable signals for improving knowledge consistency.

## What this repository contains

The repository supports the paper’s task of **modality-level inconsistency detection**: identifying and categorizing mismatches between table-grounded answers and knowledge graph answers surfaced through Text-to-SPARQL generation.

The workflow is:

```text
Raw Table-QA datasets
        ↓
Dataset filtering and split construction
        ↓
Text-to-SPARQL input
        ↓
Generated SPARQL and KG answers
        ↓
Simple heuristics + LLM-as-a-judge consistency labeling
        ↓
Modality-level inconsistency taxonomy and statistics
```

<img width="5748" height="2463" alt="triangulate_workflow_ultra" src="https://github.com/user-attachments/assets/e4354071-0aa8-488d-8063-57e3796c3d54" />


## Directory map

| Directory | Role in the workflow |
|---|---|
| [`Table_based_QA_raw/`](Table_based_QA_raw/) | Raw and intermediate Table-QA data, plus scripts for extraction, filtering, conversion, and split construction. |
| [`Input_GRASP/`](Input_GRASP/) | Final selected SimpleQA and ComplexQA inputs used for Text-to-SPARQL generation. |
| [`Output_GRASP/`](Output_GRASP/) | GRASP outputs: generated SPARQL, KG execution results, reasoning traces, valid/invalid cases, model-level statistics and simple heuristics categorization result . |
| [`LLM_as_a_Judge/`](LLM_as_a_Judge/) | LLM judging pipeline for comparing table answers with KG answers and assigning inconsistency labels. |
| [`Modality_inconsistency_labelled/`](Modality_inconsistency_labelled/) | Final merged labeled files and taxonomy-level statistics used for analysis. |

## Task

Given a table-grounded question-answer pair and a KG answer obtained through generated SPARQL, KONTRAST asks whether the modalities are consistent and, if not, label what type of inconsistency they reveal.

The taxonomy used in this repository includes:

| Label | Meaning |
|---|---|
| `Same` | The table answer and KG answer are semantically aligned. |
| `Higher accuracy in KG than in Table` | The KG appears more complete or more accurate than the table answer. |
| `Higher accuracy in Table than in KG` | The table appears more complete or more accurate than the KG answer. |
| `Different answer` | The modalities disagree, but the cause is not directly attributable to one source being better. |
| `Temporal changes` | The modalities reflect different time states. |

## Data and models

The experiments are built from real-world Table-QA datasets grounded in Wikipedia and Wikidata. The repository includes SimpleQA and ComplexQA inputs and outputs for multiple Qwen3 model variants used in Text-to-SPARQL generation and analysis.



## How to read the repository

Start with the root workflow above, then follow the directories in order:

1. [`Table_based_QA_raw/`](Table_based_QA_raw/) explains where the raw QA data and preprocessing scripts live.
2. [`Input_GRASP/`](Input_GRASP/) contains the finalized input CSVs.
3. [`Output_GRASP/`](Output_GRASP/) contains generated SPARQL and KG-answer outputs.
4. [`LLM_as_a_Judge/`](LLM_as_a_Judge/) explains how table answers and KG answers are compared.
5. [`Modality_inconsistency_labelled/`](Modality_inconsistency_labelled/) contains the final taxonomy labels and statistics.



