#!/usr/bin/env python3
"""
Convert a selected JSONL dataset into a CSV with two columns:
- question_text
- answer_list

What this script does:
1. Reads an input JSONL file line by line.
2. Extracts the `question_text` field from each record.
3. Extracts only the answer texts from the `answer_list` field.
4. Joins multiple answer texts into a single string using ` | ` as a separator.
5. Writes the result to a CSV file with columns:
   [question_text, answer_list]

Notes:
- The output `answer_list` column contains only answer text, not URLs, aliases, IDs,
  or proof fields.
- Empty or missing `answer_list` values are written as an empty string.
- The script preserves UTF-8 characters.

Example usage:
    python jsonl_to_question_answer_csv.py \
        /path/to/wikitables_simple_manual_selected.jsonl \
        /path/to/wikitables_simple_manual_selected.csv
"""

import argparse
import csv
import json
from pathlib import Path


def extract_answer_texts(answer_list):
    """Return a list of answer_text strings from a record's answer_list."""
    results = []
    if not isinstance(answer_list, list):
        return results

    for item in answer_list:
        if isinstance(item, dict):
            answer_text = item.get("answer_text", "")
            if answer_text is None:
                answer_text = ""
            answer_text = str(answer_text).strip()
            if answer_text:
                results.append(answer_text)
    return results


def jsonl_to_csv(input_jsonl: str, output_csv: str, separator: str = " | ") -> None:
    input_path = Path(input_jsonl)
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with input_path.open("r", encoding="utf-8") as fin, output_path.open(
        "w", encoding="utf-8", newline=""
    ) as fout:
        writer = csv.writer(fout)
        writer.writerow(["question_text", "answer_list"])

        for line_num, line in enumerate(fin, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Invalid JSON in {input_path} at line {line_num}: {e}"
                ) from e

            question_text = str(record.get("question_text", "")).strip()
            answers = extract_answer_texts(record.get("answer_list", []))
            joined_answers = separator.join(answers)

            writer.writerow([question_text, joined_answers])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert selected JSONL records to a CSV with question_text and flattened answer_list columns."
    )
    parser.add_argument("input_jsonl", help="Path to the input JSONL file")
    parser.add_argument("output_csv", help="Path to the output CSV file")
    parser.add_argument(
        "--separator",
        default=" | ",
        help="Separator used to join multiple answer texts into one CSV cell (default: ' | ')",
    )
    args = parser.parse_args()

    jsonl_to_csv(args.input_jsonl, args.output_csv, separator=args.separator)
