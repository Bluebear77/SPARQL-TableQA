# Global SPARQL QA Statistics

## Overall valid vs invalid

| Metric | Count | Percentage |
|---|---:|---:|
| Valid | 2281 | 79.48% |
| Invalid | 589 | 20.52% |
| Valid empty SPARQL results moved from invalid | 828 | 28.85% |

## Error distribution after patch

| Error type | Count | % of invalid |
|---|---:|---:|
| null_output | 228 | 38.71% |
| no_sparql_generated | 42 | 7.13% |
| sparql_execution_failed (execution) | 285 | 48.39% |
| sparql_execution_failed (preprocessing) | 34 | 5.77% |
| invalid_json | 0 | 0.00% |

## Per-folder summary

| Folder | Total | Valid | Valid % | Invalid | Invalid % | Moved empty |
|---|---:|---:|---:|---:|---:|---:|
| CompMix_infobox_complex | 300 | 203 | 67.67% | 97 | 32.33% | 32 |
| CompMix_table_complex | 300 | 267 | 89.00% | 33 | 11.00% | 89 |
| CompMix_table_simple_qa | 326 | 290 | 88.96% | 36 | 11.04% | 90 |
| Monaco_non_time_complex | 150 | 51 | 34.00% | 99 | 66.00% | 22 |
| Monaco_time_complex | 150 | 101 | 67.33% | 49 | 32.67% | 48 |
| NQ_table_test_simple | 966 | 881 | 91.20% | 85 | 8.80% | 285 |
| OTT_QA_dev_complex | 400 | 266 | 66.50% | 134 | 33.50% | 174 |
| Qampari_wikitables_simple | 78 | 75 | 96.15% | 3 | 3.85% | 21 |
| Sportsreason_TANQ_complex | 200 | 147 | 73.50% | 53 | 26.50% | 67 |
| **Total** | 2870 | 2281 | 79.48% | 589 | 20.52% | 828 |
