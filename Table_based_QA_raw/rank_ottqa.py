# rank by question length

import csv
import json
from pathlib import Path

# Inputs
csv_in = Path("OTT_QA_dev.csv")   # columns: question, answer (and optionally question_id)
json_in = Path("OTT_QA_dev.json") # list of dicts with question_id, question, answer-text, ...

csv_out = Path("OTT_QA_dev_ranked.csv")  # output: ONLY question, answer

def count_words(text: str) -> int:
    return len(text.split())

# Build mapping question_id -> question text (if you want to be strict on IDs)
qid_to_question = {}
with json_in.open("r", encoding="utf-8") as f:
    data = json.load(f)
    for obj in data:
        qid = obj.get("question_id")
        if qid is not None:
            qid_to_question[qid] = obj.get("question", "")

rows = []
with csv_in.open("r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        # Prefer question from CSV; you could also cross-check with the JSON mapping above
        question = row.get("question", "")
        # Here OTT_QA_dev.json has no entities field, so we set num_entities = 0
        num_entities = 0
        q_len = count_words(question)
        score = 0.5 * num_entities + 0.5 * q_len

        rows.append({
            "question": row.get("question", ""),
            "answer": row.get("answer", ""),
            "_score": score,
        })

# Sort by complexity (descending)
rows.sort(key=lambda r: r["_score"], reverse=True)

# Write ranked CSV with only question, answer
with csv_out.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["question", "answer"])
    writer.writeheader()
    for r in rows:
        writer.writerow({
            "question": r["question"],
            "answer": r["answer"],
        })
