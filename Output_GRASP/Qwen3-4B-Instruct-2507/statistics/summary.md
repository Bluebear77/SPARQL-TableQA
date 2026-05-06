# Global SPARQL QA Statistics

## Overall valid vs invalid

| Metric | Count | Percentage |
|---|---:|---:|
| Valid | 1165 | 40.59% |
| Invalid | 1705 | 59.41% |

## Error distribution (Total)

| Error type | Count | % of invalid |
|---|---:|---:|
| empty_sparql_result | 876 | 51.38% |
| invalid_json | 0 | 0.00% |
| no_sparql_generated | 101 | 5.92% |
| null_output | 458 | 26.86% |
| sparql_execution_failed (execution) | 155 | 9.09% |
| sparql_execution_failed (preprocessing) | 115 | 6.74% |

## Per-folder summary

| Folder | Total | Valid | Valid % | Invalid | Invalid % |
|---|---:|---:|---:|---:|---:|
| CompMix_infobox_complex | 300 | 210 | 70.00% | 90 | 30.00% |
| CompMix_table_complex | 300 | 120 | 40.00% | 180 | 60.00% |
| CompMix_table_simple_qa | 326 | 198 | 60.74% | 128 | 39.26% |
| Monaco_non_time_complex | 150 | 50 | 33.33% | 100 | 66.67% |
| Monaco_time_complex | 150 | 47 | 31.33% | 103 | 68.67% |
| NQ_table_test_simple | 966 | 437 | 45.24% | 529 | 54.76% |
| OTT_QA_dev_complex | 400 | 53 | 13.25% | 347 | 86.75% |
| Qampari_wikitables_simple | 78 | 25 | 32.05% | 53 | 67.95% |
| Sportsreason_TANQ_complex | 200 | 25 | 12.50% | 175 | 87.50% |
| statistics | 0 | 0 | 0.00% | 0 | 0.00% |
| **Total** | 2870 | 1165 | 40.59% | 1705 | 59.41% |