import json
import csv

rows = []

# Read JSONL
with open("Sportsreason.jsonl", "r", encoding="utf-8") as infile:
    for line in infile:
        data = json.loads(line)
        
        # Filter conditions
        if data.get("seed_dataset") == "TANQ":
            gold_type = data.get("gold_evidence_type", {})
            
            if isinstance(gold_type, dict) and "table" in gold_type:
                question = data.get("seed_question", "")
                answer = data.get("answers", [""])[0]  # first answer
                gold_evidence_type = json.dumps(gold_type)
                
                rows.append([question, answer, gold_evidence_type])

# Sort rows by length of question (descending)
rows.sort(key=lambda x: len(x[0]), reverse=True)

# Write CSV
with open("Sportsreason_TANQ.csv", "w", newline="", encoding="utf-8") as outfile:
    writer = csv.writer(outfile)
    writer.writerow(["question", "answer", "gold evidence type"])
    writer.writerows(rows)