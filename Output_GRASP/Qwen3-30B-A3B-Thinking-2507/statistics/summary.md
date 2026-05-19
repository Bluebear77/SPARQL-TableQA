# Global SPARQL QA Statistics

## Overall valid vs invalid

| Metric | Count | Percentage |
|---|---:|---:|
| Valid | 1278 | 44.53% |
| Invalid | 1592 | 55.47% |

## Error distribution (Total)

| Error type | Count | % of invalid |
|---|---:|---:|
| empty_sparql_result | 1298 | 81.53% |
| invalid_json | 0 | 0.00% |
| no_sparql_generated | 35 | 2.20% |
| null_output | 183 | 11.49% |
| sparql_execution_failed (execution) | 22 | 1.38% |
| sparql_execution_failed (preprocessing) | 54 | 3.39% |

## Per-folder summary

| Folder | Total | Valid | Valid % | Invalid | Invalid % |
|---|---:|---:|---:|---:|---:|
| CompMix_infobox_complex | 300 | 223 | 74.33% | 77 | 25.67% |
| CompMix_table_complex | 300 | 138 | 46.00% | 162 | 54.00% |
| CompMix_table_simple_qa | 326 | 168 | 51.53% | 158 | 48.47% |
| Monaco_non_time_complex | 150 | 38 | 25.33% | 112 | 74.67% |
| Monaco_time_complex | 150 | 36 | 24.00% | 114 | 76.00% |
| NQ_table_test_simple | 966 | 499 | 51.66% | 467 | 48.34% |
| OTT_QA_dev_complex | 400 | 83 | 20.75% | 317 | 79.25% |
| Qampari_wikitables_simple | 78 | 33 | 42.31% | 45 | 57.69% |
| Sportsreason_TANQ_complex | 200 | 60 | 30.00% | 140 | 70.00% |
| **Total** | 2870 | 1278 | 44.53% | 1592 | 55.47% |