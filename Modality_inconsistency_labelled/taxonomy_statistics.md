# Taxonomy Merge Statistics

This file summarizes the cleaned, merged taxonomy-labeled QA CSV outputs.

Cleaning steps applied before writing each output CSV:
1. Remove rows whose `source` / original `file_path` appears in `Output_GRASP/script/large_results_report.txt`.
2. Remove duplicate `question` rows inside each model output, keeping the first occurrence.
3. Sort the final CSV by taxonomy label while preserving original row order inside each label group.
4. Save removed rows to `Modality_inconsistency_labelled/removed_files/`, with a `cause` column.

The final merged CSVs preserve the complete dataset-relative JSON path in the `source` column, for example `SimpleQA/NQ_table_test_simple/00503.json`.

Each distribution count is shown as:

```text
count (percentage within model)
```

## Total Rows by Model

| Metric | Qwen3-4B-Instruct | Qwen3-30B-Thinking | Qwen3-235B-Thinking |
| --- | --- | --- | --- |
| Total | 902 | 1167 | 1341 |

## Rows Removed by Cleaning Step

| Model | Rows removed by >10-row file_path filter | Rows removed as duplicate questions | Total removed by these two steps | Removed rows CSV |
| --- | --- | --- | --- | --- |
| Qwen3-4B-Instruct | 251 | 12 | 263 | /workspaces/KONTRAST/Modality_inconsistency_labelled/removed_files/removed_rows_4B.csv |
| Qwen3-30B-Thinking | 97 | 14 | 111 | /workspaces/KONTRAST/Modality_inconsistency_labelled/removed_files/removed_rows_30B.csv |
| Qwen3-235B-Thinking | 95 | 17 | 112 | /workspaces/KONTRAST/Modality_inconsistency_labelled/removed_files/removed_rows_235B.csv |
| Total | 443 | 43 | 486 |  |

## Taxonomy Distribution by Model

| taxonomy_label | Qwen3-4B-Instruct | Qwen3-30B-Thinking | Qwen3-235B-Thinking |
| --- | --- | --- | --- |
| Different answer | 416 (46.12%) | 477 (40.87%) | 519 (38.70%) |
| Higher accuracy in KG than in Table | 122 (13.53%) | 135 (11.57%) | 151 (11.26%) |
| Higher accuracy in Table than in KG | 66 (7.32%) | 101 (8.65%) | 126 (9.40%) |
| Same | 285 (31.60%) | 423 (36.25%) | 518 (38.63%) |
| Temporal changes | 13 (1.44%) | 31 (2.66%) | 27 (2.01%) |
| Total | 902 (100.00%) | 1167 (100.00%) | 1341 (100.00%) |

## Method Distribution by Model

| method | Qwen3-4B-Instruct | Qwen3-30B-Thinking | Qwen3-235B-Thinking |
| --- | --- | --- | --- |
| LLM-as-a-judge | 495 (54.88%) | 625 (53.56%) | 713 (53.17%) |
| Simple heuristics | 407 (45.12%) | 542 (46.44%) | 628 (46.83%) |
| Total | 902 (100.00%) | 1167 (100.00%) | 1341 (100.00%) |

## Analysis Set Taxonomy Summary

This table is computed from the final cleaned CSVs using the complete `source` path to split rows into SimpleQA and ComplexQA.

| Group | Taxonomy Label | Qwen3-4B-Instruct | Qwen3-30B-Thinking | Qwen3-235B-Thinking |
| --- | --- | --- | --- | --- |
| SimpleQA | Same | 154 (29.8%) | 226 (35.9%) | 298 (38.4%) |
| SimpleQA | Higher accuracy in KG than in Table | 56 (10.8%) | 69 (11.0%) | 96 (12.4%) |
| SimpleQA | Higher accuracy in Table than in KG | 50 (9.7%) | 65 (10.3%) | 77 (9.9%) |
| SimpleQA | Different answer | 245 (47.4%) | 243 (38.6%) | 286 (36.9%) |
| SimpleQA | Temporal changes | 12 (2.3%) | 26 (4.1%) | 19 (2.4%) |
| SimpleQA | Inconsistent rate | 363 (70.2%) | 403 (64.1%) | 478 (61.6%) |
| ComplexQA | Same | 131 (34.0%) | 197 (36.6%) | 220 (38.9%) |
| ComplexQA | Higher accuracy in KG than in Table | 66 (17.1%) | 66 (12.3%) | 55 (9.7%) |
| ComplexQA | Higher accuracy in Table than in KG | 16 (4.2%) | 36 (6.7%) | 49 (8.7%) |
| ComplexQA | Different answer | 171 (44.4%) | 234 (43.5%) | 233 (41.2%) |
| ComplexQA | Temporal changes | 1 (0.3%) | 5 (0.9%) | 8 (1.4%) |
| ComplexQA | Inconsistent rate | 254 (66.0%) | 341 (63.4%) | 345 (61.1%) |
| All | Same | 285 (31.6%) | 423 (36.2%) | 518 (38.6%) |
| All | Higher accuracy in KG than in Table | 122 (13.5%) | 135 (11.6%) | 151 (11.3%) |
| All | Higher accuracy in Table than in KG | 66 (7.3%) | 101 (8.7%) | 126 (9.4%) |
| All | Different answer | 416 (46.1%) | 477 (40.9%) | 519 (38.7%) |
| All | Temporal changes | 13 (1.4%) | 31 (2.7%) | 27 (2.0%) |
| All | Inconsistent rate | 617 (68.4%) | 744 (63.8%) | 823 (61.4%) |
| Total | Analysis Set cases | 902 | 1167 | 1341 |

## Analysis Set LaTeX Table

```latex
\begin{table*}[t]
\centering
\scriptsize
\setlength{\tabcolsep}{4pt}
\renewcommand{\arraystretch}{1.08}
\begin{adjustbox}{max width=\textwidth}
\begin{tabular}{@{}llccc@{}}
\toprule
\textbf{Group}
& \textbf{Taxonomy Label}
& \textbf{Qwen3-4B}
& \textbf{Qwen3-30B}
& \textbf{Qwen3-235B}
\\
\midrule

\multirow{6}{*}{SimpleQA}
& Same
& 154 (29.8\%)
& 226 (35.9\%)
& 298 (38.4\%) \\
& Higher accuracy in KG than in Table
& 56 (10.8\%)
& 69 (11.0\%)
& 96 (12.4\%) \\
& Higher accuracy in Table than in KG
& 50 (9.7\%)
& 65 (10.3\%)
& 77 (9.9\%) \\
& Different answer
& \textbf{245 (47.4\%)}
& \textbf{243 (38.6\%)}
& \textbf{286 (36.9\%)} \\
& Temporal changes
& 12 (2.3\%)
& 26 (4.1\%)
& 19 (2.4\%) \\
\cmidrule(lr){2-5}
& Inconsistent rate
& 363 (70.2\%)
& 403 (64.1\%)
& \textbf{478 (61.6\%)} \\

\midrule

\multirow{6}{*}{ComplexQA}
& Same
& 131 (34.0\%)
& 197 (36.6\%)
& 220 (38.9\%) \\
& Higher accuracy in KG than in Table
& 66 (17.1\%)
& 66 (12.3\%)
& 55 (9.7\%) \\
& Higher accuracy in Table than in KG
& 16 (4.2\%)
& 36 (6.7\%)
& 49 (8.7\%) \\
& Different answer
& \textbf{171 (44.4\%)}
& \textbf{234 (43.5\%)}
& \textbf{233 (41.2\%)} \\
& Temporal changes
& 1 (0.3\%)
& 5 (0.9\%)
& 8 (1.4\%) \\
\cmidrule(lr){2-5}
& Inconsistent rate
& 254 (66.0\%)
& 341 (63.4\%)
& \textbf{345 (61.1\%)} \\

\midrule

\multirow{6}{*}{All}
& Same
& 285 (31.6\%)
& 423 (36.2\%)
& 518 (38.6\%) \\
& Higher accuracy in KG than in Table
& 122 (13.5\%)
& 135 (11.6\%)
& 151 (11.3\%) \\
& Higher accuracy in Table than in KG
& 66 (7.3\%)
& 101 (8.7\%)
& 126 (9.4\%) \\
& Different answer
& \textbf{416 (46.1\%)}
& \textbf{477 (40.9\%)}
& \textbf{519 (38.7\%)} \\
& Temporal changes
& 13 (1.4\%)
& 31 (2.7\%)
& 27 (2.0\%) \\
\cmidrule(lr){2-5}
& Inconsistent rate
& 617 (68.4\%)
& 744 (63.8\%)
& \textbf{823 (61.4\%)} \\

\midrule

\textbf{Total}
& Analysis Set cases
& 902
& 1167
& 1341 \\

\bottomrule
\end{tabular}
\end{adjustbox}
\caption{Distribution of modality-level inconsistency categories by QA group and model in the Analysis Set. Percentages are computed within each group and model after removing overlong KG answers and duplicate questions. Bold taxonomy entries mark the dominant inconsistency category for each group and model; bold inconsistent-rate entries mark the lowest inconsistent rate across models within each group.}
\label{tab:taxonomy_summary_main}
\end{table*}
```

## Updated Surrounding Text

```latex
\paragraph{Effect of model scale.}
Model strength affects both retrieval quality and downstream inconsistency analysis.
In the filtered Analysis Set, Qwen3-235B-Thinking has the lowest overall inconsistency rate among value-bearing cases (61.4\%), followed by Qwen3-30B-Thinking (63.8\%) and Qwen3-4B-Instruct (68.4\%). Across SimpleQA, ComplexQA, and the full Analysis Set, \textit{Different answer} remains the dominant inconsistency category for all three Qwen3 models, showing that most remaining modality-level disagreements are direct answer mismatches rather than temporal or granularity differences. The trend is clearer in ComplexQA, where Qwen3-235B-Thinking reaches the lowest inconsistency rate (61.1\%) and Qwen3-235B-Thinking has the highest proportion of \textit{Same} cases (38.9\\%). Overall, stronger reasoning ability reduces translation-induced mismatches and yields KG answers that are more reliable for downstream inconsistency analysis.
```

## Skipped Pairs

None.
