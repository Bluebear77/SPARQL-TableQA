#!/usr/bin/env python3
"""
build_annotation_235B_top300_second10.py

Summary
-------
This script builds two balanced annotation CSV files for the Qwen3-235B model
using the same input files as the original merge_taxonomy_full.py pipeline.

For the 235B model, the script:
1. Reads the Simple-heuristics taxonomy CSV and the LLM-as-a-judge CSV.
2. Drops Simple-heuristics rows whose taxonomy_label is different_unclassified.
3. Preserves the complete original file_path in the public `source` column,
   for example SimpleQA/NQ_table_test_simple/00503.json.
4. Removes rows whose source/file_path appears in
   Output_GRASP/script/large_results_report.txt, meaning the KG answer has
   more than 10 result rows.
5. Merges Simple-heuristics and LLM-as-a-judge rows into one shared internal
   schema.
6. Removes duplicate question rows, keeping the first occurrence.
7. Sorts each QA-group/method bucket by the correct confidence signal:
   - Simple-heuristics rows by similarity_score, high score first.
   - LLM-as-a-judge rows by difference_severity:
     major, moderate, minor, none.
8. Writes the top balanced 300 cases.
9. Writes the next balanced 10 cases for presentation.

The top 300 cases are exactly balanced as:

    SimpleQA / Simple heuristics: 75
    SimpleQA / LLM-as-a-judge:   75
    ComplexQA / Simple heuristics: 75
    ComplexQA / LLM-as-a-judge:   75

The second 10-case presentation slice is balanced as closely as possible while
preserving exact SimpleQA/ComplexQA balance and exact method balance:

    SimpleQA / Simple heuristics: 3
    SimpleQA / LLM-as-a-judge:   2
    ComplexQA / Simple heuristics: 2
    ComplexQA / LLM-as-a-judge:   3

Therefore the second slice has:

    SimpleQA: 5
    ComplexQA: 5
    Simple heuristics: 5
    LLM-as-a-judge: 5

The public output schema is exactly:

    question,gold_answer,KG answer,taxonomy_label,confidence,source

For Simple-heuristics rows, confidence is similarity_score.
For LLM-as-a-judge rows, confidence is difference_severity.

Run from the repository root with:

    python build_annotation_235B_top300_second10.py
"""

from __future__ import annotations

from pathlib import Path
import csv
import math
import re
from collections import Counter, defaultdict


# ---------------------------------------------------------------------------
# Public output schema for final annotation CSV files.
# The `source` column intentionally stores the complete dataset-relative JSON
# path, e.g. SimpleQA/NQ_table_test_simple/00503.json.
# ---------------------------------------------------------------------------
OUTPUT_COLUMNS = [
    "question",
    "gold_answer",
    "KG answer",
    "taxonomy_label",
    "confidence",
    "source",
]


# Target sizes for this script.
TOP_SELECTION_CASES = 300
SECOND_SLICE_CASES = 10


# Report containing JSON files whose result row count is greater than 10.
LARGE_RESULTS_REPORT = Path("Output_GRASP/script/large_results_report.txt")


# Final output folder requested for the annotation CSV files.
ANNOTATION_DIR = Path("Annotation")


# Preferred order for LLM-as-a-judge difference severity.
# Lower rank means more confident and therefore earlier in the output.
DIFFERENCE_SEVERITY_ORDER = {
    "major": 0,
    "moderate": 1,
    "minor": 2,
    "none": 3,
}


# Public method names used internally for balancing.
SIMPLE_METHOD = "Simple heuristics"
LLM_METHOD = "LLM-as-a-judge"


# QA groups used for balancing.
SIMPLE_QA_GROUP = "SimpleQA"
COMPLEX_QA_GROUP = "ComplexQA"


# 235B-only input/output configuration.
MODEL_PAIR = {
    "label": "235B",
    "short_model": "Qwen3-235B",
    "model": "Qwen3-235B-Thinking",
    "judged_csv": Path("LLM_as_a_Judge/235B_judged_filtered.csv"),
    "taxonomy_csv": Path("Output_GRASP/Qwen3-235B-A22B-Thinking-2507-AWQ/all_valid_cases_with_taxonomy.csv"),
    "top300_csv": Path("Annotation/annotation_cases_235B_top300.csv"),
    "second10_csv": Path("Annotation/annotation_cases_235B_second10.csv"),
    "statistics_md": Path("Annotation/annotation_235B_selection_statistics.md"),
}


# Exact balanced bucket quotas for the top 300 annotation set.
TOP300_BUCKET_QUOTAS = {
    (SIMPLE_QA_GROUP, SIMPLE_METHOD): 75,
    (SIMPLE_QA_GROUP, LLM_METHOD): 75,
    (COMPLEX_QA_GROUP, SIMPLE_METHOD): 75,
    (COMPLEX_QA_GROUP, LLM_METHOD): 75,
}


# Exact balanced bucket quotas for the next 10 presentation cases.
# This keeps SimpleQA=5, ComplexQA=5, Simple heuristics=5, LLM-as-a-judge=5.
SECOND10_BUCKET_QUOTAS = {
    (SIMPLE_QA_GROUP, SIMPLE_METHOD): 3,
    (SIMPLE_QA_GROUP, LLM_METHOD): 2,
    (COMPLEX_QA_GROUP, SIMPLE_METHOD): 2,
    (COMPLEX_QA_GROUP, LLM_METHOD): 3,
}


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
        return SIMPLE_QA_GROUP
    if key.startswith("ComplexQA/"):
        return COMPLEX_QA_GROUP
    return "UNKNOWN"


def normalize_difference_severity(value: str) -> str:
    """
    Normalize difference_severity values.

    The final value must be exactly one of:
    none, minor, moderate, major.
    """
    severity = (value or "").strip().lower().replace("_", " ").replace("-", " ")
    severity = re.sub(r"\s+", " ", severity)

    if severity in DIFFERENCE_SEVERITY_ORDER:
        return severity

    raise ValueError(
        f"Invalid difference_severity value: {value!r}. "
        "Expected exactly one of: none, minor, moderate, major."
    )


def parse_float(value: str) -> float:
    """Parse a floating-point value and return NaN if parsing fails."""
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return math.nan


def safe_sort_float(value: float) -> float:
    """Return a sortable float, sending missing values to the end."""
    if value is None or math.isnan(value):
        return float("-inf")
    return value


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
    """
    Convert all_valid_cases_with_taxonomy.csv rows to the internal schema.

    Simple-heuristics confidence is similarity_score.
    """
    converted = []
    filtered_out = 0

    for row in rows:
        raw_label = row.get("taxonomy_label", "")
        if not should_keep_simple_heuristics_row(raw_label):
            filtered_out += 1
            continue

        file_path = normalize_file_path_key(row.get("file_path", ""))
        similarity_score = row.get("similarity_score", "")
        similarity_score_float = parse_float(similarity_score)

        converted.append(
            {
                "question": row.get("question", ""),
                "gold_answer": row.get("gold_answer", ""),
                "KG answer": row.get("result_cleaned", ""),
                "taxonomy_label": normalize_taxonomy_label(raw_label),
                "confidence": similarity_score,
                "method": SIMPLE_METHOD,
                "source": file_path,
                "_file_path": file_path,
                "_qa_group": qa_group_from_source(file_path),
                "_similarity_score": similarity_score_float,
                "_difference_severity": "",
            }
        )

    return converted, filtered_out


def convert_judged_rows(rows: list[dict]) -> list[dict]:
    """
    Convert *_judged_filtered.csv rows to the internal schema.

    LLM-as-a-judge confidence is difference_severity.
    """
    converted = []

    for row in rows:
        file_path = normalize_file_path_key(row.get("file_path", ""))
        difference_severity = normalize_difference_severity(row.get("difference_severity", ""))

        converted.append(
            {
                "question": row.get("question", ""),
                "gold_answer": row.get("gold_answer", ""),
                "KG answer": row.get("KG answer", ""),
                "taxonomy_label": normalize_taxonomy_label(row.get("taxonomy_label", "")),
                "confidence": difference_severity,
                "method": LLM_METHOD,
                "source": file_path,
                "_file_path": file_path,
                "_qa_group": qa_group_from_source(file_path),
                "_similarity_score": math.nan,
                "_difference_severity": difference_severity,
            }
        )

    return converted


def public_row(row: dict) -> dict:
    """Return only columns intended for public output CSVs."""
    return {column: row.get(column, "") for column in OUTPUT_COLUMNS}


def filter_large_result_rows(rows: list[dict], large_file_paths: set[str]) -> tuple[list[dict], int]:
    """Remove rows whose source/file_path appears in the >10-row report."""
    kept_rows = []
    removed_count = 0

    for row in rows:
        if row.get("_file_path", "") in large_file_paths:
            removed_count += 1
        else:
            kept_rows.append(row)

    return kept_rows, removed_count


def deduplicate_by_question(rows: list[dict]) -> tuple[list[dict], int]:
    """Remove duplicate questions, keeping the first occurrence."""
    seen_questions = set()
    kept_rows = []
    removed_count = 0

    for row in rows:
        question_key = (row.get("question", "") or "").strip()
        if question_key in seen_questions:
            removed_count += 1
        else:
            seen_questions.add(question_key)
            kept_rows.append(row)

    return kept_rows, removed_count


def row_confidence_sort_key(row: dict) -> tuple:
    """
    Return a method-specific confidence sort key.

    Simple-heuristics rows are sorted by similarity_score, high score first.
    LLM-as-a-judge rows are sorted by difference_severity:
    major, moderate, minor, none.
    """
    method = row.get("method", "")

    if method == SIMPLE_METHOD:
        return (
            -safe_sort_float(row.get("_similarity_score", math.nan)),
            row.get("question", ""),
        )

    if method == LLM_METHOD:
        severity = row.get("_difference_severity", "")
        severity_rank = DIFFERENCE_SEVERITY_ORDER.get(severity, len(DIFFERENCE_SEVERITY_ORDER))
        return (
            severity_rank,
            row.get("question", ""),
        )

    return (
        999,
        row.get("question", ""),
    )


def bucket_rows(rows: list[dict]) -> dict[tuple[str, str], list[dict]]:
    """Bucket rows by QA group and method, then sort each bucket by confidence."""
    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)

    for row in rows:
        qa_group = row.get("_qa_group", "")
        method = row.get("method", "")
        buckets[(qa_group, method)].append(row)

    for key in list(buckets):
        buckets[key].sort(key=row_confidence_sort_key)

    return buckets


def validate_bucket_capacity(
    buckets: dict[tuple[str, str], list[dict]],
    top_quotas: dict[tuple[str, str], int],
    second_quotas: dict[tuple[str, str], int],
) -> None:
    """
    Check that every bucket has enough rows for both outputs.

    This script enforces exact balance. If a bucket is short, it raises an
    error instead of silently breaking the requested distribution.
    """
    shortages = []

    for key in sorted(top_quotas):
        required = top_quotas[key] + second_quotas.get(key, 0)
        available = len(buckets.get(key, []))
        if available < required:
            qa_group, method = key
            shortages.append(
                f"{qa_group} / {method}: required {required}, available {available}"
            )

    if shortages:
        raise RuntimeError(
            "Not enough eligible rows to build exact balanced top300 plus "
            "second10 outputs:\n  - " + "\n  - ".join(shortages)
        )


def select_top_and_second_slice(
    rows: list[dict],
    top_quotas: dict[tuple[str, str], int],
    second_quotas: dict[tuple[str, str], int],
) -> tuple[list[dict], list[dict]]:
    """
    Select the top balanced set and the next balanced presentation slice.

    The second slice is taken immediately after the top quota inside each
    QA-group/method bucket. This means it is the next most-confident balanced
    10-case slice after the top 300.
    """
    buckets = bucket_rows(rows)
    validate_bucket_capacity(buckets, top_quotas, second_quotas)

    top_rows = []
    second_rows = []

    for key in sorted(top_quotas):
        bucket = buckets[key]
        top_quota = top_quotas[key]
        second_quota = second_quotas.get(key, 0)

        top_rows.extend(bucket[:top_quota])
        second_rows.extend(bucket[top_quota:top_quota + second_quota])

    top_rows = interleave_balanced_rows(top_rows)
    second_rows = interleave_balanced_rows(second_rows)

    return top_rows, second_rows


def interleave_balanced_rows(rows: list[dict]) -> list[dict]:
    """
    Interleave rows from QA/method buckets.

    This keeps the final CSV balanced throughout the file instead of writing one
    large method or QA block. Rows inside each bucket already follow the correct
    confidence order.
    """
    buckets = bucket_rows(rows)

    bucket_order = [
        (SIMPLE_QA_GROUP, SIMPLE_METHOD),
        (COMPLEX_QA_GROUP, LLM_METHOD),
        (SIMPLE_QA_GROUP, LLM_METHOD),
        (COMPLEX_QA_GROUP, SIMPLE_METHOD),
    ]

    output = []
    bucket_positions = {key: 0 for key in bucket_order}

    while len(output) < len(rows):
        progressed = False

        for key in bucket_order:
            position = bucket_positions[key]
            bucket = buckets.get(key, [])
            if position < len(bucket):
                output.append(bucket[position])
                bucket_positions[key] += 1
                progressed = True

        if not progressed:
            break

    return output


def write_csv(csv_path: Path, rows: list[dict]) -> None:
    """Write final annotation rows to a CSV file."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(public_row(row) for row in rows)


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


def count_by_method(rows: list[dict]) -> Counter:
    """Count selected rows by internal method."""
    return Counter(row.get("method", "") or "UNKNOWN" for row in rows)


def count_by_qa_group(rows: list[dict]) -> Counter:
    """Count selected rows by QA group."""
    return Counter(row.get("_qa_group", "") or "UNKNOWN" for row in rows)


def count_by_bucket(rows: list[dict]) -> Counter:
    """Count selected rows by QA group and method."""
    return Counter((row.get("_qa_group", "UNKNOWN"), row.get("method", "UNKNOWN")) for row in rows)


def build_distribution_tables(rows: list[dict]) -> list[str]:
    """Build Markdown distribution tables for one selected output."""
    lines = []

    method_counts = count_by_method(rows)
    qa_group_counts = count_by_qa_group(rows)
    bucket_counts = count_by_bucket(rows)
    taxonomy_counts = count_by_label(rows)

    lines.append("Method distribution:")
    lines.append("")
    lines.append(
        markdown_table(
            ["Method", "Count"],
            [
                [SIMPLE_METHOD, str(method_counts.get(SIMPLE_METHOD, 0))],
                [LLM_METHOD, str(method_counts.get(LLM_METHOD, 0))],
            ],
        )
    )
    lines.append("")

    lines.append("QA group distribution:")
    lines.append("")
    lines.append(
        markdown_table(
            ["QA Group", "Count"],
            [
                [SIMPLE_QA_GROUP, str(qa_group_counts.get(SIMPLE_QA_GROUP, 0))],
                [COMPLEX_QA_GROUP, str(qa_group_counts.get(COMPLEX_QA_GROUP, 0))],
            ],
        )
    )
    lines.append("")

    lines.append("2x2 bucket distribution:")
    lines.append("")
    lines.append(
        markdown_table(
            ["QA Group", "Method", "Count"],
            [
                [SIMPLE_QA_GROUP, SIMPLE_METHOD, str(bucket_counts.get((SIMPLE_QA_GROUP, SIMPLE_METHOD), 0))],
                [SIMPLE_QA_GROUP, LLM_METHOD, str(bucket_counts.get((SIMPLE_QA_GROUP, LLM_METHOD), 0))],
                [COMPLEX_QA_GROUP, SIMPLE_METHOD, str(bucket_counts.get((COMPLEX_QA_GROUP, SIMPLE_METHOD), 0))],
                [COMPLEX_QA_GROUP, LLM_METHOD, str(bucket_counts.get((COMPLEX_QA_GROUP, LLM_METHOD), 0))],
            ],
        )
    )
    lines.append("")

    lines.append("Taxonomy distribution:")
    lines.append("")
    lines.append(
        markdown_table(
            ["taxonomy_label", "Count"],
            [[label, str(count)] for label, count in sorted(taxonomy_counts.items())],
        )
    )
    lines.append("")

    return lines


def write_statistics(
    statistics_path: Path,
    top_rows: list[dict],
    second_rows: list[dict],
    cleaning_summary: dict,
) -> None:
    """Write Markdown statistics for the two 235B annotation outputs."""
    statistics_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("# 235B Annotation Selection Statistics")
    lines.append("")
    lines.append("This file summarizes the balanced 235B annotation outputs.")
    lines.append("")
    lines.append("Public output columns:")
    lines.append("")
    lines.append("```text")
    lines.append(",".join(OUTPUT_COLUMNS))
    lines.append("```")
    lines.append("")

    lines.append("## Cleaning Summary")
    lines.append("")
    lines.append(
        markdown_table(
            ["Metric", "Count"],
            [
                ["Simple heuristics input rows", str(cleaning_summary["taxonomy_input_rows"])],
                ["LLM-as-a-judge input rows", str(cleaning_summary["judged_input_rows"])],
                ["Simple rows filtered by taxonomy_label", str(cleaning_summary["filtered_simple_rows"])],
                ["Rows removed by >10-row file_path filter", str(cleaning_summary["large_result_rows_removed"])],
                ["Duplicate question rows removed", str(cleaning_summary["duplicate_question_rows_removed"])],
                ["Eligible rows after cleaning", str(cleaning_summary["eligible_rows"])],
            ],
        )
    )
    lines.append("")

    lines.append("## Top 300 Output")
    lines.append("")
    lines.append(f"Rows written: {len(top_rows)}")
    lines.append("")
    lines.extend(build_distribution_tables(top_rows))

    lines.append("## Second 10-Case Presentation Slice")
    lines.append("")
    lines.append(f"Rows written: {len(second_rows)}")
    lines.append("")
    lines.extend(build_distribution_tables(second_rows))

    with statistics_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def print_counts(label: str, rows: list[dict]) -> None:
    """Print method, QA group, and 2x2 bucket counts."""
    method_counts = count_by_method(rows)
    qa_group_counts = count_by_qa_group(rows)
    bucket_counts = count_by_bucket(rows)

    print(f"  {label}:")
    print(f"    Rows: {len(rows)}")
    print("    Method counts:")
    print(f"      {SIMPLE_METHOD}: {method_counts.get(SIMPLE_METHOD, 0)}")
    print(f"      {LLM_METHOD}: {method_counts.get(LLM_METHOD, 0)}")
    print("    QA group counts:")
    print(f"      {SIMPLE_QA_GROUP}: {qa_group_counts.get(SIMPLE_QA_GROUP, 0)}")
    print(f"      {COMPLEX_QA_GROUP}: {qa_group_counts.get(COMPLEX_QA_GROUP, 0)}")
    print("    2x2 bucket counts:")
    print(f"      {SIMPLE_QA_GROUP} / {SIMPLE_METHOD}: {bucket_counts.get((SIMPLE_QA_GROUP, SIMPLE_METHOD), 0)}")
    print(f"      {SIMPLE_QA_GROUP} / {LLM_METHOD}: {bucket_counts.get((SIMPLE_QA_GROUP, LLM_METHOD), 0)}")
    print(f"      {COMPLEX_QA_GROUP} / {SIMPLE_METHOD}: {bucket_counts.get((COMPLEX_QA_GROUP, SIMPLE_METHOD), 0)}")
    print(f"      {COMPLEX_QA_GROUP} / {LLM_METHOD}: {bucket_counts.get((COMPLEX_QA_GROUP, LLM_METHOD), 0)}")


def main() -> None:
    """Run the 235B-only clean, balance, select, and write pipeline."""
    try:
        project_root = find_project_root()
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return

    print(f"Project root: {project_root}")
    print()

    pair = MODEL_PAIR
    model = pair["model"]
    judged_csv = project_root / pair["judged_csv"]
    taxonomy_csv = project_root / pair["taxonomy_csv"]
    top300_csv = project_root / pair["top300_csv"]
    second10_csv = project_root / pair["second10_csv"]
    statistics_md = project_root / pair["statistics_md"]

    missing_files = []
    if not judged_csv.exists():
        missing_files.append(str(judged_csv))
    if not taxonomy_csv.exists():
        missing_files.append(str(taxonomy_csv))

    if missing_files:
        print(f"ERROR: Missing file(s) for {model}:")
        for missing in missing_files:
            print(f"  - {missing}")
        return

    large_results_report = project_root / LARGE_RESULTS_REPORT
    large_paths_by_model = parse_large_results_report(large_results_report)

    model_output_dir = pair["taxonomy_csv"].parent.name
    large_file_paths = large_paths_by_model.get(model_output_dir, set())

    print(f"Processing {model}")
    print(f"  Taxonomy CSV: {taxonomy_csv}")
    print(f"  Judged CSV:   {judged_csv}")
    print()

    taxonomy_rows = read_csv_rows(taxonomy_csv)
    judged_rows = read_csv_rows(judged_csv)

    taxonomy_required = [
        "question",
        "gold_answer",
        "result_cleaned",
        "taxonomy_label",
        "similarity_score",
        "file_path",
    ]
    judged_required = [
        "question",
        "gold_answer",
        "KG answer",
        "taxonomy_label",
        "difference_severity",
        "file_path",
    ]

    taxonomy_ok = require_columns(taxonomy_csv, taxonomy_rows, taxonomy_required)
    judged_ok = require_columns(judged_csv, judged_rows, judged_required)
    if not taxonomy_ok or not judged_ok:
        print("ERROR: Required columns are missing.")
        return

    try:
        converted_taxonomy_rows, filtered_simple_rows = convert_taxonomy_rows(taxonomy_rows)
        converted_judged_rows = convert_judged_rows(judged_rows)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return

    taxonomy_after_large_filter, taxonomy_large_removed = filter_large_result_rows(
        converted_taxonomy_rows,
        large_file_paths,
    )
    judged_after_large_filter, judged_large_removed = filter_large_result_rows(
        converted_judged_rows,
        large_file_paths,
    )

    long_answer_removed_count = taxonomy_large_removed + judged_large_removed

    merged_rows_before_dedup = taxonomy_after_large_filter + judged_after_large_filter
    merged_rows, duplicate_removed_count = deduplicate_by_question(merged_rows_before_dedup)

    try:
        top300_rows, second10_rows = select_top_and_second_slice(
            rows=merged_rows,
            top_quotas=TOP300_BUCKET_QUOTAS,
            second_quotas=SECOND10_BUCKET_QUOTAS,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return

    write_csv(top300_csv, top300_rows)
    write_csv(second10_csv, second10_rows)

    cleaning_summary = {
        "taxonomy_input_rows": len(taxonomy_rows),
        "judged_input_rows": len(judged_rows),
        "filtered_simple_rows": filtered_simple_rows,
        "large_result_rows_removed": long_answer_removed_count,
        "duplicate_question_rows_removed": duplicate_removed_count,
        "eligible_rows": len(merged_rows),
    }

    write_statistics(
        statistics_path=statistics_md,
        top_rows=top300_rows,
        second_rows=second10_rows,
        cleaning_summary=cleaning_summary,
    )

    print("Cleaning summary:")
    print(f"  Simple heuristics input rows: {len(taxonomy_rows)}")
    print(f"  LLM-as-a-judge input rows: {len(judged_rows)}")
    print(f"  Simple rows filtered by taxonomy_label: {filtered_simple_rows}")
    print(f"  Rows removed by >10-row file_path filter: {long_answer_removed_count}")
    print(f"    - Simple heuristics removed: {taxonomy_large_removed}")
    print(f"    - LLM-as-a-judge removed:   {judged_large_removed}")
    print(f"  Duplicate question rows removed: {duplicate_removed_count}")
    print(f"  Eligible rows after cleaning: {len(merged_rows)}")
    print()

    print_counts("Top 300 balanced annotation cases", top300_rows)
    print()
    print_counts("Second 10 balanced presentation cases", second10_rows)
    print()

    print("Outputs written:")
    print(f"  Top 300 CSV:      {top300_csv}")
    print(f"  Second 10 CSV:    {second10_csv}")
    print(f"  Statistics file:  {statistics_md}")
    print()
    print("Done.")


if __name__ == "__main__":
    main()