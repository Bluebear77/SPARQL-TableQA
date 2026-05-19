# Patch summary

Mode: APPLY

## Root totals

| Metric | Before | After |
|---|---:|---:|
| Valid | 1165 | 2041 |
| Invalid | 1705 | 829 |
| Total | 2870 | 2870 |
| empty_sparql_result moved to valid-empty | 0 | 876 |

## Dataset changes

| Group | Dataset | Total | Original valid | Original invalid | Moved empty | New valid | New invalid |
|---|---|---:|---:|---:|---:|---:|---:|
| ComplexQA | CompMix_infobox_complex | 300 | 210 | 90 | 64 | 274 | 26 |
| ComplexQA | CompMix_table_complex | 300 | 120 | 180 | 134 | 254 | 46 |
| ComplexQA | Monaco_non_time_complex | 150 | 50 | 100 | 56 | 106 | 44 |
| ComplexQA | Monaco_time_complex | 150 | 47 | 103 | 58 | 105 | 45 |
| ComplexQA | OTT_QA_dev_complex | 400 | 53 | 347 | 89 | 142 | 258 |
| ComplexQA | Sportsreason_TANQ_complex | 200 | 25 | 175 | 36 | 61 | 139 |
| ComplexQA | statistics | 0 | 0 | 0 | 0 | 0 | 0 |
| SimpleQA | CompMix_table_simple_qa | 326 | 198 | 128 | 90 | 288 | 38 |
| SimpleQA | NQ_table_test_simple | 966 | 437 | 529 | 332 | 769 | 197 |
| SimpleQA | Qampari_wikitables_simple | 78 | 25 | 53 | 17 | 42 | 36 |
| SimpleQA | statistics | 0 | 0 | 0 | 0 | 0 | 0 |

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
- `ComplexQA/statistics/extracted_output/statistics_invalid_summary.md`
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
- `SimpleQA/statistics/extracted_output/statistics_invalid_summary.md`
- `SimpleQA/summary.md`
- `all_invalid_cases.csv`
- `all_valid_empty.csv`
- `statistics/error_distribution_total.csv`
- `statistics/per_folder_breakdown.csv`
- `statistics/summary.md`

## Updated 235B values for LaTeX table

```latex
% SimpleQA / CompMix_table_simple_qa
& 288 (88.34\%) & 38 (11.66\%) \\
% SimpleQA / NQ_table_test_simple
& 769 (79.61\%) & 197 (20.39\%) \\
% SimpleQA / Qampari_wikitables_simple
& 42 (53.85\%) & 36 (46.15\%) \\
% SimpleQA / statistics
& 0 (0.00\%) & 0 (0.00\%) \\
% SimpleQA Total
& 1099 (80.22\%) & 271 (19.78\%) \\
% ComplexQA / CompMix_infobox_complex
& 274 (91.33\%) & 26 (8.67\%) \\
% ComplexQA / CompMix_table_complex
& 254 (84.67\%) & 46 (15.33\%) \\
% ComplexQA / Monaco_non_time_complex
& 106 (70.67\%) & 44 (29.33\%) \\
% ComplexQA / Monaco_time_complex
& 105 (70.00\%) & 45 (30.00\%) \\
% ComplexQA / OTT_QA_dev_complex
& 142 (35.50\%) & 258 (64.50\%) \\
% ComplexQA / Sportsreason_TANQ_complex
& 61 (30.50\%) & 139 (69.50\%) \\
% ComplexQA / statistics
& 0 (0.00\%) & 0 (0.00\%) \\
% ComplexQA Total
& 942 (62.80\%) & 558 (37.20\%) \\
% Overall Total
& 2041 (71.11\%) & 829 (28.89\%) \\
```
