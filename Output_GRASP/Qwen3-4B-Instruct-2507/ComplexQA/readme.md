
## Output File Formats
Inside each foldre, there are:

### all_valid_cases.csv: 
- **ALL** valid cases in the ComplexQA folder.

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
