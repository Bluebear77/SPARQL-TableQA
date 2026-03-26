#!/usr/bin/env python3
"""
Filter "simple" questions from CompMix_table.jsonl.

How this works
--------------
The CompMix JSONL records do NOT contain an explicit field like
"question_type": "simple" / "temporal" / "aggregation" / "conjunction".

So this script follows the paper's taxonomy and uses a conservative heuristic:

1) Keep only records whose answer source is already "table"
   (if you run it on CompMix_table.jsonl, this is already true).

2) Mark a question as NON-simple and remove it if it looks like:
   - conjunction / multi-constraint:
       contains cues such as "both", "and", "or", "either", "also"
   - temporal understanding:
       contains years, dates, ordinals/sequencing, seasons/episodes, or time words
       such as "when", "before", "after", "first", "last", "released", etc.
   - aggregation / counting / superlatives:
       contains cues such as "how many", "most", "least", "total", "average", etc.

3) Everything not matched by those "complex" cues is kept as "simple".

This is intentionally conservative: it may exclude some truly simple questions
that happen to mention time-like wording, but it reduces false positives.
"""

import json
import re
from pathlib import Path

INPUT_PATH = Path("CompMix_table.jsonl")
OUTPUT_PATH = Path("CompMix_table_simple.jsonl")

# Cues for non-simple questions.
TEMPORAL_PATTERNS = [
    r"\bwhen\b",
    r"\bwhat year\b",
    r"\bwhich year\b",
    r"\bwhat date\b",
    r"\bwhich date\b",
    r"\bdate of birth\b",
    r"\b\d{4}\b",          # any explicit year like 1999, 2021
    r"\bbefore\b",
    r"\bafter\b",
    r"\bduring\b",
    r"\bsince\b",
    r"\buntil\b",
    r"\bto present\b",
    r"\bfirst\b",
    r"\blast\b",
    r"\bsecond\b",
    r"\bthird\b",
    r"\bfourth\b",
    r"\bfifth\b",
    r"\bsixth\b",
    r"\bseventh\b",
    r"\beighth\b",
    r"\bninth\b",
    r"\btenth\b",
    r"\bshortest\b",
    r"\blongest\b",
    r"\bfrist\b",
    r"\bdebut\b",
    r"\bseason\b",
    r"\bepisode\b",
    r"\bborn\b",
    r"\breleased\b",
    r"\bpublished\b",
    r"\binducted\b",
    r"\byear\b",
    r"\bcentury\b",
    r"\bage\b",
    r"\blatest\b",
    r"\bnext\b",
    r"\bprevious\b",
]

AGGREGATION_PATTERNS = [
    r"\bhow many\b",
    r"\bnumber of\b",
    r"\bmost\b",
    r"\bleast\b",
    r"\bhighest\b",
    r"\blowest\b",
    r"\btotal\b",
    r"\bcount\b",
    r"\bhow much\b",
    r"\baverage\b",
    r"\bmean\b",
]

CONJUNCTION_PATTERNS = [
    r"\bboth\b",
    r"\band\b",
    r"\bor\b",
    r"\balso\b",
    r"\beither\b",
]

def detect_complex_reason(question: str):
    """
    Return the reason why a question is NOT simple:
    'aggregation', 'temporal', 'conjunction', or None.
    """
    q = question.lower().strip()

    for pattern in AGGREGATION_PATTERNS:
        if re.search(pattern, q):
            return "aggregation"

    for pattern in TEMPORAL_PATTERNS:
        if re.search(pattern, q):
            return "temporal"

    for pattern in CONJUNCTION_PATTERNS:
        if re.search(pattern, q):
            return "conjunction"

    return None

def main():
    kept = 0
    removed = 0

    with INPUT_PATH.open("r", encoding="utf-8") as fin, \
         OUTPUT_PATH.open("w", encoding="utf-8") as fout:

        for line in fin:
            record = json.loads(line)

            # Safety check: if someone runs the script on a mixed file,
            # keep only table-source records.
            if record.get("answer_src") != "table":
                continue

            question = record.get("question", "")
            reason = detect_complex_reason(question)

            # If there is NO complex-reason match, treat it as a simple question.
            if reason is None:
                fout.write(json.dumps(record, ensure_ascii=False) + "\n")
                kept += 1
            else:
                removed += 1

    print(f"Wrote {kept} simple table questions to: {OUTPUT_PATH}")
    print(f"Removed {removed} non-simple table questions")

if __name__ == "__main__":
    main()
