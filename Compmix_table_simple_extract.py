#!/usr/bin/env python3
"""
Extract question/answer pairs from CompMix_table_simple.jsonl into a 2-column CSV.

How this works:
1. Read the JSONL file line by line.
2. For each JSON object:
   - Build the CSV `question` column as:
       question text + " " + entity IDs
     Example:
       "Who won ... Taxi Driver?" + " Q47221"
   - Build the CSV `answer` column from `answer_text`.
3. Write the result to a CSV with exactly two columns: question, answer.

Notes:
- If a record has multiple entities, this script appends ALL entity IDs separated by spaces.
- If a record has no entities, the question column is just the original question text.
- This script preserves UTF-8 text.
"""

import csv
import json
from pathlib import Path

INPUT_JSONL = Path("CompMix_table_simple.jsonl")
OUTPUT_CSV = Path("CompMix_table_simple_qa.csv")


def build_question(record: dict) -> str:
    """
    Build the question column as:
        question + " " + all entity IDs

    Example input record:
        {
          "question": "Who won ... ?",
          "entities": [{"id": "Q47221", "label": "Taxi Driver"}]
        }

    Output:
        "Who won ... ? Q47221"
    """
    question_text = (record.get("question") or "").strip()

    # Collect entity IDs (not labels), because that matches your requested format.
    entity_ids = []
    for ent in record.get("entities", []):
        ent_id = str(ent.get("id", "")).strip()
        if ent_id:
            entity_ids.append(ent_id)

    if entity_ids:
        return question_text + " " + " ".join(entity_ids)
    return question_text


def build_answer(record: dict) -> str:
    """Use answer_text as the answer column."""
    return (record.get("answer_text") or "").strip()


def main() -> None:
    rows = []

    # Read JSONL one line at a time.
    with INPUT_JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            rows.append({
                "question": build_question(record),
                "answer": build_answer(record),
            })

    # Write exactly 2 columns to CSV.
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["question", "answer"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
