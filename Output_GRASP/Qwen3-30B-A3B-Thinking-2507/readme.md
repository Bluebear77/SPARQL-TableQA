# Output_GRASP Pipeline Guide

This guide explains how to run `output_grasp_pipeline.py` and understand its outputs.

## Purpose

Raw GRASP results are stored as one JSON file per question, which is hard to analyze at scale. This pipeline converts those JSON files into structured CSV files and summary reports.

In one run, it:

1. reads all JSON files
2. separates valid and invalid cases
3. merges valid cases into analysis tables
4. assigns taxonomy labels to valid cases
5. aggregates summary statistics
6. exports `different_unclassified` cases

It replaces the older multi-script workflow:

- `JSON2csv.py`
- `extract_invalid.py`
- `tag.py`
- `count.py`
- `extract_unclassifed.py`

## Valid and Invalid Cases

A case is marked invalid if any of the following occurs:

- `output` is null
- no SPARQL query was generated
- SPARQL execution failed
- preprocessing or parsing failed
- the SPARQL query returned no usable table result
- the JSON file is invalid

Invalid labels include:

- `null_output`
- `no_sparql_generated`
- `empty_sparql_result`
- `sparql_execution_failed (execution)`
- `sparql_execution_failed (preprocessing)`
- `invalid_json`

All other cases are treated as valid.

## Output Files

### Per-dataset outputs

For each dataset folder, the pipeline creates:

```text
<dataset>/extracted_output/