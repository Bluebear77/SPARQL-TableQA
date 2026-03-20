import json
import re
import pandas as pd
from pathlib import Path

INPUT_PATH = Path("NQ_table_test.jsonl")
OUTPUT_PATH = Path("NQ_table_test_questions_answers_filtered.csv")

WH_STARTS = {
    "who", "when", "what", "where", "how", "which",
    "what's", "when's", "who's",
    "is", "are", "do", "does", "did", "can", "could", "will", "would", "was", "were"
}

RELATIVE_PATTERNS = [
    r"\bright now\b", r"\bcurrently\b", r"\bpresent time\b", r"\btoday\b", r"\btomorrow\b", r"\byesterday\b",
    r"\bthis year\b", r"\bthis month\b", r"\bthis week\b", r"\blast year\b",
    r"\bnew episodes?\b", r"\bseason finale\b", r"\bair date\b", r"\brelease date\b"
]

GENERAL_PATTERNS = [
    r"^\s*list of\b", r"^\s*list all\b", r"^\s*name three\b", r"^\s*different ways to\b",
    r"^\s*types of\b", r"^\s*kings and queens of\b", r"^\s*5 cities\b", r"^\s*three largest cities\b",
    r"^\s*show me\b"
]

def norm(text: str) -> str:
    text = (text or "").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text

def repair_question(question: str) -> str:
    question = norm(question)
    if not question:
        return question
    question = question[0].upper() + question[1:]
    if not question.endswith("?"):
        question += "?"
    return question

def is_standalone_specific(question: str) -> bool:
    q = norm(question).lower()
    if len(q.split()) < 5:
        return False
    if any(re.search(p, q) for p in RELATIVE_PATTERNS):
        return False
    if any(re.search(p, q) for p in GENERAL_PATTERNS):
        return False
    if re.search(r"^\s*(this|that|these|those)\b", q):
        return False
    if re.search(r"\b(real name|on a map)\b", q):
        return False
    first = q.split()[0] if q.split() else ""
    if first not in WH_STARTS:
        return False
    return True

rows = []
with INPUT_PATH.open("r", encoding="utf-8") as f:
    for line in f:
        obj = json.loads(line)
        for q in obj.get("questions", []):
            question_raw = q.get("originalText", "")
            answer_texts = q.get("answer", {}).get("answerTexts", []) or []
            answer_text = " | ".join(norm(a) for a in answer_texts if norm(a))
            question_text = repair_question(question_raw)

            if answer_text and is_standalone_specific(question_raw):
                rows.append({
                    "question_text": question_text,
                    "answer_text": answer_text,
                })

df = pd.DataFrame(rows).drop_duplicates().reset_index(drop=True)
df.to_csv(OUTPUT_PATH, index=False)

print(f"Wrote {len(df)} rows to {OUTPUT_PATH}")
print(df.head(10).to_string(index=False))
