# Global SPARQL QA Statistics

## Overall valid vs invalid

| Metric | Count | Percentage |
|---|---:|---:|
| Valid | 2041 | 71.11% |
| Invalid | 829 | 28.89% |
| Valid empty SPARQL results moved from invalid | 876 | 30.52% |

## Error distribution after patch

| Error type | Count | % of invalid |
|---|---:|---:|
| null_output | 458 | 55.25% |
| no_sparql_generated | 101 | 12.18% |
| sparql_execution_failed (execution) | 155 | 18.70% |
| sparql_execution_failed (preprocessing) | 115 | 13.87% |
| invalid_json | 0 | 0.00% |

## Per-folder summary

| Folder | Total | Valid | Valid % | Invalid | Invalid % | Moved empty |
|---|---:|---:|---:|---:|---:|---:|
| CompMix_infobox_complex | 300 | 274 | 91.33% | 26 | 8.67% | 64 |
| CompMix_table_complex | 300 | 254 | 84.67% | 46 | 15.33% | 134 |
| CompMix_table_simple_qa | 326 | 288 | 88.34% | 38 | 11.66% | 90 |
| Monaco_non_time_complex | 150 | 106 | 70.67% | 44 | 29.33% | 56 |
| Monaco_time_complex | 150 | 105 | 70.00% | 45 | 30.00% | 58 |
| NQ_table_test_simple | 966 | 769 | 79.61% | 197 | 20.39% | 332 |
| OTT_QA_dev_complex | 400 | 142 | 35.50% | 258 | 64.50% | 89 |
| Qampari_wikitables_simple | 78 | 42 | 53.85% | 36 | 46.15% | 17 |
| Sportsreason_TANQ_complex | 200 | 61 | 30.50% | 139 | 69.50% | 36 |
| statistics | 0 | 0 | 0.00% | 0 | 0.00% | 0 |
| statistics | 0 | 0 | 0.00% | 0 | 0.00% | 0 |
| **Total** | 2870 | 2041 | 71.11% | 829 | 28.89% | 876 |
