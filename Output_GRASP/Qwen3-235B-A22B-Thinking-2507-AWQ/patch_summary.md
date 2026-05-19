# Patch summary

Mode: APPLY

## Root totals

| Metric | Before | After |
|---|---:|---:|
| Valid | 1453 | 2281 |
| Invalid | 1417 | 589 |
| Total | 2870 | 2870 |
| empty_sparql_result moved to valid-empty | 0 | 828 |

## Dataset changes

| Group | Dataset | Total | Original valid | Original invalid | Moved empty | New valid | New invalid |
|---|---|---:|---:|---:|---:|---:|---:|
| ComplexQA | CompMix_infobox_complex | 300 | 171 | 129 | 32 | 203 | 97 |
| ComplexQA | CompMix_table_complex | 300 | 178 | 122 | 89 | 267 | 33 |
| ComplexQA | Monaco_non_time_complex | 150 | 29 | 121 | 22 | 51 | 99 |
| ComplexQA | Monaco_time_complex | 150 | 53 | 97 | 48 | 101 | 49 |
| ComplexQA | OTT_QA_dev_complex | 400 | 92 | 308 | 174 | 266 | 134 |
| ComplexQA | Sportsreason_TANQ_complex | 200 | 80 | 120 | 67 | 147 | 53 |
| SimpleQA | CompMix_table_simple_qa | 326 | 200 | 126 | 90 | 290 | 36 |
| SimpleQA | NQ_table_test_simple | 966 | 596 | 370 | 285 | 881 | 85 |
| SimpleQA | Qampari_wikitables_simple | 78 | 54 | 24 | 21 | 75 | 3 |

## Files overwritten/deleted

- `ComplexQA/CompMix_infobox_complex/extracted_output/CompMix_infobox_complex_invalid_cases.csv`
- `ComplexQA/CompMix_infobox_complex/extracted_output/CompMix_infobox_complex_invalid_summary.md`
- `ComplexQA/CompMix_infobox_complex/extracted_output/CompMix_infobox_complex_valid_empty.csv`
- `ComplexQA/CompMix_table_complex/extracted_output/CompMix_table_complex_invalid_cases.csv`
- `ComplexQA/CompMix_table_complex/extracted_output/CompMix_table_complex_invalid_summary.md`
- `ComplexQA/CompMix_table_complex/extracted_output/CompMix_table_complex_valid_empty.csv`
- `ComplexQA/Monaco_non_time_complex/extracted_output/Monaco_non_time_complex_invalid_cases.csv`
- `ComplexQA/Monaco_non_time_complex/extracted_output/Monaco_non_time_complex_invalid_summary.md`
- `ComplexQA/Monaco_non_time_complex/extracted_output/Monaco_non_time_complex_valid_empty.csv`
- `ComplexQA/Monaco_time_complex/extracted_output/Monaco_time_complex_invalid_cases.csv`
- `ComplexQA/Monaco_time_complex/extracted_output/Monaco_time_complex_invalid_summary.md`
- `ComplexQA/Monaco_time_complex/extracted_output/Monaco_time_complex_valid_empty.csv`
- `ComplexQA/OTT_QA_dev_complex/extracted_output/OTT_QA_dev_complex_invalid_cases.csv`
- `ComplexQA/OTT_QA_dev_complex/extracted_output/OTT_QA_dev_complex_invalid_summary.md`
- `ComplexQA/OTT_QA_dev_complex/extracted_output/OTT_QA_dev_complex_valid_empty.csv`
- `ComplexQA/Sportsreason_TANQ_complex/extracted_output/Sportsreason_TANQ_complex_invalid_cases.csv`
- `ComplexQA/Sportsreason_TANQ_complex/extracted_output/Sportsreason_TANQ_complex_invalid_summary.md`
- `ComplexQA/Sportsreason_TANQ_complex/extracted_output/Sportsreason_TANQ_complex_valid_empty.csv`
- `ComplexQA/all_invalid_cases.csv`
- `ComplexQA/all_valid_empty.csv`
- `ComplexQA/summary.md`
- `SimpleQA/CompMix_table_simple_qa/extracted_output/CompMix_table_simple_qa_invalid_cases.csv`
- `SimpleQA/CompMix_table_simple_qa/extracted_output/CompMix_table_simple_qa_invalid_summary.md`
- `SimpleQA/CompMix_table_simple_qa/extracted_output/CompMix_table_simple_qa_valid_empty.csv`
- `SimpleQA/NQ_table_test_simple/extracted_output/NQ_table_test_simple_invalid_cases.csv`
- `SimpleQA/NQ_table_test_simple/extracted_output/NQ_table_test_simple_invalid_summary.md`
- `SimpleQA/NQ_table_test_simple/extracted_output/NQ_table_test_simple_valid_empty.csv`
- `SimpleQA/Qampari_wikitables_simple/extracted_output/Qampari_wikitables_simple_invalid_cases.csv`
- `SimpleQA/Qampari_wikitables_simple/extracted_output/Qampari_wikitables_simple_invalid_summary.md`
- `SimpleQA/Qampari_wikitables_simple/extracted_output/Qampari_wikitables_simple_valid_empty.csv`
- `SimpleQA/all_invalid_cases.csv`
- `SimpleQA/all_valid_empty.csv`
- `SimpleQA/summary.md`
- `all_invalid_cases.csv`
- `all_valid_empty.csv`
- `statistics/error_distribution_total.csv`
- `statistics/per_folder_breakdown.csv`
- `statistics/summary.md`

## Updated 235B values for LaTeX table

```latex
% SimpleQA / CompMix_table_simple_qa
& 290 (88.96\%) & 36 (11.04\%) \\
% SimpleQA / NQ_table_test_simple
& 881 (91.20\%) & 85 (8.80\%) \\
% SimpleQA / Qampari_wikitables_simple
& 75 (96.15\%) & 3 (3.85\%) \\
% SimpleQA Total
& 1246 (90.95\%) & 124 (9.05\%) \\
% ComplexQA / CompMix_infobox_complex
& 203 (67.67\%) & 97 (32.33\%) \\
% ComplexQA / CompMix_table_complex
& 267 (89.00\%) & 33 (11.00\%) \\
% ComplexQA / Monaco_non_time_complex
& 51 (34.00\%) & 99 (66.00\%) \\
% ComplexQA / Monaco_time_complex
& 101 (67.33\%) & 49 (32.67\%) \\
% ComplexQA / OTT_QA_dev_complex
& 266 (66.50\%) & 134 (33.50\%) \\
% ComplexQA / Sportsreason_TANQ_complex
& 147 (73.50\%) & 53 (26.50\%) \\
% ComplexQA Total
& 1035 (69.00\%) & 465 (31.00\%) \\
% Overall Total
& 2281 (79.48\%) & 589 (20.52\%) \\
```
