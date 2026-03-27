# SPARQL TableQA Experiment - ComplexQA & SimpleQA Datasets

## Overview
Experiment evaluating GRASP SPARQL generation for table-based question answering across **9 split of 6 datasets** divided into **SimpleQA** (3 datasets) and **ComplexQA** (6 datasets). 
Each dataset contains JSON files with questions, gold answers, generated SPARQL queries, and execution results.

- **Total JSON files processed**: 2870 (1370 SimpleQA + 1500 ComplexQA)
- **Total valid cases**: 1,165 (660 SimpleQA + 505 ComplexQA)


**Model used for GRASP** 

```
vllm serve Qwen/Qwen3-4B-Instruct-2507 --tool-call-parser hermes --enable-auto-tool-choice --max-model-len 225136
```

Approximately 63 hours for 2870 questions, **average 1.3 min/question.**

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
- [Sportsreason](https://github.com/kaiyuef/SportReason): created by LLM RAG, complex question requires numerical operation, including [Multi-text, Multi-table, Single-table, Single-table + Multi-text, and Multi-table + Multi-text.] setting. We only considered table based questions; single short answer.


## Datasets Summary

### SimpleQA (660 valid / 1,370 total = 48.1%)
| Dataset | Files | Valid | Success Rate |
|---------|-------|-------|--------------|
| CompMix_table_simple_qa | 326 | 198 | 60.7% |
| NQ_table_test_simple | 966 | 437 | 45.2% |
| Qampari_wikitables_simple | 78 | 25 | 32.1% |

### ComplexQA (505 valid / 1,500 total = 33.7%)
| Dataset | Files | Valid | Success Rate |
|---------|-------|-------|--------------|
| CompMix_infobox_complex | 300 | 210 | 70.0% |
| CompMix_table_complex | 300 | 120 | 40.0% |
| Monaco_non_time_complex | 150 | 50 | 33.3% |
| Monaco_time_complex | 150 | 47 | 31.3% |
| OTT_QA_dev_complex | 400 | 53 | 13.3% |
| Sportsreason_TANQ_complex | 200 | 25 | 12.5% |

## File Structure
For detailed structure see [tree.txt](https://github.com/Bluebear77/SPARQL-TableQA/blob/main/Output_GRASP/tree.txt).

```
ComplexQA/
├── all_valid_cases.csv # 505 valid rows combined
├── CompMix_infobox_complex/
│   ├── *.json # Raw input files (300)
│   └── extracted_output/
│       ├── CompMix_infobox_complex.csv # ALL 300 rows
│       ├── CompMix_infobox_complex_valid_cases.csv # 210 valid rows
│       ├── CompMix_infobox_complex_invalid_cases.csv # 90 invalid rows
│       ├── CompMix_infobox_complex_invalid_summary.md
│       └── CompMix_infobox_complex_valid_vs_invalid_pie.png
├── CompMix_table_complex/
│   ├── *.json # Raw input files (300)
│   └── extracted_output/ # Same structure as above
├── Monaco_non_time_complex/ # 150 files, 50 valid
├── Monaco_time_complex/ # 150 files, 47 valid
├── OTT_QA_dev_complex/ # 400 files, 53 valid
├── Sportsreason_TANQ_complex/ # 200 files, 25 valid
└── JSON2csv.py

SimpleQA/
├── all_valid_cases.csv # 660 valid rows combined
├── CompMix_table_simple_qa/
│   ├── *.json # Raw input files (326)
│   └── extracted_output/
│       ├── CompMix_table_simple_qa.csv # ALL 326 rows
│       ├── CompMix_table_simple_qa_valid_cases.csv # 198 valid rows
│       ├── CompMix_table_simple_qa_invalid_cases.csv # 128 invalid rows
│       ├── CompMix_table_simple_qa_invalid_summary.md
│       └── CompMix_table_simple_qa_valid_vs_invalid_pie.png
├── NQ_table_test_simple/ # 966 files, 437 valid
│   └── extracted_output/ # Same structure as above
├── Qampari_wikitables_simple/ # 78 files, 25 valid
│   └── extracted_output/ # Same structure as above
└── JSON2csv.py
```


