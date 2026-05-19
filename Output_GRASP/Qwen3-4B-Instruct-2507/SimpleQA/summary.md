# SimpleQA SPARQL QA Statistics

## Overall valid vs invalid

| Metric | Count | Percentage |
|---|---:|---:|
| Valid | 1099 | 80.22% |
| Invalid | 271 | 19.78% |
| Valid empty SPARQL results moved from invalid | 439 | 32.04% |

## Error distribution after patch

| Error type | Count | % of invalid |
|---|---:|---:|
| null_output | 79 | 29.15% |
| no_sparql_generated | 42 | 15.50% |
| sparql_execution_failed (execution) | 110 | 40.59% |
| sparql_execution_failed (preprocessing) | 40 | 14.76% |
| invalid_json | 0 | 0.00% |

## Per-folder summary

| Folder | Total | Valid | Valid % | Invalid | Invalid % | Moved empty |
|---|---:|---:|---:|---:|---:|---:|
| CompMix_table_simple_qa | 326 | 288 | 88.34% | 38 | 11.66% | 90 |
| NQ_table_test_simple | 966 | 769 | 79.61% | 197 | 20.39% | 332 |
| Qampari_wikitables_simple | 78 | 42 | 53.85% | 36 | 46.15% | 17 |
| statistics | 0 | 0 | 0.00% | 0 | 0.00% | 0 |
| **Total** | 1370 | 1099 | 80.22% | 271 | 19.78% | 439 |
