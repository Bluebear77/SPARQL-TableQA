# Modality_inconsistency_labelled

This directory contains the final labeled modality-level inconsistency files used for KONTRAST analysis.

## Purpose

This is the final analysis layer of the repository. It consolidates valid cases from the Text-to-SPARQL stage with heuristic and LLM-based taxonomy labels.

Use this directory to inspect the final cross-modal inconsistency annotations.

## What the files represent

The labeled files summarize how table-grounded answers compare with KG answers generated from Wikidata. Each row corresponds to a value-bearing comparison case and includes a taxonomy label such as:

- `Same`
- `Higher accuracy in KG than in Table`
- `Higher accuracy in Table than in KG`
- `Different answer`
- `Temporal changes`


## How this directory connects to the experiment

This directory is produced after:

1. input questions are selected in `Input_GRASP/`;
2. SPARQL and KG answers are generated in `Output_GRASP/`;
3. consistency labels are assigned in `LLM_as_a_Judge/`.

The files here are intended for final reporting, error analysis, and benchmark comparison.

## Recommended use

Use this directory when you want to answer questions such as:

- How often do table answers and KG answers agree?
- Which inconsistency types are most common?
- Which model setting surfaces more usable cross-modal comparisons?
- Which cases are candidates for human review by Wikipedia or Wikidata editors?