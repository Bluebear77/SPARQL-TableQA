# SimpleQA SPARQL QA Statistics

## Overall valid vs invalid

| Metric | Count | Percentage |
|---|---:|---:|
| Valid | 1278 | 93.28% |
| Invalid | 92 | 6.72% |
| Valid empty SPARQL results moved from invalid | 578 | 42.19% |

## Error distribution after patch

| Error type | Count | % of invalid |
|---|---:|---:|
| null_output | 44 | 47.83% |
| no_sparql_generated | 27 | 29.35% |
| sparql_execution_failed (execution) | 7 | 7.61% |
| sparql_execution_failed (preprocessing) | 14 | 15.22% |
| invalid_json | 0 | 0.00% |

## Per-folder summary

| Folder | Total | Valid | Valid % | Invalid | Invalid % | Moved empty |
|---|---:|---:|---:|---:|---:|---:|
| CompMix_table_simple_qa | 326 | 294 | 90.18% | 32 | 9.82% | 126 |
| NQ_table_test_simple | 966 | 915 | 94.72% | 51 | 5.28% | 416 |
| Qampari_wikitables_simple | 78 | 69 | 88.46% | 9 | 11.54% | 36 |
| **Total** | 1370 | 1278 | 93.28% | 92 | 6.72% | 578 |
