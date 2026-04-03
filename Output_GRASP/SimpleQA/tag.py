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

4. Best-match strategy
   --------------------
   For each gold answer, we select the highest similarity with any
   predicted answer.

        Paris  -> max(1.00, 0.32) = 1.00
        London -> max(0.41, 0.28) = 0.41

5. Final similarity score
   ----------------------
   We compute the average of these best matches.

        similarity_score = mean(best_matches)

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


# =============================================================================
# Similarity computation function
# =============================================================================
# This function compares two sets of answers:
#
#    gold answers vs predicted answers
#
# Steps:
#   1. Split answers
#   2. Convert to embeddings
#   3. Compute cosine similarity matrix
#   4. Select best predicted match for each gold answer
#   5. Return the average similarity score

def compute_similarity(gold, pred):

    gold_list = split_answers(gold)
    pred_list = split_answers(pred)

    if len(gold_list) == 0 or len(pred_list) == 0:
        return 0.0

    # Convert answers to embeddings
    gold_embeddings = [get_embedding(x) for x in gold_list]
    pred_embeddings = [get_embedding(x) for x in pred_list]

    gold_embeddings = np.stack([g.cpu().numpy() for g in gold_embeddings])
    pred_embeddings = np.stack([p.cpu().numpy() for p in pred_embeddings])

    # Compute cosine similarity matrix
    similarity_matrix = util.cos_sim(gold_embeddings, pred_embeddings)

    # Best predicted match for each gold answer
    best_scores = similarity_matrix.max(dim=1).values

    # Final similarity score
    final_score = float(best_scores.mean())

    return final_score


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