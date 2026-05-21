"""
===========================================================
Script: Merge & Clean Complex Question Dataset
===========================================================


Purpose:
--------
This script:
1. Extracts the first two columns (question, answer)
   from multiple CSV files
2. Skips rows where the answer is "yes" or "no"
   (case-insensitive)
3. Cleans the question text by removing:
   - double quotes (")
   - question marks (?)
4. Adds a new column indicating the source file
5. Collects a fixed number of VALID rows per file
6. Splits everything into separate CSV files by source


Key Behavior:
-------------
- If a row is skipped (e.g., yes/no answer),
  the script continues reading until it collects
  the required number of valid rows.
- Ensures each dataset contributes exactly the
  requested number of rows (if available).
"""


import csv
from collections import defaultdict


# ---------------------------------------------------------
# Helper function: clean question text
# ---------------------------------------------------------
def clean_question(text):
    """
    Removes unwanted characters from the question:
    - double quotes (")
    - question marks (?)


    Args:
        text (str): Original question


    Returns:
        str: Cleaned question
    """
    return text.replace('"', '').replace('?', '')



# ---------------------------------------------------------
# Helper function: check if answer is yes/no
# ---------------------------------------------------------
import ast  # for safely parsing list-like strings


def normalize_answer(answer):
    """
    Normalize answer into a clean string:
    - Handles list-like strings (e.g., "['Yes']")
    - Extracts first element if list
    """
    answer = answer.strip()


    # Try to parse if it's a list-like string
    try:
        parsed = ast.literal_eval(answer)
        if isinstance(parsed, list) and len(parsed) > 0:
            return str(parsed[0]).strip().lower()
    except:
        pass


    # Fallback: normal string
    return answer.lower()



def is_yes_no(answer):
    """
    Checks whether the answer is 'yes' or 'no'
    after normalization.
    """
    normalized = normalize_answer(answer)
    return normalized in {"yes", "no"}


# ---------------------------------------------------------
# Helper function: extract valid rows with filtering
# ---------------------------------------------------------
def extract_rows(file_path, num_rows, source_name):
    """
    Extracts rows from a CSV file with:
    - skipping header
    - filtering yes/no answers
    - cleaning questions
    - adding source column


    Args:
        file_path (str): CSV file path
        num_rows (int): number of valid rows to collect
        source_name (str): label for source column


    Returns:
        list: rows in format [question, answer, source]
    """
    extracted = []


    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)


        # Skip header
        next(reader, None)


        # Iterate until enough valid rows are collected
        for row in reader:
            if len(extracted) >= num_rows:
                break


            # Ensure row has at least 2 columns
            if len(row) < 2:
                continue


            question, answer = row[0], row[1]


            # Skip yes/no answers
            if is_yes_no(answer):
                continue


            # Clean question text
            question = clean_question(question)


            # Append processed row
            extracted.append([question, answer, source_name])


    return extracted



# ---------------------------------------------------------
# Main aggregation
# ---------------------------------------------------------
all_rows = []
rows_by_source = defaultdict(list)


# Extract from each dataset with source labels
for row in extract_rows("CompMix_infobox_ranked.csv", 300, "CompMix_infobox"):
    rows_by_source[row[2]].append(row)
for row in extract_rows("CompMix_table_complete_ranked.csv", 300, "CompMix_table"):
    rows_by_source[row[2]].append(row)


# Monaco split (150 + 150)
for row in extract_rows("Monaco_time_dependent.csv", 150, "Monaco_time"):
    rows_by_source[row[2]].append(row)
for row in extract_rows("Monaco_non_time_dependent.csv", 150, "Monaco_non_time"):
    rows_by_source[row[2]].append(row)


for row in extract_rows("OTT_QA_dev_ranked.csv", 400, "OTT_QA_dev"):
    rows_by_source[row[2]].append(row)
for row in extract_rows("Sportsreason_TANQ.csv", 200, "Sportsreason_TANQ"):
    rows_by_source[row[2]].append(row)


# ---------------------------------------------------------
# Write split CSV files by source
# ---------------------------------------------------------
for source_name, rows in rows_by_source.items():
    output_file = f"{source_name}_complex.csv"
    with open(output_file, "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)


        # Header with new source column
        writer.writerow(["question", "answer", "source"])


        # Write rows for this source
        writer.writerows(rows)


        all_rows.extend(rows)


# ---------------------------------------------------------
# Completion message
# ---------------------------------------------------------
for source_name, rows in rows_by_source.items():
    print(f"{source_name}_complex.csv: {len(rows)} rows")

print(f"Done! Total rows written: {len(all_rows)}")