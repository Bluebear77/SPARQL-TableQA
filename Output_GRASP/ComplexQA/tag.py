"""
================================================================================
Purpose
================================================================================

This script evaluates the similarity between:
    - the ground truth answers (column: gold_answer)
    - the generated SPARQL query results (column: result_cleaned)

Each row in the dataset corresponds to a question and its expected answer(s).
The answers may contain multiple values separated by the character '|'.

Example:
    gold_answer      = "Paris|London"
    result_cleaned   = "Paris|Berlin"

To compare them semantically (not just exact string match), we use a
Sentence-BERT model to compute cosine similarity between answers.

================================================================================
How the Comparison Works
================================================================================

1. Multi-answer handling
   ----------------------
   Both columns may contain multiple answers separated by '|'.
   We split them into lists:

        "Paris|London" -> ["Paris", "London"]

2. Sentence-BERT embeddings
   -------------------------
   Each answer is converted into a vector representation (embedding)
   using the model:

        all-MiniLM-L6-v2

   This allows semantic comparison rather than exact string matching.

3. Similarity matrix
   ------------------
   We compute cosine similarity between all pairs:

        gold answers  vs  predicted answers

        Example:

                     Predicted
                  Paris  Berlin
        Gold Paris  1.00   0.32
             London 0.41   0.28
             
    Each cell represents how semantically similar a gold answer is to a predicted answer.

4. Bidirectional best-match strategy
   --------------------
  Instead of only matching gold → predicted (as in the previous version),
  we now perform matching in BOTH directions:

    (A) Gold → Predicted  (Recall)
        For each gold answer, select the highest similarity with any
        predicted answer.

            Paris  -> max(1.00, 0.32) = 1.00
            London -> max(0.41, 0.28) = 0.41       
        Recall = (1.00 + 0.41) / 2 = 0.705

        This measures how well the predicted answers cover the ground truth.


    (B) Predicted → Gold  (Precision)
        For each predicted answer, select the highest similarity with any
        gold answer.

            Paris  -> max(1.00, 0.41) = 1.00
            Berlin -> max(0.32, 0.28) = 0.32
        Precision = (1.00 + 0.32) / 2 = 0.66

    This measures:"How many predicted answers are actually correct?" 
    Thus penalizes extra or incorrect predicted answers.

5. Final similarity score
   ----------------------
  We compute:

    recall    = mean(best matches from gold → predicted)
    precision = mean(best matches from predicted → gold)

    Then combine them using the F1 score:

        similarity_score = 2 * (precision * recall) / (precision + recall)

    This ensures:
        - High score only if ALL gold answers are found (high recall)
        - AND no extra incorrect answers are predicted (high precision)

    Unlike the previous approach, this method penalizes cases where
    extra answers are present in the prediction.

    F1 = 2 × (0.66 × 0.705) / (0.66 + 0.705) = 2 × (0.4653) / 1.365 ≈ 0.681

6. Label decision
   ---------------
   If similarity_score >= SIM_THRESHOLD
        → label = "same"
   else
        → label = "different"

7. Sorting
   -------
   Finally, rows are sorted by similarity_score in descending order
   so that the most similar cases appear first.

================================================================================
Output Columns
================================================================================

Final CSV will contain:

    [
        question,
        gold_answer,
        result_cleaned,
        similarity_score,
        comparison_label,
        result,
        sparql,
        file_path
    ]

Rows are sorted by similarity_score (descending).

================================================================================
"""

import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer, util
from tqdm import tqdm

# =============================================================================
# Configuration
# =============================================================================
# File paths and similarity threshold.

INPUT_FILE = "all_valid_cases.csv"
OUTPUT_FILE = "all_valid_cases_with_similarity.csv"

# Threshold above which answers are considered equivalent
SIM_THRESHOLD = 0.80


# =============================================================================
# Load dataset
# =============================================================================
# The CSV file is loaded into a pandas DataFrame.

print("Loading dataset...")
df = pd.read_csv(INPUT_FILE)


# =============================================================================
# Load Sentence-BERT model
# =============================================================================
# We use a lightweight semantic similarity model.
# This model maps text into a dense vector space where similar sentences
# have vectors close to each other.

print("Loading Sentence-BERT model...")
model = SentenceTransformer("all-MiniLM-L6-v2")


# =============================================================================
# Helper function: split answers
# =============================================================================
# Splits answers separated by '|' and removes extra whitespace.
# Example:
#    "Paris|London" -> ["Paris", "London"]

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
# To speed up computation, we store embeddings that were already computed.
# If the same answer appears multiple times in the dataset, we reuse
# the embedding instead of recomputing it.

embedding_cache = {}


def get_embedding(text):

    if text not in embedding_cache:
        embedding_cache[text] = model.encode(text, convert_to_tensor=True)

    return embedding_cache[text]



"""
    =============================================================================
    Improved Similarity Function (F1-based)
    =============================================================================

    This function compares two sets of answers:
        - gold (ground truth)
        - pred (model prediction)

    Unlike the previous version, this implementation considers BOTH:
        ✔ Recall  (Did we find all correct answers?)
        ✔ Precision (Did we avoid extra incorrect answers?)

    This prevents false positives like:
        gold = "Mercy Health"
        pred = "Mercy Health|Toyota"

    where the previous method incorrectly returned similarity = 1.0.

    -----------------------------------------------------------------------------
    Steps:
    -----------------------------------------------------------------------------

    1. Split answers by '|'
    2. Convert each answer into embeddings
    3. Compute cosine similarity matrix
    4. Compute:
        - Recall  (gold → pred)
        - Precision (pred → gold)
    5. Combine them using F1 score
    6. Return final similarity score

    -----------------------------------------------------------------------------
    Output:
        A float in [0, 1] representing semantic similarity
    =============================================================================
"""
def compute_similarity(gold, pred):


    # -------------------------------------------------------------------------
    # Step 1: Split answers into lists
    # -------------------------------------------------------------------------
    gold_list = split_answers(gold)
    pred_list = split_answers(pred)

    # If either side is empty → no similarity
    if len(gold_list) == 0 or len(pred_list) == 0:
        return 0.0

    # -------------------------------------------------------------------------
    # Step 2: Convert answers into embeddings (with caching)
    # -------------------------------------------------------------------------
    gold_embeddings = [get_embedding(x) for x in gold_list]
    pred_embeddings = [get_embedding(x) for x in pred_list]

    # Convert tensors → numpy arrays for similarity computation
    gold_embeddings = np.stack([g.cpu().numpy() for g in gold_embeddings])
    pred_embeddings = np.stack([p.cpu().numpy() for p in pred_embeddings])

    # -------------------------------------------------------------------------
    # Step 3: Compute cosine similarity matrix
    #
    # Shape:
    #   (num_gold_answers, num_pred_answers)
    #
    # Each cell (i, j) = similarity(gold[i], pred[j])
    # -------------------------------------------------------------------------
    similarity_matrix = util.cos_sim(gold_embeddings, pred_embeddings)

    # -------------------------------------------------------------------------
    # Step 4A: Compute RECALL (gold → pred)
    #
    # For each gold answer:
    #   find the most similar predicted answer
    #
    # This answers:
    #   "Did we correctly recover each ground-truth answer?"
    # -------------------------------------------------------------------------
    recall_scores = similarity_matrix.max(dim=1).values
    recall = float(recall_scores.mean())

    # -------------------------------------------------------------------------
    # Step 4B: Compute PRECISION (pred → gold)
    #
    # For each predicted answer:
    #   find the most similar gold answer
    #
    # This penalizes extra predictions that do not match anything in gold.
    #
    # Example:
    #   pred = ["Mercy Health", "Toyota"]
    #
    #   "Toyota" will have low similarity → lowers precision
    # -------------------------------------------------------------------------
    precision_scores = similarity_matrix.max(dim=0).values
    precision = float(precision_scores.mean())

    # -------------------------------------------------------------------------
    # Step 5: Combine using F1 score
    #
    # F1 balances precision and recall:
    #
    #   - High recall + low precision → penalized
    #   - High precision + low recall → penalized
    #
    # Prevents division by zero when both are 0.
    # -------------------------------------------------------------------------
    if precision + recall == 0:
        return 0.0

    f1_score = 2 * (precision * recall) / (precision + recall)

    # -------------------------------------------------------------------------
    # Step 6: Return final similarity score
    # -------------------------------------------------------------------------
    return f1_score

# =============================================================================
# Main evaluation loop
# =============================================================================
# Iterate through all rows and compute similarity scores.
# tqdm provides a progress bar for long datasets.

similarities = []
labels = []

print("Computing similarities...")

for _, row in tqdm(df.iterrows(), total=len(df)):

    score = compute_similarity(
        row["gold_answer"],
        row["result_cleaned"]
    )

    similarities.append(score)

    if score >= SIM_THRESHOLD:
        labels.append("same")
    else:
        labels.append("different")


# =============================================================================
# Add computed columns
# =============================================================================

df["similarity_score"] = similarities
df["comparison_label"] = labels


# =============================================================================
# Reorder columns
# =============================================================================

df = df[
    [
        "question",
        "gold_answer",
        "result_cleaned",
        "similarity_score",
        "comparison_label",
        "result",
        "sparql",
        "file_path",
    ]
]


# =============================================================================
# Sort rows by similarity score (descending)
# =============================================================================
# This allows quick inspection of:
#   - highest similarity cases
#   - borderline cases near the threshold

df = df.sort_values(by="similarity_score", ascending=False)


# =============================================================================
# Save results
# =============================================================================

df.to_csv(OUTPUT_FILE, index=False)

print("\nFinished.")
print("Results saved to:", OUTPUT_FILE)