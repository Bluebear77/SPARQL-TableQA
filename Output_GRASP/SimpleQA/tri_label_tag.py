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
Why SBERT is Used
================================================================================

This script uses Sentence-BERT (SBERT), specifically:

    all-MiniLM-L6-v2

SBERT converts each answer into a vector (embedding), so answers can be compared
semantically rather than only by exact string matching.

This is important because two answers may express the same meaning even if the
text is not identical.

Example:
    "USA" and "United States"
may receive a high similarity score even though the strings are different.

Important:
    This script strictly uses SBERT.
    It does NOT use RapidFuzz or any string-matching fallback.


================================================================================
How the Comparison Works
================================================================================

1. Split multi-answer fields
   --------------------------
   If an answer contains '|', it is split into a list.

   Example:
       "Paris|London" -> ["Paris", "London"]

2. Build a similarity matrix
   --------------------------
   Every gold answer item is compared with every predicted answer item
   using SBERT cosine similarity.

   Example:

                    Predicted
                 Paris   Berlin
       Gold Paris  1.00    0.32
            London 0.41    0.28

   Each cell shows how semantically similar two answer items are.

3. Compute Recall
   ---------------
   For each gold answer, select its best matching predicted answer.

   This tells us:
       "How well does the predicted answer cover the gold answer?"

   Example:
       Paris  -> max(1.00, 0.32) = 1.00
       London -> max(0.41, 0.28) = 0.41

       recall = (1.00 + 0.41) / 2 = 0.705

4. Compute Precision
   ------------------
   For each predicted answer, select its best matching gold answer.

   This tells us:
       "How much of the predicted answer is actually correct?"

   Example:
       Paris  -> max(1.00, 0.41) = 1.00
       Berlin -> max(0.32, 0.28) = 0.32

       precision = (1.00 + 0.32) / 2 = 0.66

5. Compute Final Similarity Score
   -------------------------------
   Recall and precision are combined using the harmonic mean (F1 score):

       similarity_score = 2 * (precision * recall) / (precision + recall)

   This gives a high score only when:
       - the prediction covers the gold answer well
       - and it does not add too many incorrect extra answers

6. Extra alignment signals
   ------------------------
   In addition to recall, precision, and F1, the script also records:

       - max_gold_to_pred
       - max_pred_to_gold

   These help detect cases where two answers have almost no meaningful overlap,
   even if tiny non-zero similarity scores appear.

7. Assign taxonomy labels
   -----------------------
   The script assigns labels in this priority order:

   A) same
      If the final F1 score is high enough:

          similarity_score >= SAME_THRESHOLD

   B) Higher accuracy in Wikidata than in Table
      If the SPARQL/Wikidata answer fully covers the table answer,
      but also contains extra information:

          recall ~= 1
          precision < 1

      Interpretation:
          Wikidata is more complete / more informative here.

   C) Higher accuracy in Table than in Wikidata
      If everything returned by SPARQL is correct, but the SPARQL result
      misses some part of the gold answer:

          precision ~= 1
          recall < 1

      Interpretation:
          The table answer is more complete here.

   D) Different answer
      If both sides have the same number of answer items, but they show
      very weak semantic alignment overall:

          gold_size == pred_size
          recall and precision are both very low
          strongest pairwise matches are still weak

   E) different_unclassified
      Used as a fallback when none of the above rules apply.

8. Save and sort results
   ----------------------
   The final CSV is sorted by similarity_score in descending order.

   A text log named record.txt is also created.
   All important print messages are written both to the console and to record.txt.


================================================================================
Output Columns
================================================================================

The output CSV contains:

    [
        question,
        gold_answer,
        result_cleaned,
        gold_size,
        pred_size,
        recall,
        precision,
        similarity_score,
        taxonomy_label,
        result,
        sparql,
        file_path
    ]

Rows are sorted by similarity_score in descending order.

================================================================================
"""

import pandas as pd
import numpy as np
from tqdm import tqdm
from sentence_transformers import SentenceTransformer, util


# =============================================================================
# Configuration
# =============================================================================

INPUT_FILE = "all_valid_cases.csv"
OUTPUT_FILE = "all_valid_cases_with_taxonomy.csv"
RECORD_FILE = "record.txt"


# =============================================================================
# Logging helper
# =============================================================================
# This keeps the normal print output and also writes the same messages to
# record.txt so there is a saved execution record.

record_handle = open(RECORD_FILE, "w", encoding="utf-8")


def log_print(*args, sep=" ", end="\n"):
    message = sep.join(str(arg) for arg in args)
    print(message, end=end)
    record_handle.write(message + end)
    record_handle.flush()


# =============================================================================
# Similarity thresholds
# =============================================================================

# SAME_THRESHOLD:
#   If the final F1 similarity is at or above this threshold,
#   we treat the two answers as semantically the same overall.
SAME_THRESHOLD = 0.80

# PERFECT_MATCH_THRESHOLD:
#   Used instead of exact float equality with 1.0 because cosine similarity
#   values may be extremely close to 1 without being exactly 1.
PERFECT_MATCH_THRESHOLD = 0.999

# LOW_SCORE_THRESHOLD:
#   Used to define cases with almost no overlap at the aggregate level.
LOW_SCORE_THRESHOLD = 0.10

# STRICT_ALIGNMENT_THRESHOLD:
#   Even the strongest item-to-item match must stay below this threshold
#   for the script to confidently call the pair "Different answer".
STRICT_ALIGNMENT_THRESHOLD = 0.35


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

log_print("Loading Sentence-BERT model...")
model = SentenceTransformer("all-MiniLM-L6-v2")


# =============================================================================
# Helper function: split_answers
# =============================================================================
# Splits a pipe-separated answer string into a cleaned list.
#
# Example:
#     "Paris|London" -> ["Paris", "London"]

def split_answers(answer_string):
    if pd.isna(answer_string):
        return []

    return [
        a.strip()
        for a in str(answer_string).split("|")
        if a.strip()
    ]


# =============================================================================
# Embedding cache
# =============================================================================
# Reusing embeddings avoids recomputing them for repeated answer strings.

embedding_cache = {}


def get_embedding(text):
    if text not in embedding_cache:
        embedding_cache[text] = model.encode(text, convert_to_tensor=True)
    return embedding_cache[text]


# =============================================================================
# Helper function: pair_similarity
# =============================================================================
# Returns a similarity score in [0, 1] for one answer-item pair using SBERT
# cosine similarity.
#
# We clamp the score into [0, 1] because cosine similarity can sometimes be
# slightly negative for unrelated text, while this pipeline expects a
# non-negative similarity scale.

def pair_similarity(a, b):
    emb_a = get_embedding(a)
    emb_b = get_embedding(b)
    score = float(util.cos_sim(emb_a, emb_b).item())
    return max(0.0, min(1.0, score))


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
        }

    # -------------------------------------------------------------------------
    # Step 3: Build similarity matrix
    # -------------------------------------------------------------------------
    # Shape:
    #   (num_gold_answers, num_pred_answers)
    #
    # Each cell (i, j) contains similarity(gold_list[i], pred_list[j]).
    similarity_matrix = np.zeros((gold_size, pred_size), dtype=float)

    for i, gold_item in enumerate(gold_list):
        for j, pred_item in enumerate(pred_list):
            similarity_matrix[i, j] = pair_similarity(gold_item, pred_item)

    # -------------------------------------------------------------------------
    # Step 4A: Recall = average best match for each gold answer
    # -------------------------------------------------------------------------
    recall_scores = similarity_matrix.max(axis=1)
    recall = float(recall_scores.mean())

    # -------------------------------------------------------------------------
    # Step 4B: Precision = average best match for each predicted answer
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
    }


# =============================================================================
# Taxonomy labeling function
# =============================================================================
# Priority order:
#   1. same
#   2. Higher accuracy in Wikidata than in Table
#   3. Higher accuracy in Table than in Wikidata
#   4. Different answer
#   5. different_unclassified

def assign_taxonomy_label(metrics):
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
    if f1_score >= SAME_THRESHOLD:
        return "same"

    # -------------------------------------------------------------------------
    # Case 2: Higher accuracy in Wikidata than in Table
    # -------------------------------------------------------------------------
    if recall >= PERFECT_MATCH_THRESHOLD and precision < PERFECT_MATCH_THRESHOLD:
        return "Higher accuracy in Wikidata than in Table"

    # -------------------------------------------------------------------------
    # Case 3: Higher accuracy in Table than in Wikidata
    # -------------------------------------------------------------------------
    if precision >= PERFECT_MATCH_THRESHOLD and recall < PERFECT_MATCH_THRESHOLD:
        return "Higher accuracy in Table than in Wikidata"

    # -------------------------------------------------------------------------
    # Case 4: Different answer
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

log_print("Computing answer metrics and taxonomy labels using backend: sbert")

for _, row in tqdm(df.iterrows(), total=len(df)):
    metrics = compute_answer_metrics(
        row["gold_answer"],
        row["result_cleaned"]
    )

    label = assign_taxonomy_label(metrics)

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
