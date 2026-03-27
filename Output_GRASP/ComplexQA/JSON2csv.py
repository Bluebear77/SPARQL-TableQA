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
    text = text.replace("\\n", "\n")  # Convert escaped newlines
    match = re.search(r"(?is)\bSELECT\b.*", text)
    return match.group(0).strip() if match else ""

def extract_table(text: str) -> str:
    """
    Extract the full markdown table portion from output.result field.
    Returns empty string if result contains SPARQL errors.
    """
    if not text:
        return ""
    text = text.replace("\\n", "\n")
    
    # Skip if result contains execution/parsing errors
    if "Error executing SPARQL query" in text or "SPARQL parsing failed" in text:
        return ""
    
    lines = text.splitlines()
    table_lines = []
    started = False
    
    # Collect all lines that start with | (table format)
    for line in lines:
        if line.strip().startswith("|"):
            started = True
            table_lines.append(line)
        elif started:
            break  # Stop after table ends
    
    return "\n".join(table_lines).strip()

def clean_result_all_first_column(result_table: str) -> str:
    """
    EXTRACT ALL VALUES FROM 1st COLUMN OF ALL DATA ROWS (starting from 2nd row):
    
    Steps:
    1. Split table into lines
    2. Skip 1st row (header like "| followedBy |") 
    3. Skip separator row ("| --- |")
    4. From 2nd+ data rows, extract 1st column values
    5. Remove (wd:Q...) patterns from each cell
    6. Clean punctuation, join with '|' separator
    
    Input example:
    "| followedBy                              |
     | --------------------------------------- |
     | Terminator 2: Judgment Day (wd:Q170564) |"
    
    Output: "Terminator 2 Judgment Day"
    """
    if not result_table:
        return ""
    
    lines = result_table.split('\n')
    first_column_values = []
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Skip if not a table row
        if not line.startswith('|'):
            continue
            
        # Skip 1st row (header) - ALWAYS starts with 2nd row as requested
        if i == 0:
            continue
            
        # Skip separator row
        if line.startswith('| ---'):
            continue
            
        # Data row: extract 1st column
        cells = [cell.strip() for cell in line.split('|') if cell.strip()]
        if cells and len(cells) >= 1:
            first_cell = cells[0]
            
            # Remove (wd:Q...) pattern
            cleaned_cell = re.sub(r'\s*\(wd:Q[^)]*\)', '', first_cell).strip()
            
            # Remove punctuation but preserve special chars (ö, ä, etc.)
            cleaned_cell = re.sub(r'[^\w\säöüßÄÖÜ]', ' ', cleaned_cell).strip()
            cleaned_cell = ' '.join(cleaned_cell.split())  # Normalize spaces
            
            if cleaned_cell:
                first_column_values.append(cleaned_cell)
    
    return '|'.join(first_column_values)

def classify_case(output_obj, sparql_text: str, result_raw: str):
    """
    Classify JSON record as valid or invalid based on these rules:
    1. null_output: output field is null
    2. no_sparql_generated: SPARQL query is empty  
    3. sparql_execution_failed: "Error executing SPARQL query" in result
    4. sparql_parsing_failed: "SPARQL parsing failed" in result
    5. empty_sparql_result: valid SPARQL but no table extracted
    6. invalid_json: JSON parsing failed
    """
    if output_obj is None:
        return "null_output", ""
    if not sparql_text:
        return "no_sparql_generated", ""
    if isinstance(result_raw, str) and "Error executing SPARQL query" in result_raw:
        return "sparql_execution_failed", ""
    if isinstance(result_raw, str) and "SPARQL parsing failed" in result_raw:
        return "sparql_parsing_failed", ""
    
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
    Saved as: extracted_output/<folder>_valid_vs_invalid_pie.png
    """
    labels = ["Valid cases", "Invalid cases"]
    sizes = [valid, invalid]
    colors = ["#5CB85C", "#D9534F"]  # Green for valid, Red for invalid
    
    fig, ax = plt.subplots(figsize=(6, 4))
    
    def format_autopct(pct):
        total = sum(sizes)
        if total == 0:
            return "0%"
        count = int(round(pct / 100.0 * total))
        return f"{pct:.1f}%\n({count})"
    
    ax.pie(sizes, labels=labels, autopct=format_autopct, 
           colors=colors, startangle=90)
    ax.set_title(f"Valid vs Invalid cases ({folder})")
    ax.axis("equal")  # Ensure perfect circle
    
    png_path = output_dir / f"{folder}_valid_vs_invalid_pie.png"
    fig.savefig(png_path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    return png_path

def process_folder(base_folder: Path, all_valid_rows: list):
    """
    Process ONE parent folder (e.g., "NQ_table_test_simple"):
    
    1. Finds all JSON files recursively in folder + subdirectories
    2. Extracts: question, gold_answer, result_cleaned, result, sparql
    3. Writes 4 files to extracted_output/:
       - <folder>.csv: ALL rows [question,gold_answer,result_cleaned,result,sparql]
       - <folder>_valid_cases.csv: VALID rows [question,gold_answer,result_cleaned,result,sparql,file_path]  
       - <folder>_invalid_cases.csv: [file_name,invalid_label]
       - <folder>_invalid_summary.md: Summary + pie chart
    4. Collects valid rows for combined CSV
    """
    folder_name = base_folder.name
    output_dir = base_folder / "extracted_output"
    output_dir.mkdir(exist_ok=True)

    # Output file paths
    main_csv = output_dir / f"{folder_name}.csv"
    valid_csv = output_dir / f"{folder_name}_valid_cases.csv"
    invalid_csv = output_dir / f"{folder_name}_invalid_cases.csv"
    md_file = output_dir / f"{folder_name}_invalid_summary.md"

    # Step 1: Find all JSON files (skip extracted_output itself)
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

    # Step 2: Process each JSON file
    all_rows = []           # All files: [question,gold_answer,result_cleaned,result,sparql]
    valid_rows = []         # Valid only: [... + file_path]
    invalid_rows = []       # Invalid: [file_name,invalid_label]
    counts = Counter()
    valid_total = 0

    for fp in json_files:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            # JSON parsing failed
            invalid_rows.append([fp.name, "invalid_json"])
            counts["invalid_json"] += 1
            all_rows.append(["", "", "", "", ""])
            continue

        # Extract fields
        question = data.get("question", "")
        gold_answer = data.get("reference_answer", "")
        output_obj = data.get("output", None)

        if isinstance(output_obj, dict):
            sparql = normalize_sparql(output_obj.get("sparql", ""))
            result_raw = output_obj.get("result", "")
        else:
            sparql = ""
            result_raw = ""

        # Classify and clean
        invalid_label, result_table = classify_case(output_obj, sparql, result_raw)
        result_cleaned = clean_result_all_first_column(result_table)

        if invalid_label:
            invalid_rows.append([fp.name, invalid_label])
            counts[invalid_label] += 1
        else:
            valid_total += 1
            rel_path = str(fp.relative_to(base_folder))  # "00001.json" or "subfolder/00001.json"
            folder_file_path = f"{folder_name}_{fp.name}"  # "NQ_table_test_simple_00001.json"
            
            # Valid row for per-folder CSV
            valid_rows.append([question, gold_answer, result_cleaned, result_table, sparql, rel_path])
            
            # Valid row for combined CSV (no folder prefix in columns)
            all_valid_rows.append([question, gold_answer, result_cleaned, result_table, sparql, folder_file_path])

        # Row for main CSV (all files)
        all_rows.append([question, gold_answer, result_cleaned, result_table, sparql])

    # Step 3: Write per-folder output files
    
    # Main CSV: ALL rows
    with main_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["question", "gold_answer", "result_cleaned", "result", "sparql"])
        writer.writerows(all_rows)

    # Valid cases CSV
    with valid_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["question", "gold_answer", "result_cleaned", "result", "sparql", "file_path"])
        writer.writerows(valid_rows)

    # Invalid cases CSV
    with invalid_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file_name", "invalid_label"])
        writer.writerows(invalid_rows)

    # Step 4: Markdown summary with pie chart
    invalid_labels = ["null_output", "no_sparql_generated", "empty_sparql_result", 
                     "sparql_execution_failed", "sparql_parsing_failed", "invalid_json"]
    invalid_total = sum(counts.get(lbl, 0) for lbl in invalid_labels)

    md_lines = [
        f"# Invalid case summary for {folder_name}",
        "",
        f"Total JSON files: {total_files}",
        "",
        f"Valid cases: {valid_total} ({pct(valid_total, total_files):.2f}%)",
        f"Invalid cases: {invalid_total} ({pct(invalid_total, total_files):.2f}%)",
        "",
        f"![](extracted_output/{folder_name}_valid_vs_invalid_pie.png)",
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
    """
    MAIN FUNCTION: Process ALL parent folders and create combined CSV.
    
    Expected directory structure:
    ./script.py
    ./CompMix_table_simple_qa/     <- contains JSON files
    ./NQ_table_test_simple/        <- contains JSON files  
    ./Qampari_wikitables_simple/   <- contains JSON files
    """
    all_valid_rows = []
    
    # Find all parent folders (directories in current location)
    parent_folders = [p for p in parents_dir.iterdir() if p.is_dir()]
    parent_folders.sort(key=str)

    print(f"Found {len(parent_folders)} folders to process:")
    for folder in parent_folders:
        print(f"  - {folder.name}")

    # Process each folder
    for parent_folder in parent_folders:
        process_folder(parent_folder, all_valid_rows)

    # Step 5: Create COMBINED valid cases CSV
    combined_csv = parents_dir / "all_valid_cases.csv"
    with combined_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["question", "gold_answer", "result_cleaned", "result", "sparql", "file_path"])
        writer.writerows(all_valid_rows)
    
    print(f"\n🎉 ALL DONE!")
    print(f"✓ Combined valid cases: {combined_csv}")
    print(f"✓ Total valid rows across all folders: {len(all_valid_rows)}")

def main_standalone():
    """Run script from directory containing parent folders."""
    current_dir = Path.cwd()
    main(current_dir)

if __name__ == "__main__":
    main_standalone()