# ComplexQA SPARQL QA Statistics

## Overall valid vs invalid

| Metric | Count | Percentage |
|---|---:|---:|
| Valid | 942 | 62.80% |
| Invalid | 558 | 37.20% |
| Valid empty SPARQL results moved from invalid | 437 | 29.13% |

## Error distribution after patch

| Error type | Count | % of invalid |
|---|---:|---:|
| null_output | 379 | 67.92% |
| no_sparql_generated | 59 | 10.57% |
| sparql_execution_failed (execution) | 45 | 8.06% |
| sparql_execution_failed (preprocessing) | 75 | 13.44% |
| invalid_json | 0 | 0.00% |

## Per-folder summary

| Folder | Total | Valid | Valid % | Invalid | Invalid % | Moved empty |
|---|---:|---:|---:|---:|---:|---:|
| CompMix_infobox_complex | 300 | 274 | 91.33% | 26 | 8.67% | 64 |
| CompMix_table_complex | 300 | 254 | 84.67% | 46 | 15.33% | 134 |
| Monaco_non_time_complex | 150 | 106 | 70.67% | 44 | 29.33% | 56 |
| Monaco_time_complex | 150 | 105 | 70.00% | 45 | 30.00% | 58 |
| OTT_QA_dev_complex | 400 | 142 | 35.50% | 258 | 64.50% | 89 |
| Sportsreason_TANQ_complex | 200 | 61 | 30.50% | 139 | 69.50% | 36 |
| statistics | 0 | 0 | 0.00% | 0 | 0.00% | 0 |
| **Total** | 1500 | 942 | 62.80% | 558 | 37.20% | 437 |
