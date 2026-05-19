# Patch summary

Mode: APPLY

## Root totals

| Metric | Before | After |
|---|---:|---:|
| Valid | 1278 | 2576 |
| Invalid | 1592 | 294 |
| Total | 2870 | 2870 |
| empty_sparql_result moved to valid-empty | 0 | 1298 |

## Dataset changes

| Group | Dataset | Total | Original valid | Original invalid | Moved empty | New valid | New invalid |
|---|---|---:|---:|---:|---:|---:|---:|
| ComplexQA | CompMix_infobox_complex | 300 | 223 | 77 | 66 | 289 | 11 |
| ComplexQA | CompMix_table_complex | 300 | 138 | 162 | 140 | 278 | 22 |
| ComplexQA | Monaco_non_time_complex | 150 | 38 | 112 | 85 | 123 | 27 |
| ComplexQA | Monaco_time_complex | 150 | 36 | 114 | 81 | 117 | 33 |
| ComplexQA | OTT_QA_dev_complex | 400 | 83 | 317 | 254 | 337 | 63 |
| ComplexQA | Sportsreason_TANQ_complex | 200 | 60 | 140 | 94 | 154 | 46 |
| SimpleQA | CompMix_table_simple_qa | 326 | 168 | 158 | 126 | 294 | 32 |
| SimpleQA | NQ_table_test_simple | 966 | 499 | 467 | 416 | 915 | 51 |
| SimpleQA | Qampari_wikitables_simple | 78 | 33 | 45 | 36 | 69 | 9 |

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
& 294 (90.18\%) & 32 (9.82\%) \\
% SimpleQA / NQ_table_test_simple
& 915 (94.72\%) & 51 (5.28\%) \\
% SimpleQA / Qampari_wikitables_simple
& 69 (88.46\%) & 9 (11.54\%) \\
% SimpleQA Total
& 1278 (93.28\%) & 92 (6.72\%) \\
% ComplexQA / CompMix_infobox_complex
& 289 (96.33\%) & 11 (3.67\%) \\
% ComplexQA / CompMix_table_complex
& 278 (92.67\%) & 22 (7.33\%) \\
% ComplexQA / Monaco_non_time_complex
& 123 (82.00\%) & 27 (18.00\%) \\
% ComplexQA / Monaco_time_complex
& 117 (78.00\%) & 33 (22.00\%) \\
% ComplexQA / OTT_QA_dev_complex
& 337 (84.25\%) & 63 (15.75\%) \\
% ComplexQA / Sportsreason_TANQ_complex
& 154 (77.00\%) & 46 (23.00\%) \\
% ComplexQA Total
& 1298 (86.53\%) & 202 (13.47\%) \\
% Overall Total
& 2576 (89.76\%) & 294 (10.24\%) \\
```
