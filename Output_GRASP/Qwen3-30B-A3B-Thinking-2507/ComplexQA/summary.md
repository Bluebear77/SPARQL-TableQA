# ComplexQA SPARQL QA Statistics

## Overall valid vs invalid

| Metric | Count | Percentage |
|---|---:|---:|
| Valid | 1298 | 86.53% |
| Invalid | 202 | 13.47% |
| Valid empty SPARQL results moved from invalid | 720 | 48.00% |

## Error distribution after patch

| Error type | Count | % of invalid |
|---|---:|---:|
| null_output | 139 | 68.81% |
| no_sparql_generated | 8 | 3.96% |
| sparql_execution_failed (execution) | 15 | 7.43% |
| sparql_execution_failed (preprocessing) | 40 | 19.80% |
| invalid_json | 0 | 0.00% |

## Per-folder summary

| Folder | Total | Valid | Valid % | Invalid | Invalid % | Moved empty |
|---|---:|---:|---:|---:|---:|---:|
| CompMix_infobox_complex | 300 | 289 | 96.33% | 11 | 3.67% | 66 |
| CompMix_table_complex | 300 | 278 | 92.67% | 22 | 7.33% | 140 |
| Monaco_non_time_complex | 150 | 123 | 82.00% | 27 | 18.00% | 85 |
| Monaco_time_complex | 150 | 117 | 78.00% | 33 | 22.00% | 81 |
| OTT_QA_dev_complex | 400 | 337 | 84.25% | 63 | 15.75% | 254 |
| Sportsreason_TANQ_complex | 200 | 154 | 77.00% | 46 | 23.00% | 94 |
| **Total** | 1500 | 1298 | 86.53% | 202 | 13.47% | 720 |
