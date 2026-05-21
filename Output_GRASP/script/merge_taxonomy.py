#!/usr/bin/env python3
"""
merge_taxonomy_csvs.py

Summary
-------
This script merges taxonomy-labeled QA rows for three Qwen model outputs and
writes one cleaned CSV per model plus a Markdown statistics report.

What the script does for each model:
1. Reads the Simple-heuristics taxonomy CSV and the LLM-as-a-judge CSV.
2. Drops Simple-heuristics rows whose taxonomy_label is different_unclassified.
3. Removes rows whose file_path appears in
   Output_GRASP/script/large_results_report.txt, where the report identifies
   JSON files with more than 10 answer/result rows.
4. Merges the two sources into one shared output schema.
5. Removes duplicate question rows inside each output CSV, keeping the first
   row encountered.
6. Writes cleaned outputs to Modality_inconsistency_labelled/.
7. Writes one removed-rows CSV per model to
   Modality_inconsistency_labelled/removed_files/.
8. Prints and saves removal counts for:
   - rows removed because their file_path appeared in large_results_report.txt
   - duplicate question rows removed

Run directly with:

    python merge_taxonomy_csvs.py

No command-line arguments are required.
"""

from pathlib import Path
import csv
import re
from collections import Counter


# ---------------------------------------------------------------------------
# Output columns for each merged CSV.
#
# Every merged output CSV will contain these columns in this exact order.
# Internal helper keys, such as _file_path, are removed before writing.
# ---------------------------------------------------------------------------
OUTPUT_COLUMNS = [
    "question",
    "gold_answer",
    "KG answer",
    "taxonomy_label",
    "method",
    "source",
]


# ---------------------------------------------------------------------------
# Output columns for each removed-rows audit CSV.
#
# These files contain the same public columns as the final merged CSVs, plus a
# cause column explaining why each row was removed: duplicate or long answer.
# ---------------------------------------------------------------------------
REMOVED_OUTPUT_COLUMNS = OUTPUT_COLUMNS + ["cause"]


# ---------------------------------------------------------------------------
# Report containing JSON files whose result row count is greater than 10.
#
# Rows whose file_path appears in this report are removed before duplicate
# question removal. The script parses the "Matching files" section and uses the
# path ending in .json as the file_path key.
# ---------------------------------------------------------------------------
LARGE_RESULTS_REPORT = Path("Output_GRASP/script/large_results_report.txt")


# ---------------------------------------------------------------------------
# Input/output configuration for each model.
#
# Each dictionary describes:
# - label: short name used in logs
# - model: full model name used in statistics tables
# - judged_csv: CSV produced by LLM-as-a-judge
# - taxonomy_csv: CSV produced by simple heuristic taxonomy labeling
# - output_csv: cleaned merged output CSV for that model
# ---------------------------------------------------------------------------
MERGE_PAIRS = [
    {
        "label": "4B",
        "model": "Qwen3-4B-Instruct",
        "judged_csv": Path("LLM_as_a_Judge/4B_judged_filtered.csv"),
        "taxonomy_csv": Path("Output_GRASP/Qwen3-4B-Instruct-2507/all_valid_cases_with_taxonomy.csv"),
        "output_csv": Path("Modality_inconsistency_labelled/merged_taxonomy_answers_4B.csv"),
        "removed_csv": Path("Modality_inconsistency_labelled/removed_files/removed_rows_4B.csv"),
    },
    {
        "label": "30B",
        "model": "Qwen3-30B-Thinking",
        "judged_csv": Path("LLM_as_a_Judge/30B_judged_filtered.csv"),
        "taxonomy_csv": Path("Output_GRASP/Qwen3-30B-A3B-Thinking-2507/all_valid_cases_with_taxonomy.csv"),
        "output_csv": Path("Modality_inconsistency_labelled/merged_taxonomy_answers_30B.csv"),
        "removed_csv": Path("Modality_inconsistency_labelled/removed_files/removed_rows_30B.csv"),
    },
    {
        "label": "235B",
        "model": "Qwen3-235B-Thinking",
        "judged_csv": Path("LLM_as_a_Judge/235B_judged_filtered.csv"),
        "taxonomy_csv": Path("Output_GRASP/Qwen3-235B-A22B-Thinking-2507-AWQ/all_valid_cases_with_taxonomy.csv"),
        "output_csv": Path("Modality_inconsistency_labelled/merged_taxonomy_answers_235B.csv"),
        "removed_csv": Path("Modality_inconsistency_labelled/removed_files/removed_rows_235B.csv"),
    },
]


def find_project_root() -> Path:
    """
    Locate the project root.

    This allows the script to run from either:
    1. The project root directory, where Output_GRASP exists with a judge folder.
    2. The Output_GRASP directory, whose parent is the project root.

    Both judge-folder spellings are supported:
    - LLM_as_a_Judge
    - LLM-as-Judge

    Returns:
        Path: Resolved project root path.

    Raises:
        RuntimeError: If the project root cannot be found.
    """
    cwd = Path.cwd().resolve()
    judge_dir_names = ["LLM_as_a_Judge", "LLM-as-Judge"]

    # Case 1: script is run from the project root.
    for judge_dir_name in judge_dir_names:
        if (cwd / judge_dir_name).is_dir() and (cwd / "Output_GRASP").is_dir():
            return cwd

    # Case 2: script is run from Output_GRASP.
    if cwd.name == "Output_GRASP":
        parent = cwd.parent
        for judge_dir_name in judge_dir_names:
            if (parent / judge_dir_name).is_dir() and (parent / "Output_GRASP").is_dir():
                return parent

    raise RuntimeError(
        "Could not locate project root. "
        "Run this script from the project root or from the Output_GRASP directory. "
        "Expected Output_GRASP plus one of: LLM_as_a_Judge, LLM-as-Judge."
    )


def normalize_taxonomy_label(label: str) -> str:
    """
    Normalize taxonomy labels so equivalent labels are counted together.

    Current normalization:
    - same -> Same

    Args:
        label: Raw taxonomy label from the input CSV.

    Returns:
        str: Normalized taxonomy label.
    """
    label = (label or "").strip()

    # Keep the existing canonical spelling for the Same class.
    if label.lower() == "same":
        return "Same"

    return label


def should_keep_simple_heuristics_row(label: str) -> bool:
    """
    Decide whether a row from all_valid_cases_with_taxonomy.csv should be kept.

    Rows labeled different_unclassified are excluded from the Simple heuristics
    source, because they are not considered valid taxonomy-labeled cases.

    Args:
        label: Raw taxonomy_label value.

    Returns:
        bool: True if the row should be kept, False otherwise.
    """
    normalized = (label or "").strip().lower()
    return normalized != "different_unclassified"


def normalize_file_path_key(file_path_value: str) -> str:
    """
    Normalize a file_path value so CSV rows and report rows can be matched.

    The large-results report stores paths such as:
        SimpleQA/NQ_table_test_simple/00925.json

    Input CSVs may store the same value directly or inside a longer absolute
    path. This function keeps the suffix starting at SimpleQA/ or ComplexQA/.

    Args:
        file_path_value: Raw file path from a CSV or report line.

    Returns:
        str: Comparable normalized key, or an empty string if no path is given.
    """
    if not file_path_value:
        return ""

    # Normalize Windows-style separators before matching path components.
    normalized = str(file_path_value).strip().replace("\\", "/")

    # Prefer the dataset-relative suffix because that is what the report uses.
    match = re.search(r"(?:^|/)((?:SimpleQA|ComplexQA)/[^\s]+\.json)$", normalized)
    if match:
        return match.group(1)

    # Fall back to the normalized path when it is already relative.
    return normalized


def parse_large_results_report(report_path: Path) -> dict[str, set[str]]:
    """
    Parse Output_GRASP/script/large_results_report.txt.

    The returned dictionary maps each model output directory name to the set of
    JSON file_path keys whose answer/result row count is greater than 10.

    Args:
        report_path: Absolute path to large_results_report.txt.

    Returns:
        dict[str, set[str]]: {model_directory_name: {normalized file_path keys}}.
    """
    large_paths_by_model: dict[str, set[str]] = {}

    # The report is optional in the sense that the script should still run and
    # report zero large-result removals if the file is missing.
    if not report_path.exists():
        print(f"WARNING: Large-results report not found: {report_path}")
        print("         No rows will be removed by large-result file_path filtering.")
        return large_paths_by_model

    # Example matching line:
    # Qwen3-235B-A22B-Thinking-2507-AWQ  29 rows  ...  ComplexQA/.../00128.json
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

            # Store only the normalized relative JSON path for reliable matching.
            model_dir = match.group("model")
            file_path_key = normalize_file_path_key(match.group("file_path"))
            large_paths_by_model.setdefault(model_dir, set()).add(file_path_key)

    return large_paths_by_model


def extract_source(file_path_value: str) -> str:
    """
    Extract a dataset/source name from a file path.

    Example:
        SimpleQA/NQ_table_test_simple/00501.json

    Becomes:
        NQ_table

    The function:
    1. Normalizes Windows-style backslashes to forward slashes.
    2. Uses the middle path component when possible.
    3. Removes common suffixes such as _test_simple, _complex, and _qa.

    Args:
        file_path_value: Raw file_path string from the input CSV.

    Returns:
        str: Cleaned source name.
    """
    if not file_path_value:
        return ""

    normalized = file_path_value.replace("\\", "/")
    parts = [p for p in normalized.split("/") if p]

    # Prefer the second path component when available.
    if len(parts) >= 2:
        source = parts[1]
    elif parts:
        source = parts[0]
    else:
        return ""

    # Common suffixes to remove from source directory names.
    suffix_patterns = [
        r"_test_simple$",
        r"_test_complex$",
        r"_simple_qa$",
        r"_complex_qa$",
        r"_simple$",
        r"_complex$",
        r"_test$",
        r"_qa$",
    ]

    # Keep removing suffixes until no more changes are made.
    # This handles names that may contain multiple removable suffixes.
    changed = True
    while changed:
        changed = False
        for pattern in suffix_patterns:
            new_source = re.sub(pattern, "", source)
            if new_source != source:
                source = new_source
                changed = True

    return source


def read_csv_rows(csv_path: Path) -> list[dict]:
    """
    Read a CSV file into a list of dictionaries.

    utf-8-sig is used so files with a UTF-8 BOM are handled correctly.

    Args:
        csv_path: Path to the CSV file.

    Returns:
        list[dict]: CSV rows as dictionaries.
    """
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def require_columns(csv_path: Path, rows: list[dict], required_columns: list[str]) -> bool:
    """
    Check whether a CSV contains all required columns.

    If the CSV has no rows, this returns True because there is no row header
    dictionary to inspect. Empty files are handled later by producing empty
    outputs/statistics.

    Args:
        csv_path: Path to the CSV being checked.
        rows: Rows read from the CSV.
        required_columns: Required column names.

    Returns:
        bool: True if all required columns are present, False otherwise.
    """
    if not rows:
        return True

    missing = [col for col in required_columns if col not in rows[0]]
    if missing:
        print(f"  Missing required columns in {csv_path}: {', '.join(missing)}")
        return False

    return True


def convert_taxonomy_rows(rows: list[dict]) -> tuple[list[dict], int]:
    """
    Convert rows from all_valid_cases_with_taxonomy.csv into OUTPUT_COLUMNS.

    Important behavior:
    - Keep only rows whose taxonomy_label is not different_unclassified.
    - Normalize taxonomy_label values, for example same -> Same.
    - Mark these rows as method = Simple heuristics.
    - Use result_cleaned as the KG answer.
    - Preserve an internal _file_path key for large-result filtering.

    Args:
        rows: Raw CSV rows from all_valid_cases_with_taxonomy.csv.

    Returns:
        tuple[list[dict], int]: Converted rows and number of rows filtered out
        because they were different_unclassified.
    """
    converted = []
    filtered_out = 0

    for row in rows:
        raw_label = row.get("taxonomy_label", "")

        # Exclude simple-heuristics rows that were not assigned a usable class.
        if not should_keep_simple_heuristics_row(raw_label):
            filtered_out += 1
            continue

        taxonomy_label = normalize_taxonomy_label(raw_label)
        file_path = row.get("file_path", "")

        converted.append(
            {
                "question": row.get("question", ""),
                "gold_answer": row.get("gold_answer", ""),
                "KG answer": row.get("result_cleaned", ""),
                "taxonomy_label": taxonomy_label,
                "method": "Simple heuristics",
                "source": extract_source(file_path),
                "_file_path": normalize_file_path_key(file_path),
            }
        )

    return converted, filtered_out


def convert_judged_rows(rows: list[dict]) -> list[dict]:
    """
    Convert rows from *_judged.csv into OUTPUT_COLUMNS.

    Important behavior:
    - Normalize taxonomy_label values, for example same -> Same.
    - Do not filter out different_unclassified here.
    - Mark these rows as method = LLM-as-a-judge.
    - Preserve an internal _file_path key for large-result filtering.

    Args:
        rows: Raw CSV rows from the judged CSV.

    Returns:
        list[dict]: Converted rows in the shared output schema.
    """
    converted = []

    for row in rows:
        taxonomy_label = normalize_taxonomy_label(row.get("taxonomy_label", ""))
        file_path = row.get("file_path", "")

        converted.append(
            {
                "question": row.get("question", ""),
                "gold_answer": row.get("gold_answer", ""),
                "KG answer": row.get("KG answer", ""),
                "taxonomy_label": taxonomy_label,
                "method": "LLM-as-a-judge",
                "source": extract_source(file_path),
                "_file_path": normalize_file_path_key(file_path),
            }
        )

    return converted


def add_removal_cause(row: dict, cause: str) -> dict:
    """
    Convert an internal row into a removed-row audit record.

    Args:
        row: Converted row that may contain helper keys such as _file_path.
        cause: Human-readable removal reason. Expected values are duplicate or
            long answer.

    Returns:
        dict: Removed-row record restricted to REMOVED_OUTPUT_COLUMNS.
    """
    removed_row = {column: row.get(column, "") for column in OUTPUT_COLUMNS}
    removed_row["cause"] = cause
    return removed_row


def filter_large_result_rows(
    rows: list[dict],
    large_file_paths: set[str],
) -> tuple[list[dict], list[dict]]:
    """
    Remove rows whose internal _file_path appears in large_results_report.txt.

    Removed rows are returned with cause = long answer.

    Args:
        rows: Converted rows containing an internal _file_path key.
        large_file_paths: Set of normalized file_path values to remove.

    Returns:
        tuple[list[dict], list[dict]]: Kept rows and removed-row audit records.
    """
    kept_rows = []
    removed_rows = []

    for row in rows:
        # _file_path is not written to the final CSV; it is only used here.
        if row.get("_file_path", "") in large_file_paths:
            removed_rows.append(add_removal_cause(row, "long answer"))
            continue

        kept_rows.append(row)

    return kept_rows, removed_rows


def deduplicate_by_question(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Remove duplicate questions within one model's merged output.

    The first occurrence of each question is kept, and later rows with the same
    normalized question string are removed. Removed rows are returned with
    cause = duplicate. This guarantees that each output CSV contains unique
    question values.

    Args:
        rows: Merged rows for one output CSV.

    Returns:
        tuple[list[dict], list[dict]]: Deduplicated rows and removed-row audit
        records.
    """
    seen_questions = set()
    deduplicated_rows = []
    removed_rows = []

    for row in rows:
        # Strip surrounding whitespace so accidental leading/trailing spaces do
        # not create fake unique questions.
        question_key = (row.get("question", "") or "").strip()

        if question_key in seen_questions:
            removed_rows.append(add_removal_cause(row, "duplicate"))
            continue

        seen_questions.add(question_key)
        deduplicated_rows.append(row)

    return deduplicated_rows, removed_rows


def strip_internal_columns(rows: list[dict]) -> list[dict]:
    """
    Remove helper keys before writing final CSV files or statistics.

    Args:
        rows: Rows that may contain internal keys such as _file_path.

    Returns:
        list[dict]: Rows restricted to OUTPUT_COLUMNS.
    """
    return [{column: row.get(column, "") for column in OUTPUT_COLUMNS} for row in rows]


def write_csv(csv_path: Path, rows: list[dict]) -> None:
    """
    Write merged rows to a CSV file.

    The parent directory is created automatically if it does not already exist.

    Args:
        csv_path: Output CSV path.
        rows: Rows to write.
    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(strip_internal_columns(rows))


def write_removed_csv(csv_path: Path, rows: list[dict]) -> None:
    """
    Write removed rows to a per-model audit CSV.

    The parent directory is created automatically if it does not already exist.
    The CSV is always written, even when there are zero removed rows, so each
    configured pair has an explicit audit file.

    Args:
        csv_path: Removed-rows CSV path.
        rows: Removed-row audit records containing a cause column.
    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REMOVED_OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(
            {column: row.get(column, "") for column in REMOVED_OUTPUT_COLUMNS}
            for row in rows
        )


def format_count_percentage(count: int, total: int) -> str:
    """
    Format a count and percentage for Markdown tables.

    Example:
        count = 638
        total = 1165

    Returns:
        638 (54.76%)

    Args:
        count: Number of rows in a category.
        total: Total number of rows for the model.

    Returns:
        str: Formatted count and percentage.
    """
    if total == 0:
        return "0 (0.00%)"

    percentage = count / total * 100
    return f"{count} ({percentage:.2f}%)"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    """
    Build a Markdown table.

    Args:
        headers: Column headers.
        rows: Table rows.

    Returns:
        str: Markdown table text.
    """
    lines = []

    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")

    return "\n".join(lines)


def build_total_distribution_row(
    row_label: str,
    model_names: list[str],
    merged_rows_by_model: dict[str, list[dict]],
) -> list[str]:
    """
    Build a Total row for a distribution table.

    Args:
        row_label: Label for the first column, usually "Total".
        model_names: Ordered list of model names.
        merged_rows_by_model: Mapping from model name to merged rows.

    Returns:
        list[str]: A Markdown-table-ready row.
    """
    total_row = [row_label]

    for model in model_names:
        total = len(merged_rows_by_model[model])
        total_row.append(format_count_percentage(total, total))

    return total_row


def write_taxonomy_statistics(
    statistics_path: Path,
    merged_rows_by_model: dict[str, list[dict]],
    skipped_pairs: list[dict],
    removal_summaries: list[dict],
) -> None:
    """
    Write taxonomy, method, and row-removal statistics by model.

    This function writes:
    1. Total Rows by Model
    2. Rows Removed by Cleaning Step
    3. Taxonomy Distribution by Model
    4. Method Distribution by Model
    5. Skipped Pairs

    Args:
        statistics_path: Path to taxonomy_statistics.md.
        merged_rows_by_model: Mapping from model name to final cleaned rows.
        skipped_pairs: Metadata for model pairs skipped due to missing files
            or missing required columns.
        removal_summaries: Per-model counts for large-result and duplicate
            question removals.
    """
    statistics_path.parent.mkdir(parents=True, exist_ok=True)

    # Preserve the insertion order of models from the merge loop.
    model_names = list(merged_rows_by_model.keys())

    # Collect all taxonomy labels that appear in any final merged model output.
    all_taxonomy_labels = sorted(
        {
            normalize_taxonomy_label(row.get("taxonomy_label", "")) or "UNKNOWN"
            for rows in merged_rows_by_model.values()
            for row in rows
        }
    )

    # Collect all method names that appear in any final merged model output.
    all_methods = sorted(
        {
            row.get("method", "").strip() or "UNKNOWN"
            for rows in merged_rows_by_model.values()
            for row in rows
        }
    )

    # Build the taxonomy distribution table.
    taxonomy_table_rows = []
    for taxonomy_label in all_taxonomy_labels:
        table_row = [taxonomy_label]

        for model in model_names:
            rows = merged_rows_by_model[model]
            total = len(rows)
            counter = Counter(
                normalize_taxonomy_label(row.get("taxonomy_label", "")) or "UNKNOWN"
                for row in rows
            )
            table_row.append(format_count_percentage(counter[taxonomy_label], total))

        taxonomy_table_rows.append(table_row)

    # Add a final Total row to the taxonomy table.
    if model_names:
        taxonomy_table_rows.append(
            build_total_distribution_row(
                row_label="Total",
                model_names=model_names,
                merged_rows_by_model=merged_rows_by_model,
            )
        )

    # Build the method distribution table.
    method_table_rows = []
    for method in all_methods:
        table_row = [method]

        for model in model_names:
            rows = merged_rows_by_model[model]
            total = len(rows)
            counter = Counter(row.get("method", "").strip() or "UNKNOWN" for row in rows)
            table_row.append(format_count_percentage(counter[method], total))

        method_table_rows.append(table_row)

    # Add a final Total row to the method table.
    if model_names:
        method_table_rows.append(
            build_total_distribution_row(
                row_label="Total",
                model_names=model_names,
                merged_rows_by_model=merged_rows_by_model,
            )
        )

    # Compact top-level row-count summary.
    total_rows = [
        ["Total"] + [str(len(merged_rows_by_model[model])) for model in model_names]
    ]

    # Per-model removal summary requested by the user.
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
        removal_table_rows.append(
            [
                "Total",
                str(total_large_removed),
                str(total_duplicate_removed),
                str(total_large_removed + total_duplicate_removed),
                "",
            ]
        )

    # Write the Markdown file.
    lines = []
    lines.append("# Taxonomy Merge Statistics")
    lines.append("")
    lines.append("This file summarizes the cleaned, merged taxonomy-labeled QA CSV outputs.")
    lines.append("")
    lines.append("Cleaning steps applied before writing each output CSV:")
    lines.append("1. Remove rows whose `file_path` appears in `Output_GRASP/script/large_results_report.txt`.")
    lines.append("2. Remove duplicate `question` rows inside each model output, keeping the first occurrence.")
    lines.append("3. Save removed rows to `Modality_inconsistency_labelled/removed_files/`, with a `cause` column.")
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
        lines.append(
            markdown_table(
                [
                    "Model",
                    "Rows removed by >10-row file_path filter",
                    "Rows removed as duplicate questions",
                    "Total removed by these two steps",
                    "Removed rows CSV",
                ],
                removal_table_rows,
            )
        )
    else:
        lines.append("No rows were removed because no files were merged.")
    lines.append("")

    lines.append("## Taxonomy Distribution by Model")
    lines.append("")
    if taxonomy_table_rows:
        lines.append(markdown_table(["taxonomy_label"] + model_names, taxonomy_table_rows))
    else:
        lines.append("No taxonomy rows were available.")
    lines.append("")

    lines.append("## Method Distribution by Model")
    lines.append("")
    if method_table_rows:
        lines.append(markdown_table(["method"] + model_names, method_table_rows))
    else:
        lines.append("No method rows were available.")
    lines.append("")

    lines.append("## Skipped Pairs")
    lines.append("")
    if skipped_pairs:
        skipped_rows = []
        for item in skipped_pairs:
            skipped_rows.append(
                [
                    item["label"],
                    item.get("model", ""),
                    item["reason"],
                    "<br>".join(item.get("missing_files", [])) or "",
                ]
            )

        lines.append(
            markdown_table(
                ["Pair", "Model", "Reason", "Missing Files"],
                skipped_rows,
            )
        )
    else:
        lines.append("None.")
    lines.append("")

    with statistics_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def print_progress(current: int, total: int, label: str) -> None:
    """
    Print a simple command-line progress bar.

    Args:
        current: Current item number.
        total: Total number of items.
        label: Text label for the current step.
    """
    bar_width = 30
    filled = int(bar_width * current / total)
    bar = "#" * filled + "-" * (bar_width - filled)
    percent = current / total * 100
    print(f"[{bar}] {percent:6.2f}%  {current}/{total}  {label}")


def main() -> None:
    """
    Main execution flow.

    For each configured model:
    1. Locate input CSV files.
    2. Validate required columns.
    3. Convert simple-heuristics rows.
    4. Convert LLM-as-a-judge rows.
    5. Remove rows with file_path listed in large_results_report.txt.
    6. Merge both row sets.
    7. Remove duplicate question rows from the merged output.
    8. Write the cleaned merged CSV.
    9. Write the removed-rows audit CSV for this model.
    10. Collect rows and removal counts for Markdown statistics.

    After all models are processed:
    1. Write taxonomy_statistics.md.
    2. Print a final summary to the terminal.
    """
    try:
        project_root = find_project_root()
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return

    print(f"Project root: {project_root}")
    print()

    # Load the >10-row file_path removal index once and reuse it for all models.
    large_results_report = project_root / LARGE_RESULTS_REPORT
    large_paths_by_model = parse_large_results_report(large_results_report)

    if large_paths_by_model:
        total_large_file_paths = sum(len(paths) for paths in large_paths_by_model.values())
        print(f"Loaded {total_large_file_paths} large-result file_path entries from:")
        print(f"  {large_results_report}")
    print()

    merged_summaries = []
    skipped_pairs = []
    merged_rows_by_model = {}
    removal_summaries = []

    total_pairs = len(MERGE_PAIRS)

    for index, pair in enumerate(MERGE_PAIRS, start=1):
        label = pair["label"]
        model = pair["model"]

        judged_csv = project_root / pair["judged_csv"]
        taxonomy_csv = project_root / pair["taxonomy_csv"]
        output_csv = project_root / pair["output_csv"]
        removed_csv = project_root / pair["removed_csv"]

        # The taxonomy CSV parent directory matches the model names used in the
        # large-results report, for example Qwen3-4B-Instruct-2507.
        model_output_dir = pair["taxonomy_csv"].parent.name
        large_file_paths = large_paths_by_model.get(model_output_dir, set())

        print_progress(index, total_pairs, f"Processing {model}")

        missing_files = []

        # The judged CSV is required for this model.
        if not judged_csv.exists():
            missing_files.append(str(judged_csv))

        # The taxonomy CSV is required for this model.
        if not taxonomy_csv.exists():
            missing_files.append(str(taxonomy_csv))

        # Skip this model if either input file is missing.
        if missing_files:
            print(f"  Skipped {model}: missing file(s):")
            for missing in missing_files:
                print(f"    - {missing}")

            skipped_pairs.append(
                {
                    "label": label,
                    "model": model,
                    "reason": "missing file(s)",
                    "missing_files": missing_files,
                }
            )
            print()
            continue

        # Read both input CSVs into dictionaries.
        taxonomy_rows = read_csv_rows(taxonomy_csv)
        judged_rows = read_csv_rows(judged_csv)

        # Required columns for the simple-heuristics taxonomy CSV.
        taxonomy_required = [
            "question",
            "gold_answer",
            "result_cleaned",
            "taxonomy_label",
            "file_path",
        ]

        # Required columns for the LLM-as-a-judge CSV.
        judged_required = [
            "question",
            "gold_answer",
            "KG answer",
            "taxonomy_label",
            "file_path",
        ]

        taxonomy_ok = require_columns(taxonomy_csv, taxonomy_rows, taxonomy_required)
        judged_ok = require_columns(judged_csv, judged_rows, judged_required)

        # Skip this model if required columns are missing.
        if not taxonomy_ok or not judged_ok:
            print(f"  Skipped {model}: required columns missing.")

            skipped_pairs.append(
                {
                    "label": label,
                    "model": model,
                    "reason": "required columns missing",
                    "missing_files": [],
                }
            )

            print()
            continue

        # Convert rows to the shared output schema while keeping _file_path for filtering.
        converted_taxonomy_rows, filtered_simple_rows = convert_taxonomy_rows(taxonomy_rows)
        converted_judged_rows = convert_judged_rows(judged_rows)

        # Remove rows whose original file_path appears in the >10-row report.
        taxonomy_after_large_filter, taxonomy_long_answer_removed_rows = filter_large_result_rows(
            converted_taxonomy_rows,
            large_file_paths,
        )
        judged_after_large_filter, judged_long_answer_removed_rows = filter_large_result_rows(
            converted_judged_rows,
            large_file_paths,
        )
        long_answer_removed_rows = taxonomy_long_answer_removed_rows + judged_long_answer_removed_rows
        large_result_rows_removed = len(long_answer_removed_rows)

        # Merge Simple heuristics and LLM-as-a-judge rows after file_path filtering.
        merged_rows_before_dedup = taxonomy_after_large_filter + judged_after_large_filter

        # Remove duplicate questions so each output CSV contains only unique questions.
        merged_rows, duplicate_removed_rows = deduplicate_by_question(
            merged_rows_before_dedup
        )
        duplicate_question_rows_removed = len(duplicate_removed_rows)

        # Write the cleaned output CSV.
        write_csv(output_csv, merged_rows)

        # Write all rows removed by the two requested cleaning steps.
        removed_rows = long_answer_removed_rows + duplicate_removed_rows
        write_removed_csv(removed_csv, removed_rows)

        # Store final rows for later Markdown statistics.
        merged_rows_by_model[model] = strip_internal_columns(merged_rows)

        # Store removal counts for taxonomy_statistics.md.
        removal_summaries.append(
            {
                "label": label,
                "model": model,
                "large_result_rows_removed": large_result_rows_removed,
                "duplicate_question_rows_removed": duplicate_question_rows_removed,
                "total_cleaning_rows_removed": large_result_rows_removed + duplicate_question_rows_removed,
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
            "taxonomy_rows_removed_by_large_result_filter": len(taxonomy_long_answer_removed_rows),
            "judged_rows_before_large_result_filter": len(converted_judged_rows),
            "judged_rows_removed_by_large_result_filter": len(judged_long_answer_removed_rows),
            "large_result_rows_removed": large_result_rows_removed,
            "duplicate_question_rows_removed": duplicate_question_rows_removed,
            "judged_rows_after_large_result_filter": len(judged_after_large_filter),
            "taxonomy_rows_after_large_result_filter": len(taxonomy_after_large_filter),
            "total_rows_before_duplicate_filter": len(merged_rows_before_dedup),
            "total_rows": len(merged_rows),
        }

        merged_summaries.append(summary)

        print(f"  Merged {model}:")
        print(f"    Simple heuristics rows before label filter: {summary['taxonomy_rows_before_filter']}")
        print(f"    Simple heuristics rows kept after label filter: {summary['taxonomy_rows_after_label_filter']}")
        print(f"    Simple heuristics rows filtered out by label: {summary['taxonomy_rows_filtered_out']}")
        print(f"    Rows removed by >10-row file_path filter: {summary['large_result_rows_removed']}")
        print(f"      - Simple heuristics removed: {summary['taxonomy_rows_removed_by_large_result_filter']}")
        print(f"      - LLM-as-a-judge removed:   {summary['judged_rows_removed_by_large_result_filter']}")
        print(f"    LLM-as-a-judge rows after >10-row filter: {summary['judged_rows_after_large_result_filter']}")
        print(f"    Rows before duplicate-question filter: {summary['total_rows_before_duplicate_filter']}")
        print(f"    Duplicate question rows removed: {summary['duplicate_question_rows_removed']}")
        print(f"    Total rows written: {summary['total_rows']}")
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
            print(f"    Taxonomy CSV: {item['taxonomy_input']}")
            print(f"    Judged CSV:   {item['judged_input']}")
            print(f"    Output CSV:   {item['output']}")
            print(f"    Removed CSV:  {item['removed_output']}")
            print(f"    Simple heuristics rows kept after label filter: {item['taxonomy_rows_after_label_filter']}")
            print(f"    Simple heuristics rows filtered out by label: {item['taxonomy_rows_filtered_out']}")
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
    print()

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