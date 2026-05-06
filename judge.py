#!/usr/bin/env python3

"""
Command to run:
export MODEL="Qwen/Qwen3-30B-A3B-Thinking-2507"
export MODEL_ENDPOINT="https://litellm.tools.eurecom.fr/v1"
export HOSTED_VLLM_API_KEY="sk-s_8h8KQn8dloO75nkjtSLg"

python judge.py \
  --input_csvs ComplexQA_unclassified_questions.csv SimpleQA_unclassified_questions.csv \
  --model "$MODEL" \
  --base_url "$MODEL_ENDPOINT" \
  --api_key "$HOSTED_VLLM_API_KEY"

Run an LLM-as-judge experiment over one or more CSV files using an OpenAI-compatible endpoint
(such as vLLM, LiteLLM, or another compatible server).

What this script does:
1. Reads one or more input CSV files row by row.
2. Sends each (question, gold_answer, KG answer) triple to an LLM judge.
3. Asks the model to return structured JSON for each row.
4. Parses that JSON in Python.
5. Writes the parsed results into one output CSV per input file by adding:
      - taxonomy_label
      - LLM explanation
6. Shows a tqdm progress bar while processing rows.
7. Periodically saves progress so long runs can be resumed safely.
8. Sorts each final output CSV by taxonomy_label.
9. Writes one Markdown statistics report per input CSV with the number and percentage
   of each taxonomy label.

Important clarification:
- The model DOES return JSON for each row.
- This script parses that JSON internally and stores only the useful fields in the
  CSV, so your final files are normal CSV files rather than JSON files.
- If you want to inspect the exact raw JSON returned by the model, this script can
  optionally save it in an extra column called `LLM raw JSON`.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from openai import OpenAI
from tqdm import tqdm


# ============================================================
# 1) Default file paths and server settings
# ============================================================
DEFAULT_INPUT_CSVS = [
    "different_unclassified_question_235B.csv",
    "different_unclassified_question_4B.csv"
   ]

DEFAULT_OUTPUT_DIR = "judge_outputs"
DEFAULT_BASE_URL = "https://litellm.tools.eurecom.fr/v1"
# http://localhost:8000/v1"
DEFAULT_API_KEY = "EMPTY"  # Local vLLM often accepts any placeholder value
DEFAULT_MODEL = "Qwen/Qwen3-30B-A3B-Thinking-2507"

# Default suffixes used to build per-input output filenames.
# Example:
#   ComplexQA_unclassified_questions.csv
# becomes:
#   judge_outputs/ComplexQA_unclassified_questions_judged.csv
#   judge_outputs/ComplexQA_unclassified_questions_taxonomy_label_statistics.md
DEFAULT_OUTPUT_SUFFIX = "_judged.csv"
DEFAULT_STATS_SUFFIX = "_taxonomy_label_statistics.md"


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

# We also use a custom error label in Python if a row cannot be judged after retries.
# This value is NOT sent as an allowed model label, but it can appear in output CSV
# when the script fails on a row.
ERROR_LABEL = "ERROR"

# Sort order used for the final CSV and statistics output.
# This keeps results grouped in a stable, human-friendly order instead of plain
# alphabetical order.
LABEL_SORT_ORDER = VALID_LABELS + [ERROR_LABEL]



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
# This schema is passed to the OpenAI-compatible endpoint to constrain the
# model output to the exact JSON structure we want.
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
    """
    Fill the judge prompt template with row-specific values.

    Empty strings are used instead of None so that prompt formatting never fails.
    """
    return JUDGE_PROMPT_TEMPLATE.format(
        question=question or "",
        gold_answer=gold_answer or "",
        kg_answer=kg_answer or "",
        valid_labels_json=json.dumps(VALID_LABELS, ensure_ascii=False),
    )


def ensure_required_columns(df: pd.DataFrame) -> None:
    """
    Validate that the input DataFrame contains the columns required by the script.

    Required columns:
    - question
    - gold_answer
    - KG answer

    We fail early with a clear error message because the rest of the script depends
    on these names exactly.
    """
    required = {"question", "gold_answer", "KG answer"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            "Input CSV is missing required columns: " + ", ".join(sorted(missing))
        )


def extract_chat_text(completion: Any) -> str:
    """
    Extract the text content from a chat completion response.

    The OpenAI-compatible client returns a structured object. We expect the model's
    JSON string to be in:
        completion.choices[0].message.content

    A dedicated helper makes response parsing easier to read and centralizes the
    error handling.
    """
    try:
        return completion.choices[0].message.content
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Could not extract text from chat completion response") from exc


def normalize_text_cell(value: Any) -> str:
    """
    Convert a DataFrame cell to a safe string for prompting.

    Pandas may store missing values as NaN. For prompting, we want missing entries
    to become empty strings rather than the literal text 'nan'.
    """
    return "" if pd.isna(value) else str(value)


def sort_dataframe_by_taxonomy_label(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a copy of the DataFrame sorted by taxonomy_label using a custom label order.

    Why not just use alphabetical sorting?
    - The taxonomy has a logical order defined by the experiment design.
    - Grouping rows in that order makes the output easier to inspect manually.

    Any unknown labels are placed after known labels.
    """
    sorted_df = df.copy()

    order_map = {label: i for i, label in enumerate(LABEL_SORT_ORDER)}
    fallback_index = len(order_map)

    # Create a temporary numeric key for sorting, then remove it afterward.
    sorted_df["_taxonomy_sort_key"] = sorted_df["taxonomy_label"].map(
        lambda x: order_map.get(str(x), fallback_index)
    )

    sorted_df = sorted_df.sort_values(
        by=["_taxonomy_sort_key", "taxonomy_label"],
        kind="stable",
    ).drop(columns=["_taxonomy_sort_key"])

    return sorted_df


def write_taxonomy_statistics_markdown(df: pd.DataFrame, output_path: str) -> None:
    """
    Write a Markdown report summarizing taxonomy label counts and percentages.

    The report includes:
    - total number of rows
    - one row per taxonomy label
    - count for each label
    - percentage for each label

    Labels from VALID_LABELS are always shown, even if their count is zero.
    The custom ERROR label is also included when present.
    """
    total_rows = len(df)

    # Count labels while normalizing values to strings.
    label_counts = df["taxonomy_label"].fillna("").astype(str).value_counts().to_dict()

    # Start with the known taxonomy labels in desired order.
    labels_to_report = list(LABEL_SORT_ORDER)

    # If there are unexpected labels in the data, append them to the end so they are
    # not silently omitted from the report.
    unexpected_labels = [
        label for label in label_counts.keys() if label not in labels_to_report
    ]
    labels_to_report.extend(sorted(unexpected_labels))

    lines = []
    lines.append("# Taxonomy Label Statistics")
    lines.append("")
    lines.append(f"Total rows: **{total_rows}**")
    lines.append("")
    lines.append("| Taxonomy Label | Count | Percentage |")
    lines.append("|---|---:|---:|")

    for label in labels_to_report:
        count = label_counts.get(label, 0)
        percentage = (count / total_rows * 100.0) if total_rows > 0 else 0.0
        lines.append(f"| {label} | {count} | {percentage:.2f}% |")

    lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


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
    use_guided_json: bool = True,
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

    Retry strategy:
    - If the request fails or the JSON is invalid, retry up to max_retries times.
    - Wait longer after each failure using a simple linear backoff:
          sleep_seconds * attempt

    Compatibility note:
    - Some endpoints support structured decoding with `guided_json`.
    - Others do not.
    - This function can run in either mode based on `use_guided_json`.
    """
    prompt = build_prompt(question, gold_answer, kg_answer)
    last_error: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            request_kwargs: Dict[str, Any] = {
                "model": model,
                "messages": [
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
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            # Add guided JSON only when requested.
            if use_guided_json:
                request_kwargs["extra_body"] = {"guided_json": GUIDED_JSON_SCHEMA}

            completion = client.chat.completions.create(**request_kwargs)

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

    # If all retries fail, return a structured fallback result rather than crashing
    # the whole run. This is useful for large experiments where a few bad rows should
    # not abort everything.
    return {
        "taxonomy_label": ERROR_LABEL,
        "LLM explanation": f"Judge call failed after {max_retries} attempts: {last_error}",
        "LLM raw JSON": "",
    }


def build_output_paths(input_csv: str, output_dir: str) -> Tuple[str, str]:
    """
    Build the output CSV path and Markdown statistics path for one input CSV.

    Example:
    - Input:
        ComplexQA_unclassified_questions.csv
    - Output CSV:
        judge_outputs/ComplexQA_unclassified_questions_judged.csv
    - Stats MD:
        judge_outputs/ComplexQA_unclassified_questions_taxonomy_label_statistics.md

    Using one output file per input file keeps the run easy to inspect and avoids
    mixing multiple datasets into one judged CSV.
    """
    input_path = Path(input_csv)
    stem = input_path.stem

    output_csv = str(Path(output_dir) / f"{stem}{DEFAULT_OUTPUT_SUFFIX}")
    stats_md = str(Path(output_dir) / f"{stem}{DEFAULT_STATS_SUFFIX}")

    return output_csv, stats_md


def save_outputs(df: pd.DataFrame, output_csv: str, stats_md: str) -> None:
    """
    Save both final artifacts:
    1. A CSV sorted by taxonomy_label.
    2. A Markdown statistics file with counts and percentages.

    This helper is used both during periodic checkpoint saves and at the end of the run
    so that the CSV and statistics file stay in sync.
    """
    sorted_df = sort_dataframe_by_taxonomy_label(df)
    sorted_df.to_csv(output_csv, index=False)
    write_taxonomy_statistics_markdown(sorted_df, stats_md)


def load_or_initialize_dataframe(
    input_csv: str,
    output_csv: str,
    resume: bool,
    save_raw_json: bool,
) -> pd.DataFrame:
    """
    Load the input CSV and prepare output columns.

    Resume behavior:
    - If `resume` is enabled and the output CSV already exists, previously saved
      judgment columns are copied back into the freshly loaded input DataFrame.

    Why load the original input CSV again even when resuming?
    - It ensures the source data remains authoritative.
    - It avoids accidental drift if the judged file was edited manually.
    """
    df = pd.read_csv(input_csv)
    ensure_required_columns(df)

    # Add output columns if they do not already exist.
    if "taxonomy_label" not in df.columns:
        df["taxonomy_label"] = ""
    if "LLM explanation" not in df.columns:
        df["LLM explanation"] = ""
    if save_raw_json and "LLM raw JSON" not in df.columns:
        df["LLM raw JSON"] = ""

    # Resume from an existing judged CSV if requested.
    if resume and os.path.exists(output_csv):
        existing = pd.read_csv(output_csv)
        ensure_required_columns(existing)

        if "taxonomy_label" in existing.columns and len(existing) == len(df):
            df["taxonomy_label"] = existing["taxonomy_label"]
        if "LLM explanation" in existing.columns and len(existing) == len(df):
            df["LLM explanation"] = existing["LLM explanation"]
        if save_raw_json and "LLM raw JSON" in existing.columns and len(existing) == len(df):
            df["LLM raw JSON"] = existing["LLM raw JSON"]

    return df


def process_single_csv(
    client: OpenAI,
    input_csv: str,
    output_csv: str,
    stats_md: str,
    model: str,
    resume: bool,
    save_every: int,
    max_retries: int,
    temperature: float,
    max_tokens: int,
    save_raw_json: bool,
    use_guided_json: bool,
) -> None:
    """
    Process one input CSV from start to finish.

    This function is intentionally separated from `main()` because the multi-file
    workflow becomes much easier to read when one helper handles the logic for a
    single dataset.
    """
    # Ensure parent directories exist before writing any files.
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    Path(stats_md).parent.mkdir(parents=True, exist_ok=True)

    # Load the input data and optionally merge in prior judgments.
    df = load_or_initialize_dataframe(
        input_csv=input_csv,
        output_csv=output_csv,
        resume=resume,
        save_raw_json=save_raw_json,
    )

    processed_since_save = 0

    # Build a list of row indices still needing judgment.
    # This makes tqdm progress accurate even when resuming a partially completed run.
    indices_to_process: List[int] = []
    for idx, row in df.iterrows():
        if resume and str(row.get("taxonomy_label", "")).strip():
            continue
        indices_to_process.append(idx)

    progress_bar = tqdm(
        indices_to_process,
        desc=f"Judging {Path(input_csv).name}",
        unit="row",
    )

    for idx in progress_bar:
        row = df.loc[idx]

        question = normalize_text_cell(row["question"])
        gold_answer = normalize_text_cell(row["gold_answer"])
        kg_answer = normalize_text_cell(row["KG answer"])

        result = judge_row(
            client=client,
            model=model,
            question=question,
            gold_answer=gold_answer,
            kg_answer=kg_answer,
            max_retries=max_retries,
            temperature=temperature,
            max_tokens=max_tokens,
            use_guided_json=use_guided_json,
        )

        # Write the returned judgment back into the working DataFrame.
        df.at[idx, "taxonomy_label"] = result["taxonomy_label"]
        df.at[idx, "LLM explanation"] = result["LLM explanation"]
        if save_raw_json:
            df.at[idx, "LLM raw JSON"] = result["LLM raw JSON"]

        processed_since_save += 1

        # Show the latest predicted label in the tqdm postfix for quick monitoring.
        progress_bar.set_postfix(label=result["taxonomy_label"])

        # Periodically save progress.
        # We save both the sorted CSV and the Markdown statistics report at each checkpoint.
        if processed_since_save >= save_every:
            save_outputs(df, output_csv, stats_md)
            processed_since_save = 0

    # Final save after all rows are processed.
    save_outputs(df, output_csv, stats_md)

    print(f"Done. Wrote judged CSV to: {output_csv}")
    print(f"Done. Wrote taxonomy statistics to: {stats_md}")


def main() -> None:
    """
    Parse arguments, run row-by-row judging across one or more CSV files, and save
    one output CSV plus one stats file for each input CSV.

    Multi-file behavior:
    - Each input CSV is processed independently.
    - Each input CSV gets its own output CSV.
    - Each input CSV gets its own Markdown statistics report.

    Resume behavior:
    - If --resume is used, each input CSV checks for its own existing judged CSV
      and skips rows that already have a taxonomy_label.

    Output naming behavior:
    - Output files are created under --output_dir.
    - Filenames are derived automatically from the input filename stem.
    """
    parser = argparse.ArgumentParser(
        description="Run an LLM-as-judge taxonomy experiment using an OpenAI-compatible server."
    )

    parser.add_argument(
        "--input_csvs",
        nargs="+",
        default=DEFAULT_INPUT_CSVS,
        help=(
            "One or more input CSV paths. "
            f"Default: {' '.join(DEFAULT_INPUT_CSVS)}"
        ),
    )
    parser.add_argument(
        "--output_dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory where per-input output files will be written. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("MODEL", DEFAULT_MODEL),
        help=f"Model name exposed by the server. Default: {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--base_url",
        default=os.getenv("MODEL_ENDPOINT", DEFAULT_BASE_URL),
        help=f"OpenAI-compatible base URL. Default: {DEFAULT_BASE_URL}",
    )
    parser.add_argument(
        "--api_key",
        default=os.getenv("OPENAI_API_KEY", DEFAULT_API_KEY),
        help="API key passed to the OpenAI client.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from existing judged CSV files by skipping already judged rows.",
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
    parser.add_argument(
        "--disable_guided_json",
        action="store_true",
        help=(
            "Disable `guided_json` for endpoints that do not support it. "
            "Use this for some LiteLLM or proxy setups if structured decoding fails."
        ),
    )

    args = parser.parse_args()

    # Ensure the output directory exists once at startup.
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    client = OpenAI(api_key=args.api_key, base_url=args.base_url)

    # Process each input CSV independently.
    # This gives one judged CSV and one stats file per input CSV.
    for input_csv in args.input_csvs:
        output_csv, stats_md = build_output_paths(
            input_csv=input_csv,
            output_dir=args.output_dir,
        )

        print(f"Starting input CSV: {input_csv}")
        print(f"Output CSV will be: {output_csv}")
        print(f"Stats Markdown will be: {stats_md}")

        process_single_csv(
            client=client,
            input_csv=input_csv,
            output_csv=output_csv,
            stats_md=stats_md,
            model=args.model,
            resume=args.resume,
            save_every=args.save_every,
            max_retries=args.max_retries,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            save_raw_json=args.save_raw_json,
            use_guided_json=not args.disable_guided_json,
        )


if __name__ == "__main__":
    main()
