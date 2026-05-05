#!/usr/bin/env python3
"""
Run an LLM-as-judge experiment over a CSV using a local vLLM server.

What this script does:
1. Reads an input CSV row by row.
2. Sends each (question, gold_answer, KG answer) triple to an LLM judge.
3. Asks the model to return structured JSON for each row.
4. Parses that JSON in Python.
5. Writes the parsed results into an output CSV by adding:
      - taxonomy_label
      - LLM explanation
6. Shows a tqdm progress bar while processing rows.
7. Periodically saves progress so long runs can be resumed safely.

Important clarification:
- The model DOES return JSON for each row.
- This script parses that JSON internally and stores only the useful fields in the
  CSV, so your final file is expected to be a normal CSV rather than a JSON file.
- If you want to inspect the exact raw JSON returned by the model, this script can
  optionally save it in an extra column called `LLM raw JSON`.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any, Dict, Optional

import pandas as pd
from openai import OpenAI
from tqdm import tqdm


# ============================================================
# 1) Default file paths and server settings
# ============================================================
DEFAULT_INPUT_CSV = "sample.csv"
DEFAULT_OUTPUT_CSV = "sample_judged.csv"
DEFAULT_BASE_URL = "http://localhost:8000/v1"
DEFAULT_API_KEY = "EMPTY"  # vLLM usually accepts any placeholder value
DEFAULT_MODEL = "Qwen/Qwen3-4B-Instruct-2507"

# ============================================================
# 2) Taxonomy labels
# ============================================================
VALID_LABELS = [
    "Same",
    "Higher accuracy in Wikidata than in Table",
    "Higher accuracy in Table than in Wikidata",
    "Different answer",
    "Temporal changes",
]


# ============================================================
# 3) Prompt template
# ============================================================
JUDGE_PROMPT_TEMPLATE = """
You are an expert evaluator for answer comparison and inconsistency analysis.

Your task is to compare a Gold answer and a KG answer for the same question and assign exactly one label from the inconsistency taxonomy.

Judge semantic meaning, factual content, completeness, precision, and time sensitivity.
Do not judge based on superficial formatting alone.

Input:
- Question: {question}
- Reference (Gold) Answer: {gold_answer}
- KG Answer: {kg_answer}

Evaluation procedure:
1. Read the question carefully and identify the exact information being asked.
2. Read the Gold answer and extract its key facts.
3. Read the KG answer and extract its key facts.
4. Compare the two answers for:
   - semantic equivalence
   - factual agreement or conflict
   - completeness
   - precision/specificity
   - temporal validity
5. Decide whether the answers are effectively the same or meaningfully different.
6. If they differ, determine the best taxonomy label.
7. Return exactly one taxonomy label and one concise explanation.

Important judging rules:
- Treat answers as Same if they express the same meaning, even with different wording.
- Treat different date formats as Same if they refer to the same date.
- Also treat a bare year and a full timestamp ending in 01-01 as Same when they clearly represent the same year.
  Example: "1939" and "1939-01-01T00:00:00Z" should be treated as Same.
- Ignore differences that are only due to formatting, punctuation, capitalization, ordering, separators, or minor normalization.
- If one answer is a strict subset of the other, determine whether the larger answer is genuinely more complete or more precise.
- Use Different answer when the core values or facts conflict.
- Use Temporal changes only when both answers could be correct at different times and the disagreement is best explained by change over time.

Taxonomy labels and definitions:

Example format: [Question; Gold answer; KG answer]

1. Same
Definition:
The answers are semantically equivalent. Any differences are limited to formatting, normalization, ordering, or equivalent date representation. Neither answer is meaningfully more accurate or more complete than the other.

Examples:
- [Which type of genre is The Scarlet Letter?; Romantic, Historical; historical fiction romantic fiction]
- [What country does the soccer player Johan Cruyff represent?; Netherlands; Kingdom of the Netherlands]
- [What is the current population of Bora Bora?; 10,605; 10605]

2. Higher accuracy in Wikidata than in Table
Definition:
The KG answer fully covers the Gold answer and provides additional correct detail, higher precision, or greater completeness. The Gold answer is a subset of the KG answer.
Alternatively, the Gold answer refers to the same fact but with less precision.

Examples:
- [Who was the shirt sponsor for FC Cincinnati soccer club?; Mercy Health; Mercy Health, Toyota]
  Explanation: The KG answer includes the Gold answer and adds another sponsor.
- [When was the Mission San Antonio de Valero built?; 1718; 1718-05-01T00:00:00Z]
  Explanation: The KG answer is more precise because it gives a full year-month-day date.
- [What is the genre of the series The Sopranos?; crime serial; drama television series, crime television series]
  Explanation: The KG answer includes the Gold answer and extends it to a broader and more complete set of genres.

3. Higher accuracy in Table than in Wikidata
Definition:
The Gold answer fully covers the KG answer and provides additional correct detail, higher precision, or greater completeness. The KG answer is a subset of the Gold answer.
Alternatively, the KG answer refers to the same fact but with less precision.

Examples:
- [Where did the Battle of Freeman's Farm take place?; Stillwater, Saratoga County, New York; Stillwater]
  Explanation: The Gold answer covers the KG answer with higher precision and provides the county and state for Stillwater.
- [Who starred in Pirates of the Caribbean?; Johnny Depp, Geoffrey Rush, Kevin McNally, Orlando Bloom, Keira Knightley, Jack Davenport, Jonathan Pryce; Johnny Depp]
  Explanation: The Gold answer provides a more complete cast list. The KG answer is a subset of the Gold answer.
- [In what movie did Ian Charleson play Eric Liddell, and what year did the movie come out?; Chariots of Fire, 30 Mar 1981, 31 Mar 1981, 15 May 1981, 26 Sep 1981, 9 Apr 1982, 7 May 1982; Ian Charleson played Eric Liddell in Chariots of Fire, in 1981]
  Explanation: The Gold answer gives more complete release-date information across regions.

4. Different answer
Definition:
The answers contain conflicting core facts or values, and the disagreement is not best explained by different precision levels or by temporal change.

Examples:
- [What was the date of the signing of the Declaration of Independence?; August 2, 1776; 1776-07-04T00:00:00Z]
  Explanation: The answers conflict on the date; the month and day are contradictory.
- [What is the elevation of Dakar?; 22 m; 10 m]
  Explanation: The elevation values are contradictory.
- [What country did Raúl González represent in football?; Spain; Argentina]
  Explanation: The countries conflict.

5. Temporal changes
Definition:
The answers differ because the underlying fact changes over time, and both answers could plausibly be correct at different times.

Time-sensitive cue words or phrases in the question:
- currently
- current
- now
- as of now
- at present
- present-day
- latest
- newest
- most recent
- recently
- today
- this year
- at the time
- at that time
- before
- after
- since
- until
- last
- previous
- former
- updated
- update

Common time-sensitive fact types:
- population
- box office
- revenue
- net worth
- ranking
- standings
- champion
- CEO
- president
- prime minister
- office holder
- membership
- roster
- cast
- season finale
- release date
- sponsor

Judging guidance:
- Prefer this label when the question asks about a fact that can change over time.
- Prefer this label when both answers could be correct, but at different times.
- Cue words such as "current" or "latest" strengthen the case for this label, but they are not required.
- A question may still be time-sensitive even without explicit cue words if the fact type normally changes over time.
- Do not use this label when one answer is simply incorrect and time does not explain the difference.
- Do not use this label when the difference is only due to greater precision, formatting, or completeness rather than an actual change over time.

Examples:
- [What is the box office collection of the movie Oblivion?; $287.9 million; 286168572.0]
  Explanation: Box office totals can change over time as revenue accumulates.
- [What is the population of St. Petersburg, FL?; 260,999; 258308]
  Explanation: Population changes over time.
- [When is the season finale of Designated Survivor (Q22662417)?; May 16, 2018; 7 June 2019]
  Explanation: The answers appear to refer to different seasons at different times.

Output requirements:
- Return valid JSON only.
- The JSON must contain exactly these keys:
  - taxonomy_label
  - llm_explanation
  - difference_severity
- taxonomy_label must be exactly one of the allowed labels.
- difference_severity must be exactly one of:
  - none
  - minor
  - moderate
  - major
- Keep llm_explanation under 120 words.
- The explanation must briefly state:
  - whether the answers match or differ
  - the main missing, additional, or conflicting facts
  - the scale of the difference

Allowed taxonomy labels:
{valid_labels_json}
""".strip()

# ============================================================
# 4) JSON schema for guided output
# ============================================================
GUIDED_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "taxonomy_label": {
            "type": "string",
            "enum": VALID_LABELS,
        },
        "llm_explanation": {
            "type": "string",
        },
        "difference_severity": {
            "type": "string",
            "enum": ["none", "minor", "moderate", "major"],
        },
    },
    "required": [
        "taxonomy_label",
        "llm_explanation",
        "difference_severity",
    ],
}


def build_prompt(question: str, gold_answer: str, kg_answer: str) -> str:
    """Fill the prompt template with row values."""
    return JUDGE_PROMPT_TEMPLATE.format(
        question=question or "",
        gold_answer=gold_answer or "",
        kg_answer=kg_answer or "",
        valid_labels_json=json.dumps(VALID_LABELS, ensure_ascii=False),
    )



def ensure_required_columns(df: pd.DataFrame) -> None:
    """Fail early if the CSV does not have the required input columns."""
    required = {"question", "gold_answer", "KG answer"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            "Input CSV is missing required columns: " + ", ".join(sorted(missing))
        )



def extract_chat_text(completion: Any) -> str:
    """Extract the plain text content from a chat completion response."""
    try:
        return completion.choices[0].message.content
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Could not extract text from chat completion response") from exc



def judge_row(
    client: OpenAI,
    model: str,
    question: str,
    gold_answer: str,
    kg_answer: str,
    max_retries: int = 3,
    sleep_seconds: float = 2.0,
    temperature: float = 0.0,
    max_tokens: int = 220,
) -> Dict[str, str]:
    """
    Judge a single row with the model.

    Returns a dictionary with:
    - taxonomy_label
    - LLM explanation
    - LLM raw JSON

    Why include raw JSON?
    - It makes debugging much easier.
    - You can verify what the model actually returned.
    - If parsing ever looks suspicious, you have the original per-row payload saved.
    """
    prompt = build_prompt(question, gold_answer, kg_answer)
    last_error: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a careful evaluation assistant. "
                            "Follow the user's instructions exactly and return only valid JSON."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body={"guided_json": GUIDED_JSON_SCHEMA},
            )

            raw_text = extract_chat_text(completion)
            parsed = json.loads(raw_text)

            taxonomy_label = parsed["taxonomy_label"]
            llm_explanation = parsed["llm_explanation"]

            if taxonomy_label not in VALID_LABELS:
                raise ValueError(f"Invalid taxonomy label returned: {taxonomy_label}")

            return {
                "taxonomy_label": taxonomy_label,
                "LLM explanation": llm_explanation,
                "LLM raw JSON": raw_text,
            }

        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < max_retries:
                time.sleep(sleep_seconds * attempt)
            else:
                break

    return {
        "taxonomy_label": "ERROR",
        "LLM explanation": f"Judge call failed after {max_retries} attempts: {last_error}",
        "LLM raw JSON": "",
    }



def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run an LLM-as-judge taxonomy experiment using a local vLLM server."
    )

    parser.add_argument(
        "--input_csv",
        default=DEFAULT_INPUT_CSV,
        help=f"Path to input CSV. Default: {DEFAULT_INPUT_CSV}",
    )
    parser.add_argument(
        "--output_csv",
        default=DEFAULT_OUTPUT_CSV,
        help=f"Path to output CSV. Default: {DEFAULT_OUTPUT_CSV}",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model name exposed by the vLLM server. Default: {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--base_url",
        default=DEFAULT_BASE_URL,
        help=f"OpenAI-compatible base URL for vLLM. Default: {DEFAULT_BASE_URL}",
    )
    parser.add_argument(
        "--api_key",
        default=os.getenv("OPENAI_API_KEY", DEFAULT_API_KEY),
        help="API key passed to the OpenAI client. For local vLLM, 'EMPTY' is usually fine.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from an existing output CSV by skipping already judged rows.",
    )
    parser.add_argument(
        "--save_every",
        type=int,
        default=10,
        help="Save progress every N processed rows.",
    )
    parser.add_argument(
        "--max_retries",
        type=int,
        default=3,
        help="How many times to retry a failed row.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Sampling temperature. 0.0 is recommended for stable judging.",
    )
    parser.add_argument(
        "--max_tokens",
        type=int,
        default=220,
        help="Maximum completion tokens per judgment.",
    )
    parser.add_argument(
        "--save_raw_json",
        action="store_true",
        help="Also save the raw JSON returned by the model in a column called 'LLM raw JSON'.",
    )

    args = parser.parse_args()

    client = OpenAI(api_key=args.api_key, base_url=args.base_url)

    df = pd.read_csv(args.input_csv)
    ensure_required_columns(df)

    if "taxonomy_label" not in df.columns:
        df["taxonomy_label"] = ""
    if "LLM explanation" not in df.columns:
        df["LLM explanation"] = ""
    if args.save_raw_json and "LLM raw JSON" not in df.columns:
        df["LLM raw JSON"] = ""

    if args.resume and os.path.exists(args.output_csv):
        existing = pd.read_csv(args.output_csv)
        ensure_required_columns(existing)

        if "taxonomy_label" in existing.columns:
            df["taxonomy_label"] = existing["taxonomy_label"]
        if "LLM explanation" in existing.columns:
            df["LLM explanation"] = existing["LLM explanation"]
        if args.save_raw_json and "LLM raw JSON" in existing.columns:
            df["LLM raw JSON"] = existing["LLM raw JSON"]

    processed_since_save = 0

    # Build a list of row indices to process.
    # This makes tqdm progress accurate even when resuming.
    indices_to_process = []
    for idx, row in df.iterrows():
        if args.resume and str(row.get("taxonomy_label", "")).strip():
            continue
        indices_to_process.append(idx)

    progress_bar = tqdm(indices_to_process, desc="Judging rows", unit="row")

    for idx in progress_bar:
        row = df.loc[idx]

        question = "" if pd.isna(row["question"]) else str(row["question"])
        gold_answer = "" if pd.isna(row["gold_answer"]) else str(row["gold_answer"])
        kg_answer = "" if pd.isna(row["KG answer"]) else str(row["KG answer"])

        result = judge_row(
            client=client,
            model=args.model,
            question=question,
            gold_answer=gold_answer,
            kg_answer=kg_answer,
            max_retries=args.max_retries,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )

        df.at[idx, "taxonomy_label"] = result["taxonomy_label"]
        df.at[idx, "LLM explanation"] = result["LLM explanation"]
        if args.save_raw_json:
            df.at[idx, "LLM raw JSON"] = result["LLM raw JSON"]

        processed_since_save += 1

        # Show the latest label in the progress bar postfix for quick monitoring.
        progress_bar.set_postfix(label=result["taxonomy_label"])

        if processed_since_save >= args.save_every:
            df.to_csv(args.output_csv, index=False)
            processed_since_save = 0

    df.to_csv(args.output_csv, index=False)
    print(f"Done. Wrote judged CSV to: {args.output_csv}")


if __name__ == "__main__":
    main()
