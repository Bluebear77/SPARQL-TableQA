# ComplexQA SPARQL QA Statistics

## Overall valid vs invalid

| Metric | Count | Percentage |
|---|---:|---:|
| Valid | 1035 | 69.00% |
| Invalid | 465 | 31.00% |
| Valid empty SPARQL results moved from invalid | 432 | 28.80% |

## Error distribution after patch

| Error type | Count | % of invalid |
|---|---:|---:|
| null_output | 219 | 47.10% |
| no_sparql_generated | 6 | 1.29% |
| sparql_execution_failed (execution) | 231 | 49.68% |
| sparql_execution_failed (preprocessing) | 9 | 1.94% |
| invalid_json | 0 | 0.00% |

## Per-folder summary

| Folder | Total | Valid | Valid % | Invalid | Invalid % | Moved empty |
|---|---:|---:|---:|---:|---:|---:|
| CompMix_infobox_complex | 300 | 203 | 67.67% | 97 | 32.33% | 32 |
| CompMix_table_complex | 300 | 267 | 89.00% | 33 | 11.00% | 89 |
| Monaco_non_time_complex | 150 | 51 | 34.00% | 99 | 66.00% | 22 |
| Monaco_time_complex | 150 | 101 | 67.33% | 49 | 32.67% | 48 |
| OTT_QA_dev_complex | 400 | 266 | 66.50% | 134 | 33.50% | 174 |
| Sportsreason_TANQ_complex | 200 | 147 | 73.50% | 53 | 26.50% | 67 |
| **Total** | 1500 | 1035 | 69.00% | 465 | 31.00% | 432 |
