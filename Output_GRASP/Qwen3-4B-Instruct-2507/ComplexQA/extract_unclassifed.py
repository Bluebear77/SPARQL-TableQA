import pandas as pd

input_csv = "all_valid_cases_with_taxonomy.csv"
output_csv = "different_unclassified_questions.csv"

df = pd.read_csv(input_csv)

filtered = (
    df.loc[df["taxonomy_label"] == "different_unclassified",
           ["question", "gold_answer", "result_cleaned","file_path"]]
      .rename(columns={"result_cleaned": "KG answer"})
)

filtered.to_csv(output_csv, index=False)

print(f"Saved {len(filtered)} rows to {output_csv}")
