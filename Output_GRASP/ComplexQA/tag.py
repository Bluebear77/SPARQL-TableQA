"""
================================================================================
Purpose
================================================================================

This script compares answers from two sources:

    1. gold_answer
       -> the expected answer from the dataset / table side

    2. result_cleaned
       -> the answer returned from the SPARQL query / Wikidata side

The goal is not only to measure how similar the two answers are, but also to
assign a taxonomy label that explains the type of inconsistency.

This script focuses on the following labels:

    1. same
    2. Higher accuracy in Wikidata than in Table
    3. Higher accuracy in Table than in Wikidata
    4. Different answer
    5. different_unclassified

Both answer columns may contain multiple values separated by '|'.

Example:
    gold_answer    = "Paris|London"
    result_cleaned = "Paris|Berlin"


================================================================================
Overview
================================================================================

This script compares answer pairs in a CSV file and assigns taxonomy labels
based on how well the predicted answer aligns with the gold answer.

The pipeline combines:
    - answer splitting for multi-value answers
    - date-aware normalization and comparison
    - semantic similarity with SBERT
    - precision / recall / F1 style aggregation
    - taxonomy labeling based on alignment patterns

This design is useful because answer strings may differ in several ways:

    - exact wording differences
    - multiple answers vs single answers
    - date formatting differences
    - differences in answer completeness
    - truly contradictory answers

Examples:
    "USA" vs "United States"
    "2018" vs "May 16, 2018"
    "Paris|London" vs "Paris|Berlin"
    "1939" vs "1939-01-01T00:00:00Z"

The script handles these systematically and produces an output CSV with
comparison metrics and taxonomy labels.


================================================================================
How the Script Works
================================================================================

1. Load the input CSV
   ------------------
   The script reads a CSV file containing at least these columns:

       question
       gold_answer
       result_cleaned
       result
       sparql
       file_path

2. Split multi-answer fields
   --------------------------
   If an answer contains multiple values separated by '|' or line breaks,
   the script splits it into answer items.

   Example:
       "Paris|London"
       -> ["Paris", "London"]

3. Normalize and compare date values
   ---------------------------------
   Before semantic similarity is used, the script checks whether a pair of
   answer items are dates.

   Supported date forms include:
       - YYYY
       - Month YYYY
       - DD Month YYYY
       - Month DD, YYYY
       - YYYY-MM-DD
       - YYYY-MM-DDTHH:MM:SSZ

   Dates are normalized into precision-aware forms:

       year  -> "2018"
       month -> "2018-05"
       day   -> "2018-05-16"

   The date comparison logic is precision-aware.

   Example:
       gold = "2018"
       pred = "May 16, 2018"
       -> prediction is more precise

   There is also a special rule for bare years compared with canonical
   January 1 representations:

       "1939" vs "1939-01-01T00:00:00Z"
       -> treated as Same

   This rule exists because many knowledge graph systems store year-only
   values as a full timestamp on January 1.

4. Compare non-date text with SBERT
   --------------------------------
   If two answer items are not both parseable as dates, the script compares
   them semantically using SBERT.

   Model used:
       all-MiniLM-L6-v2

   Similarity is computed with cosine similarity between embeddings.

5. Build a similarity matrix
   --------------------------
   Every gold answer item is compared with every predicted answer item.

   Example:

                    Predicted
                 Paris   Berlin
       Gold Paris  1.00    0.32
            London 0.41    0.28

6. Compute recall
   --------------
   For each gold answer item, the script finds the best matching predicted
   answer item.

   This measures:
       "How well does the prediction cover the gold answer?"

7. Compute precision
   -----------------
   For each predicted answer item, the script finds the best matching gold
   answer item.

   This measures:
       "How much of the prediction is actually supported by the gold answer?"

8. Compute F1
   ----------
   Recall and precision are combined using the harmonic mean.

9. Assign taxonomy labels
   ----------------------
   Labels are assigned in this priority order:

       1. date-specific single-item decision
       2. same
       3. Higher accuracy in Wikidata than in Table
       4. Higher accuracy in Table than in Wikidata
       5. Different answer
       6. different_unclassified

   Interpretation of key labels:

   same
       The answers match strongly overall.

   Higher accuracy in Wikidata than in Table
       The predicted answer fully covers the gold answer and includes more
       detail.

   Higher accuracy in Table than in Wikidata
       The gold answer is more complete than the predicted answer.

   Different answer
       The answers are weakly aligned and appear contradictory.

   different_unclassified
       Fallback label when none of the main patterns apply.


================================================================================
Output
================================================================================

The script writes:

    1. all_valid_cases_with_taxonomy.csv
       -> final output with metrics and labels

    2. record.txt
       -> execution log

The output CSV contains these columns:

    question
    gold_answer
    result_cleaned
    gold_size
    pred_size
    recall
    precision
    similarity_score
    taxonomy_label
    result
    sparql
    file_path


================================================================================
Important Design Notes
================================================================================

1. SBERT is the only semantic backend
   ----------------------------------
   This script uses SBERT for semantic matching of non-date text.

2. Dates are compared deterministically
   ------------------------------------
   Date comparisons are handled separately because semantic embeddings alone
   are not reliable enough for date equivalence and date precision judgments.

3. Precision-aware date comparison
   -------------------------------
   The script distinguishes:
       - exact same date
       - same year but one side more precise
       - same month but one side more precise
       - contradictory dates

4. Year vs January 1 normalization rule
   ------------------------------------
   A year-only answer and the corresponding January 1 timestamp for that year
   are treated as the same fact.

   Example:
       "1939"
       "1939-01-01T00:00:00Z"

   -> label as Same

================================================================================
"""

import math
import re
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from tqdm import tqdm
from sentence_transformers import SentenceTransformer, util


# =============================================================================
# Configuration
# =============================================================================
# INPUT_FILE:
#   CSV file containing the answer pairs to compare.
#
# OUTPUT_FILE:
#   Final CSV with metrics and taxonomy labels.
#
# RECORD_FILE:
#   Plain text log file storing console messages.

INPUT_FILE = "all_valid_cases.csv"
OUTPUT_FILE = "all_valid_cases_with_taxonomy.csv"
RECORD_FILE = "record.txt"

# MODEL_NAME:
#   SBERT model name. This script is intentionally SBERT-only.
MODEL_NAME = "all-MiniLM-L6-v2"


# =============================================================================
# Logging helper
# =============================================================================
# This keeps the normal print output and also writes the same messages to
# record.txt so there is a saved execution record.

record_handle = open(RECORD_FILE, "w", encoding="utf-8")


def log_print(*args, sep=" ", end="\n"):
    """
    Print a message to the terminal and also write it to record.txt.

    Parameters
    ----------
    *args :
        Objects to print.
    sep : str
        Separator used between printed arguments.
    end : str
        Line ending.
    """
    message = sep.join(str(arg) for arg in args)
    print(message, end=end)
    record_handle.write(message + end)
    record_handle.flush()


# =============================================================================
# Similarity thresholds
# =============================================================================
# SAME_THRESHOLD:
#   If overall F1 is at or above this threshold, we label the pair as "same".
#
# PERFECT_MATCH_THRESHOLD:
#   Used when a side is considered fully covered. This avoids depending on
#   exact float equality with 1.0.
#
# LOW_SCORE_THRESHOLD:
#   Used to define cases with extremely weak aggregate overlap.
#
# STRICT_ALIGNMENT_THRESHOLD:
#   Even the strongest pairwise match must stay below this threshold for the
#   script to confidently label the case as "Different answer".

SAME_THRESHOLD = 0.9
PERFECT_MATCH_THRESHOLD = 0.995
LOW_SCORE_THRESHOLD = 0.10
STRICT_ALIGNMENT_THRESHOLD = 0.35


# =============================================================================
# Month dictionary used by the date parser
# =============================================================================
# This maps month names and abbreviations to numeric months.

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


# =============================================================================
# ParsedDate dataclass
# =============================================================================
# This stores a normalized date and its precision level:
#
#   precision = "year"  -> only year known
#   precision = "month" -> year and month known
#   precision = "day"   -> full date known
#
# Example:
#   "2018"            -> ParsedDate(normalized="2018", precision="year")
#   "October 1973"    -> ParsedDate(normalized="1973-10", precision="month")
#   "May 16, 2018"    -> ParsedDate(normalized="2018-05-16", precision="day")

@dataclass
class ParsedDate:
    normalized: str
    precision: str
    year: int
    month: Optional[int] = None
    day: Optional[int] = None


# =============================================================================
# Text cleaning helpers
# =============================================================================

def clean_text(value):
    """
    Basic text cleaning used across the pipeline.

    This function:
    - converts NaN/None safely to empty string
    - replaces non-breaking spaces with normal spaces
    - normalizes long dashes to simple hyphen spacing
    - compresses repeated whitespace

    Parameters
    ----------
    value : any
        Raw field value.

    Returns
    -------
    str
        Cleaned string.
    """
    if value is None:
        return ""

    if isinstance(value, float) and math.isnan(value):
        return ""

    text = str(value)
    text = text.replace("\u00A0", " ")
    text = text.replace("–", " - ").replace("—", " - ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_text_for_similarity(value):
    """
    Normalize text before exact equality checks or SBERT encoding.

    This is intentionally light-touch:
    - lowercase
    - remove quote marks
    - normalize whitespace

    We do NOT aggressively strip punctuation because some punctuation carries
    answer meaning.

    Parameters
    ----------
    value : any
        Raw text.

    Returns
    -------
    str
        Cleaned and normalized string.
    """
    text = clean_text(value).lower()
    text = re.sub(r"[“”\"'`]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_delimiters(text):
    """
    Normalize separators used in answer strings.

    Why needed:
    - some rows separate answers with '|'
    - some rows use line breaks
    - some rows contain date ranges with dash-like characters

    Important:
    We convert certain date ranges into pipe-separated values so they can be
    handled as multi-item answer lists rather than one long string.

    Examples:
        "2017-01-01 - 2017-01-05"
        -> "2017-01-01|2017-01-05"

        "1 September 1939 – 2 September 1945"
        -> "1 September 1939|2 September 1945"

    Parameters
    ----------
    text : str

    Returns
    -------
    str
        Delimiter-normalized string.
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


# =============================================================================
# Helper function: split_answers
# =============================================================================
# Splits an answer string into a cleaned list of answer items.
#
# This version splits on:
#   - '|'
#   - line breaks
#
# It intentionally does NOT split on comma because commas are part of many
# date formats such as:
#   "October 12, 2017"

def split_answers(answer_string):
    """
    Split a possibly multi-valued answer string into answer items.

    Parameters
    ----------
    answer_string : str

    Returns
    -------
    list[str]
        Cleaned list of answer items.
    """
    if pd.isna(answer_string):
        return []

    text = normalize_delimiters(answer_string)
    parts = re.split(r"[|\n]+", text)

    return [clean_text(part) for part in parts if clean_text(part)]


# =============================================================================
# Date parsing helpers
# =============================================================================

def is_plausible_year(year):
    """
    Reject clearly invalid year-like numbers.

    This avoids accidentally treating arbitrary numeric values as dates.

    Parameters
    ----------
    year : int

    Returns
    -------
    bool
    """
    return 1500 <= year <= 2099


def parse_date_like(text):
    """
    Parse a date-like answer string into a ParsedDate object.

    Supported formats:
        - YYYY
        - Month YYYY
        - DD Month YYYY
        - Month DD, YYYY
        - YYYY-MM-DD
        - YYYY-MM-DDTHH:MM:SSZ

    Examples:
        "2018"                    -> ParsedDate("2018", "year", 2018)
        "October 1973"            -> ParsedDate("1973-10", "month", 1973, 10)
        "9 February 2018"         -> ParsedDate("2018-02-09", "day", 2018, 2, 9)
        "May 16, 2018"            -> ParsedDate("2018-05-16", "day", 2018, 5, 16)
        "2017-03-31T00:00:00Z"    -> ParsedDate("2017-03-31", "day", 2017, 3, 31)

    Parameters
    ----------
    text : str

    Returns
    -------
    ParsedDate or None
        None if the string does not match a supported date format.
    """
    text = clean_text(text)
    if not text:
        return None

    # -------------------------------------------------------------------------
    # Case 1: Full ISO timestamp
    # Example:
    #   2017-03-31T00:00:00Z
    # -------------------------------------------------------------------------
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})T\d{2}:\d{2}:\d{2}Z", text)
    if match:
        year, month, day = map(int, match.groups())
        if is_plausible_year(year) and 1 <= month <= 12 and 1 <= day <= 31:
            return ParsedDate(
                normalized=f"{year:04d}-{month:02d}-{day:02d}",
                precision="day",
                year=year,
                month=month,
                day=day,
            )

    # -------------------------------------------------------------------------
    # Case 2: ISO day format
    # Example:
    #   2018-05-16
    # -------------------------------------------------------------------------
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        year, month, day = map(int, match.groups())
        if is_plausible_year(year) and 1 <= month <= 12 and 1 <= day <= 31:
            return ParsedDate(
                normalized=f"{year:04d}-{month:02d}-{day:02d}",
                precision="day",
                year=year,
                month=month,
                day=day,
            )

    # -------------------------------------------------------------------------
    # Case 3: Year only
    # Example:
    #   2018
    # -------------------------------------------------------------------------
    match = re.fullmatch(r"(\d{4})", text)
    if match:
        year = int(match.group(1))
        if is_plausible_year(year):
            return ParsedDate(
                normalized=f"{year:04d}",
                precision="year",
                year=year,
            )

    # -------------------------------------------------------------------------
    # Case 4: Month Year
    # Examples:
    #   October 1973
    #   Jan. 2009
    # -------------------------------------------------------------------------
    match = re.fullmatch(r"([A-Za-z]+)\.?\s+(\d{4})", text)
    if match:
        month_text, year = match.groups()
        month_num = MONTHS.get(month_text.lower().rstrip("."))
        year = int(year)
        if month_num and is_plausible_year(year):
            return ParsedDate(
                normalized=f"{year:04d}-{month_num:02d}",
                precision="month",
                year=year,
                month=month_num,
            )

    # -------------------------------------------------------------------------
    # Case 5: Day Month Year
    # Examples:
    #   9 February 2018
    #   11 Jul 2017
    # -------------------------------------------------------------------------
    match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\.?\s+(\d{4})", text)
    if match:
        day, month_text, year = match.groups()
        month_num = MONTHS.get(month_text.lower().rstrip("."))
        day = int(day)
        year = int(year)
        if month_num and is_plausible_year(year) and 1 <= day <= 31:
            return ParsedDate(
                normalized=f"{year:04d}-{month_num:02d}-{day:02d}",
                precision="day",
                year=year,
                month=month_num,
                day=day,
            )

    # -------------------------------------------------------------------------
    # Case 6: Month Day, Year
    # Examples:
    #   May 16, 2018
    #   Aug. 25, 2009
    # -------------------------------------------------------------------------
    match = re.fullmatch(r"([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})", text)
    if match:
        month_text, day, year = match.groups()
        month_num = MONTHS.get(month_text.lower().rstrip("."))
        day = int(day)
        year = int(year)
        if month_num and is_plausible_year(year) and 1 <= day <= 31:
            return ParsedDate(
                normalized=f"{year:04d}-{month_num:02d}-{day:02d}",
                precision="day",
                year=year,
                month=month_num,
                day=day,
            )

    return None


def compare_dates(gold_text, pred_text):
    """
    Compare two answer items as dates, if both are parseable as dates.

    This is a precision-aware comparison. We do not force everything into a
    full YYYY-MM-DD date because that would lose important information about
    answer granularity.

    Example decisions:
        gold = "2018"
        pred = "May 16, 2018"
        -> pred_more_precise

        gold = "October 1973"
        pred = "1973-10-03"
        -> pred_more_precise

        gold = "2017-12-20"
        pred = "December 20, 2017"
        -> same

        gold = "Aug. 25, 2009"
        pred = "January 2009"
        -> same_year_but_different

        gold = "1939"
        pred = "1939-01-01T00:00:00Z"
        -> same

    Parameters
    ----------
    gold_text : str
    pred_text : str

    Returns
    -------
    dict or None
        None if either string is not date-like.
        Otherwise returns a dict with:
            relation
            score
            gold_normalized
            pred_normalized
    """
    gold_date = parse_date_like(gold_text)
    pred_date = parse_date_like(pred_text)

    if not gold_date or not pred_date:
        return None

    # -------------------------------------------------------------------------
    # Exact same date with the same precision
    # -------------------------------------------------------------------------
    if gold_date.normalized == pred_date.normalized and gold_date.precision == pred_date.precision:
        return {
            "relation": "same",
            "score": 1.0,
            "gold_normalized": gold_date.normalized,
            "pred_normalized": pred_date.normalized,
        }

    # -------------------------------------------------------------------------
    # Special case:
    # A bare year and January 1 of that same year are treated as the same fact.
    #
    # Examples:
    #   1939  <->  1939-01-01
    # -------------------------------------------------------------------------
    if gold_date.year == pred_date.year:
        if gold_date.precision == "year" and pred_date.precision == "day":
            if pred_date.month == 1 and pred_date.day == 1:
                return {
                    "relation": "same",
                    "score": 1.0,
                    "gold_normalized": gold_date.normalized,
                    "pred_normalized": pred_date.normalized,
                }

        if pred_date.precision == "year" and gold_date.precision == "day":
            if gold_date.month == 1 and gold_date.day == 1:
                return {
                    "relation": "same",
                    "score": 1.0,
                    "gold_normalized": gold_date.normalized,
                    "pred_normalized": pred_date.normalized,
                }

    # -------------------------------------------------------------------------
    # Same year, but different granularity
    # -------------------------------------------------------------------------
    if gold_date.year == pred_date.year:

        # Gold is less precise, prediction is more specific
        if gold_date.precision == "year" and pred_date.precision in {"month", "day"}:
            return {
                "relation": "pred_more_precise",
                "score": 0.995,
                "gold_normalized": gold_date.normalized,
                "pred_normalized": pred_date.normalized,
            }

        # Prediction is less precise, gold is more specific
        if pred_date.precision == "year" and gold_date.precision in {"month", "day"}:
            return {
                "relation": "gold_more_precise",
                "score": 0.995,
                "gold_normalized": gold_date.normalized,
                "pred_normalized": pred_date.normalized,
            }

        # Same year and month, but one side has full day precision
        if gold_date.month == pred_date.month and gold_date.precision == "month" and pred_date.precision == "day":
            return {
                "relation": "pred_more_precise",
                "score": 0.995,
                "gold_normalized": gold_date.normalized,
                "pred_normalized": pred_date.normalized,
            }

        if pred_date.month == gold_date.month and pred_date.precision == "month" and gold_date.precision == "day":
            return {
                "relation": "gold_more_precise",
                "score": 0.995,
                "gold_normalized": gold_date.normalized,
                "pred_normalized": pred_date.normalized,
            }

        # Same year and same month, but conflicting day values
        if gold_date.month is not None and pred_date.month is not None and gold_date.month == pred_date.month:
            return {
                "relation": "same_month_but_different",
                "score": 0.35,
                "gold_normalized": gold_date.normalized,
                "pred_normalized": pred_date.normalized,
            }

        # Same year only, but month/day disagree
        return {
            "relation": "same_year_but_different",
            "score": 0.20,
            "gold_normalized": gold_date.normalized,
            "pred_normalized": pred_date.normalized,
        }

    # -------------------------------------------------------------------------
    # Entirely different years
    # -------------------------------------------------------------------------
    return {
        "relation": "different",
        "score": 0.0,
        "gold_normalized": gold_date.normalized,
        "pred_normalized": pred_date.normalized,
    }


# =============================================================================
# Load dataset
# =============================================================================

log_print("Loading dataset...")
df = pd.read_csv(INPUT_FILE)


# =============================================================================
# Validate required columns
# =============================================================================

required_columns = [
    "question",
    "gold_answer",
    "result_cleaned",
    "result",
    "sparql",
    "file_path",
]

missing_columns = [c for c in required_columns if c not in df.columns]
if missing_columns:
    record_handle.close()
    raise ValueError(f"Missing required columns: {missing_columns}")


# =============================================================================
# Load SBERT model
# =============================================================================
# This script is intentionally SBERT-only.
# If this fails, the script should fail rather than silently falling back to
# another backend.

log_print("Loading Sentence-BERT model...")
model = SentenceTransformer(MODEL_NAME)


# =============================================================================
# Embedding cache
# =============================================================================
# Reusing embeddings avoids recomputing them for repeated answer strings.

embedding_cache = {}


def get_embedding(text):
    """
    Get SBERT embedding for one normalized text string, using a cache.

    Parameters
    ----------
    text : str

    Returns
    -------
    torch.Tensor
        SBERT embedding tensor.
    """
    if text not in embedding_cache:
        embedding_cache[text] = model.encode(text, convert_to_tensor=True)
    return embedding_cache[text]


# =============================================================================
# Helper function: pair_similarity
# =============================================================================
# Returns a similarity score in [0, 1] for one answer-item pair.
#
# Comparison order:
#   1. Exact normalized text match
#   2. Date-aware comparison if both items are dates
#   3. SBERT cosine similarity otherwise
#
# We clamp SBERT cosine scores into [0, 1] because cosine similarity can be
# slightly negative for unrelated texts, but this pipeline expects a
# non-negative similarity scale.

def pair_similarity(a, b):
    """
    Compute similarity for one pair of answer items.

    Parameters
    ----------
    a : str
        Gold answer item.
    b : str
        Predicted answer item.

    Returns
    -------
    tuple(float, str)
        (score, comparison_mode)

        comparison_mode examples:
            "exact"
            "date:same"
            "date:pred_more_precise"
            "date:gold_more_precise"
            "date:different"
            "sbert"
    """
    a_norm = normalize_text_for_similarity(a)
    b_norm = normalize_text_for_similarity(b)

    # -------------------------------------------------------------------------
    # Exact normalized text match
    # -------------------------------------------------------------------------
    if a_norm and a_norm == b_norm:
        return 1.0, "exact"

    # -------------------------------------------------------------------------
    # Date-aware comparison
    # -------------------------------------------------------------------------
    date_comparison = compare_dates(a, b)
    if date_comparison is not None:
        return date_comparison["score"], f"date:{date_comparison['relation']}"

    # -------------------------------------------------------------------------
    # SBERT comparison for non-date text
    # -------------------------------------------------------------------------
    emb_a = get_embedding(a_norm)
    emb_b = get_embedding(b_norm)
    score = float(util.cos_sim(emb_a, emb_b).item())

    return max(0.0, min(1.0, score)), "sbert"


# =============================================================================
# Core function: compute_answer_metrics
# =============================================================================
# This compares one gold answer string and one predicted answer string.
#
# Returned metrics:
#   - gold_size
#   - pred_size
#   - recall
#   - precision
#   - f1_score
#   - max_gold_to_pred
#   - max_pred_to_gold

def compute_answer_metrics(gold, pred):
    """
    Compare one gold answer field and one predicted answer field.

    Steps:
    1. Split each field into answer items
    2. Build a pairwise similarity matrix
    3. Compute recall, precision, and F1 over best matches

    Parameters
    ----------
    gold : str
        Gold answer field.
    pred : str
        Predicted answer field.

    Returns
    -------
    dict
        Metrics and split answer items.
    """
    # -------------------------------------------------------------------------
    # Step 1: Split into individual answer items
    # -------------------------------------------------------------------------
    gold_list = split_answers(gold)
    pred_list = split_answers(pred)

    gold_size = len(gold_list)
    pred_size = len(pred_list)

    # -------------------------------------------------------------------------
    # Step 2: Handle empty-answer edge cases
    # -------------------------------------------------------------------------
    if gold_size == 0 or pred_size == 0:
        return {
            "gold_size": gold_size,
            "pred_size": pred_size,
            "recall": 0.0,
            "precision": 0.0,
            "f1_score": 0.0,
            "max_gold_to_pred": 0.0,
            "max_pred_to_gold": 0.0,
            "gold_items": gold_list,
            "pred_items": pred_list,
        }

    # -------------------------------------------------------------------------
    # Step 3: Build similarity matrix
    # -------------------------------------------------------------------------
    similarity_matrix = np.zeros((gold_size, pred_size), dtype=float)

    for i, gold_item in enumerate(gold_list):
        for j, pred_item in enumerate(pred_list):
            similarity_matrix[i, j], _ = pair_similarity(gold_item, pred_item)

    # -------------------------------------------------------------------------
    # Step 4A: Recall = average best match for each gold answer item
    # -------------------------------------------------------------------------
    recall_scores = similarity_matrix.max(axis=1)
    recall = float(recall_scores.mean())

    # -------------------------------------------------------------------------
    # Step 4B: Precision = average best match for each predicted answer item
    # -------------------------------------------------------------------------
    precision_scores = similarity_matrix.max(axis=0)
    precision = float(precision_scores.mean())

    # -------------------------------------------------------------------------
    # Step 5: Harmonic mean = F1
    # -------------------------------------------------------------------------
    if precision + recall == 0:
        f1_score = 0.0
    else:
        f1_score = 2 * (precision * recall) / (precision + recall)

    # -------------------------------------------------------------------------
    # Step 6: Alignment signals for "Different answer" detection
    # -------------------------------------------------------------------------
    max_gold_to_pred = float(recall_scores.max())
    max_pred_to_gold = float(precision_scores.max())

    return {
        "gold_size": gold_size,
        "pred_size": pred_size,
        "recall": recall,
        "precision": precision,
        "f1_score": f1_score,
        "max_gold_to_pred": max_gold_to_pred,
        "max_pred_to_gold": max_pred_to_gold,
        "gold_items": gold_list,
        "pred_items": pred_list,
    }


# =============================================================================
# Date-specific taxonomy helper
# =============================================================================
# For single-item date answers, we can often make a stronger decision than
# generic aggregate similarity alone.

def classify_single_date_pair(gold_items, pred_items):
    """
    Make a direct taxonomy decision for single-item date pairs.

    Why this exists:
    Generic F1 similarity is not enough for cases like:
        gold = "2018"
        pred = "May 16, 2018"

    That should be:
        "Higher accuracy in Wikidata than in Table"

    Parameters
    ----------
    gold_items : list[str]
    pred_items : list[str]

    Returns
    -------
    str or None
        Taxonomy label if date-specific logic applies, else None.
    """
    if len(gold_items) != 1 or len(pred_items) != 1:
        return None

    comparison = compare_dates(gold_items[0], pred_items[0])
    if comparison is None:
        return None

    if comparison["relation"] == "same":
        return "same"

    if comparison["relation"] == "pred_more_precise":
        return "Higher accuracy in Wikidata than in Table"

    if comparison["relation"] == "gold_more_precise":
        return "Higher accuracy in Table than in Wikidata"

    return "Different answer"


# =============================================================================
# Taxonomy labeling function
# =============================================================================
# Priority order:
#   1. date-specific single-item decision
#   2. same
#   3. Higher accuracy in Wikidata than in Table
#   4. Higher accuracy in Table than in Wikidata
#   5. Different answer
#   6. different_unclassified

def assign_taxonomy_label(metrics, gold_answer, pred_answer):
    """
    Assign taxonomy label for one answer pair.

    Parameters
    ----------
    metrics : dict
        Output from compute_answer_metrics.
    gold_answer : str
        Original gold answer field.
    pred_answer : str
        Original predicted answer field.

    Returns
    -------
    str
        Taxonomy label.
    """
    gold_items = split_answers(gold_answer)
    pred_items = split_answers(pred_answer)

    # -------------------------------------------------------------------------
    # Case 0: Date-specific override for single-item date answers
    # -------------------------------------------------------------------------
    single_date_label = classify_single_date_pair(gold_items, pred_items)
    if single_date_label is not None:
        return single_date_label

    gold_size = metrics["gold_size"]
    pred_size = metrics["pred_size"]
    recall = metrics["recall"]
    precision = metrics["precision"]
    f1_score = metrics["f1_score"]
    max_gold_to_pred = metrics["max_gold_to_pred"]
    max_pred_to_gold = metrics["max_pred_to_gold"]

    # -------------------------------------------------------------------------
    # Case 1: same
    # -------------------------------------------------------------------------

    if (
        recall >= SAME_THRESHOLD
        and precision >= SAME_THRESHOLD
        and f1_score >= SAME_THRESHOLD
    ):
        return "same"

    # -------------------------------------------------------------------------
    # Case 2: Higher accuracy in Wikidata than in Table
    #
    # Interpretation:
    #   The predicted answer fully covers the gold answer, but also contains
    #   extra information or extra answer content.
    # -------------------------------------------------------------------------
    if recall >= PERFECT_MATCH_THRESHOLD and precision < PERFECT_MATCH_THRESHOLD:
        return "Higher accuracy in Wikidata than in Table"

    # -------------------------------------------------------------------------
    # Case 3: Higher accuracy in Table than in Wikidata
    #
    # Interpretation:
    #   Everything predicted seems correct, but the prediction misses some part
    #   of the gold answer.
    # -------------------------------------------------------------------------
    if precision >= PERFECT_MATCH_THRESHOLD and recall < PERFECT_MATCH_THRESHOLD:
        return "Higher accuracy in Table than in Wikidata"

    # -------------------------------------------------------------------------
    # Case 4: Different answer
    #
    # Use this when both sides are similarly sized but semantic overlap is
    # extremely weak overall.
    # -------------------------------------------------------------------------
    if (
        gold_size == pred_size
        and recall <= LOW_SCORE_THRESHOLD
        and precision <= LOW_SCORE_THRESHOLD
        and max_gold_to_pred < STRICT_ALIGNMENT_THRESHOLD
        and max_pred_to_gold < STRICT_ALIGNMENT_THRESHOLD
    ):
        return "Different answer"

    # -------------------------------------------------------------------------
    # Fallback
    # -------------------------------------------------------------------------
    return "different_unclassified"


# =============================================================================
# Main evaluation loop
# =============================================================================

gold_sizes = []
pred_sizes = []
recalls = []
precisions = []
similarities = []
taxonomy_labels = []

log_print(f"Loaded {len(df)} rows.")
log_print(f"Using SBERT model: {MODEL_NAME}")
log_print("Computing answer metrics and taxonomy labels using backend: sbert")

for _, row in tqdm(df.iterrows(), total=len(df)):
    metrics = compute_answer_metrics(
        row["gold_answer"],
        row["result_cleaned"]
    )

    label = assign_taxonomy_label(
        metrics,
        row["gold_answer"],
        row["result_cleaned"]
    )

    gold_sizes.append(metrics["gold_size"])
    pred_sizes.append(metrics["pred_size"])
    recalls.append(metrics["recall"])
    precisions.append(metrics["precision"])
    similarities.append(metrics["f1_score"])
    taxonomy_labels.append(label)


# =============================================================================
# Add computed columns to DataFrame
# =============================================================================

df["gold_size"] = gold_sizes
df["pred_size"] = pred_sizes
df["recall"] = recalls
df["precision"] = precisions
df["similarity_score"] = similarities
df["taxonomy_label"] = taxonomy_labels


# =============================================================================
# Reorder columns
# =============================================================================

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


# =============================================================================
# Sort rows
# =============================================================================

df = df.sort_values(by="similarity_score", ascending=False)


# =============================================================================
# Save results
# =============================================================================

df.to_csv(OUTPUT_FILE, index=False)

log_print("\nFinished.")
log_print("Results saved to:", OUTPUT_FILE)
log_print("Execution log saved to:", RECORD_FILE)


# =============================================================================
# Basic sanity report
# =============================================================================

label_counts = df["taxonomy_label"].value_counts(dropna=False)

log_print("\nLabel counts:")
log_print(label_counts.to_string())

record_handle.close()