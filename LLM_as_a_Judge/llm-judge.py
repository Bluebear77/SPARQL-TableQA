#!/usr/bin/env python3

"""
Command to run:

export MODEL="Qwen/Qwen3-30B-A3B-Thinking-2507"
export MODEL_ENDPOINT="https://litellm.tools.eurecom.fr/v1"
export OPENAI_API_KEY="your_api_key_here"

python llm-judge.py \
  --input_csv different_unclassified_question_30B.csv \
  --output_csv judge_outputs/30B_judge.csv \
  --model "$MODEL" \
  --base_url "$MODEL_ENDPOINT" \
  --api_key "$OPENAI_API_KEY" \
  --resume \
  --max_tokens 4096 \
  --disable_guided_json \
  --save_every 1 \
  --stream_reasoning

What this script does:
1. Reads a raw input CSV row by row.
2. Sends each (question, gold_answer, KG answer) triple to an LLM judge.
3. Keeps thinking mode enabled for thinking models.
4. Streams live model output to the terminal while each row is being judged.
5. Extracts final JSON from:
      - streamed/final message.content
      - streamed/final message.reasoning
      - streamed/final message.reasoning_content
      - text containing <think>...</think> followed by JSON
6. Parses the JSON in Python.
7. Writes the parsed results into one full output CSV by adding:
      - source_row_id
      - taxonomy_label
      - LLM explanation
      - difference_severity
      - optionally LLM raw JSON
8. Shows a tqdm progress bar while processing rows.
9. Prints each row result immediately after it is judged.
10. Periodically saves progress so long runs can be resumed safely.
11. Supports resume by loading the output CSV and skipping already judged rows.
12. Sorts the final output CSV by taxonomy_label.
13. Writes one Markdown statistics report.

Important:
- Do not hardcode real API keys in this file.
- Use environment variables instead.
- Live reasoning display depends on whether the endpoint exposes reasoning deltas.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from openai import OpenAI
from tqdm import tqdm

# ============================================================
# 1) Default file paths and server settings
# ============================================================

DEFAULT_INPUT_CSV = "different_unclassified_question_30B.csv"
DEFAULT_OUTPUT_CSV = "judge_outputs/30B_judge.csv"
DEFAULT_BASE_URL = "https://litellm.tools.eurecom.fr/v1"
DEFAULT_API_KEY = "EMPTY"
DEFAULT_MODEL = "Qwen/Qwen3-30B-A3B-Thinking-2507"

DEFAULT_STATS_SUFFIX = "_taxonomy_label_statistics.md"

SOURCE_ROW_ID_COL = "source_row_id"

# ============================================================
# 2) Taxonomy labels
# ============================================================

VALID_LABELS = [
    "Same",
    "Higher accuracy in KG than in Table",
    "Higher accuracy in Table than in KG",
    "Different answer",
    "Temporal changes",
]

ERROR_LABEL = "ERROR"

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

2. Higher accuracy in KG than in Table
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

3. Higher accuracy in Table than in KG
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
- You may think internally before answering.
- The final answer must contain valid JSON.
- The final JSON must contain exactly these keys:
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

Return exactly one valid JSON object and nothing else.
Do not output free-form analysis, markdown, prefixes, suffixes, or code fences.
If the case is ambiguous, still choose the best label and return JSON only.
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

# ============================================================
# 5) Utility helpers
# ============================================================

def build_prompt(question: str, gold_answer: str, kg_answer: str) -> str:
    return JUDGE_PROMPT_TEMPLATE.format(
        question=question or "",
        gold_answer=gold_answer or "",
        kg_answer=kg_answer or "",
        valid_labels_json=json.dumps(VALID_LABELS, ensure_ascii=False),
    )

def ensure_required_columns(df: pd.DataFrame) -> None:
    required = {"question", "gold_answer", "KG answer"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            "Input CSV is missing required columns: " + ", ".join(sorted(missing))
        )

def normalize_text_cell(value: Any) -> str:
    return "" if pd.isna(value) else str(value)

def compact_text(value: Any, max_chars: int = 120) -> str:
    text = normalize_text_cell(value).replace("\n", " ").replace("\r", " ")
    text = " ".join(text.split())

    if len(text) <= max_chars:
        return text

    return text[: max_chars - 3] + "..."

def object_to_debug_json(obj: Any) -> str:
    try:
        return obj.model_dump_json(indent=2)
    except Exception:
        pass

    try:
        return json.dumps(obj, indent=2, default=str, ensure_ascii=False)
    except Exception:
        return repr(obj)

# ============================================================
# 6) Robust extraction for thinking models
# ============================================================

def extract_message_fields(message: Any) -> Dict[str, str]:
    fields: Dict[str, str] = {}

    for field_name in ["content", "reasoning", "reasoning_content"]:
        value = getattr(message, field_name, None)
        if value is not None and str(value).strip():
            fields[field_name] = str(value).strip()

    try:
        message_dict = message.model_dump()
    except Exception:
        message_dict = None

    if isinstance(message_dict, dict):
        for field_name in ["content", "reasoning", "reasoning_content"]:
            value = message_dict.get(field_name)
            if value is not None and str(value).strip():
                fields[field_name] = str(value).strip()

    return fields

def extract_chat_text(completion: Any) -> str:
    try:
        message = completion.choices[0].message
    except Exception as exc:
        raise ValueError("Could not extract message from chat completion response") from exc

    fields = extract_message_fields(message)

    if fields:
        combined_parts = []
        for key in ["content", "reasoning", "reasoning_content"]:
            if key in fields:
                combined_parts.append(fields[key])
        return "\n\n".join(combined_parts).strip()

    debug_payload = object_to_debug_json(completion)
    print("\nFULL EMPTY-CONTENT COMPLETION DEBUG:")
    print(debug_payload)
    print("", flush=True)

    raise ValueError("Chat completion returned empty content")

def strip_markdown_code_fence(text: str) -> str:
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json|JSON)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    return text.strip()

def remove_think_blocks(text: str) -> str:
    text = text.strip()
    text = re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return text.strip()

def find_json_candidates(text: str) -> List[str]:
    candidates: List[str] = []
    stack: List[int] = []
    in_string = False
    escape = False
    start_index: Optional[int] = None

    for i, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char == "{":
            if not stack:
                start_index = i
            stack.append(i)
            continue

        if char == "}":
            if stack:
                stack.pop()
                if not stack and start_index is not None:
                    candidates.append(text[start_index : i + 1])
                    start_index = None

    return candidates

def extract_json_object(text: str) -> Dict[str, Any]:
    original_text = text.strip()

    attempts = [
        original_text,
        strip_markdown_code_fence(original_text),
        remove_think_blocks(original_text),
        strip_markdown_code_fence(remove_think_blocks(original_text)),
    ]

    for candidate in attempts:
        candidate = candidate.strip()
        if not candidate:
            continue

        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    cleaned_text = strip_markdown_code_fence(remove_think_blocks(original_text))

    for candidate in find_json_candidates(cleaned_text):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    for candidate in find_json_candidates(original_text):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    preview = original_text[:1000].replace("\n", "\\n")
    raise ValueError(f"No valid JSON object found in model output. Preview: {preview}")

# ============================================================
# 7) Streaming helpers
# ============================================================

def extract_delta_fields(delta: Any) -> Dict[str, str]:
    fields: Dict[str, str] = {}

    for field_name in ["content", "reasoning", "reasoning_content"]:
        value = getattr(delta, field_name, None)
        if value is not None and str(value):
            fields[field_name] = str(value)

    try:
        delta_dict = delta.model_dump()
    except Exception:
        delta_dict = None

    if isinstance(delta_dict, dict):
        for field_name in ["content", "reasoning", "reasoning_content"]:
            value = delta_dict.get(field_name)
            if value is not None and str(value):
                fields[field_name] = str(value)

    return fields

def print_stream_header(*, source_row_id: Any, question: str, show_inputs: bool) -> None:
    tqdm.write("")
    tqdm.write("-" * 90)
    tqdm.write(f"Streaming judge output for {SOURCE_ROW_ID_COL}={source_row_id}")
    if show_inputs:
        tqdm.write(f"Question: {compact_text(question, 220)}")
    tqdm.write("-" * 90)
    sys.stdout.flush()
    sys.stderr.flush()

def print_stream_footer() -> None:
    sys.stdout.write("\n")
    sys.stdout.flush()
    tqdm.write("-" * 90)
    sys.stdout.flush()
    sys.stderr.flush()

def stream_chat_text(
    client: OpenAI,
    request_kwargs: Dict[str, Any],
    stream_reasoning: bool = True,
) -> str:
    full_content_parts: List[str] = []
    full_reasoning_parts: List[str] = []
    full_reasoning_content_parts: List[str] = []

    seen_any_stream_text = False
    printed_reasoning_prefix = False
    printed_content_prefix = False

    stream = client.chat.completions.create(stream=True, **request_kwargs)

    for chunk in stream:
        try:
            choice = chunk.choices[0]
        except Exception:
            continue

        delta = getattr(choice, "delta", None)
        if delta is None:
            continue

        fields = extract_delta_fields(delta)

        reasoning_piece = ""
        content_piece = ""

        if stream_reasoning:
            reasoning_piece = fields.get("reasoning", "") + fields.get("reasoning_content", "")

        if fields.get("content"):
            content_piece = fields["content"]

        if reasoning_piece:
            if not printed_reasoning_prefix:
                sys.stdout.write("[reasoning] ")
                printed_reasoning_prefix = True
                seen_any_stream_text = True
            sys.stdout.write(reasoning_piece)
            sys.stdout.flush()

        if content_piece:
            if stream_reasoning and printed_reasoning_prefix and not printed_content_prefix:
                sys.stdout.write("\n[final] ")
                printed_content_prefix = True
            elif not printed_content_prefix:
                sys.stdout.write("[final] ")
                printed_content_prefix = True
                seen_any_stream_text = True
            sys.stdout.write(content_piece)
            sys.stdout.flush()

        if fields.get("reasoning"):
            full_reasoning_parts.append(fields["reasoning"])

        if fields.get("reasoning_content"):
            full_reasoning_content_parts.append(fields["reasoning_content"])

        if fields.get("content"):
            full_content_parts.append(fields["content"])

    if seen_any_stream_text:
        sys.stdout.write("\n")
        sys.stdout.flush()

    combined_parts: List[str] = []

    content_text = "".join(full_content_parts).strip()
    reasoning_text = "".join(full_reasoning_parts).strip()
    reasoning_content_text = "".join(full_reasoning_content_parts).strip()

    for part in [content_text, reasoning_text, reasoning_content_text]:
        if part:
            combined_parts.append(part)

    return "\n\n".join(combined_parts).strip()

# ============================================================
# 8) Sorting and output
# ============================================================

def sort_dataframe_by_taxonomy_label(df: pd.DataFrame) -> pd.DataFrame:
    sorted_df = df.copy()

    order_map = {label: i for i, label in enumerate(LABEL_SORT_ORDER)}
    fallback_index = len(order_map)

    sorted_df["_taxonomy_sort_key"] = sorted_df["taxonomy_label"].map(
        lambda x: order_map.get(str(x), fallback_index)
    )

    sort_columns = ["_taxonomy_sort_key", "taxonomy_label"]
    if SOURCE_ROW_ID_COL in sorted_df.columns:
        sort_columns.append(SOURCE_ROW_ID_COL)

    sorted_df = sorted_df.sort_values(
        by=sort_columns,
        kind="stable",
    ).drop(columns=["_taxonomy_sort_key"])

    return sorted_df

def build_stats_path(output_csv: str) -> str:
    output_path = Path(output_csv)
    return str(output_path.with_name(output_path.stem + DEFAULT_STATS_SUFFIX))

def write_taxonomy_statistics_markdown(df: pd.DataFrame, output_path: str) -> None:
    total_rows = len(df)
    label_counts = df["taxonomy_label"].fillna("").astype(str).value_counts().to_dict()

    labels_to_report = list(LABEL_SORT_ORDER)
    unexpected_labels = [label for label in label_counts.keys() if label not in labels_to_report]
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

def save_outputs(df: pd.DataFrame, output_csv: str, stats_md: str) -> None:
    sorted_df = sort_dataframe_by_taxonomy_label(df)
    sorted_df.to_csv(output_csv, index=False)
    write_taxonomy_statistics_markdown(sorted_df, stats_md)

# ============================================================
# 9) Live row output
# ============================================================

def print_row_result(
    *,
    row_number: int,
    source_row_id: Any,
    question: str,
    gold_answer: str,
    kg_answer: str,
    result: Dict[str, str],
    show_inputs: bool,
) -> None:
    label = result.get("taxonomy_label", "")
    explanation = result.get("LLM explanation", "")
    severity = result.get("difference_severity", "")

    lines = []
    lines.append("")
    lines.append("=" * 90)
    lines.append(f"Processed row: {row_number}")
    lines.append(f"{SOURCE_ROW_ID_COL}: {source_row_id}")
    lines.append(f"taxonomy_label: {label}")
    lines.append(f"difference_severity: {severity}")
    lines.append(f"LLM explanation: {explanation}")

    if show_inputs:
        lines.append("")
        lines.append(f"Question: {compact_text(question, 220)}")
        lines.append(f"Gold answer: {compact_text(gold_answer, 220)}")
        lines.append(f"KG answer: {compact_text(kg_answer, 220)}")

    lines.append("=" * 90)

    tqdm.write("\n".join(lines))
    sys.stdout.flush()
    sys.stderr.flush()

# ============================================================
# 10) LLM judging
# ============================================================

def judge_row(
    client: OpenAI,
    model: str,
    question: str,
    gold_answer: str,
    kg_answer: str,
    max_retries: int = 3,
    sleep_seconds: float = 2.0,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    use_guided_json: bool = True,
    debug_empty: bool = False,
    stream_reasoning: bool = False,
    source_row_id: Any = None,
    show_inputs: bool = False,
) -> Dict[str, str]:
    prompt = build_prompt(question, gold_answer, kg_answer)

    last_error: Optional[Exception] = None
    last_raw_text = ""

    for attempt in range(1, max_retries + 1):
        try:
            request_kwargs: Dict[str, Any] = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a careful evaluation assistant. "
                            "You may reason internally, but the final answer must be valid JSON only."
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

            if use_guided_json:
                request_kwargs["extra_body"] = {
                    "guided_json": GUIDED_JSON_SCHEMA,
                }

            if stream_reasoning:
                print_stream_header(
                    source_row_id=source_row_id,
                    question=question,
                    show_inputs=show_inputs,
                )
                raw_text = stream_chat_text(
                    client=client,
                    request_kwargs=request_kwargs,
                    stream_reasoning=True,
                )
                print_stream_footer()
            else:
                completion = client.chat.completions.create(**request_kwargs)
                raw_text = extract_chat_text(completion)

            last_raw_text = raw_text
            parsed = extract_json_object(raw_text)

            taxonomy_label = parsed["taxonomy_label"]
            llm_explanation = parsed["llm_explanation"]
            difference_severity = parsed["difference_severity"]

            if taxonomy_label not in VALID_LABELS:
                raise ValueError(f"Invalid taxonomy label returned: {taxonomy_label}")

            if difference_severity not in {"none", "minor", "moderate", "major"}:
                raise ValueError(f"Invalid difference_severity returned: {difference_severity}")

            return {
                "taxonomy_label": taxonomy_label,
                "LLM explanation": str(llm_explanation),
                "difference_severity": str(difference_severity),
                "LLM raw JSON": raw_text,
            }

        except Exception as exc:
            last_error = exc

            if debug_empty:
                tqdm.write("")
                tqdm.write(f"Attempt {attempt} failed: {exc}")
                if last_raw_text:
                    tqdm.write("Last raw model text preview:")
                    tqdm.write(last_raw_text[:2000])
                tqdm.write("")
                sys.stdout.flush()

            if attempt < max_retries:
                time.sleep(sleep_seconds * attempt)
            else:
                break

    return {
        "taxonomy_label": ERROR_LABEL,
        "LLM explanation": f"Judge call failed after {max_retries} attempts: {last_error}",
        "difference_severity": "major",
        "LLM raw JSON": last_raw_text,
    }

# ============================================================
# 11) Loading and resume
# ============================================================

def initialize_output_columns(df: pd.DataFrame, save_raw_json: bool) -> pd.DataFrame:
    df = df.copy()

    if SOURCE_ROW_ID_COL not in df.columns:
        df.insert(0, SOURCE_ROW_ID_COL, range(len(df)))

    if "taxonomy_label" not in df.columns:
        df["taxonomy_label"] = ""

    if "LLM explanation" not in df.columns:
        df["LLM explanation"] = ""

    if "difference_severity" not in df.columns:
        df["difference_severity"] = ""

    if save_raw_json and "LLM raw JSON" not in df.columns:
        df["LLM raw JSON"] = ""

    return df

def load_existing_judgments(
    df: pd.DataFrame,
    output_csv: str,
    save_raw_json: bool,
) -> pd.DataFrame:
    if not os.path.exists(output_csv):
        return df

    existing = pd.read_csv(output_csv)

    if SOURCE_ROW_ID_COL not in existing.columns:
        return df

    columns_to_merge = [
        SOURCE_ROW_ID_COL,
        "taxonomy_label",
        "LLM explanation",
        "difference_severity",
    ]

    if save_raw_json and "LLM raw JSON" in existing.columns:
        columns_to_merge.append("LLM raw JSON")

    columns_to_merge = [col for col in columns_to_merge if col in existing.columns]

    existing_subset = existing[columns_to_merge].copy().drop_duplicates(
        subset=[SOURCE_ROW_ID_COL],
        keep="last",
    )

    df = df.drop(
        columns=[
            col for col in [
                "taxonomy_label",
                "LLM explanation",
                "difference_severity",
                "LLM raw JSON",
            ] if col in df.columns
        ],
        errors="ignore",
    )

    df = df.merge(existing_subset, on=SOURCE_ROW_ID_COL, how="left")

    for col in ["taxonomy_label", "LLM explanation", "difference_severity"]:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("")

    if save_raw_json:
        if "LLM raw JSON" not in df.columns:
            df["LLM raw JSON"] = ""
        df["LLM raw JSON"] = df["LLM raw JSON"].fillna("")

    return df

def load_or_initialize_dataframe(
    input_csv: str,
    output_csv: str,
    resume: bool,
    save_raw_json: bool,
) -> pd.DataFrame:
    df = pd.read_csv(input_csv)
    ensure_required_columns(df)

    df = initialize_output_columns(df, save_raw_json=save_raw_json)

    if resume:
        df = load_existing_judgments(
            df=df,
            output_csv=output_csv,
            save_raw_json=save_raw_json,
        )

    return df

def build_indices_to_process(df: pd.DataFrame, resume: bool) -> List[int]:
    indices_to_process: List[int] = []

    for idx, row in df.iterrows():
        label = str(row.get("taxonomy_label", "")).strip()

        if not resume:
            indices_to_process.append(idx)
            continue

        if not label:
            indices_to_process.append(idx)
            continue

        if label == ERROR_LABEL:
            indices_to_process.append(idx)
            continue

    return indices_to_process

# ============================================================
# 12) Processing
# ============================================================

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
    show_inputs: bool,
    debug_empty: bool,
    stream_reasoning: bool,
) -> None:
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    Path(stats_md).parent.mkdir(parents=True, exist_ok=True)

    df = load_or_initialize_dataframe(
        input_csv=input_csv,
        output_csv=output_csv,
        resume=resume,
        save_raw_json=save_raw_json,
    )

    indices_to_process = build_indices_to_process(df=df, resume=resume)
    already_done_count = len(df) - len(indices_to_process)

    print("", flush=True)
    print(f"Input CSV: {input_csv}", flush=True)
    print(f"Output CSV: {output_csv}", flush=True)
    print(f"Stats Markdown: {stats_md}", flush=True)
    print(f"Total rows: {len(df)}", flush=True)
    print(f"Rows already judged/skipped: {already_done_count}", flush=True)
    print(f"Rows to process now: {len(indices_to_process)}", flush=True)
    print("", flush=True)

    processed_since_save = 0

    progress_bar = tqdm(
        indices_to_process,
        desc=f"Judging {Path(input_csv).name}",
        unit="row",
        dynamic_ncols=True,
    )

    for processed_number, idx in enumerate(progress_bar, start=1):
        row = df.loc[idx]

        source_row_id = int(row[SOURCE_ROW_ID_COL])
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
            debug_empty=debug_empty,
            stream_reasoning=stream_reasoning,
            source_row_id=source_row_id,
            show_inputs=show_inputs,
        )

        df.at[idx, "taxonomy_label"] = result["taxonomy_label"]
        df.at[idx, "LLM explanation"] = result["LLM explanation"]
        df.at[idx, "difference_severity"] = result["difference_severity"]

        if save_raw_json:
            df.at[idx, "LLM raw JSON"] = result["LLM raw JSON"]

        processed_since_save += 1

        progress_bar.set_postfix(label=result["taxonomy_label"], refresh=True)

        print_row_result(
            row_number=processed_number,
            source_row_id=source_row_id,
            question=question,
            gold_answer=gold_answer,
            kg_answer=kg_answer,
            result=result,
            show_inputs=show_inputs,
        )

        if processed_since_save >= save_every:
            save_outputs(df, output_csv, stats_md)
            processed_since_save = 0
            tqdm.write(f"Checkpoint saved to: {output_csv}")
            sys.stdout.flush()

    save_outputs(df, output_csv, stats_md)

    print("", flush=True)
    print(f"Done. Wrote judged CSV to: {output_csv}", flush=True)
    print(f"Done. Wrote taxonomy statistics to: {stats_md}", flush=True)

# ============================================================
# 13) CLI
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a full first-pass LLM-as-judge experiment on a new input CSV."
    )

    parser.add_argument(
        "--input_csv",
        default=DEFAULT_INPUT_CSV,
        help=f"Raw input CSV file to judge. Default: {DEFAULT_INPUT_CSV}",
    )

    parser.add_argument(
        "--output_csv",
        default=DEFAULT_OUTPUT_CSV,
        help=f"Output CSV path for judged results. Default: {DEFAULT_OUTPUT_CSV}",
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
        help="API key passed to the OpenAI client. Prefer using OPENAI_API_KEY.",
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from an existing judged output CSV by skipping already judged rows.",
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
        default=4096,
        help="Maximum completion tokens per judgment.",
    )

    parser.add_argument(
        "--save_raw_json",
        action="store_true",
        help="Also save the raw model text in a column called 'LLM raw JSON'.",
    )

    parser.add_argument(
        "--disable_guided_json",
        action="store_true",
        help="Disable `guided_json` for endpoints that do not support it.",
    )

    parser.add_argument(
        "--show_inputs",
        action="store_true",
        help="Print the question, gold answer, and KG answer with every live row result.",
    )

    parser.add_argument(
        "--debug_empty",
        action="store_true",
        help="Print extra debug information when extraction or parsing fails.",
    )

    parser.add_argument(
        "--stream_reasoning",
        action="store_true",
        help="Stream live model output to the terminal.",
    )

    args = parser.parse_args()

    if args.save_every <= 0:
        raise ValueError("--save_every must be greater than 0")

    Path(args.output_csv).parent.mkdir(parents=True, exist_ok=True)
    stats_md = build_stats_path(args.output_csv)

    client = OpenAI(
        api_key=args.api_key,
        base_url=args.base_url,
    )

    process_single_csv(
        client=client,
        input_csv=args.input_csv,
        output_csv=args.output_csv,
        stats_md=stats_md,
        model=args.model,
        resume=args.resume,
        save_every=args.save_every,
        max_retries=args.max_retries,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        save_raw_json=args.save_raw_json,
        use_guided_json=not args.disable_guided_json,
        show_inputs=args.show_inputs,
        debug_empty=args.debug_empty,
        stream_reasoning=args.stream_reasoning,
    )

if __name__ == "__main__":
    main()
