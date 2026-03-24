import json
import csv
from pathlib import Path

# Define input JSON and output CSV paths
in_path = Path("OTT_QA_dev.json")
out_path = Path("OTT_QA_dev.csv")

# Load JSON data (expected: list of objects)
with in_path.open("r", encoding="utf-8") as f:
    data = json.load(f)

# Write selected fields to CSV
with out_path.open("w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["question", "answer"])  # CSV header
    for item in data:
        # Safely get "question" and "answer-text" fields
        writer.writerow([
            item.get("question", ""),
            item.get("answer-text", "")
        ])

