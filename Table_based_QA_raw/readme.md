# Table_based_QA_raw

This directory contains the raw and intermediate Table-QA resources used to construct the KONTRAST experiment inputs.

## Purpose

KONTRAST studies cross-modal inconsistencies between table-grounded answers and knowledge graph answers. This directory stores the source Table-QA material and scripts used to select questions that can be passed to the Text-to-SPARQL stage.

The data here is not the final model input. It is the preparation layer that turns heterogeneous Table-QA sources into controlled SimpleQA and ComplexQA subsets.

## Contents

This directory includes dataset-specific files and scripts for sources such as:

- CompMix
- Monaco
- NQ Table
- OTT-QA
- Qampari
- Sportsreason / TANQ-style sports questions

It also includes utilities for:

- extracting table-based QA examples;
- converting source formats into CSV-style experiment files;
- separating simple and complex questions;
- filtering answer sources;
- splitting by temporal and non-temporal settings;
- ranking or selecting candidate examples for downstream Text-to-SPARQL generation.

## Output of this stage

The selected and normalized questions from this stage are written into:

```text
Input_GRASP/
```

Those files are the actual inputs consumed by GRASP / Text-to-SPARQL models.

## Notes

Files in this directory may include raw, intermediate, and dataset-specific formats. For the clean experiment inputs, use `Input_GRASP/`. For generated SPARQL and KG answers, use `Output_GRASP/`.

## Dataset Source:

- [NQ-Table](https://github.com/google-research/tapas): created by human, natural simple question, single short answer.

- [Qampari](https://samsam3232.github.io/qampari/): created by template, where answers are **lists of entities**, spread across many paragraphs supported by text evidence.

- [Compmix](https://qa.mpi-inf.mpg.de/compmix/): created by human, natural question range from simple to complex, single short answer. Also found in [CompMix](https://huggingface.co/datasets/pchristm/CompMix/tree/main): train_set.zip, dev_set.zip,test_set.zip.

- [Monaco](https://huggingface.co/datasets/allenai/MoNaCo_Benchmark/tree/main): created by human, natural complex time-consuming questions that requires implict reasoning.

- [OTT-QA](https://github.com/wenhuchen/OTT-QA):created by template, complex question designed in a way to test model's resoning ability, single short answer.

- [Sportsreason](https://aclanthology.org/2025.emnlp-main.34.pdf): created by LLM RAG, complex question requires numerical operation, including [Multi-text, Multi-table, Single-table, Single-table + Multi-text, and Multi-table + Multi-text.] setting. We only considered table based questions; single short answer.





