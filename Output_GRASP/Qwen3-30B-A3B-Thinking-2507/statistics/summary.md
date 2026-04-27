# Global SPARQL QA Statistics

## Overall valid vs invalid

| Metric | Count | Percentage |
|---|---:|---:|
| Valid | 388 | 13.48% |
| Invalid | 2490 | 86.52% |

## Error distribution (Total)

| Error type | Count | % of invalid |
|---|---:|---:|
| empty_sparql_result | 641 | 25.74% |
| invalid_json | 1674 | 67.23% |
| no_sparql_generated | 9 | 0.36% |
| null_output | 83 | 3.33% |
| sparql_execution_failed (execution) | 62 | 2.49% |
| sparql_execution_failed (preprocessing) | 21 | 0.84% |

## Per-folder summary

| Folder | Total | Valid | Valid % | Invalid | Invalid % |
|---|---:|---:|---:|---:|---:|
| CompMix_infobox_complex | 301 | 222 | 73.75% | 79 | 26.25% |
| CompMix_table_complex | 301 | 120 | 39.87% | 181 | 60.13% |
| CompMix_table_simple_qa | 327 | 0 | 0.00% | 327 | 100.00% |
| Monaco_non_time_complex | 151 | 9 | 5.96% | 142 | 94.04% |
| Monaco_time_complex | 151 | 10 | 6.62% | 141 | 93.38% |
| NQ_table_test_simple | 967 | 0 | 0.00% | 967 | 100.00% |
| OTT_QA_dev_complex | 401 | 27 | 6.73% | 374 | 93.27% |
| Qampari_wikitables_simple | 78 | 0 | 0.00% | 78 | 100.00% |
| Sportsreason_TANQ_complex | 201 | 0 | 0.00% | 201 | 100.00% |
| **Total** | 2878 | 388 | 13.48% | 2490 | 86.52% |