# rank by score = 0.5 * num_entities + 0.5 * q_len

import csv
import json
from pathlib import Path

# Input / output paths
csv_in = Path("CompMix_infobox.csv")      # columns: question, answer, (optionally question_id)
jsonl_in = Path("CompMix_infobox.jsonl")     # contains question_id and entities
csv_out = Path("CompMix_infobox_ranked.csv") # output: ONLY question, answer

def count_words(text: str) -> int:
    return len(text.split())

# Build mapping: question_id -> num_entities
qid_to_num_entities = {}
with jsonl_in.open("r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        qid = obj.get("question_id")
        entities = obj.get("entities", [])
        if qid is not None:
            qid_to_num_entities[qid] = len(entities)

# Read CSV, compute complexity, keep rows in memory
rows = []
with csv_in.open("r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        question = row.get("question", "")
        # If you have question_id in the CSV, use it; otherwise complexity is based only on length
        qid = row.get("question_id")
        num_entities = qid_to_num_entities.get(qid, 0) if qid else 0
        q_len = count_words(question)
        score = 0.5 * num_entities + 0.5 * q_len
        rows.append({
            "question": row.get("question", ""),
            "answer": row.get("answer", ""),
            "_score": score,  # internal field, not written to CSV
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
