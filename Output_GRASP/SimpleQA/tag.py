import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer, util
from tqdm import tqdm

# ------------------------------------------------
# Configuration
# ------------------------------------------------

INPUT_FILE = "all_valid_cases.csv"
OUTPUT_FILE = "all_valid_cases_with_similarity.csv"

SIM_THRESHOLD = 0.80

# ------------------------------------------------
# Load data
# ------------------------------------------------

df = pd.read_csv(INPUT_FILE)

# ------------------------------------------------
# Load SBERT model
# ------------------------------------------------

print("Loading Sentence-BERT model...")
model = SentenceTransformer("all-MiniLM-L6-v2")

# ------------------------------------------------
# Helper functions
# ------------------------------------------------

def split_answers(answer_string):
    """
    Split answers separated by '|'
    Example:
    'Paris|London' -> ['Paris','London']
    """

    if pd.isna(answer_string):
        return []

    return [
        a.strip()
        for a in str(answer_string).split("|")
        if a.strip()
    ]


# ------------------------------------------------
# Cache embeddings to avoid recomputing
# ------------------------------------------------

embedding_cache = {}


def get_embedding(text):

    if text not in embedding_cache:
        embedding_cache[text] = model.encode(text, convert_to_tensor=True)

    return embedding_cache[text]


# ------------------------------------------------
# Compute similarity between two answer sets
# ------------------------------------------------

def compute_similarity(gold, pred):

    gold_list = split_answers(gold)
    pred_list = split_answers(pred)

    if len(gold_list) == 0 or len(pred_list) == 0:
        return 0.0

    gold_embeddings = [get_embedding(x) for x in gold_list]
    pred_embeddings = [get_embedding(x) for x in pred_list]

    gold_embeddings = np.stack([g.cpu().numpy() for g in gold_embeddings])
    pred_embeddings = np.stack([p.cpu().numpy() for p in pred_embeddings])

    similarity_matrix = util.cos_sim(gold_embeddings, pred_embeddings)

    # best predicted match for each gold answer
    best_scores = similarity_matrix.max(dim=1).values

    final_score = float(best_scores.mean())

    return final_score


# ------------------------------------------------
# Main loop with tqdm
# ------------------------------------------------

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


# ------------------------------------------------
# Add results
# ------------------------------------------------

df["similarity_score"] = similarities
df["comparison_label"] = labels


# ------------------------------------------------
# Reorder columns
# ------------------------------------------------

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


# ------------------------------------------------
# Save output
# ------------------------------------------------

df.to_csv(OUTPUT_FILE, index=False)

print("\nDone!")
print("Output saved to:", OUTPUT_FILE)