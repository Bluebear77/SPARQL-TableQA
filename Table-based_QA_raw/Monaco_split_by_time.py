import json
import pandas as pd

# Load the time dependency JSON
with open('monaco_time_dependent_questions.json', 'r') as f:
    time_dep_data = json.load(f)

# Load the existing Monaco.csv
df = pd.read_csv('Monaco.csv')

# Create a mapping from question to time dependency status
time_dep_map = {}
for question, info in time_dep_data.items():
    time_dep_map[question] = info['is_time_dependent']

# Filter out binary True/False pairs
binary_mask = ~df['answer'].str.contains(r'^\s*\[?(True|False)\]?\s*$', regex=True, na=False, case=False)
df_clean = df[binary_mask].copy()

# 🔹 Add answer length and sort (NEW PART)
df_clean['answer_length'] = df_clean['answer'].astype(str).str.len()
df_clean = df_clean.sort_values(by='answer_length', ascending=False)

# Add time dependency column and categorize
df_clean['is_time_dependent'] = df_clean['question'].map(time_dep_map).fillna(False)
df_clean['category'] = df_clean['is_time_dependent'].map({True: 'time_dependent', False: 'non_time_dependent'})

# Split into two CSVs (already sorted by answer length)
time_dependent_df = df_clean[df_clean['is_time_dependent'] == True][['question', 'answer']]
non_time_dependent_df = df_clean[df_clean['is_time_dependent'] == False][['question', 'answer']]

# Save split files
time_dependent_df.to_csv('Monaco_time_dependent.csv', index=False)
non_time_dependent_df.to_csv('Monaco_non_time_dependent.csv', index=False)

# Print summary
print("Files created successfully!")
print(f"Original Monaco.csv: {len(df)} rows")
print(f"After removing binary T/F pairs: {len(df_clean)} rows")
print(f"Time-dependent questions: {len(time_dependent_df)} rows → Monaco_time_dependent.csv")
print(f"Non-time-dependent questions: {len(non_time_dependent_df)} rows → Monaco_non_time_dependent.csv")