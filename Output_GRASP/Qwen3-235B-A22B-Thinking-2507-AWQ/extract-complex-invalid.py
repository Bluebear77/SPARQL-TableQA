import pandas as pd

input_csv = "all_invalid_cases.csv"
output_csv = "complexqa_questions.csv"

# Read input CSV
df = pd.read_csv(input_csv)

# Total number of rows
total_rows = len(df)

# Filter rows where file_path contains 'ComplexQA/'
filtered_df = df[df["file_path"].astype(str).str.contains("ComplexQA/", na=False)]

# Extract only the question column
questions = filtered_df["question"]

# Save without title/header and without index
questions.to_csv(output_csv, index=False, header=False)

# Print count and percentage
extracted_count = len(questions)
percentage = (extracted_count / total_rows * 100) if total_rows > 0 else 0

print(f"Extracted questions: {extracted_count}")
print(f"Percentage of extracted questions: {percentage:.2f}%")
print(f"Saved to: {output_csv}")
