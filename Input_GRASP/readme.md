# Input_GRASP

This directory contains  **9 split of 6 datasets** divided into **SimpleQA** (3 datasets) and **ComplexQA** (6 datasets), the finalized Table-QA inputs used by KONTRAST for Text-to-SPARQL generation.


## Purpose

Each file contains selected table-grounded questions and reference table answers. These are passed to GRASP, the Text-to-SPARQL model, which attempt to generate SPARQL queries over Wikidata and retrieve corresponding KG answers.


The comparison between the original table answer and the generated KG answer is the starting point for modality-level inconsistency detection.

## Structure

The inputs are organized into two groups:

```text
Input_GRASP/
├── SimpleQA/
└── ComplexQA/
```

## SimpleQA

`SimpleQA/` consists of  natural or lightly structured questions that are asked in a straightforward way.

## ComplexQA

`ComplexQA/` contains questions that require richer evidence integration or more complex reasoning.

## Dataset Selection

The selected dataset are stored in [Input_GRSP](https://github.com/Bluebear77/SPARQL-TableQA/tree/main/Input_GRASP) folder.

- [SimpleQA](https://github.com/Bluebear77/SPARQL-TableQA/tree/main/Output_GRASP/SimpleQA): focus on simple question answering with single hop structure asked in a strightforward way.

- [ComplexQA](https://github.com/Bluebear77/SPARQL-TableQA/tree/main/Output_GRASP/ComplexQA): focus on complex question answering with complex structure, such as multi-hop, numerical operation,implicit reasoning,etc.

## Dataset Source:

- [NQ-Table](https://github.com/google-research/tapas): created by human, natural simple question, single short answer.

- [Qampari](https://samsam3232.github.io/qampari/): created by template, where answers are **lists of entities**, spread across many paragraphs supported by text evidence.

- [Compmix](https://qa.mpi-inf.mpg.de/compmix/): created by human, natural question range from simple to complex, single short answer.

- [Monaco](https://huggingface.co/datasets/allenai/MoNaCo_Benchmark/tree/main): created by human, natural complex time-consuming questions that requires implict reasoning.

- [OTT-QA](https://github.com/wenhuchen/OTT-QA):created by template, complex question designed in a way to test model's resoning ability, single short answer.

- [Sportsreason](https://aclanthology.org/2025.emnlp-main.34.pdf): created by LLM RAG, complex question requires numerical operation, including [Multi-text, Multi-table, Single-table, Single-table + Multi-text, and Multi-table + Multi-text.] setting. We only considered table based questions; single short answer.
