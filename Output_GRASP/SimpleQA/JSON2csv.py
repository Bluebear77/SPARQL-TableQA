import os
import json
import csv
import re
import matplotlib.pyplot as plt
from pathlib import Path
from collections import Counter

# -----------------------------------------------------------------------------
# Purpose
# -----------------------------------------------------------------------------
# This script processes multiple parent folders such as:
#   CompMix_table_simple_qa, NQ_table_test_simple, Qampari_wikitables_simple
#
# Each parent folder may contain subdirectories with JSON files.
#
# For each parent folder:
#   - It discovers all JSON files under that folder and subdirectories.
#   - For each JSON:
#       * extracts:
#           - question
#           - reference_answer (stored as gold_answer)
#           - output.sparql (normalized to start from SELECT)
#           - output.result (markdown table portion only)
#   - It writes:
#       1) <folder_name>.csv
#           Columns: question, gold_answer, result, sparql
#       2) <folder_name>_valid_cases.csv
#           Columns: question, gold_answer, result, sparql, file_path
#       3) <folder_name>_invalid_cases.csv
#           Columns: file_name, invalid_label
#       4) <folder_name>_invalid_summary.md
#           With valid vs invalid pie chart and percentages
#
# Invalid cases:
#   - null_output
#   - no_sparql_generated
#   - empty_sparql_result
#   - sparql_execution_failed
#   - sparql_parsing_failed
#   - invalid_json (cannot parse JSON)
# -----------------------------------------------------------------------------

def normalize_sparql(text: str) -> str:
    """
    Keep only the SPARQL query starting from SELECT.
    This removes prefixes and any text before SELECT.
    """
    if not text:
        return ""

    # Convert escaped newlines to real newlines.
    text = text.replace("\\n", "\n")

    # Keep from the first SELECT to the end.
    match = re.search(r"(?is)\bSELECT\b.*", text)
    if not match:
        return ""

    return match.group(0).strip()


def extract_table(text: str) -> str:
    """
    Extract only the markdown table portion from output.result.
    """
    if not text:
        return ""

    # Convert escaped newlines to real lines.
    text = text.replace("\\n", "\n")

    # If the result is clearly an error, do not extract a table.
    if "Error executing SPARQL query" in text:
        return ""
    if "SPARQL parsing failed" in text:
        return ""

    lines = text.splitlines()
    table_lines = []
    started = False

    # Start collecting once we see the first markdown table row.
    for line in lines:
        if line.strip().startswith("|"):
            started = True
            table_lines.append(line)
        elif started:
            # Stop once the table block ends.
            break

    return "\n".join(table_lines).strip()


def classify_case(output_obj, sparql_text: str, result_raw: str):
    """
    Classify the record into valid or invalid.
    Returns (invalid_label, table_text).
    """
    # Case 1: output is null
    if output_obj is None:
        return "null_output", ""

    # Case 2: no SPARQL generated
    if not sparql_text:
        return "no_sparql_generated", ""

    # Case 4: SPARQL execution failed
    if isinstance(result_raw, str) and "Error executing SPARQL query" in result_raw:
        return "sparql_execution_failed", ""

    # Case 5: SPARQL parsing failed
    if isinstance(result_raw, str) and "SPARQL parsing failed" in result_raw:
        return "sparql_parsing_failed", ""

    # Try to extract the table.
    table = extract_table(result_raw)

    # Case 3: SPARQL exists but no table found
    if not table:
        return "empty_sparql_result", ""

    return "", table


def pct(value: int, total: int) -> float:
    """Safe percentage helper."""
    return (value / total * 100.0) if total else 0.0


def create_pie_chart(valid: int, invalid: int, folder: str, output_dir: Path):
    """
    Create and save a pie chart PNG: valid vs invalid cases.
    """
    if valid == 0 and invalid == 0:
        # Still create a small empty plot so the file exists.
        fig, _ = plt.subplots(figsize=(6, 4))
        fig.savefig(output_dir / f"{folder}_valid_vs_invalid_pie.png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        return output_dir / f"{folder}_valid_vs_invalid_pie.png"

    labels = ["Valid cases", "Invalid cases"]
    sizes = [valid, invalid]
    colors = ["#5CB85C", "#D9534F"]

    fig, ax = plt.subplots(figsize=(6, 4))

    # Safely format the autopct so NaN is never passed to int().
    def format_autopct(pct):
        total = sum(sizes)
        if total == 0:
            return "0%"
        count = int(pct / 100.0 * total)
        return f"{pct:.1f}%\n({count})"

    ax.pie(
        sizes,
        labels=labels,
        autopct=format_autopct,
        colors=colors,
        startangle=90,
    )
    ax.set_title(f"Valid vs Invalid cases ({folder})")
    ax.axis("equal")  # Keep the pie circular.

    png_path = output_dir / f"{folder}_valid_vs_invalid_pie.png"
    fig.savefig(png_path, bbox_inches="tight", dpi=150)
    plt.close(fig)

    return png_path


def process_folder(base_folder: Path):
    """
    Process one parent folder (e.g., Qampari_wikitables_simple).

    Reads JSON files recursively, extracts:
      question, reference_answer (as gold_answer),
      result table, and normalized SPARQL.

    Writes CSVs and markdown summary with pie chart.
    """
    folder_name = base_folder.name

    # Output directory: base_folder/extracted_output/
    output_dir = base_folder / "extracted_output"
    output_dir.mkdir(exist_ok=True)

    # Output file paths.
    main_csv = output_dir / f"{folder_name}.csv"
    valid_csv = output_dir / f"{folder_name}_valid_cases.csv"
    invalid_csv = output_dir / f"{folder_name}_invalid_cases.csv"
    md_file = output_dir / f"{folder_name}_invalid_summary.md"

    # Collect all JSON files recursively.
    json_files = []
    for root, _, files in os.walk(base_folder):
        root_path = Path(root)

        # Skip the extracted_output subdirectory.
        if root_path.name == "extracted_output" and root_path.parent == base_folder:
            continue

        for fname in files:
            if Path(fname).suffix.lower() == ".json":
                json_files.append(root_path / fname)

    json_files.sort(key=str)
    total_files = len(json_files)

    # Data containers.
    all_rows = []        # [question, gold_answer, result, sparql]
    valid_rows = []      # [question, gold_answer, result, sparql, file_path]
    invalid_rows = []    # [file_name, invalid_label]
    counts = Counter()
    valid_total = 0

    # Process each JSON file.
    for fp in json_files:
        # Read data.
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            invalid_rows.append([fp.name, "invalid_json"])
            counts["invalid_json"] += 1
            all_rows.append(["", "", "", ""])
            continue

        question = data.get("question", "")
        gold_answer = data.get("reference_answer", "")  # New 'gold_answer' column
        output_obj = data.get("output", None)

        # If output is a dict, extract sparql and result.
        if isinstance(output_obj, dict):
            sparql = normalize_sparql(output_obj.get("sparql", ""))
            result_raw = output_obj.get("result", "")
        else:
            sparql = ""
            result_raw = ""

        # Classify and extract table.
        invalid_label, result_table = classify_case(
            output_obj=output_obj,
            sparql_text=sparql,
            result_raw=result_raw
        )

        if invalid_label:
            invalid_rows.append([fp.name, invalid_label])
            counts[invalid_label] += 1
        else:
            valid_total += 1
            rel_path = "/".join(fp.relative_to(base_folder).parts)
            valid_rows.append([
                question,
                gold_answer,
                result_table,
                sparql,
                rel_path,  # file_path as last column
            ])

        # All rows: question, gold_answer, result, sparql
        all_rows.append([
            question,
            gold_answer,
            result_table,
            sparql,
        ])

    # Write the main CSV: question, gold_answer, result, sparql
    with main_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["question", "gold_answer", "result", "sparql"])
        writer.writerows(all_rows)

    # Write valid cases CSV: question, gold_answer, result, sparql, file_path
    with valid_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["question", "gold_answer", "result", "sparql", "file_path"])
        writer.writerows(valid_rows)

    # Write invalid cases CSV
    with invalid_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file_name", "invalid_label"])
        writer.writerows(invalid_rows)

    # Build markdown summary with valid/invalid percentages and pie chart reference.
    invalid_labels = [
        "null_output",
        "no_sparql_generated",
        "empty_sparql_result",
        "sparql_execution_failed",
        "sparql_parsing_failed",
        "invalid_json",
    ]

    invalid_total = sum(counts.get(lbl, 0) for lbl in invalid_labels)

    md_lines = []
    md_lines.append(f"# Invalid case summary for {folder_name}")
    md_lines.append("")
    md_lines.append(f"Total JSON files: {total_files}")
    md_lines.append("")
    md_lines.append(f"Valid cases with valid result: {valid_total} ({pct(valid_total, total_files):.2f}%)")
    md_lines.append(f"Invalid cases: {invalid_total} ({pct(invalid_total, total_files):.2f}%)")
    md_lines.append("")
    md_lines.append(f"![](extracted_output/{folder_name}_valid_vs_invalid_pie.png)")
    md_lines.append("")
    md_lines.append("## Invalid case breakdown")
    md_lines.append("")

    for lbl in invalid_labels:
        n = counts.get(lbl, 0)
        md_lines.append(f"- {lbl}: {n} ({pct(n, total_files):.2f}%)")

    # Write the markdown file.
    md_file.write_text("\n".join(md_lines), encoding="utf-8")

    # Create the pie chart.
    create_pie_chart(valid_total, invalid_total, folder_name, output_dir)

    print(f"Processed {folder_name}: {main_csv}")


def main(parents_dir: Path):
    """
    Process all parent folders inside parents_dir.

    parents_dir: directory containing:
      CompMix_table_simple_qa, NQ_table_test_simple, Qampari_wikitables_simple
    """
    parent_folders = [p for p in parents_dir.iterdir() if p.is_dir()]
    parent_folders.sort(key=str)

    for parent_folder in parent_folders:
        process_folder(parent_folder)


def main_standalone():
    """
    Run this script from the directory containing the parent folders.
    """
    current_dir = Path.cwd()
    main(parents_dir=current_dir)


if __name__ == "__main__":
    main_standalone()