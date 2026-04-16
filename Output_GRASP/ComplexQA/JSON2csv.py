import os
import json
import csv
import re
import matplotlib.pyplot as plt
from pathlib import Path
from collections import Counter


def normalize_sparql(text: str) -> str:
    """
    Extract only the SPARQL query starting from SELECT keyword.
    Removes all PREFIX declarations and any text before SELECT.

    Example input: "PREFIX ... \nSELECT ?item WHERE {...}"
    Example output: "SELECT ?item WHERE {...}"
    """

    if not text:
        return ""

    text = text.replace("\\n", "\n")

    match = re.search(r"(?is)\bSELECT\b.*", text)

    return match.group(0).strip() if match else ""


def extract_table(text: str) -> str:
    """
    Extract the full markdown table portion from output.result field.

    IMPORTANT:
    This function ONLY extracts tables and does NOT determine
    whether the SPARQL execution failed. Error classification
    is handled earlier in `classify_case()`.

    Returns empty string if no table is found.
    """

    if not text:
        return ""

    text = text.replace("\\n", "\n")

    lines = text.splitlines()

    table_lines = []
    started = False

    for line in lines:
        if line.strip().startswith("|"):
            started = True
            table_lines.append(line)
        elif started:
            break

    return "\n".join(table_lines).strip()


def clean_result_all_cells(result_table: str) -> str:
    """
    Extract all cell values from all data rows in a markdown table.

    Rules:
    1. Skip header row
    2. Skip separator row
    3. Extract every cell from each data row
    4. Remove Wikidata entity suffixes like (wd:Q...)
    5. Remove datatype suffixes like (xsd:dateTime)
    6. Normalize whitespace
    7. Join cells in each row with '|'
    8. Join rows with '\\n'

    Example:
    Input table:
    | book                                       | pubdate                             |
    | ------------------------------------------ | ----------------------------------- |
    | By the Shores of Silver Lake (wd:Q3427960) | 1939-10-20T00:00:00Z (xsd:dateTime) |

    Output:
    By the Shores of Silver Lake|1939-10-20T00:00:00Z
    """

    if not result_table:
        return ""

    lines = result_table.split("\n")
    cleaned_rows = []

    for i, line in enumerate(lines):
        line = line.strip()

        if not line.startswith("|"):
            continue

        # Skip header row
        if i == 0:
            continue

        # Skip markdown separator row
        if re.match(r"^\|\s*[-: ]+(\|\s*[-: ]+)+\|?\s*$", line) or line.startswith("| ---"):
            continue

        # Extract inner cells only; ignore leading/trailing empty split parts
        cells = [cell.strip() for cell in line.split("|")[1:-1]]

        cleaned_cells = []

        for cell in cells:
            # Remove Wikidata entity suffixes like (wd:Q3427960)
            cell = re.sub(r"\s*\(wd:Q[^)]*\)", "", cell).strip()

            # Remove datatype suffixes like (xsd:dateTime)
            cell = re.sub(r"\s*\(xsd:[^)]+\)", "", cell).strip()

            # Normalize whitespace
            cell = " ".join(cell.split())

            cleaned_cells.append(cell)

        if cleaned_cells:
            cleaned_rows.append("|".join(cleaned_cells))

    return "\n".join(cleaned_rows)


def classify_case(output_obj, sparql_text: str, result_raw: str):
    """
    Classify JSON record as valid or invalid based on these rules.

    Updated definitions exactly matching dataset structure:

    1. null_output
       output field is null:
       "output": null

    2. no_sparql_generated
       SPARQL query is empty because the generation was cancelled.
       Example structure:
       "output": {
           "sparql": null,
           "kg": null,
           "selections": null,
           "result": null
       }

    3. sparql_execution_failed (execution)
       Example result:
       "SPARQL execution failed:('Connection aborted.', ConnectionResetError...)"

    4. sparql_execution_failed (preprocessing)
       Detected via regex for "parse error"

    5. empty_sparql_result
       Example:
       "Got no rows and 1 columns"

    6. invalid_json
       JSON parsing failed
    """

    # 1️⃣ output field is null
    if output_obj is None:
        return "null_output", ""

    # 2️⃣ no SPARQL generated (cancel case)
    if (
        isinstance(output_obj, dict)
        and output_obj.get("sparql") is None
        and output_obj.get("result") is None
    ):
        return "no_sparql_generated", ""

    # normalize sparql for later logic
    if not sparql_text:
        return "no_sparql_generated", ""

    if isinstance(result_raw, str):

        # Execution failure (network / endpoint errors)
        if "SPARQL execution failed" in result_raw:
            return "sparql_execution_failed (execution)", ""

        # Preprocessing / parsing failure
        if re.search(r"parse error", result_raw, re.IGNORECASE):
            return "sparql_execution_failed (preprocessing)", ""

        # Empty result case
        if re.search(r"Got no rows and \d+ columns?", result_raw):
            return "empty_sparql_result", ""

    table = extract_table(result_raw)

    if not table:
        return "empty_sparql_result", ""

    return "", table


def pct(value: int, total: int) -> float:
    """Calculate percentage safely (avoid division by zero)."""
    return (value / total * 100.0) if total else 0.0


def create_pie_chart(valid: int, invalid: int, folder: str, output_dir: Path):
    """
    Create pie chart PNG showing valid vs invalid case distribution.
    Handles zero-total folders safely.
    """

    labels = ["Valid cases", "Invalid cases"]
    sizes = [valid, invalid]
    colors = ["#5CB85C", "#D9534F"]

    fig, ax = plt.subplots(figsize=(6, 4))

    total = sum(sizes)

    if total == 0:
        ax.text(
            0.5,
            0.5,
            "No data available",
            ha="center",
            va="center",
            fontsize=14,
        )
        ax.set_title(f"Valid vs Invalid cases ({folder})")
        ax.axis("off")
    else:
        def format_autopct(pct_value):
            count = int(round(pct_value / 100.0 * total))
            return f"{pct_value:.1f}%\n({count})"

        ax.pie(
            sizes,
            labels=labels,
            autopct=format_autopct,
            colors=colors,
            startangle=90,
        )
        ax.set_title(f"Valid vs Invalid cases ({folder})")
        ax.axis("equal")

    png_path = output_dir / f"{folder}_valid_vs_invalid_pie.png"
    fig.savefig(png_path, bbox_inches="tight", dpi=150)
    plt.close(fig)

    return png_path

def process_folder(base_folder: Path, all_valid_rows: list):
    """
    Process ONE parent folder.

    Generates:
    - main CSV
    - valid CSV
    - invalid CSV
    - markdown summary
    """

    folder_name = base_folder.name

    output_dir = base_folder / "extracted_output"
    output_dir.mkdir(exist_ok=True)

    main_csv = output_dir / f"{folder_name}.csv"
    valid_csv = output_dir / f"{folder_name}_valid_cases.csv"
    invalid_csv = output_dir / f"{folder_name}_invalid_cases.csv"
    md_file = output_dir / f"{folder_name}_invalid_summary.md"

    json_files = []

    for root, _, files in os.walk(base_folder):
        root_path = Path(root)

        if root_path.name == "extracted_output" and root_path.parent == base_folder:
            continue

        for fname in files:
            if Path(fname).suffix.lower() == ".json":
                json_files.append(root_path / fname)

    json_files.sort(key=str)

    total_files = len(json_files)

    all_rows = []
    valid_rows = []
    invalid_rows = []
    counts = Counter()
    valid_total = 0

    for fp in json_files:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))

        except Exception:
            invalid_rows.append([fp.name, "invalid_json"])
            counts["invalid_json"] += 1
            all_rows.append(["", "", "", "", ""])
            continue

        question = data.get("question", "")
        gold_answer = data.get("reference_answer", "")
        output_obj = data.get("output", None)

        if isinstance(output_obj, dict):
            sparql = normalize_sparql(output_obj.get("sparql", ""))
            result_raw = output_obj.get("result", "")
        else:
            sparql = ""
            result_raw = ""

        invalid_label, result_table = classify_case(output_obj, sparql, result_raw)

        # NEW: extract all cells from all data rows, not only first column
        result_cleaned = clean_result_all_cells(result_table)

        if invalid_label:
            invalid_rows.append([fp.name, invalid_label])
            counts[invalid_label] += 1
        else:
            valid_total += 1

            rel_path = str(fp.relative_to(base_folder))
            folder_file_path = f"{folder_name}_{fp.name}"

            valid_rows.append(
                [question, gold_answer, result_cleaned, result_table, sparql, rel_path]
            )

            all_valid_rows.append(
                [
                    question,
                    gold_answer,
                    result_cleaned,
                    result_table,
                    sparql,
                    folder_file_path,
                ]
            )

        all_rows.append([question, gold_answer, result_cleaned, result_table, sparql])

    with main_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["question", "gold_answer", "result_cleaned", "result", "sparql"]
        )
        writer.writerows(all_rows)

    with valid_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["question", "gold_answer", "result_cleaned", "result", "sparql", "file_path"]
        )
        writer.writerows(valid_rows)

    with invalid_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file_name", "invalid_label"])
        writer.writerows(invalid_rows)

    invalid_labels = [
        "null_output",
        "no_sparql_generated",
        "empty_sparql_result",
        "sparql_execution_failed (execution)",
        "sparql_execution_failed (preprocessing)",
        "invalid_json",
    ]

    invalid_total = sum(counts.get(lbl, 0) for lbl in invalid_labels)

    md_lines = [
        f"# Invalid case summary for {folder_name}",
        "",
        f"Total JSON files: {total_files}",
        "",
        f"Valid cases: {valid_total} ({pct(valid_total, total_files):.2f}%)",
        f"Invalid cases: {invalid_total} ({pct(invalid_total, total_files):.2f}%)",
        "",
        f"!extracted_output/{folder_name}_valid_vs_invalid_pie.png",
        "",
        "## Invalid case breakdown",
        "",
    ]

    for lbl in invalid_labels:
        n = counts.get(lbl, 0)
        md_lines.append(f"- {lbl}: {n} ({pct(n, total_files):.2f}%)")

    md_file.write_text("\n".join(md_lines), encoding="utf-8")

    create_pie_chart(valid_total, invalid_total, folder_name, output_dir)

    print(f"✓ Processed {folder_name}: {valid_total}/{total_files} valid cases")


def main(parents_dir: Path):
    all_valid_rows = []

    parent_folders = [p for p in parents_dir.iterdir() if p.is_dir()]
    parent_folders.sort(key=str)

    print(f"Found {len(parent_folders)} folders to process:")

    for folder in parent_folders:
        print(f"  - {folder.name}")

    for parent_folder in parent_folders:
        process_folder(parent_folder, all_valid_rows)

    combined_csv = parents_dir / "all_valid_cases.csv"

    with combined_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["question", "gold_answer", "result_cleaned", "result", "sparql", "file_path"]
        )
        writer.writerows(all_valid_rows)

    print("\n🎉 ALL DONE!")
    print(f"✓ Combined valid cases: {combined_csv}")
    print(f"✓ Total valid rows across all folders: {len(all_valid_rows)}")


def main_standalone():
    """Run script from directory containing parent folders."""
    current_dir = Path.cwd()
    main(current_dir)


if __name__ == "__main__":
    main_standalone()