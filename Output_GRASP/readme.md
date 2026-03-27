# SPARQL TableQA Experiment - Complex & Simple QA Datasets

## Overview
Experiment evaluating GRASP SPARQL generation for table-based question answering across **9 split of 6 datasets** divided into **SimpleQA** (3 datasets) and **ComplexQA** (6 datasets). Each dataset contains JSON files with questions, gold answers, generated SPARQL queries, and execution results.

**Total JSON files processed**: 2,926  
**Total valid cases**: 1,165 (660 SimpleQA + 505 ComplexQA)

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
For detailed structure see tree.txt.

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

## Output File Formats

### Main CSV: `<dataset>.csv` **[question, gold_answer, result_cleaned, result, sparql]**
- **ALL** JSON files (valid + invalid)
- `result_cleaned`: 1st column values from result table (QIDs removed, pipe-separated)

### Valid Cases: `<dataset>_valid_cases.csv` **[question, gold_answer, result_cleaned, result, sparql, file_path]**
- **Only successful SPARQL executions** with non-empty results
- `file_path`: `dataset_00001.json`

### Invalid Cases: `<dataset>_invalid_cases.csv` **[file_name, invalid_label]**
Invalid types:
- `null_output`, `no_sparql_generated`, `empty_sparql_result`
- `sparql_execution_failed`, `sparql_parsing_failed`, `invalid_json`

### Summary: `<dataset>_invalid_summary.md`
Markdown with valid/invalid percentages wiht pie chart

## Processing Pipeline (JSON2csv.py)
1. **Input**: JSON files with `{question, reference_answer, output: {sparql, result}}`
2. **Extract**: SPARQL (post-SELECT), markdown table from result
3. **Clean**: `result_cleaned` = 1st column values (skip header, remove `wd:Q123`, join by `|`)
4. **Classify**: Valid if SPARQL executes + table exists
5. **Output**: 4 files per dataset + combined `all_valid_cases.csv`

