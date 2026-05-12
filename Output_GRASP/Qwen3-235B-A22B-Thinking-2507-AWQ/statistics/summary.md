# Global SPARQL QA Statistics

## Overall valid vs invalid

| Metric | Count | Percentage |
|---|---:|---:|
| Valid | 1453 | 50.63% |
| Invalid | 1417 | 49.37% |

## Error distribution (Total)

| Error type | Count | % of invalid |
|---|---:|---:|
| empty_sparql_result | 828 | 58.43% |
| invalid_json | 0 | 0.00% |
| no_sparql_generated | 42 | 2.96% |
| null_output | 228 | 16.09% |
| sparql_execution_failed (execution) | 285 | 20.11% |
| sparql_execution_failed (preprocessing) | 34 | 2.40% |

## Per-folder summary

| Folder | Total | Valid | Valid % | Invalid | Invalid % |
|---|---:|---:|---:|---:|---:|
| CompMix_infobox_complex | 300 | 171 | 57.00% | 129 | 43.00% |
| CompMix_table_complex | 300 | 178 | 59.33% | 122 | 40.67% |
| CompMix_table_simple_qa | 326 | 200 | 61.35% | 126 | 38.65% |
| Monaco_non_time_complex | 150 | 29 | 19.33% | 121 | 80.67% |
| Monaco_time_complex | 150 | 53 | 35.33% | 97 | 64.67% |
| NQ_table_test_simple | 966 | 596 | 61.70% | 370 | 38.30% |
| OTT_QA_dev_complex | 400 | 92 | 23.00% | 308 | 77.00% |
| Qampari_wikitables_simple | 78 | 54 | 69.23% | 24 | 30.77% |
| Sportsreason_TANQ_complex | 200 | 80 | 40.00% | 120 | 60.00% |
| **Total** | 2870 | 1453 | 50.63% | 1417 | 49.37% |