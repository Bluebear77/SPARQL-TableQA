# Global SPARQL QA Statistics

## Overall valid vs invalid

| Metric | Count | Percentage |
|---|---:|---:|
| Valid | 2576 | 89.76% |
| Invalid | 294 | 10.24% |
| Valid empty SPARQL results moved from invalid | 1298 | 45.23% |

## Error distribution after patch

| Error type | Count | % of invalid |
|---|---:|---:|
| null_output | 183 | 62.24% |
| no_sparql_generated | 35 | 11.90% |
| sparql_execution_failed (execution) | 22 | 7.48% |
| sparql_execution_failed (preprocessing) | 54 | 18.37% |
| invalid_json | 0 | 0.00% |

## Per-folder summary

| Folder | Total | Valid | Valid % | Invalid | Invalid % | Moved empty |
|---|---:|---:|---:|---:|---:|---:|
| CompMix_infobox_complex | 300 | 289 | 96.33% | 11 | 3.67% | 66 |
| CompMix_table_complex | 300 | 278 | 92.67% | 22 | 7.33% | 140 |
| CompMix_table_simple_qa | 326 | 294 | 90.18% | 32 | 9.82% | 126 |
| Monaco_non_time_complex | 150 | 123 | 82.00% | 27 | 18.00% | 85 |
| Monaco_time_complex | 150 | 117 | 78.00% | 33 | 22.00% | 81 |
| NQ_table_test_simple | 966 | 915 | 94.72% | 51 | 5.28% | 416 |
| OTT_QA_dev_complex | 400 | 337 | 84.25% | 63 | 15.75% | 254 |
| Qampari_wikitables_simple | 78 | 69 | 88.46% | 9 | 11.54% | 36 |
| Sportsreason_TANQ_complex | 200 | 154 | 77.00% | 46 | 23.00% | 94 |
| **Total** | 2870 | 2576 | 89.76% | 294 | 10.24% | 1298 |
