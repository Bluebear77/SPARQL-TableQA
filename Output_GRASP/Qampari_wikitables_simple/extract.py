import os
import json
import csv
import re
from pathlib import Path
from collections import Counter

# -----------------------------------------------------------------------------
# Purpose:
#   Scan all JSON files in the current directory and extract:
#     1) question
#     2) output.sparql
#     3) output.result (only the actual table, not the leading explanation)
#
# Outputs:
#   1) <current_folder_name>.csv
#      Columns: question, sparql, result
#   2) <current_folder_name>_invalid_cases.csv
#      Columns: file_name, invalid_label
#   3) <current_folder_name>_invalid_summary.md
#      A markdown summary with invalid-case percentages
# -----------------------------------------------------------------------------

def get_current_folder_name() -> str:
    """Return the name of the current working directory."""
    return Path.cwd().name


def list_json_files():
    """Return all .json files in the current directory, sorted by filename."""
    return sorted([p for p in Path.cwd().iterdir() if p.is_file() and p.suffix.lower() == ".json"])


def read_json_file(file_path: Path):
    """Safely read and parse a JSON file."""
    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_sparql(sparql_text: str) -> str:
    """
    Extract only the SPARQL query starting from SELECT.
    This removes prefixes and any text before SELECT.
    """
    if not sparql_text:
        return ""
    
    # Convert escaped newlines into actual newlines if needed.
    sparql_text = sparql_text.replace("\\n", "\n")

    # Keep only the part beginning with SELECT.
    match = re.search(r"(?is)\bSELECT\b.*", sparql_text)
    if not match:
        return ""

    return match.group(0).strip()


def extract_table_from_result(result_text: str) -> str:
    """
    Extract only the table portion from output.result.
    
    Example input:
      "Got 18 rows and 2 columns, showing ...\\n| body | label |\\n| --- | --- |\\n| ..."

    Desired output:
      | body | label |
      | --- | --- |
      | ...
    """
    if not result_text:
        return ""

    # Convert escaped newlines to real newlines.
    result_text = result_text.replace("\\n", "\n")

    # If the result is clearly an execution/parsing failure, treat as empty table.
    if "Error executing SPARQL query" in result_text:
        return ""
    if "SPARQL parsing failed" in result_text:
        return ""

    # Find the first line that looks like a markdown table row.
    lines = result_text.splitlines()
    table_lines = []
    started = False

    for line in lines:
        if line.strip().startswith("|"):
            started = True
            table_lines.append(line)
        elif started:
            # Stop once the table block ends.
            break

    return "\n".join(table_lines).strip()


def classify_invalid_case(output_value, sparql_text, result_text):
    """
    Classify invalid cases according to your rules:
      1) null_output
      2) no_sparql_generated
      3) empty_sparql_result
      4) sparql_execution_failed
      5) sparql_parsing_failed
    Returns:
      (invalid_label, result_table)
    """
    if output_value is None:
        return "null_output", ""

    if not sparql_text:
        return "no_sparql_generated", ""

    if isinstance(result_text, str) and "Error executing SPARQL query" in result_text:
        return "sparql_execution_failed", ""

    if isinstance(result_text, str) and "SPARQL parsing failed" in result_text:
        return "sparql_parsing_failed", ""

    table = extract_table_from_result(result_text)
    if not table:
        return "empty_sparql_result", ""

    return "", table


def main():
    folder_name = get_current_folder_name()

    # Output files go into an output/ directory.
    output_dir = Path.cwd() / "output"
    output_dir.mkdir(exist_ok=True)

    main_csv_path = output_dir / f"{folder_name}.csv"
    invalid_csv_path = output_dir / f"{folder_name}_invalid_cases.csv"
    md_path = output_dir / f"{folder_name}_invalid_summary.md"

    json_files = list_json_files()

    rows = []
    invalid_rows = []
    counts = Counter()

    for json_file in json_files:
        try:
            data = read_json_file(json_file)
        except Exception:
            # If the file itself cannot be parsed, record it as invalid JSON.
            invalid_rows.append([json_file.name, "invalid_json"])
            counts["invalid_json"] += 1
            rows.append(["", "", ""])
            continue

        question = data.get("question", "")
        output_value = data.get("output", None)

        # output is expected to be a dictionary when valid.
        sparql_text = ""
        result_text = ""

        if isinstance(output_value, dict):
            sparql_text = normalize_sparql(output_value.get("sparql", ""))
            result_text = output_value.get("result", "")
        else:
            # If output is not a dictionary (or is null), leave fields empty.
            sparql_text = ""
            result_text = ""

        invalid_label, result_table = classify_invalid_case(
            output_value=output_value,
            sparql_text=sparql_text,
            result_text=result_text
        )

        if invalid_label:
            invalid_rows.append([json_file.name, invalid_label])
            counts[invalid_label] += 1

        rows.append([question, sparql_text, result_table])

    # -------------------------------------------------------------------------
    # Write the main CSV: question, sparql, result
    # -------------------------------------------------------------------------
    with main_csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["question", "sparql", "result"])
        writer.writerows(rows)

    # -------------------------------------------------------------------------
    # Write the invalid cases CSV
    # -------------------------------------------------------------------------
    with invalid_csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file_name", "invalid_label"])
        writer.writerows(invalid_rows)

    # -------------------------------------------------------------------------
    # Write the markdown summary with percentages
    # -------------------------------------------------------------------------
    total_files = len(json_files)

    summary_lines = []
    summary_lines.append(f"# Invalid case summary for {folder_name}")
    summary_lines.append("")
    summary_lines.append(f"Total JSON files: {total_files}")
    summary_lines.append("")

    labels = [
        "null_output",
        "no_sparql_generated",
        "empty_sparql_result",
        "sparql_execution_failed",
        "sparql_parsing_failed",
        "invalid_json",
    ]

    for label in labels:
        count = counts.get(label, 0)
        pct = (count / total_files * 100) if total_files else 0.0
        summary_lines.append(f"- {label}: {count} ({pct:.2f}%)")

    md_path.write_text("\n".join(summary_lines), encoding="utf-8")

    print(f"Created: {main_csv_path}")
    print(f"Created: {invalid_csv_path}")
    print(f"Created: {md_path}")


if __name__ == "__main__":
    main()
