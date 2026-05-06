# Global SPARQL QA Statistics

## Overall valid vs invalid

| Metric | Count | Percentage |
|---|---:|---:|
| Valid | 1450 | 50.52% |
| Invalid | 1420 | 49.48% |

## Error distribution (Total)

| Error type | Count | % of invalid |
|---|---:|---:|
| empty_sparql_result | 828 | 58.31% |
| invalid_json | 0 | 0.00% |
| no_sparql_generated | 42 | 2.96% |
| null_output | 232 | 16.34% |
| sparql_execution_failed (execution) | 285 | 20.07% |
| sparql_execution_failed (preprocessing) | 33 | 2.32% |

## Per-folder summary

| Folder | Total | Valid | Valid % | Invalid | Invalid % |
|---|---:|---:|---:|---:|---:|
| CompMix_infobox_complex | 300 | 169 | 56.33% | 131 | 43.67% |
| CompMix_table_complex | 300 | 178 | 59.33% | 122 | 40.67% |
| CompMix_table_simple_qa | 326 | 200 | 61.35% | 126 | 38.65% |
| Monaco_non_time_complex | 150 | 29 | 19.33% | 121 | 80.67% |
| Monaco_time_complex | 150 | 53 | 35.33% | 97 | 64.67% |
| NQ_table_test_simple | 966 | 595 | 61.59% | 371 | 38.41% |
| OTT_QA_dev_complex | 400 | 92 | 23.00% | 308 | 77.00% |
| Qampari_wikitables_simple | 78 | 54 | 69.23% | 24 | 30.77% |
| Sportsreason_TANQ_complex | 200 | 80 | 40.00% | 120 | 60.00% |
| **Total** | 2870 | 1450 | 50.52% | 1420 | 49.48% |