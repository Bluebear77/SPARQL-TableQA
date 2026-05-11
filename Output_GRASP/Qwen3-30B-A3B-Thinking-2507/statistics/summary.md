# Global SPARQL QA Statistics

## Overall valid vs invalid

| Metric | Count | Percentage |
|---|---:|---:|
| Valid | 749 | 26.10% |
| Invalid | 2121 | 73.90% |

## Error distribution (Total)

| Error type | Count | % of invalid |
|---|---:|---:|
| empty_sparql_result | 1679 | 79.16% |
| invalid_json | 0 | 0.00% |
| no_sparql_generated | 37 | 1.74% |
| null_output | 143 | 6.74% |
| sparql_execution_failed (execution) | 213 | 10.04% |
| sparql_execution_failed (preprocessing) | 49 | 2.31% |

## Per-folder summary

| Folder | Total | Valid | Valid % | Invalid | Invalid % |
|---|---:|---:|---:|---:|---:|
| CompMix_infobox_complex | 300 | 224 | 74.67% | 76 | 25.33% |
| CompMix_table_complex | 300 | 121 | 40.33% | 179 | 59.67% |
| CompMix_table_simple_qa | 326 | 69 | 21.17% | 257 | 78.83% |
| Monaco_non_time_complex | 150 | 9 | 6.00% | 141 | 94.00% |
| Monaco_time_complex | 150 | 10 | 6.67% | 140 | 93.33% |
| NQ_table_test_simple | 966 | 211 | 21.84% | 755 | 78.16% |
| OTT_QA_dev_complex | 400 | 41 | 10.25% | 359 | 89.75% |
| Qampari_wikitables_simple | 78 | 21 | 26.92% | 57 | 73.08% |
| Sportsreason_TANQ_complex | 200 | 43 | 21.50% | 157 | 78.50% |
| **Total** | 2870 | 749 | 26.10% | 2121 | 73.90% |