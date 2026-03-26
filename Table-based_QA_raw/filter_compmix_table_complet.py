import json
from pathlib import Path
import csv

# Input / output paths
full_path = Path("CompMix_table.jsonl")
simple_path = Path("CompMix_table_simple.jsonl")
complete_path = Path("CompMix_table_complete.jsonl")
csv_path = Path("CompMix_table_complete_qa.csv")

def load_jsonl_to_dict(path):
    """Load JSONL as dict keyed by question_id."""
    data = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            qid = obj.get("question_id")
            if qid is not None:
                data[qid] = obj
    return data

# Load both files
full_data = load_jsonl_to_dict(full_path)
simple_data = load_jsonl_to_dict(simple_path)

# Items present in full but not in simple
complete_items = [obj for qid, obj in full_data.items() if qid not in simple_data]

# Write CompMix_table_complete.jsonl
with complete_path.open("w", encoding="utf-8") as f:
    for obj in complete_items:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

# Write CSV with question and answer_text
with csv_path.open("w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["question", "answer"])
    for obj in complete_items:
        writer.writerow([
            obj.get("question", ""),
            # handle both answer_text and answer-text keys
            obj.get("answer_text", obj.get("answer-text", ""))
        ])
