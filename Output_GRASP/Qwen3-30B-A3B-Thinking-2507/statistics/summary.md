# Global SPARQL QA Statistics

## Overall valid vs invalid

| Metric | Count | Percentage |
|---|---:|---:|
| Valid | 533 | 18.52% |
| Invalid | 2345 | 81.48% |

## Error distribution (Total)

| Error type | Count | % of invalid |
|---|---:|---:|
| empty_sparql_result | 1070 | 45.63% |
| invalid_json | 0 | 0.00% |
| no_sparql_generated | 34 | 1.45% |
| null_output | 1006 | 42.90% |
| sparql_execution_failed (execution) | 196 | 8.36% |
| sparql_execution_failed (preprocessing) | 39 | 1.66% |

## Per-folder summary

| Folder | Total | Valid | Valid % | Invalid | Invalid % |
|---|---:|---:|---:|---:|---:|
| CompMix_infobox_complex | 301 | 224 | 74.42% | 77 | 25.58% |
| CompMix_table_complex | 301 | 121 | 40.20% | 180 | 59.80% |
| CompMix_table_simple_qa | 327 | 69 | 21.10% | 258 | 78.90% |
| Monaco_non_time_complex | 150 | 9 | 6.00% | 141 | 94.00% |
| Monaco_time_complex | 151 | 10 | 6.62% | 141 | 93.38% |
| NQ_table_test_simple | 967 | 16 | 1.65% | 951 | 98.35% |
| OTT_QA_dev_complex | 401 | 41 | 10.22% | 360 | 89.78% |
| Qampari_wikitables_simple | 79 | 0 | 0.00% | 79 | 100.00% |
| Sportsreason_TANQ_complex | 201 | 43 | 21.39% | 158 | 78.61% |
| **Total** | 2878 | 533 | 18.52% | 2345 | 81.48% |