#!/usr/bin/env python3
"""
Extract question and answer text from CompMix_table_simple.jsonl into a 2-column CSV.

This version keeps:
- question = the original "question" field only
- answer   = the "answer_text" field

It does NOT append entity IDs / QIDs to the question.
"""

import csv
import json
from pathlib import Path


def main():
    # Change these paths if your files are elsewhere.
    # input_jsonl = Path("CompMix_table_simple.jsonl")
    input_jsonl = Path("CompMix_infobox.jsonl")
    output_csv = Path("CompMix_infobox.csv")

    rows = []

    with input_jsonl.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            record = json.loads(line)

            # How the fields are built:
            # 1) question:
            #    Use ONLY the original "question" text exactly as stored.
            #    Do not append entity IDs / QIDs.
            # 2) answer:
            #    Use the "answer_text" field.
            question = (record.get("question") or "").strip()
            answer = (record.get("answer_text") or "").strip()

            rows.append({
                "question": question,
                "answer": answer,
            })

    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["question", "answer"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output_csv}")


if __name__ == "__main__":
    main()
