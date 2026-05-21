import json
import csv

INPUT_JSONL = "NQ_table_test.jsonl"
OUTPUT_CSV = "NQ_table_test.csv"

def extract_jsonl_to_csv(input_jsonl: str, output_csv: str) -> None:
    rows = []

    with open(input_jsonl, "r", encoding="utf-8") as infile:
        for line in infile:
            obj = json.loads(line)

            for q in obj.get("questions", []):
                question = (q.get("originalText") or "").replace("\n", " ").strip()
                answers = q.get("answer", {}).get("answerTexts") or []
                answers = [str(a).replace("\n", " ").strip() for a in answers if str(a).strip()]
                answer = " | ".join(answers)

                rows.append({
                    "question": question,
                    "answer": answer,
                })

    with open(output_csv, "w", encoding="utf-8", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=["question", "answer"])
        writer.writeheader()
        writer.writerows(rows)

if __name__ == "__main__":
    extract_jsonl_to_csv(INPUT_JSONL, OUTPUT_CSV)
    print(f"Wrote {OUTPUT_CSV}")
