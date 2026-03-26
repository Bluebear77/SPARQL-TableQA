import os
import json
import csv
import re
from pathlib import Path
from collections import Counter

# -----------------------------------------------------------------------------
# Goal
# -----------------------------------------------------------------------------
# This script scans all JSON files in the current directory and extracts:
#   1) question
#   2) output.sparql
#   3) output.result
#
# It then writes:
#   - <current_folder_name>.csv
#       Columns: question, sparql, result
#   - <current_folder_name>_invalid_cases.csv
#       Columns: file_name, invalid_label
#   - <current_folder_name>_valid_cases.csv
#       Columns: file_name, question, sparql, result
#   - <current_folder_name>_invalid_summary.md
#       Summary of invalid cases and valid cases with percentages
#
# Notes:
#   - The SPARQL output is trimmed so it starts from SELECT.
#   - The result output is trimmed so it keeps only the actual markdown table.
#   - Invalid cases are classified into:
#       null_output
#       no_sparql_generated
#       empty_sparql_result
#       sparql_execution_failed
#       sparql_parsing_failed
#       invalid_json
# -----------------------------------------------------------------------------

def current_folder_name() -> str:
    """Return the name of the current working directory."""
    return Path.cwd().name


def list_json_files():
    """List all JSON files in the current directory, sorted by filename."""
    return sorted(
        [p for p in Path.cwd().iterdir() if p.is_file() and p.suffix.lower() == ".json"]
    )


def load_json(path: Path):
    """Safely load a JSON file."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_sparql(text: str) -> str:
    """
    Keep only the SPARQL query starting from SELECT.
    This removes prefix lines and anything before SELECT.
    """
    if not text:
        return ""

    # Convert escaped newlines into real newlines if the content is stored that way.
    text = text.replace("\\n", "\n")

    # Capture from the first SELECT to the end.
    match = re.search(r"(?is)\bSELECT\b.*", text)
    if not match:
        return ""

    return match.group(0).strip()


def extract_table(text: str) -> str:
    """
    Extract only the markdown table portion from output.result.

    Example input:
      "Got 18 rows and 2 columns, showing the first 5 and last 5 rows below:\\n| a | b |\\n|---|---|\\n|...|"

    Desired output:
      | a | b |
      |---|---|
      |...|
    """
    if not text:
        return ""

    # Convert escaped newlines into actual line breaks.
    text = text.replace("\\n", "\n")

    # If the result contains a known error message, do not try to extract a table.
    if "Error executing SPARQL query" in text:
        return ""
    if "SPARQL parsing failed" in text:
        return ""

    lines = text.splitlines()
    table_lines = []
    started = False

    # Start collecting lines once we see the first markdown table row.
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
    Classify the current record into an invalid label or valid case.

    Returns:
      (invalid_label, table_text)

    If valid:
      invalid_label = ""
      table_text = extracted markdown table

    If invalid:
      invalid_label = one of the specified labels
      table_text = ""
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

    # If we get here, try to extract the actual markdown table.
    table = extract_table(result_raw)

    # Case 3: SPARQL exists but result is empty / no table found
    if not table:
        return "empty_sparql_result", ""

    return "", table


def pct(value: int, total: int) -> float:
    """Safe percentage helper."""
    return (value / total * 100.0) if total else 0.0


def main():
    folder = current_folder_name()

    # All output files go into ./output/
    output_dir = Path.cwd() / "output"
    output_dir.mkdir(exist_ok=True)

    main_csv = output_dir / f"{folder}.csv"
    invalid_csv = output_dir / f"{folder}_invalid_cases.csv"
    valid_csv = output_dir / f"{folder}_valid_cases.csv"
    md_file = output_dir / f"{folder}_invalid_summary.md"

    json_files = list_json_files()
    total_files = len(json_files)

    # Main rows: every file gets one row here
    all_rows = []

    # Invalid-only rows
    invalid_rows = []

    # Valid-only rows
    valid_rows = []

    # Counts for invalid labels
    counts = Counter()

    for fp in json_files:
        try:
            data = load_json(fp)
        except Exception:
            # If the file cannot be parsed as JSON, mark it invalid.
            invalid_rows.append([fp.name, "invalid_json"])
            counts["invalid_json"] += 1
            all_rows.append(["", "", ""])
            continue

        question = data.get("question", "")
        output_obj = data.get("output", None)

        # output is expected to be a dictionary when present
        if isinstance(output_obj, dict):
            sparql = normalize_sparql(output_obj.get("sparql", ""))
            result_raw = output_obj.get("result", "")
        else:
            sparql = ""
            result_raw = ""

        invalid_label, result_table = classify_case(
            output_obj=output_obj,
            sparql_text=sparql,
            result_raw=result_raw
        )

        # Save invalid cases
        if invalid_label:
            invalid_rows.append([fp.name, invalid_label])
            counts[invalid_label] += 1
        else:
            # Save valid cases only when output/result are usable
            valid_rows.append([fp.name, question, sparql, result_table])

        # Save the all-rows CSV
        all_rows.append([question, sparql, result_table])

    # -------------------------------------------------------------------------
    # Write the main CSV
    # -------------------------------------------------------------------------
    with main_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["question", "sparql", "result"])
        writer.writerows(all_rows)

    # -------------------------------------------------------------------------
    # Write the invalid cases CSV
    # -------------------------------------------------------------------------
    with invalid_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file_name", "invalid_label"])
        writer.writerows(invalid_rows)

    # -------------------------------------------------------------------------
    # Write the valid cases CSV
    # -------------------------------------------------------------------------
    with valid_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file_name", "question", "sparql", "result"])
        writer.writerows(valid_rows)

    # -------------------------------------------------------------------------
    # Build the markdown summary
    # -------------------------------------------------------------------------
    invalid_labels = [
        "null_output",
        "no_sparql_generated",
        "empty_sparql_result",
        "sparql_execution_failed",
        "sparql_parsing_failed",
        "invalid_json",
    ]

    invalid_total = sum(counts.get(lbl, 0) for lbl in invalid_labels)
    valid_total = total_files - invalid_total

    md_lines = []
    md_lines.append(f"# Invalid case summary for {folder}")
    md_lines.append("")
    md_lines.append(f"Total JSON files: {total_files}")
    md_lines.append("")
    md_lines.append(f"Valid cases with valid result: {valid_total} ({pct(valid_total, total_files):.2f}%)")
    md_lines.append("")

    for lbl in invalid_labels:
        n = counts.get(lbl, 0)
        md_lines.append(f"- {lbl}: {n} ({pct(n, total_files):.2f}%)")

    md_file.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"Created: {main_csv}")
    print(f"Created: {invalid_csv}")
    print(f"Created: {valid_csv}")
    print(f"Created: {md_file}")


if __name__ == "__main__":
    main()