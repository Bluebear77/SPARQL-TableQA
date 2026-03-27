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
#   - It iterates into the folder and all its subdirectories.
#   - It finds all JSON files under that parent.
#   - For each JSON:
#       * extracts the question
#       * extracts the SPARQL starting from SELECT (ignoring prefixes)
#       * extracts the markdown table from output.result
#   - It writes several files under a subfolder named `extracted_output/`:
#       1) <folder_name>.csv
#       2) <folder_name>_valid_cases.csv
#       3) <folder_name>_invalid_cases.csv
#       4) <folder_name>_invalid_summary.md
#   - It also creates a pie chart PNG (`<folder_name>_valid_vs_invalid_pie.png`)
#     in the same `extracted_output/` folder and references it in the markdown.
#
# Types of invalid cases:
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

    # Convert escaped newlines into real newlines.
    text = text.replace("\\n", "\n")

    # Keep from the first SELECT to the end.
    match = re.search(r"(?is)\bSELECT\b.*", text)
    if not match:
        return ""

    return match.group(0).strip()


def extract_table(text: str) -> str:
    """
    Extract only the markdown table portion from output.result.

    Example input:
      "Got 18 rows and 2 columns, showing the first 5 and last 5 rows below:\\n
       | body | label |\\n
       | ---  | ---   |\\n
       | ..."

    Desired output:
       | body | label |
       | ---  | ---   |
       | ...
    """
    if not text:
        return ""

    # Convert escaped newlines to real lines.
    text = text.replace("\\n", "\n")

    # If the result contains execution or parsing error, do not extract a table.
    if "Error executing SPARQL query" in text:
        return ""
    if "SPARQL parsing failed" in text:
        return ""

    lines = text.splitlines()
    table_lines = []
    started = False

    # Start collecting as soon as we see the first markdown table row.
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
    Classify the current JSON record into:
      - an invalid label (one of the known error types), or
      - a valid case (label = "").

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

    # Try to extract the markdown table.
    table = extract_table(result_raw)

    # Case 3: SPARQL exists but result is empty / no table found
    if not table:
        return "empty_sparql_result", ""

    return "", table


def pct(value: int, total: int) -> float:
    """Safe percentage helper."""
    return (value / total * 100.0) if total else 0.0


def create_pie_chart(valid: int, invalid: int, folder: str, output_dir: Path):
    """
    Create and save a pie chart PNG showing valid vs invalid cases.

    The pie chart image is saved as:
        <output_dir>/<folder>_valid_vs_invalid_pie.png
    """
    # Do not try to plot if both are zero.
    if valid == 0 and invalid == 0:
        # Still create empty file so markdown reference is safe.
        fig, _ = plt.subplots(figsize=(6, 4))
        fig.savefig(output_dir / f"{folder}_valid_vs_invalid_pie.png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        return output_dir / f"{folder}_valid_vs_invalid_pie.png"

    labels = ["Valid cases", "Invalid cases"]
    sizes = [valid, invalid]
    colors = ["#5CB85C", "#D9534F"]

    fig, ax = plt.subplots(figsize=(6, 4))

    # Safely format the pie labels so NaN is never passed to int().
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

    Steps:
      - Collect all JSON files under base_folder and its subdirectories.
      - For each JSON file:
          * extract question, sparql, result
          * classify as valid / invalid
      - Write CSV files into `base_folder/extracted_output/`.
      - Write a markdown summary with a pie chart and valid/invalid percentages.
    """
    folder_name = base_folder.name

    # Create output folder: base_folder/extracted_output/
    output_dir = base_folder / "extracted_output"
    output_dir.mkdir(exist_ok=True)

    # Paths for output files.
    main_csv = output_dir / f"{folder_name}.csv"
    valid_csv = output_dir / f"{folder_name}_valid_cases.csv"
    invalid_csv = output_dir / f"{folder_name}_invalid_cases.csv"
    md_file = output_dir / f"{folder_name}_invalid_summary.md"

    # Collect all JSON files beneath base_folder (including subdirectories).
    json_files = []
    for root, _, files in os.walk(base_folder):
        root_path = Path(root)

        # Skip the extracted_output subdirectory itself.
        if root_path.name == "extracted_output" and root_path.parent == base_folder:
            continue

        for fname in files:
            if Path(fname).suffix.lower() == ".json":
                json_files.append(root_path / fname)

    # Sort by path for deterministic output.
    json_files.sort(key=str)
    total_files = len(json_files)

    # Container rows.
    all_rows = []        # Every JSON file.
    valid_rows = []      # Only valid cases.
    invalid_rows = []    # Only invalid cases.
    counts = Counter()
    valid_total = 0

    # Process each JSON file.
    for fp in json_files:
        # Read the file.
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            invalid_rows.append([fp.name, "invalid_json"])
            counts["invalid_json"] += 1
            all_rows.append(["", "", ""])
            continue

        question = data.get("question", "")
        output_obj = data.get("output", None)

        # If output exists and is a dict, extract sparql and result.
        if isinstance(output_obj, dict):
            sparql = normalize_sparql(output_obj.get("sparql", ""))
            result_raw = output_obj.get("result", "")
        else:
            sparql = ""
            result_raw = ""

        # Classify the case and get the table text.
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
            # Store relative path from base_folder.
            rel_path = "/".join(fp.relative_to(base_folder).parts)
            valid_rows.append([rel_path, question, sparql, result_table])

        all_rows.append([question, sparql, result_table])

    # Write the main CSV: all JSON rows.
    with main_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["question", "sparql", "result"])
        writer.writerows(all_rows)

    # Write the valid cases CSV.
    with valid_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file_path", "question", "sparql", "result"])
        writer.writerows(valid_rows)

    # Write the invalid cases CSV.
    with invalid_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file_name", "invalid_label"])
        writer.writerows(invalid_rows)

    # Build the markdown summary.
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

    # Create the pie chart PNG.
    create_pie_chart(valid_total, invalid_total, folder_name, output_dir)

    print(f"Processed {folder_name}: {main_csv}")
    print(f"Valid cases CSV: {valid_csv}")
    print(f"Invalid cases CSV: {invalid_csv}")
    print(f"Summary markdown: {md_file}")


def main(parents_dir: Path):
    """
    Entry point that processes all parent folders inside `parents_dir`.

    parents_dir: directory containing folders such as
        CompMix_table_simple_qa, NQ_table_test_simple, Qampari_wikitables_simple.
    """
    # Find all subdirectories (parent folders).
    parent_folders = [p for p in parents_dir.iterdir() if p.is_dir()]
    parent_folders.sort(key=str)

    for parent_folder in parent_folders:
        process_folder(parent_folder)


def main_standalone():
    """
    Run this script from the directory that contains the parent folders.

    Example layout:
        ./CompMix_table_simple_qa/
        ./NQ_table_test_simple/
        ./Qampari_wikitables_simple/
    """
    current_dir = Path.cwd()
    main(parents_dir=current_dir)


if __name__ == "__main__":
    main_standalone()