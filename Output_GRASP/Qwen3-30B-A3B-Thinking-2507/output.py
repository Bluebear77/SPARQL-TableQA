#!/usr/bin/env python3
"""
Unified processing pipeline for GRASP JSON outputs.

Place this file inside Output_GRASP/Qwen3-4B-Instruct-2507/ and run it from
that directory. It processes both SimpleQA/ and ComplexQA/.
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer, util
from tqdm import tqdm

# -----------------------------------------------------------------------------
# Global configuration
# -----------------------------------------------------------------------------
# Embedding model used by the taxonomy stage.
MODEL_NAME = "all-MiniLM-L6-v2"

# The pipeline looks for these two category folders under the current working
# directory. Missing categories are skipped.
CATEGORY_DIRS = ("SimpleQA", "ComplexQA")

# Canonical CSV column order for combined valid and invalid tables.
VALID_COLUMNS = ["question", "gold_answer", "result_cleaned", "result", "sparql", "file_path"]
INVALID_COLUMNS = [
    "file_path",
    "invalid_label",
    "question",
    "gold_answer",
    "sparql",
    "result",
    "answer",
    "explanation",
    "formatted",
]

# Taxonomy thresholds inherited from the original tag.py behavior.
SAME_THRESHOLD = 0.90
PERFECT_MATCH_THRESHOLD = 0.995
LOW_SCORE_THRESHOLD = 0.10
STRICT_ALIGNMENT_THRESHOLD = 0.35

# Simple month-name mapping used by date parsing.
MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

record_handle = None
MODEL = None


# -----------------------------------------------------------------------------
# Shared helpers
# -----------------------------------------------------------------------------

def log_print(*args, sep: str = " ", end: str = "\n") -> None:
    """Print to stdout and mirror the same message to record.txt if open."""
    global record_handle
    message = sep.join(str(arg) for arg in args)
    print(message, end=end)
    if record_handle is not None:
        record_handle.write(message + end)
        record_handle.flush()


def pct(value: int, total: int) -> float:
    """Return a percentage safely when total may be zero."""
    return (value / total * 100.0) if total else 0.0


def stage_bar(total: int) -> tqdm:
    """Top-level progress bar for the four major pipeline stages."""
    return tqdm(total=total, desc="Pipeline stages", unit="stage", position=0)


def normalize_sparql(text: str) -> str:
    """
    Normalize a generated SPARQL string.

    The raw JSON sometimes stores literal '\\n' sequences and extra text before
    the actual query. We keep only the text starting from the first SELECT.
    """
    if not text:
        return ""
    text = text.replace("\\n", "\n")
    match = re.search(r"(?is)\bSELECT\b.*", text)
    return match.group(0).strip() if match else ""


def extract_table(text: str) -> str:
    """
    Extract the first markdown-style table block from a raw result string.

    The extraction logic mirrors the original JSON2csv.py behavior.
    """
    if not text:
        return ""
    text = text.replace("\\n", "\n")
    lines = text.splitlines()
    table_lines: List[str] = []
    started = False
    for line in lines:
        if line.strip().startswith("|"):
            started = True
            table_lines.append(line)
        elif started:
            break
    return "\n".join(table_lines).strip()


def clean_result_all_cells(result_table: str) -> str:
    """
    Flatten a markdown result table into compact answer text.

    We skip the header row and the markdown separator row, then clean each cell
    by removing embedded Wikidata IDs and datatype suffixes.
    """
    if not result_table:
        return ""

    lines = result_table.split("\n")
    cleaned_rows: List[str] = []

    for i, line in enumerate(lines):
        line = line.strip()
        if not line.startswith("|"):
            continue
        if i == 0:
            continue
        if re.match(r"^\|\s*[-: ]+(\|\s*[-: ]+)+\|?\s*$", line) or line.startswith("| ---"):
            continue

        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        cleaned_cells: List[str] = []

        for cell in cells:
            cell = re.sub(r"\s*\(wd:Q[^)]*\)", "", cell).strip()
            cell = re.sub(r"\s*\(xsd:[^)]+\)", "", cell).strip()
            cell = " ".join(cell.split())
            cleaned_cells.append(cell)

        if cleaned_cells:
            cleaned_rows.append("|".join(cleaned_cells))

    return "\n".join(cleaned_rows)


def classify_case(output_obj: Any, sparql_text: str, result_raw: str) -> Tuple[str, str]:
    """
    Reproduce the original invalid-case logic from JSON2csv.py.

    Returns
    -------
    (invalid_label, result_table)

    If invalid_label is empty, the case is valid and result_table contains the
    extracted markdown table.
    """
    if output_obj is None:
        return "null_output", ""

    if isinstance(output_obj, dict) and output_obj.get("sparql") is None and output_obj.get("result") is None:
        return "no_sparql_generated", ""

    if not sparql_text:
        return "no_sparql_generated", ""

    if isinstance(result_raw, str):
        if "SPARQL execution failed" in result_raw:
            return "sparql_execution_failed (execution)", ""
        if re.search(r"parse error", result_raw, re.IGNORECASE):
            return "sparql_execution_failed (preprocessing)", ""
        if re.search(r"Got no rows and \d+ columns?", result_raw):
            return "empty_sparql_result", ""

    table = extract_table(result_raw)
    if not table:
        return "empty_sparql_result", ""

    return "", table


# -----------------------------------------------------------------------------
# Stage 1. Extract valid and invalid cases from JSON
# -----------------------------------------------------------------------------


def discover_json_files(base_folder: Path) -> List[Path]:
    """Recursively collect JSON files in one dataset folder, skipping extracted_output/ and timing_summary.json."""
    json_files: List[Path] = []
    for root, _, files in os.walk(base_folder):
        root_path = Path(root)
        if root_path.name == "extracted_output" and root_path.parent == base_folder:
            continue
        for fname in files:
            if Path(fname).suffix.lower() == ".json" and fname != "timing_summary.json":
                json_files.append(root_path / fname)
    json_files.sort(key=str)
    return json_files


def process_dataset_folder(
    base_folder: Path,
    combined_valid_rows: List[List[str]],
    combined_invalid_rows: List[Dict[str, str]],
) -> None:
    """
    Process one dataset folder and write its per-folder outputs.

    Example dataset folder:
        SimpleQA/NQ_table_test_simple/

    Generated outputs:
        extracted_output/<dataset>.csv
        extracted_output/<dataset>_valid_cases.csv
        extracted_output/<dataset>_invalid_cases.csv
        extracted_output/<dataset>_invalid_summary.md
    """
    folder_name = base_folder.name
    output_dir = base_folder / "extracted_output"
    output_dir.mkdir(exist_ok=True)

    main_csv = output_dir / f"{folder_name}.csv"
    valid_csv = output_dir / f"{folder_name}_valid_cases.csv"
    invalid_csv = output_dir / f"{folder_name}_invalid_cases.csv"
    md_file = output_dir / f"{folder_name}_invalid_summary.md"

    json_files = discover_json_files(base_folder)
    total_files = len(json_files)

    all_rows: List[List[str]] = []
    valid_rows: List[List[str]] = []
    invalid_rows: List[List[str]] = []
    counts: Counter = Counter()
    valid_total = 0

    file_bar = tqdm(
        json_files,
        desc=f"JSON extraction [{base_folder.parent.name}/{folder_name}]",
        unit="json",
        leave=False,
        position=1,
    )

    for fp in file_bar:
        # Root-relative path: SimpleQA/.../00001.json or ComplexQA/.../00001.json
        rel_path_from_root = str(fp.relative_to(base_folder.parent.parent))

        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            invalid_rows.append([fp.name, "invalid_json"])
            counts["invalid_json"] += 1
            all_rows.append(["", "", "", "", ""])
            combined_invalid_rows.append({
                "file_path": rel_path_from_root,
                "invalid_label": "invalid_json",
                "question": "",
                "gold_answer": "",
                "sparql": "",
                "result": "",
                "answer": "",
                "explanation": "",
                "formatted": "",
            })
            continue

        question = data.get("question", "")
        gold_answer = data.get("reference_answer", "")
        output_obj = data.get("output", None)

        if isinstance(output_obj, dict):
            sparql = normalize_sparql(output_obj.get("sparql", ""))
            result_raw = output_obj.get("result", "")
            answer = output_obj.get("answer", "")
            explanation = output_obj.get("explanation", "")
            formatted = output_obj.get("formatted", "")
        else:
            sparql = ""
            result_raw = ""
            answer = ""
            explanation = ""
            formatted = ""

        invalid_label, result_table = classify_case(output_obj, sparql, result_raw)
        result_cleaned = clean_result_all_cells(result_table)

        if invalid_label:
            invalid_rows.append([fp.name, invalid_label])
            counts[invalid_label] += 1
            combined_invalid_rows.append({
                "file_path": rel_path_from_root,
                "invalid_label": invalid_label,
                "question": question,
                "gold_answer": gold_answer,
                "sparql": sparql,
                "result": result_raw,
                "answer": answer,
                "explanation": explanation,
                "formatted": formatted,
            })
        else:
            valid_total += 1
            row = [question, gold_answer, result_cleaned, result_table, sparql, rel_path_from_root]
            valid_rows.append(row)
            combined_valid_rows.append(row)

        all_rows.append([question, gold_answer, result_cleaned, result_table, sparql])

    with main_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["question", "gold_answer", "result_cleaned", "result", "sparql"])
        writer.writerows(all_rows)

    with valid_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(VALID_COLUMNS)
        writer.writerows(valid_rows)

    with invalid_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file_name", "invalid_label"])
        writer.writerows(invalid_rows)

    invalid_labels = [
        "null_output",
        "no_sparql_generated",
        "empty_sparql_result",
        "sparql_execution_failed (execution)",
        "sparql_execution_failed (preprocessing)",
        "invalid_json",
    ]
    invalid_total = sum(counts.get(lbl, 0) for lbl in invalid_labels)

    md_lines = [
        f"# Invalid case summary for {folder_name}",
        "",
        f"Total JSON files: {total_files}",
        "",
        f"Valid cases: {valid_total} ({pct(valid_total, total_files):.2f}%)",
        f"Invalid cases: {invalid_total} ({pct(invalid_total, total_files):.2f}%)",
        "",
        "## Invalid case breakdown",
        "",
    ]
    for lbl in invalid_labels:
        n = counts.get(lbl, 0)
        md_lines.append(f"- {lbl}: {n} ({pct(n, total_files):.2f}%)")
    md_file.write_text("\n".join(md_lines), encoding="utf-8")

    log_print(f"✓ Processed {base_folder.parent.name}/{folder_name}: {valid_total}/{total_files} valid cases")


def extract_json_outputs(category_dir: Path) -> Tuple[List[List[str]], List[Dict[str, str]]]:
    """Process all dataset folders under one category and write category-level combined CSVs."""
    combined_valid_rows: List[List[str]] = []
    combined_invalid_rows: List[Dict[str, str]] = []

    dataset_folders = [p for p in category_dir.iterdir() if p.is_dir()]
    dataset_folders.sort(key=str)
    log_print(f"Found {len(dataset_folders)} dataset folders in {category_dir.name}")

    folder_bar = tqdm(
        dataset_folders,
        desc=f"Datasets in {category_dir.name}",
        unit="folder",
        leave=False,
        position=1,
    )

    for folder in folder_bar:
        process_dataset_folder(folder, combined_valid_rows, combined_invalid_rows)

    with (category_dir / "all_valid_cases.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(VALID_COLUMNS)
        writer.writerows(combined_valid_rows)

    with (category_dir / "all_invalid_cases.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=INVALID_COLUMNS)
        writer.writeheader()
        writer.writerows(combined_invalid_rows)

    return combined_valid_rows, combined_invalid_rows


def write_root_case_tables(
    root_dir: Path,
    all_valid_rows: List[List[str]],
    all_invalid_rows: List[Dict[str, str]],
) -> None:
    """Write root-level all_valid_cases.csv and all_invalid_cases.csv."""
    with (root_dir / "all_valid_cases.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(VALID_COLUMNS)
        writer.writerows(all_valid_rows)

    with (root_dir / "all_invalid_cases.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=INVALID_COLUMNS)
        writer.writeheader()
        writer.writerows(all_invalid_rows)


# -----------------------------------------------------------------------------
# Stage 2. Taxonomy tagging for valid cases
# -----------------------------------------------------------------------------
@dataclass
class ParsedDate:
    """Small normalized date object used by the taxonomy step."""
    normalized: str
    precision: str
    year: int
    month: Optional[int] = None
    day: Optional[int] = None


def clean_text(value: Any) -> str:
    """Normalize whitespace and a few punctuation variants."""
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value)
    text = text.replace("\u00A0", " ")
    text = text.replace("–", " - ").replace("—", " - ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_text_for_similarity(value: Any) -> str:
    """Lowercase and simplify text before semantic similarity."""
    text = clean_text(value).lower()
    text = re.sub(r"[“”\"'`]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_delimiters(text: str) -> str:
    """
    Normalize separators before splitting multi-answer strings.

    The pipeline uses '|' and newlines as answer delimiters. Date ranges are
    protected by converting the dash between endpoints into '|'.
    """
    text = str(text).replace("\u00A0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("–", " - ").replace("—", " - ")

    date_range_patterns = [
        r"(\b\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}Z)?\b)\s*-\s*(\b\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}Z)?\b)",
        r"(\b\d{1,2}\s+[A-Za-z]+\.?\s+\d{4}\b)\s*-\s*(\b\d{1,2}\s+[A-Za-z]+\.?\s+\d{4}\b)",
        r"(\b[A-Za-z]+\.?\s+\d{1,2},?\s+\d{4}\b)\s*-\s*(\b[A-Za-z]+\.?\s+\d{1,2},?\s+\d{4}\b)",
    ]
    for pattern in date_range_patterns:
        text = re.sub(pattern, r"\1|\2", text)
    return text


def split_answers(answer_string: Any) -> List[str]:
    """Split an answer field into items using '|' or newlines."""
    if pd.isna(answer_string):
        return []
    text = normalize_delimiters(str(answer_string))
    parts = re.split(r"\||\n+", text)
    items = [clean_text(part) for part in parts]
    return [item for item in items if item]


def parse_date_string(value: str) -> Optional[ParsedDate]:
    """Parse common benchmark date formats into ParsedDate."""
    text = clean_text(value)
    if not text:
        return None

    m = re.fullmatch(r"(\d{4})", text)
    if m:
        year = int(m.group(1))
        return ParsedDate(normalized=f"{year:04d}", precision="year", year=year)

    m = re.fullmatch(r"(\d{4})-(\d{2})", text)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12:
            return ParsedDate(normalized=f"{year:04d}-{month:02d}", precision="month", year=year, month=month)

    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})(?:T\d{2}:\d{2}:\d{2}Z)?", text)
    if m:
        year, month, day = map(int, m.groups())
        if 1 <= month <= 12 and 1 <= day <= 31:
            return ParsedDate(normalized=f"{year:04d}-{month:02d}-{day:02d}", precision="day", year=year, month=month, day=day)

    m = re.fullmatch(r"([A-Za-z]+)\.?\s+(\d{4})", text)
    if m:
        month_name, year = m.group(1).lower(), int(m.group(2))
        month = MONTHS.get(month_name)
        if month:
            return ParsedDate(normalized=f"{year:04d}-{month:02d}", precision="month", year=year, month=month)

    m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\.?\s+(\d{4})", text)
    if m:
        day, month_name, year = int(m.group(1)), m.group(2).lower(), int(m.group(3))
        month = MONTHS.get(month_name)
        if month and 1 <= day <= 31:
            return ParsedDate(normalized=f"{year:04d}-{month:02d}-{day:02d}", precision="day", year=year, month=month, day=day)

    m = re.fullmatch(r"([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})", text)
    if m:
        month_name, day, year = m.group(1).lower(), int(m.group(2)), int(m.group(3))
        month = MONTHS.get(month_name)
        if month and 1 <= day <= 31:
            return ParsedDate(normalized=f"{year:04d}-{month:02d}-{day:02d}", precision="day", year=year, month=month, day=day)

    return None


def compare_dates(gold: ParsedDate, pred: ParsedDate) -> float:
    """Compare two normalized dates and return a soft similarity score."""
    if gold.precision == pred.precision and gold.normalized == pred.normalized:
        return 1.0
    if gold.precision == "year" and pred.precision == "day" and pred.month == 1 and pred.day == 1 and gold.year == pred.year:
        return 1.0
    if pred.precision == "year" and gold.precision == "day" and gold.month == 1 and gold.day == 1 and gold.year == pred.year:
        return 1.0
    if gold.year != pred.year:
        return 0.0
    if gold.precision == "year" or pred.precision == "year":
        return 0.95
    if gold.month != pred.month:
        return 0.0
    if gold.precision == "month" or pred.precision == "month":
        return 0.97
    return 0.0


def get_model() -> SentenceTransformer:
    """Lazily load the sentence-transformer model only when needed."""
    global MODEL
    if MODEL is None:
        MODEL = SentenceTransformer(MODEL_NAME)
    return MODEL


def semantic_similarity(text_a: str, text_b: str) -> float:
    """Compute similarity using exact match, date logic, or SBERT embeddings."""
    a = normalize_text_for_similarity(text_a)
    b = normalize_text_for_similarity(text_b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    date_a = parse_date_string(a)
    date_b = parse_date_string(b)
    if date_a and date_b:
        return compare_dates(date_a, date_b)
    model = get_model()
    emb = model.encode([a, b], convert_to_tensor=True)
    return float(util.cos_sim(emb[0], emb[1]).item())


def build_similarity_matrix(gold_items: Sequence[str], pred_items: Sequence[str]) -> np.ndarray:
    """Build the full pairwise similarity matrix between gold and predicted answers."""
    if not gold_items or not pred_items:
        return np.zeros((len(gold_items), len(pred_items)), dtype=float)
    matrix = np.zeros((len(gold_items), len(pred_items)), dtype=float)
    for i, g in enumerate(gold_items):
        for j, p in enumerate(pred_items):
            matrix[i, j] = semantic_similarity(g, p)
    return matrix


def compute_answer_metrics(gold_answer: Any, pred_answer: Any) -> Dict[str, float]:
    """Compute the set-style answer alignment metrics used by the taxonomy step."""
    gold_items = split_answers(gold_answer)
    pred_items = split_answers(pred_answer)
    gold_size = len(gold_items)
    pred_size = len(pred_items)

    if gold_size == 0 and pred_size == 0:
        return {
            "gold_size": 0,
            "pred_size": 0,
            "recall": 1.0,
            "precision": 1.0,
            "f1_score": 1.0,
            "max_gold_to_pred": 1.0,
            "max_pred_to_gold": 1.0,
        }

    if gold_size == 0 or pred_size == 0:
        return {
            "gold_size": gold_size,
            "pred_size": pred_size,
            "recall": 0.0,
            "precision": 0.0,
            "f1_score": 0.0,
            "max_gold_to_pred": 0.0,
            "max_pred_to_gold": 0.0,
        }

    matrix = build_similarity_matrix(gold_items, pred_items)
    gold_best = matrix.max(axis=1)
    pred_best = matrix.max(axis=0)
    recall = float(gold_best.mean()) if len(gold_best) else 0.0
    precision = float(pred_best.mean()) if len(pred_best) else 0.0
    f1_score = 0.0 if recall + precision == 0 else 2 * recall * precision / (recall + precision)

    return {
        "gold_size": gold_size,
        "pred_size": pred_size,
        "recall": recall,
        "precision": precision,
        "f1_score": f1_score,
        "max_gold_to_pred": float(gold_best.max()) if len(gold_best) else 0.0,
        "max_pred_to_gold": float(pred_best.max()) if len(pred_best) else 0.0,
    }


def assign_taxonomy_label(metrics: Dict[str, float], gold_answer: Any, pred_answer: Any) -> str:
    """Assign one taxonomy label to a valid case."""
    recall = metrics["recall"]
    precision = metrics["precision"]
    f1_score = metrics["f1_score"]
    gold_size = metrics["gold_size"]
    pred_size = metrics["pred_size"]
    max_gold_to_pred = metrics["max_gold_to_pred"]
    max_pred_to_gold = metrics["max_pred_to_gold"]

    gold_items = split_answers(gold_answer)
    pred_items = split_answers(pred_answer)

    if gold_size == 1 and pred_size == 1:
        gold_date = parse_date_string(gold_items[0]) if gold_items else None
        pred_date = parse_date_string(pred_items[0]) if pred_items else None
        if gold_date and pred_date:
            sim = compare_dates(gold_date, pred_date)
            if sim >= SAME_THRESHOLD:
                return "same"
            if gold_date.year == pred_date.year and pred_date.precision != gold_date.precision:
                if pred_date.precision == "day" and gold_date.precision in {"year", "month"}:
                    return "Higher accuracy in KG than in Table"
                if gold_date.precision == "day" and pred_date.precision in {"year", "month"}:
                    return "Higher accuracy in Table than in KG"

    if f1_score >= SAME_THRESHOLD:
        return "same"
    if recall >= PERFECT_MATCH_THRESHOLD and precision < PERFECT_MATCH_THRESHOLD and pred_size > gold_size:
        return "Higher accuracy in KG than in Table"
    if precision >= PERFECT_MATCH_THRESHOLD and recall < PERFECT_MATCH_THRESHOLD and gold_size > pred_size:
        return "Higher accuracy in Table than in KG"
    if (
        gold_size == pred_size
        and recall <= LOW_SCORE_THRESHOLD
        and precision <= LOW_SCORE_THRESHOLD
        and max_gold_to_pred < STRICT_ALIGNMENT_THRESHOLD
        and max_pred_to_gold < STRICT_ALIGNMENT_THRESHOLD
    ):
        return "Different answer"
    return "different_unclassified"


def run_taxonomy(root_dir: Path) -> None:
    """Read all_valid_cases.csv, assign taxonomy labels, and write labeled output."""
    global record_handle
    input_file = root_dir / "all_valid_cases.csv"
    output_file = root_dir / "all_valid_cases_with_taxonomy.csv"
    record_file = root_dir / "record.txt"

    record_handle = open(record_file, "w", encoding="utf-8")
    try:
        df = pd.read_csv(input_file)
        gold_sizes, pred_sizes, recalls, precisions, similarities, taxonomy_labels = ([] for _ in range(6))

        log_print(f"Loaded {len(df)} valid rows from {input_file.name}")
        log_print(f"Using SBERT model: {MODEL_NAME}")
        log_print("Computing answer metrics and taxonomy labels...")

        row_bar = tqdm(
            df.iterrows(),
            total=len(df),
            desc="Taxonomy tagging",
            unit="row",
            leave=False,
            position=1,
        )

        for _, row in row_bar:
            metrics = compute_answer_metrics(row["gold_answer"], row["result_cleaned"])
            label = assign_taxonomy_label(metrics, row["gold_answer"], row["result_cleaned"])
            gold_sizes.append(metrics["gold_size"])
            pred_sizes.append(metrics["pred_size"])
            recalls.append(metrics["recall"])
            precisions.append(metrics["precision"])
            similarities.append(metrics["f1_score"])
            taxonomy_labels.append(label)

        df["gold_size"] = gold_sizes
        df["pred_size"] = pred_sizes
        df["recall"] = recalls
        df["precision"] = precisions
        df["similarity_score"] = similarities
        df["taxonomy_label"] = taxonomy_labels

        df = df[
            [
                "question",
                "gold_answer",
                "result_cleaned",
                "gold_size",
                "pred_size",
                "recall",
                "precision",
                "similarity_score",
                "taxonomy_label",
                "result",
                "sparql",
                "file_path",
            ]
        ]
        df = df.sort_values(by="similarity_score", ascending=False)
        df.to_csv(output_file, index=False)

        log_print("Finished taxonomy tagging.")
        log_print("Results saved to:", output_file.name)
        log_print("Execution log saved to:", record_file.name)
        log_print("\nLabel counts:")
        log_print(df["taxonomy_label"].value_counts(dropna=False).to_string())

    finally:
        if record_handle is not None:
            record_handle.close()
            record_handle = None


# -----------------------------------------------------------------------------
# Stage 3. Aggregate counts/statistics (NO plots)
# -----------------------------------------------------------------------------

def parse_summary_md(md_path: Path) -> Dict[str, Any]:
    """Parse one dataset-level invalid summary markdown file."""
    text = md_path.read_text(encoding="utf-8")
    total = int(re.search(r"Total JSON files:\s*(\d+)", text).group(1))
    valid = int(re.search(r"Valid cases:\s*(\d+)", text).group(1))
    invalid = int(re.search(r"Invalid cases:\s*(\d+)", text).group(1))
    errors: Dict[str, int] = {}
    for label, count in re.findall(r"-\s*(.*?):\s*(\d+)", text):
        errors[label.strip()] = int(count)
    return {"total": total, "valid": valid, "invalid": invalid, "errors": errors}


def run_statistics(root_dir: Path) -> None:
    """
    Aggregate global counts and write text-only statistics outputs.

    This version intentionally removes all plotting. The statistics directory
    contains markdown and CSV only.
    """
    statistics_dir = root_dir / "statistics"
    statistics_dir.mkdir(exist_ok=True)

    summary_files = sorted(root_dir.rglob("*_invalid_summary.md"))
    if not summary_files:
        log_print("No summary files found for statistics.")
        return

    data: Dict[str, Dict[str, Any]] = {}
    total_valid = 0
    total_invalid = 0
    total_all = 0
    error_totals: Dict[str, int] = defaultdict(int)

    file_bar = tqdm(
        summary_files,
        desc="Aggregating statistics",
        unit="summary",
        leave=False,
        position=1,
    )

    for md in file_bar:
        folder = md.stem.replace("_invalid_summary", "")
        stats = parse_summary_md(md)
        data[folder] = stats
        total_valid += stats["valid"]
        total_invalid += stats["invalid"]
        total_all += stats["total"]
        for label, count in stats["errors"].items():
            error_totals[label] += count

    with (statistics_dir / "per_folder_breakdown.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["folder", "total", "valid", "valid_pct", "invalid", "invalid_pct"])
        for folder, stats in sorted(data.items()):
            writer.writerow([
                folder,
                stats["total"],
                stats["valid"],
                f"{pct(stats['valid'], stats['total']):.2f}",
                stats["invalid"],
                f"{pct(stats['invalid'], stats['total']):.2f}",
            ])
        writer.writerow([
            "TOTAL",
            total_all,
            total_valid,
            f"{pct(total_valid, total_all):.2f}",
            total_invalid,
            f"{pct(total_invalid, total_all):.2f}",
        ])

    with (statistics_dir / "error_distribution_total.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["error_type", "count", "pct_of_invalid"])
        for label, count in sorted(error_totals.items()):
            writer.writerow([label, count, f"{pct(count, total_invalid):.2f}"])

    md_lines: List[str] = []
    md_lines.append("# Global SPARQL QA Statistics")
    md_lines.append("")
    md_lines.append("## Overall valid vs invalid")
    md_lines.append("")
    md_lines.append("| Metric | Count | Percentage |")
    md_lines.append("|---|---:|---:|")
    md_lines.append(f"| Valid | {total_valid} | {pct(total_valid, total_all):.2f}% |")
    md_lines.append(f"| Invalid | {total_invalid} | {pct(total_invalid, total_all):.2f}% |")
    md_lines.append("")
    md_lines.append("## Error distribution (Total)")
    md_lines.append("")
    md_lines.append("| Error type | Count | % of invalid |")
    md_lines.append("|---|---:|---:|")
    for label, count in sorted(error_totals.items()):
        md_lines.append(f"| {label} | {count} | {pct(count, total_invalid):.2f}% |")
    md_lines.append("")
    md_lines.append("## Per-folder summary")
    md_lines.append("")
    md_lines.append("| Folder | Total | Valid | Valid % | Invalid | Invalid % |")
    md_lines.append("|---|---:|---:|---:|---:|---:|")
    for folder, stats in sorted(data.items()):
        md_lines.append(
            f"| {folder} | {stats['total']} | {stats['valid']} | {pct(stats['valid'], stats['total']):.2f}% | "
            f"{stats['invalid']} | {pct(stats['invalid'], stats['total']):.2f}% |"
        )
    md_lines.append(
        f"| **Total** | {total_all} | {total_valid} | {pct(total_valid, total_all):.2f}% | "
        f"{total_invalid} | {pct(total_invalid, total_all):.2f}% |"
    )

    (statistics_dir / "summary.md").write_text("\n".join(md_lines), encoding="utf-8")
    log_print(f"✓ Statistics written to: {statistics_dir}")


# -----------------------------------------------------------------------------
# Stage 4. Export different_unclassified subset
# -----------------------------------------------------------------------------

def extract_unclassified(root_dir: Path) -> None:
    """Export rows whose taxonomy label is exactly 'different_unclassified'."""
    input_csv = root_dir / "all_valid_cases_with_taxonomy.csv"
    output_csv = root_dir / "different_unclassified_questions.csv"

    df = pd.read_csv(input_csv)
    filtered = (
        df.loc[
            df["taxonomy_label"] == "different_unclassified",
            ["question", "gold_answer", "result_cleaned", "file_path"],
        ]
        .rename(columns={"result_cleaned": "KG answer"})
    )
    filtered.to_csv(output_csv, index=False)
    log_print(f"Saved {len(filtered)} rows to {output_csv.name}")


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main() -> None:
    """
    Run the full four-stage pipeline with stage-level and inner progress bars.

    Stage 1: JSON extraction
    Stage 2: taxonomy tagging
    Stage 3: statistics aggregation (text only)
    Stage 4: export different_unclassified
    """
    root_dir = Path.cwd()
    all_valid_rows: List[List[str]] = []
    all_invalid_rows: List[Dict[str, str]] = []

    stages = [
        "Extract valid/invalid cases from JSON",
        "Run taxonomy on valid cases",
        "Aggregate statistics",
        "Export different_unclassified questions",
    ]
    progress = stage_bar(len(stages))

    log_print(f"\n[Stage 1/{len(stages)}] {stages[0]}")
    for category_name in CATEGORY_DIRS:
        category_dir = root_dir / category_name
        if not category_dir.exists():
            log_print(f"Skipping missing directory: {category_dir}")
            continue
        valid_rows, invalid_rows = extract_json_outputs(category_dir)
        all_valid_rows.extend(valid_rows)
        all_invalid_rows.extend(invalid_rows)
    write_root_case_tables(root_dir, all_valid_rows, all_invalid_rows)
    log_print(f"✓ Combined valid rows: {len(all_valid_rows)}")
    log_print(f"✓ Combined invalid rows: {len(all_invalid_rows)}")
    progress.update(1)

    log_print(f"\n[Stage 2/{len(stages)}] {stages[1]}")
    run_taxonomy(root_dir)
    progress.update(1)

    log_print(f"\n[Stage 3/{len(stages)}] {stages[2]}")
    run_statistics(root_dir)
    progress.update(1)

    log_print(f"\n[Stage 4/{len(stages)}] {stages[3]}")
    extract_unclassified(root_dir)
    progress.update(1)

    progress.close()
    log_print("\n🎉 ALL DONE!")


if __name__ == "__main__":
    main()
