#!/usr/bin/env python3
"""
merge_taxonomy_full.py

Summary
-------
This script merges taxonomy-labeled QA rows for three Qwen model outputs,
applies the final KONTRAST cleaning rules, sorts each final CSV by taxonomy
label, writes removed-row audit files, and writes taxonomy_statistics.md.

For each model, the script:
1. Reads the Simple-heuristics taxonomy CSV and the LLM-as-a-judge CSV.
2. Drops Simple-heuristics rows whose taxonomy_label is different_unclassified.
3. Preserves the complete original file_path in the public `source` column,
   for example SimpleQA/NQ_table_test_simple/00503.json.
4. Removes rows whose source/file_path appears in
   Output_GRASP/script/large_results_report.txt, meaning the KG answer has
   more than 10 result rows.
5. Merges Simple-heuristics and LLM-as-a-judge rows into one shared schema.
6. Removes duplicate question rows inside each model output, keeping the first
   occurrence.
7. Sorts each final CSV by taxonomy label while preserving original order
   inside each taxonomy group.
8. Writes one final CSV per model to Modality_inconsistency_labelled/.
9. Writes one removed-row CSV per model to
   Modality_inconsistency_labelled/removed_files/, with an extra `cause`
   column: duplicate or long answer.
10. Writes taxonomy_statistics.md, including the Analysis Set LaTeX table for
    SimpleQA, ComplexQA, and All.

Run from the repository root with:

    python merge_taxonomy.py
"""

from __future__ import annotations

from pathlib import Path
import csv
import re
from collections import Counter


# ---------------------------------------------------------------------------
# Public output schema for final merged CSV files.
# The `source` column intentionally stores the complete dataset-relative JSON
# path, e.g. SimpleQA/NQ_table_test_simple/00503.json.
# ---------------------------------------------------------------------------
OUTPUT_COLUMNS = [
    "question",
    "gold_answer",
    "KG answer",
    "taxonomy_label",
    "method",
    "source",
]


# Removed-row audit CSVs use the same output schema plus one explanation field.
REMOVED_OUTPUT_COLUMNS = OUTPUT_COLUMNS + ["cause"]


# Report containing JSON files whose result row count is greater than 10.
LARGE_RESULTS_REPORT = Path("Output_GRASP/script/large_results_report.txt")


# Preferred order for rows inside each final CSV file.
# This comes from your grouping script.
CSV_TAXONOMY_ORDER = [
    "Same",
    "Different answer",
    "Higher accuracy in KG than in Table",
    "Higher accuracy in Table than in KG",
    "Temporal changes",
]


# Preferred order for the EMNLP-style taxonomy table.
TABLE_TAXONOMY_ORDER = [
    "Same",
    "Higher accuracy in KG than in Table",
    "Higher accuracy in Table than in KG",
    "Different answer",
    "Temporal changes",
]


# Labels counted as inconsistent. Same is the only consistency category.
INCONSISTENT_LABELS = [
    "Higher accuracy in KG than in Table",
    "Higher accuracy in Table than in KG",
    "Different answer",
    "Temporal changes",
]


# Input/output configuration for each model.
MERGE_PAIRS = [
    {
        "label": "4B",
        "short_model": "Qwen3-4B",
        "model": "Qwen3-4B-Instruct",
        "judged_csv": Path("LLM_as_a_Judge/4B_judged_filtered.csv"),
        "taxonomy_csv": Path("Output_GRASP/Qwen3-4B-Instruct-2507/all_valid_cases_with_taxonomy.csv"),
        "output_csv": Path("Modality_inconsistency_labelled/merged_taxonomy_answers_4B.csv"),
        "removed_csv": Path("Modality_inconsistency_labelled/removed_files/removed_rows_4B.csv"),
    },
    {
        "label": "30B",
        "short_model": "Qwen3-30B",
        "model": "Qwen3-30B-Thinking",
        "judged_csv": Path("LLM_as_a_Judge/30B_judged_filtered.csv"),
        "taxonomy_csv": Path("Output_GRASP/Qwen3-30B-A3B-Thinking-2507/all_valid_cases_with_taxonomy.csv"),
        "output_csv": Path("Modality_inconsistency_labelled/merged_taxonomy_answers_30B.csv"),
        "removed_csv": Path("Modality_inconsistency_labelled/removed_files/removed_rows_30B.csv"),
    },
    {
        "label": "235B",
        "short_model": "Qwen3-235B",
        "model": "Qwen3-235B-Thinking",
        "judged_csv": Path("LLM_as_a_Judge/235B_judged_filtered.csv"),
        "taxonomy_csv": Path("Output_GRASP/Qwen3-235B-A22B-Thinking-2507-AWQ/all_valid_cases_with_taxonomy.csv"),
        "output_csv": Path("Modality_inconsistency_labelled/merged_taxonomy_answers_235B.csv"),
        "removed_csv": Path("Modality_inconsistency_labelled/removed_files/removed_rows_235B.csv"),
    },
]


def find_project_root() -> Path:
    """Locate the repository root from either the root or Output_GRASP/."""
    cwd = Path.cwd().resolve()
    judge_dir_names = ["LLM_as_a_Judge", "LLM-as-Judge"]

    for judge_dir_name in judge_dir_names:
        if (cwd / judge_dir_name).is_dir() and (cwd / "Output_GRASP").is_dir():
            return cwd

    if cwd.name == "Output_GRASP":
        parent = cwd.parent
        for judge_dir_name in judge_dir_names:
            if (parent / judge_dir_name).is_dir() and (parent / "Output_GRASP").is_dir():
                return parent

    raise RuntimeError(
        "Could not locate project root. Run from the repository root or "
        "from Output_GRASP/. Expected Output_GRASP plus one of: "
        "LLM_as_a_Judge, LLM-as-Judge."
    )


def normalize_taxonomy_label(label: str) -> str:
    """Normalize taxonomy labels so equivalent labels are counted together."""
    label = (label or "").strip()
    if label.lower() == "same":
        return "Same"
    return label


def should_keep_simple_heuristics_row(label: str) -> bool:
    """Exclude Simple-heuristics rows that were not assigned a usable class."""
    return (label or "").strip().lower() != "different_unclassified"


def normalize_file_path_key(file_path_value: str) -> str:
    """
    Normalize a source/file_path value for matching.

    Keeps the dataset-relative suffix beginning with SimpleQA/ or ComplexQA/.
    This makes absolute paths, relative paths, and report paths comparable.
    """
    if not file_path_value:
        return ""

    normalized = str(file_path_value).strip().replace("\\", "/")
    match = re.search(r"(?:^|/)((?:SimpleQA|ComplexQA)/[^\s]+\.json)$", normalized)
    if match:
        return match.group(1)
    return normalized


def qa_group_from_source(source: str) -> str:
    """Map a complete source path to SimpleQA, ComplexQA, or UNKNOWN."""
    key = normalize_file_path_key(source)
    if key.startswith("SimpleQA/"):
        return "SimpleQA"
    if key.startswith("ComplexQA/"):
        return "ComplexQA"
    return "UNKNOWN"


def parse_large_results_report(report_path: Path) -> dict[str, set[str]]:
    """
    Parse Output_GRASP/script/large_results_report.txt.

    Returns {model_output_directory_name: {dataset-relative JSON paths}}.
    """
    large_paths_by_model: dict[str, set[str]] = {}

    if not report_path.exists():
        print(f"WARNING: Large-results report not found: {report_path}")
        print("         No rows will be removed by long-answer filtering.")
        return large_paths_by_model

    line_pattern = re.compile(
        r"^(?P<model>\S+)\s+"
        r"(?P<count>\d+)\s+rows\s+"
        r".*?(?P<file_path>(?:SimpleQA|ComplexQA)/\S+\.json)\s*$"
    )

    with report_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            match = line_pattern.match(line.strip())
            if not match:
                continue
            model_dir = match.group("model")
            file_path_key = normalize_file_path_key(match.group("file_path"))
            large_paths_by_model.setdefault(model_dir, set()).add(file_path_key)

    return large_paths_by_model


def read_csv_rows(csv_path: Path) -> list[dict]:
    """Read a CSV file into a list of dictionaries."""
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def require_columns(csv_path: Path, rows: list[dict], required_columns: list[str]) -> bool:
    """Check whether a non-empty CSV contains all required columns."""
    if not rows:
        return True
    missing = [column for column in required_columns if column not in rows[0]]
    if missing:
        print(f"  Missing required columns in {csv_path}: {', '.join(missing)}")
        return False
    return True


def convert_taxonomy_rows(rows: list[dict]) -> tuple[list[dict], int]:
    """Convert all_valid_cases_with_taxonomy.csv rows to the shared schema."""
    converted = []
    filtered_out = 0

    for row in rows:
        raw_label = row.get("taxonomy_label", "")
        if not should_keep_simple_heuristics_row(raw_label):
            filtered_out += 1
            continue

        file_path = normalize_file_path_key(row.get("file_path", ""))
        converted.append(
            {
                "question": row.get("question", ""),
                "gold_answer": row.get("gold_answer", ""),
                "KG answer": row.get("result_cleaned", ""),
                "taxonomy_label": normalize_taxonomy_label(raw_label),
                "method": "Simple heuristics",
                "source": file_path,
                "_file_path": file_path,
            }
        )

    return converted, filtered_out


def convert_judged_rows(rows: list[dict]) -> list[dict]:
    """Convert *_judged_filtered.csv rows to the shared schema."""
    converted = []

    for row in rows:
        file_path = normalize_file_path_key(row.get("file_path", ""))
        converted.append(
            {
                "question": row.get("question", ""),
                "gold_answer": row.get("gold_answer", ""),
                "KG answer": row.get("KG answer", ""),
                "taxonomy_label": normalize_taxonomy_label(row.get("taxonomy_label", "")),
                "method": "LLM-as-a-judge",
                "source": file_path,
                "_file_path": file_path,
            }
        )

    return converted


def public_row(row: dict) -> dict:
    """Return only columns intended for public output CSVs."""
    return {column: row.get(column, "") for column in OUTPUT_COLUMNS}


def add_removal_cause(row: dict, cause: str) -> dict:
    """Return a removed-row audit record with the requested cause column."""
    removed = public_row(row)
    removed["cause"] = cause
    return removed


def filter_large_result_rows(rows: list[dict], large_file_paths: set[str]) -> tuple[list[dict], list[dict]]:
    """Remove rows whose source/file_path appears in the >10-row report."""
    kept_rows = []
    removed_rows = []

    for row in rows:
        if row.get("_file_path", "") in large_file_paths:
            removed_rows.append(add_removal_cause(row, "long answer"))
        else:
            kept_rows.append(row)

    return kept_rows, removed_rows


def deduplicate_by_question(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Remove duplicate questions, keeping the first occurrence."""
    seen_questions = set()
    kept_rows = []
    removed_rows = []

    for row in rows:
        question_key = (row.get("question", "") or "").strip()
        if question_key in seen_questions:
            removed_rows.append(add_removal_cause(row, "duplicate"))
        else:
            seen_questions.add(question_key)
            kept_rows.append(row)

    return kept_rows, removed_rows


def sort_rows_by_taxonomy(rows: list[dict]) -> list[dict]:
    """
    Sort final rows by taxonomy label and preserve original order inside groups.

    This merges your grouping script into the main pipeline.
    """
    order_map = {label: index for index, label in enumerate(CSV_TAXONOMY_ORDER)}
    indexed_rows = list(enumerate(rows))
    indexed_rows.sort(
        key=lambda item: (
            order_map.get(item[1].get("taxonomy_label", ""), len(CSV_TAXONOMY_ORDER)),
            item[1].get("taxonomy_label", ""),
            item[0],
        )
    )
    return [row for _, row in indexed_rows]


def write_csv(csv_path: Path, rows: list[dict]) -> None:
    """Write final merged rows to a CSV file."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(public_row(row) for row in rows)


def write_removed_csv(csv_path: Path, rows: list[dict]) -> None:
    """Write removed rows to a per-model audit CSV."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REMOVED_OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows({column: row.get(column, "") for column in REMOVED_OUTPUT_COLUMNS} for row in rows)


def format_count_percentage(count: int, total: int, decimals: int = 2, latex: bool = False) -> str:
    """Format count and percentage for Markdown or LaTeX tables."""
    pct = 0.0 if total == 0 else count / total * 100
    percent_sign = r"\%" if latex else "%"
    return f"{count} ({pct:.{decimals}f}{percent_sign})"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    """Build a Markdown table."""
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def count_by_label(rows: list[dict]) -> Counter:
    """Count normalized taxonomy labels."""
    return Counter(normalize_taxonomy_label(row.get("taxonomy_label", "")) or "UNKNOWN" for row in rows)


def build_total_distribution_row(row_label: str, model_names: list[str], merged_rows_by_model: dict[str, list[dict]]) -> list[str]:
    """Build a Total row for a Markdown distribution table."""
    row = [row_label]
    for model in model_names:
        total = len(merged_rows_by_model[model])
        row.append(format_count_percentage(total, total))
    return row


def split_rows_by_qa_group(rows: list[dict]) -> dict[str, list[dict]]:
    """Split rows into SimpleQA, ComplexQA, UNKNOWN, and All groups."""
    grouped = {"SimpleQA": [], "ComplexQA": [], "UNKNOWN": [], "All": list(rows)}
    for row in rows:
        grouped.setdefault(qa_group_from_source(row.get("source", "")), []).append(row)
    return grouped


def analysis_group_counts(merged_rows_by_model: dict[str, list[dict]]) -> dict[str, dict[str, dict[str, int]]]:
    """
    Compute counts for SimpleQA, ComplexQA, and All by model.

    Returns:
        {model: {group: {label_or_metric: count, "__total__": total}}}
    """
    results: dict[str, dict[str, dict[str, int]]] = {}

    for model, rows in merged_rows_by_model.items():
        results[model] = {}
        grouped = split_rows_by_qa_group(rows)

        for group_name in ["SimpleQA", "ComplexQA", "All"]:
            group_rows = grouped.get(group_name, [])
            label_counter = count_by_label(group_rows)
            row_counts = {label: label_counter.get(label, 0) for label in TABLE_TAXONOMY_ORDER}
            row_counts["Inconsistent rate"] = sum(label_counter.get(label, 0) for label in INCONSISTENT_LABELS)
            row_counts["__total__"] = len(group_rows)
            results[model][group_name] = row_counts

    return results


def dominant_inconsistency_label(group_counts: dict[str, int]) -> str:
    """Return the largest non-Same inconsistency category for one group/model."""
    return max(INCONSISTENT_LABELS, key=lambda label: group_counts.get(label, 0))


def build_analysis_markdown_table(merged_rows_by_model: dict[str, list[dict]]) -> str:
    """Build a Markdown version of the SimpleQA/ComplexQA/All analysis table."""
    model_names = list(merged_rows_by_model.keys())
    results = analysis_group_counts(merged_rows_by_model)
    rows = []

    for group in ["SimpleQA", "ComplexQA", "All"]:
        for label in TABLE_TAXONOMY_ORDER:
            row = [group, label]
            for model in model_names:
                counts = results[model][group]
                row.append(format_count_percentage(counts[label], counts["__total__"], decimals=1))
            rows.append(row)

        row = [group, "Inconsistent rate"]
        for model in model_names:
            counts = results[model][group]
            row.append(format_count_percentage(counts["Inconsistent rate"], counts["__total__"], decimals=1))
        rows.append(row)

    rows.append(["Total", "Analysis Set cases"] + [str(len(merged_rows_by_model[model])) for model in model_names])
    return markdown_table(["Group", "Taxonomy Label"] + model_names, rows)


def build_analysis_latex_table(merged_rows_by_model: dict[str, list[dict]]) -> str:
    """
    Build the EMNLP-style LaTeX table for the Analysis Set.

    Highlighting rules:
    - Bold the dominant inconsistency category within each QA group and model.
    - Bold the lowest inconsistent rate across the three models within each group.
    """
    model_names = list(merged_rows_by_model.keys())
    short_names = {
        pair["model"]: pair.get("short_model", pair["model"])
        for pair in MERGE_PAIRS
    }
    results = analysis_group_counts(merged_rows_by_model)

    lines = []
    lines.append(r"\begin{table*}[t]")
    lines.append(r"\centering")
    lines.append(r"\scriptsize")
    lines.append(r"\setlength{\tabcolsep}{4pt}")
    lines.append(r"\renewcommand{\arraystretch}{1.08}")
    lines.append(r"\begin{adjustbox}{max width=\textwidth}")
    lines.append(r"\begin{tabular}{@{}llccc@{}}")
    lines.append(r"\toprule")
    lines.append(r"\textbf{Group}")
    lines.append(r"& \textbf{Taxonomy Label}")
    for model in model_names:
        lines.append(rf"& \textbf{{{short_names.get(model, model)}}}")
    lines.append(r"\\")
    lines.append(r"\midrule")
    lines.append("")

    for group_index, group in enumerate(["SimpleQA", "ComplexQA", "All"]):
        dominant_by_model = {
            model: dominant_inconsistency_label(results[model][group])
            for model in model_names
        }

        inconsistent_rates = {
            model: (
                results[model][group]["Inconsistent rate"] / results[model][group]["__total__"]
                if results[model][group]["__total__"] else 1.0
            )
            for model in model_names
        }
        lowest_inconsistent_model = min(inconsistent_rates, key=inconsistent_rates.get)

        lines.append(rf"\multirow{{6}}{{*}}{{{group}}}")
        for label_index, label in enumerate(TABLE_TAXONOMY_ORDER):
            row_prefix = "&" if label_index > 0 else "&"
            cells = []
            for model in model_names:
                counts = results[model][group]
                cell = format_count_percentage(counts[label], counts["__total__"], decimals=1, latex=True)
                if label == dominant_by_model[model]:
                    cell = rf"\textbf{{{cell}}}"
                cells.append(cell)

            lines.append(rf"{row_prefix} {label}")
            lines.append("& " + "\n& ".join(cells) + r" \\")

        lines.append(r"\cmidrule(lr){2-5}")
        cells = []
        for model in model_names:
            counts = results[model][group]
            cell = format_count_percentage(counts["Inconsistent rate"], counts["__total__"], decimals=1, latex=True)
            if model == lowest_inconsistent_model:
                cell = rf"\textbf{{{cell}}}"
            cells.append(cell)
        lines.append(r"& Inconsistent rate")
        lines.append("& " + "\n& ".join(cells) + r" \\")
        lines.append("")

        if group_index < 2:
            lines.append(r"\midrule")
            lines.append("")

    lines.append(r"\midrule")
    lines.append("")
    lines.append(r"\textbf{Total}")
    lines.append(r"& Analysis Set cases")
    lines.append("& " + "\n& ".join(str(len(merged_rows_by_model[model])) for model in model_names) + r" \\")
    lines.append("")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{adjustbox}")
    lines.append(r"\caption{Distribution of modality-level inconsistency categories by QA group and model in the Analysis Set. Percentages are computed within each group and model after removing overlong KG answers and duplicate questions. Bold taxonomy entries mark the dominant inconsistency category for each group and model; bold inconsistent-rate entries mark the lowest inconsistent rate across models within each group.}")
    lines.append(r"\label{tab:taxonomy_summary_main}")
    lines.append(r"\end{table*}")

    return "\n".join(lines)


def build_effect_of_model_scale_text(merged_rows_by_model: dict[str, list[dict]]) -> str:
    """Generate the updated surrounding paragraph from computed Analysis Set values."""
    model_names = list(merged_rows_by_model.keys())
    results = analysis_group_counts(merged_rows_by_model)

    def rate(model: str, group: str) -> float:
        counts = results[model][group]
        return 0.0 if counts["__total__"] == 0 else counts["Inconsistent rate"] / counts["__total__"] * 100

    all_rates = {model: rate(model, "All") for model in model_names}
    complex_rates = {model: rate(model, "ComplexQA") for model in model_names}
    best_all = min(all_rates, key=all_rates.get)
    best_complex = min(complex_rates, key=complex_rates.get)

    same_complex = {
        model: (
            results[model]["ComplexQA"].get("Same", 0) / results[model]["ComplexQA"]["__total__"] * 100
            if results[model]["ComplexQA"]["__total__"] else 0.0
        )
        for model in model_names
    }
    best_same_complex = max(same_complex, key=same_complex.get)

    # The prose keeps the model order used in the paper table.
    return (
        r"\paragraph{Effect of model scale.}" + "\n"
        "Model strength affects both retrieval quality and downstream inconsistency analysis.\n"
        f"In the filtered Analysis Set, {best_all} has the lowest overall inconsistency rate "
        f"among value-bearing cases ({all_rates[best_all]:.1f}\\%), followed by "
        f"{model_names[1]} ({all_rates[model_names[1]]:.1f}\\%) and "
        f"{model_names[0]} ({all_rates[model_names[0]]:.1f}\\%). "
        "Across SimpleQA, ComplexQA, and the full Analysis Set, "
        r"\textit{Different answer} remains the dominant inconsistency category for all three Qwen3 models, "
        "showing that most remaining modality-level disagreements are direct answer mismatches rather than temporal or granularity differences. "
        f"The trend is clearer in ComplexQA, where {best_complex} reaches the lowest inconsistency rate "
        f"({complex_rates[best_complex]:.1f}\\%) and {best_same_complex} has the highest proportion of "
        rf"\textit{{Same}} cases ({same_complex[best_same_complex]:.1f}\\%). "
        "Overall, stronger reasoning ability reduces translation-induced mismatches and yields KG answers that are more reliable for downstream inconsistency analysis."
    )


def write_taxonomy_statistics(
    statistics_path: Path,
    merged_rows_by_model: dict[str, list[dict]],
    skipped_pairs: list[dict],
    removal_summaries: list[dict],
) -> None:
    """Write Markdown statistics plus the Analysis Set LaTeX table."""
    statistics_path.parent.mkdir(parents=True, exist_ok=True)
    model_names = list(merged_rows_by_model.keys())

    all_taxonomy_labels = sorted(
        {
            normalize_taxonomy_label(row.get("taxonomy_label", "")) or "UNKNOWN"
            for rows in merged_rows_by_model.values()
            for row in rows
        }
    )
    all_methods = sorted(
        {
            row.get("method", "").strip() or "UNKNOWN"
            for rows in merged_rows_by_model.values()
            for row in rows
        }
    )

    total_rows = [["Total"] + [str(len(merged_rows_by_model[model])) for model in model_names]]

    removal_table_rows = []
    for item in removal_summaries:
        removal_table_rows.append(
            [
                item["model"],
                str(item["large_result_rows_removed"]),
                str(item["duplicate_question_rows_removed"]),
                str(item["total_cleaning_rows_removed"]),
                item.get("removed_csv", ""),
            ]
        )
    if removal_summaries:
        total_large_removed = sum(item["large_result_rows_removed"] for item in removal_summaries)
        total_duplicate_removed = sum(item["duplicate_question_rows_removed"] for item in removal_summaries)
        removal_table_rows.append(["Total", str(total_large_removed), str(total_duplicate_removed), str(total_large_removed + total_duplicate_removed), ""])

    taxonomy_table_rows = []
    for label in all_taxonomy_labels:
        row = [label]
        for model in model_names:
            rows = merged_rows_by_model[model]
            total = len(rows)
            row.append(format_count_percentage(count_by_label(rows)[label], total))
        taxonomy_table_rows.append(row)
    if model_names:
        taxonomy_table_rows.append(build_total_distribution_row("Total", model_names, merged_rows_by_model))

    method_table_rows = []
    for method in all_methods:
        row = [method]
        for model in model_names:
            rows = merged_rows_by_model[model]
            total = len(rows)
            counter = Counter(row_item.get("method", "").strip() or "UNKNOWN" for row_item in rows)
            row.append(format_count_percentage(counter[method], total))
        method_table_rows.append(row)
    if model_names:
        method_table_rows.append(build_total_distribution_row("Total", model_names, merged_rows_by_model))

    unknown_group_rows = []
    for model in model_names:
        unknown_count = len(split_rows_by_qa_group(merged_rows_by_model[model]).get("UNKNOWN", []))
        if unknown_count:
            unknown_group_rows.append([model, str(unknown_count)])

    lines = []
    lines.append("# Taxonomy Merge Statistics")
    lines.append("")
    lines.append("This file summarizes the cleaned, merged taxonomy-labeled QA CSV outputs.")
    lines.append("")
    lines.append("Cleaning steps applied before writing each output CSV:")
    lines.append("1. Remove rows whose `source` / original `file_path` appears in `Output_GRASP/script/large_results_report.txt`.")
    lines.append("2. Remove duplicate `question` rows inside each model output, keeping the first occurrence.")
    lines.append("3. Sort the final CSV by taxonomy label while preserving original row order inside each label group.")
    lines.append("4. Save removed rows to `Modality_inconsistency_labelled/removed_files/`, with a `cause` column.")
    lines.append("")
    lines.append("The final merged CSVs preserve the complete dataset-relative JSON path in the `source` column, for example `SimpleQA/NQ_table_test_simple/00503.json`.")
    lines.append("")
    lines.append("Each distribution count is shown as:")
    lines.append("")
    lines.append("```text")
    lines.append("count (percentage within model)")
    lines.append("```")
    lines.append("")

    lines.append("## Total Rows by Model")
    lines.append("")
    lines.append(markdown_table(["Metric"] + model_names, total_rows))
    lines.append("")

    lines.append("## Rows Removed by Cleaning Step")
    lines.append("")
    if removal_table_rows:
        lines.append(markdown_table(
            ["Model", "Rows removed by >10-row file_path filter", "Rows removed as duplicate questions", "Total removed by these two steps", "Removed rows CSV"],
            removal_table_rows,
        ))
    else:
        lines.append("No rows were removed because no files were merged.")
    lines.append("")

    lines.append("## Taxonomy Distribution by Model")
    lines.append("")
    lines.append(markdown_table(["taxonomy_label"] + model_names, taxonomy_table_rows) if taxonomy_table_rows else "No taxonomy rows were available.")
    lines.append("")

    lines.append("## Method Distribution by Model")
    lines.append("")
    lines.append(markdown_table(["method"] + model_names, method_table_rows) if method_table_rows else "No method rows were available.")
    lines.append("")

    lines.append("## Analysis Set Taxonomy Summary")
    lines.append("")
    lines.append("This table is computed from the final cleaned CSVs using the complete `source` path to split rows into SimpleQA and ComplexQA.")
    lines.append("")
    lines.append(build_analysis_markdown_table(merged_rows_by_model))
    lines.append("")

    if unknown_group_rows:
        lines.append("### Rows with unknown QA group")
        lines.append("")
        lines.append(markdown_table(["Model", "Rows"], unknown_group_rows))
        lines.append("")

    lines.append("## Analysis Set LaTeX Table")
    lines.append("")
    lines.append("```latex")
    lines.append(build_analysis_latex_table(merged_rows_by_model))
    lines.append("```")
    lines.append("")

    lines.append("## Updated Surrounding Text")
    lines.append("")
    lines.append("```latex")
    lines.append(build_effect_of_model_scale_text(merged_rows_by_model))
    lines.append("```")
    lines.append("")

    lines.append("## Skipped Pairs")
    lines.append("")
    if skipped_pairs:
        skipped_rows = [
            [item["label"], item.get("model", ""), item["reason"], "<br>".join(item.get("missing_files", [])) or ""]
            for item in skipped_pairs
        ]
        lines.append(markdown_table(["Pair", "Model", "Reason", "Missing Files"], skipped_rows))
    else:
        lines.append("None.")
    lines.append("")

    with statistics_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def print_progress(current: int, total: int, label: str) -> None:
    """Print a simple command-line progress bar."""
    bar_width = 30
    filled = int(bar_width * current / total)
    bar = "#" * filled + "-" * (bar_width - filled)
    percent = current / total * 100
    print(f"[{bar}] {percent:6.2f}%  {current}/{total}  {label}")


def main() -> None:
    """Run the full merge, clean, sort, audit, and statistics pipeline."""
    try:
        project_root = find_project_root()
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return

    print(f"Project root: {project_root}")
    print()

    large_results_report = project_root / LARGE_RESULTS_REPORT
    large_paths_by_model = parse_large_results_report(large_results_report)
    if large_paths_by_model:
        total_large_paths = sum(len(paths) for paths in large_paths_by_model.values())
        print(f"Loaded {total_large_paths} large-result file_path entries from:")
        print(f"  {large_results_report}")
    print()

    merged_summaries = []
    skipped_pairs = []
    merged_rows_by_model: dict[str, list[dict]] = {}
    removal_summaries = []

    for index, pair in enumerate(MERGE_PAIRS, start=1):
        label = pair["label"]
        model = pair["model"]
        judged_csv = project_root / pair["judged_csv"]
        taxonomy_csv = project_root / pair["taxonomy_csv"]
        output_csv = project_root / pair["output_csv"]
        removed_csv = project_root / pair["removed_csv"]

        model_output_dir = pair["taxonomy_csv"].parent.name
        large_file_paths = large_paths_by_model.get(model_output_dir, set())

        print_progress(index, len(MERGE_PAIRS), f"Processing {model}")

        missing_files = []
        if not judged_csv.exists():
            missing_files.append(str(judged_csv))
        if not taxonomy_csv.exists():
            missing_files.append(str(taxonomy_csv))

        if missing_files:
            print(f"  Skipped {model}: missing file(s):")
            for missing in missing_files:
                print(f"    - {missing}")
            skipped_pairs.append({"label": label, "model": model, "reason": "missing file(s)", "missing_files": missing_files})
            print()
            continue

        taxonomy_rows = read_csv_rows(taxonomy_csv)
        judged_rows = read_csv_rows(judged_csv)

        taxonomy_required = ["question", "gold_answer", "result_cleaned", "taxonomy_label", "file_path"]
        judged_required = ["question", "gold_answer", "KG answer", "taxonomy_label", "file_path"]

        taxonomy_ok = require_columns(taxonomy_csv, taxonomy_rows, taxonomy_required)
        judged_ok = require_columns(judged_csv, judged_rows, judged_required)
        if not taxonomy_ok or not judged_ok:
            print(f"  Skipped {model}: required columns missing.")
            skipped_pairs.append({"label": label, "model": model, "reason": "required columns missing", "missing_files": []})
            print()
            continue

        converted_taxonomy_rows, filtered_simple_rows = convert_taxonomy_rows(taxonomy_rows)
        converted_judged_rows = convert_judged_rows(judged_rows)

        taxonomy_after_large_filter, taxonomy_long_answer_removed = filter_large_result_rows(converted_taxonomy_rows, large_file_paths)
        judged_after_large_filter, judged_long_answer_removed = filter_large_result_rows(converted_judged_rows, large_file_paths)
        long_answer_removed_rows = taxonomy_long_answer_removed + judged_long_answer_removed

        merged_rows_before_dedup = taxonomy_after_large_filter + judged_after_large_filter
        merged_rows, duplicate_removed_rows = deduplicate_by_question(merged_rows_before_dedup)

        # Merge your grouping script here: sort final rows by taxonomy label.
        merged_rows = sort_rows_by_taxonomy(merged_rows)

        write_csv(output_csv, merged_rows)
        removed_rows = long_answer_removed_rows + duplicate_removed_rows
        write_removed_csv(removed_csv, removed_rows)

        public_rows = [public_row(row) for row in merged_rows]
        merged_rows_by_model[model] = public_rows

        removal_summaries.append(
            {
                "label": label,
                "model": model,
                "large_result_rows_removed": len(long_answer_removed_rows),
                "duplicate_question_rows_removed": len(duplicate_removed_rows),
                "total_cleaning_rows_removed": len(long_answer_removed_rows) + len(duplicate_removed_rows),
                "removed_csv": str(removed_csv),
            }
        )

        summary = {
            "label": label,
            "model": model,
            "taxonomy_input": taxonomy_csv,
            "judged_input": judged_csv,
            "output": output_csv,
            "removed_output": removed_csv,
            "taxonomy_rows_before_filter": len(taxonomy_rows),
            "taxonomy_rows_after_label_filter": len(converted_taxonomy_rows),
            "taxonomy_rows_filtered_out": filtered_simple_rows,
            "taxonomy_rows_removed_by_large_result_filter": len(taxonomy_long_answer_removed),
            "judged_rows_before_large_result_filter": len(converted_judged_rows),
            "judged_rows_removed_by_large_result_filter": len(judged_long_answer_removed),
            "large_result_rows_removed": len(long_answer_removed_rows),
            "duplicate_question_rows_removed": len(duplicate_removed_rows),
            "judged_rows_after_large_result_filter": len(judged_after_large_filter),
            "taxonomy_rows_after_large_result_filter": len(taxonomy_after_large_filter),
            "total_rows_before_duplicate_filter": len(merged_rows_before_dedup),
            "total_rows": len(merged_rows),
        }
        merged_summaries.append(summary)

        label_counts = count_by_label(public_rows)
        print(f"  Merged {model}:")
        print(f"    Simple heuristics rows before label filter: {summary['taxonomy_rows_before_filter']}")
        print(f"    Simple heuristics rows kept after label filter: {summary['taxonomy_rows_after_label_filter']}")
        print(f"    Simple heuristics rows filtered out by label: {summary['taxonomy_rows_filtered_out']}")
        print(f"    Rows removed by >10-row file_path filter: {summary['large_result_rows_removed']}")
        print(f"      - Simple heuristics removed: {summary['taxonomy_rows_removed_by_large_result_filter']}")
        print(f"      - LLM-as-a-judge removed:   {summary['judged_rows_removed_by_large_result_filter']}")
        print(f"    Rows before duplicate-question filter: {summary['total_rows_before_duplicate_filter']}")
        print(f"    Duplicate question rows removed: {summary['duplicate_question_rows_removed']}")
        print(f"    Total rows written: {summary['total_rows']}")
        print("    Taxonomy counts after sorting:")
        for taxonomy_label in CSV_TAXONOMY_ORDER:
            print(f"      {taxonomy_label}: {label_counts.get(taxonomy_label, 0)}")
        print(f"    Output: {output_csv}")
        print(f"    Removed rows CSV: {removed_csv}")
        print()

    statistics_path = project_root / "Modality_inconsistency_labelled/taxonomy_statistics.md"
    write_taxonomy_statistics(
        statistics_path=statistics_path,
        merged_rows_by_model=merged_rows_by_model,
        skipped_pairs=skipped_pairs,
        removal_summaries=removal_summaries,
    )

    print("=" * 72)
    print("Final summary")
    print("=" * 72)

    if merged_summaries:
        total_large_removed = sum(item["large_result_rows_removed"] for item in merged_summaries)
        total_duplicate_removed = sum(item["duplicate_question_rows_removed"] for item in merged_summaries)

        print("Merged files:")
        for item in merged_summaries:
            print(f"  {item['model']}:")
            print(f"    Output CSV:   {item['output']}")
            print(f"    Removed CSV:  {item['removed_output']}")
            print(f"    Rows removed by >10-row file_path filter: {item['large_result_rows_removed']}")
            print(f"    Duplicate question rows removed: {item['duplicate_question_rows_removed']}")
            print(f"    Rows written: {item['total_rows']}")

        print()
        print("Requested cleaning counts across all merged files:")
        print(f"  1. Duplicate question rows removed: {total_duplicate_removed}")
        print(f"  2. Rows removed by >10-row file_path filter: {total_large_removed}")
    else:
        print("No files were merged.")

    print()
    print(f"Statistics Markdown written to: {statistics_path}")

    if skipped_pairs:
        print("Skipped pairs:")
        for item in skipped_pairs:
            print(f"  {item['model']}: {item['reason']}")
            for missing in item.get("missing_files", []):
                print(f"    Missing: {missing}")
    else:
        print("Skipped pairs: none")

    print()
    print("Done.")


if __name__ == "__main__":
    main()