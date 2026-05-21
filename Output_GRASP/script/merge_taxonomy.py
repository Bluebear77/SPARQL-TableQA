#!/usr/bin/env python3
"""
merge_taxonomy_csvs.py

Merge taxonomy-labeled QA CSV files for multiple Qwen model outputs and
write summary statistics to taxonomy_statistics.md.

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
# Rows from both input sources are converted into this shared schema.
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
# Input/output configuration for each model.
#
# Each dictionary describes:
# - label: short name used in logs
# - model: full model name used in statistics tables
# - judged_csv: CSV produced by LLM-as-a-judge
# - taxonomy_csv: CSV produced by simple heuristic taxonomy labeling
# - output_csv: merged output CSV for that model
# ---------------------------------------------------------------------------
MERGE_PAIRS = [
    {
        "label": "4B",
        "model": "Qwen3-4B-Instruct",
        "judged_csv": Path("LLM-as-Judge/4B_judged_filtered.csv"),
        "taxonomy_csv": Path("Output_GRASP/Qwen3-4B-Instruct-2507/all_valid_cases_with_taxonomy.csv"),
        "output_csv": Path("Output_GRASP/merged_taxonomy_answers_4B.csv"),
    },
    {
        "label": "30B",
        "model": "Qwen3-30B-Thinking",
        "judged_csv": Path("LLM-as-Judge/30B_judged_filtered.csv"),
        "taxonomy_csv": Path("Output_GRASP/Qwen3-30B-A3B-Thinking-2507/all_valid_cases_with_taxonomy.csv"),
        "output_csv": Path("Output_GRASP/merged_taxonomy_answers_30B.csv"),
    },
    {
        "label": "235B",
        "model": "Qwen3-235B-Thinking",
        "judged_csv": Path("LLM-as-Judge/235B_judged_filtered.csv"),
        "taxonomy_csv": Path("Output_GRASP/Qwen3-235B-A22B-Thinking-2507-AWQ/all_valid_cases_with_taxonomy.csv"),
        "output_csv": Path("Output_GRASP/merged_taxonomy_answers_235B.csv"),
    },
]


def find_project_root() -> Path:
    """
    Locate the SPARQL-TableQA project root.

    This allows the script to run from either:
    1. The project root directory, where both LLM-as-Judge and Output_GRASP exist.
    2. The Output_GRASP directory, whose parent is the project root.

    Returns:
        Path: Resolved project root path.

    Raises:
        RuntimeError: If the project root cannot be found.
    """
    cwd = Path.cwd().resolve()

    # Case 1: script is run from the project root.
    if (cwd / "LLM-as-Judge").is_dir() and (cwd / "Output_GRASP").is_dir():
        return cwd

    # Case 2: script is run from Output_GRASP.
    if cwd.name == "Output_GRASP":
        parent = cwd.parent
        if (parent / "LLM-as-Judge").is_dir() and (parent / "Output_GRASP").is_dir():
            return parent

    raise RuntimeError(
        "Could not locate SPARQL-TableQA project root. "
        "Run this script from the project root or from the Output_GRASP directory."
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


def convert_taxonomy_rows(rows: list[dict]) -> list[dict]:
    """
    Convert rows from all_valid_cases_with_taxonomy.csv into OUTPUT_COLUMNS.

    Important behavior:
    - Keep only rows whose taxonomy_label is not different_unclassified.
    - Normalize taxonomy_label values, for example same -> Same.
    - Mark these rows as method = Simple heuristics.
    - Use result_cleaned as the KG answer.

    Args:
        rows: Raw CSV rows from all_valid_cases_with_taxonomy.csv.

    Returns:
        list[dict]: Converted rows in the shared output schema.
    """
    converted = []

    for row in rows:
        raw_label = row.get("taxonomy_label", "")

        # Exclude simple-heuristics rows that were not assigned a usable class.
        if not should_keep_simple_heuristics_row(raw_label):
            continue

        taxonomy_label = normalize_taxonomy_label(raw_label)

        converted.append(
            {
                "question": row.get("question", ""),
                "gold_answer": row.get("gold_answer", ""),
                "KG answer": row.get("result_cleaned", ""),
                "taxonomy_label": taxonomy_label,
                "method": "Simple heuristics",
                "source": extract_source(row.get("file_path", "")),
            }
        )

    return converted


def convert_judged_rows(rows: list[dict]) -> list[dict]:
    """
    Convert rows from *_judged.csv into OUTPUT_COLUMNS.

    Important behavior:
    - Normalize taxonomy_label values, for example same -> Same.
    - Do not filter out different_unclassified here.
    - Mark these rows as method = LLM-as-a-judge.

    Args:
        rows: Raw CSV rows from the judged CSV.

    Returns:
        list[dict]: Converted rows in the shared output schema.
    """
    converted = []

    for row in rows:
        taxonomy_label = normalize_taxonomy_label(row.get("taxonomy_label", ""))

        converted.append(
            {
                "question": row.get("question", ""),
                "gold_answer": row.get("gold_answer", ""),
                "KG answer": row.get("KG answer", ""),
                "taxonomy_label": taxonomy_label,
                "method": "LLM-as-a-judge",
                "source": extract_source(row.get("file_path", "")),
            }
        )

    return converted


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
        writer.writerows(rows)


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
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def build_total_distribution_row(
    row_label: str,
    model_names: list[str],
    merged_rows_by_model: dict[str, list[dict]],
) -> list[str]:
    """
    Build a Total row for a distribution table.

    This row is useful inside tables such as:
    - Taxonomy Distribution by Model
    - Method Distribution by Model

    For each model, the total cell is shown as:
        total_count (100.00%)

    Example:
        ["Total", "1165 (100.00%)", "1278 (100.00%)", "1453 (100.00%)"]

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
) -> None:
    """
    Write taxonomy and method distribution tables by model.

    This function writes:
    1. Total Rows by Model
    2. Taxonomy Distribution by Model
    3. Method Distribution by Model
    4. Skipped Pairs

    Each distribution table cell is formatted as:
        count (percentage within model)

    New behavior:
    - The Taxonomy Distribution by Model table now includes a final Total row.
    - The Method Distribution by Model table now includes a final Total row.

    Args:
        statistics_path: Path to taxonomy_statistics.md.
        merged_rows_by_model: Mapping from model name to merged rows.
        skipped_pairs: Metadata for model pairs skipped due to missing files
            or missing required columns.
    """
    statistics_path.parent.mkdir(parents=True, exist_ok=True)

    # Preserve the insertion order of models from the merge loop.
    model_names = list(merged_rows_by_model.keys())

    # Collect all taxonomy labels that appear in any merged model output.
    all_taxonomy_labels = sorted(
        {
            normalize_taxonomy_label(row.get("taxonomy_label", "")) or "UNKNOWN"
            for rows in merged_rows_by_model.values()
            for row in rows
        }
    )

    # Collect all method names that appear in any merged model output.
    all_methods = sorted(
        {
            row.get("method", "").strip() or "UNKNOWN"
            for rows in merged_rows_by_model.values()
            for row in rows
        }
    )

    # -----------------------------------------------------------------------
    # Build the taxonomy distribution table.
    #
    # Rows are taxonomy labels.
    # Columns are models.
    # Each cell is count plus percentage within that model.
    # -----------------------------------------------------------------------
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
    # This makes the table self-contained and allows readers to quickly verify
    # that the percentages sum to 100% for each model.
    if model_names:
        taxonomy_table_rows.append(
            build_total_distribution_row(
                row_label="Total",
                model_names=model_names,
                merged_rows_by_model=merged_rows_by_model,
            )
        )

    # -----------------------------------------------------------------------
    # Build the method distribution table.
    #
    # Rows are methods, for example:
    # - LLM-as-a-judge
    # - Simple heuristics
    #
    # Columns are models.
    # Each cell is count plus percentage within that model.
    # -----------------------------------------------------------------------
    method_table_rows = []

    for method in all_methods:
        table_row = [method]

        for model in model_names:
            rows = merged_rows_by_model[model]
            total = len(rows)

            counter = Counter(
                row.get("method", "").strip() or "UNKNOWN"
                for row in rows
            )

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

    # This separate summary table is kept from the original script.
    # It shows total rows by model as a compact top-level summary.
    total_rows = [
        ["Total"] + [str(len(merged_rows_by_model[model])) for model in model_names]
    ]

    # -----------------------------------------------------------------------
    # Write the Markdown file.
    # -----------------------------------------------------------------------
    lines = []
    lines.append("# Taxonomy Merge Statistics")
    lines.append("")
    lines.append("This file summarizes the merged taxonomy-labeled QA CSV outputs.")
    lines.append("")

    lines.append("Each count is shown as:")
    lines.append("")
    lines.append("```text")
    lines.append("count (percentage within model)")
    lines.append("```")
    lines.append("")

    lines.append("## Total Rows by Model")
    lines.append("")
    lines.append(markdown_table(["Metric"] + model_names, total_rows))
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
    5. Merge both row sets.
    6. Write the merged CSV.
    7. Collect rows for Markdown statistics.

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

    merged_summaries = []
    skipped_pairs = []
    merged_rows_by_model = {}

    total_pairs = len(MERGE_PAIRS)

    for index, pair in enumerate(MERGE_PAIRS, start=1):
        label = pair["label"]
        model = pair["model"]

        judged_csv = project_root / pair["judged_csv"]
        taxonomy_csv = project_root / pair["taxonomy_csv"]
        output_csv = project_root / pair["output_csv"]

        print_progress(index, total_pairs, f"Processing {model}")

        missing_files = []

        if not judged_csv.exists():
            missing_files.append(str(judged_csv))

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

        converted_taxonomy_rows = convert_taxonomy_rows(taxonomy_rows)
        converted_judged_rows = convert_judged_rows(judged_rows)

        # Merge Simple heuristics and LLM-as-a-judge rows.
        merged_rows = converted_taxonomy_rows + converted_judged_rows

        write_csv(output_csv, merged_rows)

        # Store merged rows for later Markdown statistics.
        merged_rows_by_model[model] = merged_rows

        filtered_simple_rows = len(taxonomy_rows) - len(converted_taxonomy_rows)

        summary = {
            "label": label,
            "model": model,
            "taxonomy_input": taxonomy_csv,
            "judged_input": judged_csv,
            "output": output_csv,
            "taxonomy_rows_before_filter": len(taxonomy_rows),
            "taxonomy_rows_after_filter": len(converted_taxonomy_rows),
            "taxonomy_rows_filtered_out": filtered_simple_rows,
            "judged_rows": len(converted_judged_rows),
            "total_rows": len(merged_rows),
        }

        merged_summaries.append(summary)

        print(f"  Merged {model}:")
        print(f"    Simple heuristics rows before filter: {summary['taxonomy_rows_before_filter']}")
        print(f"    Simple heuristics rows kept:          {summary['taxonomy_rows_after_filter']}")
        print(f"    Simple heuristics rows filtered out:  {summary['taxonomy_rows_filtered_out']}")
        print(f"    LLM-as-a-judge rows:                  {summary['judged_rows']}")
        print(f"    Total rows written:                   {summary['total_rows']}")
        print(f"    Output: {output_csv}")
        print()

    statistics_path = project_root / "Output_GRASP/taxonomy_statistics.md"

    write_taxonomy_statistics(
        statistics_path=statistics_path,
        merged_rows_by_model=merged_rows_by_model,
        skipped_pairs=skipped_pairs,
    )

    print("=" * 72)
    print("Final summary")
    print("=" * 72)

    if merged_summaries:
        print("Merged files:")
        for item in merged_summaries:
            print(f"  {item['model']}:")
            print(f"    Taxonomy CSV: {item['taxonomy_input']}")
            print(f"    Judged CSV:   {item['judged_input']}")
            print(f"    Output CSV:   {item['output']}")
            print(f"    Simple heuristics rows kept: {item['taxonomy_rows_after_filter']}")
            print(f"    Simple heuristics rows filtered out: {item['taxonomy_rows_filtered_out']}")
            print(f"    LLM-as-a-judge rows: {item['judged_rows']}")
            print(f"    Rows written: {item['total_rows']}")
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