# SimpleQA SPARQL QA Statistics

## Overall valid vs invalid

| Metric | Count | Percentage |
|---|---:|---:|
| Valid | 1246 | 90.95% |
| Invalid | 124 | 9.05% |
| Valid empty SPARQL results moved from invalid | 396 | 28.91% |

## Error distribution after patch

| Error type | Count | % of invalid |
|---|---:|---:|
| null_output | 9 | 7.26% |
| no_sparql_generated | 36 | 29.03% |
| sparql_execution_failed (execution) | 54 | 43.55% |
| sparql_execution_failed (preprocessing) | 25 | 20.16% |
| invalid_json | 0 | 0.00% |

## Per-folder summary

| Folder | Total | Valid | Valid % | Invalid | Invalid % | Moved empty |
|---|---:|---:|---:|---:|---:|---:|
| CompMix_table_simple_qa | 326 | 290 | 88.96% | 36 | 11.04% | 90 |
| NQ_table_test_simple | 966 | 881 | 91.20% | 85 | 8.80% | 285 |
| Qampari_wikitables_simple | 78 | 75 | 96.15% | 3 | 3.85% | 21 |
| **Total** | 1370 | 1246 | 90.95% | 124 | 9.05% | 396 |
