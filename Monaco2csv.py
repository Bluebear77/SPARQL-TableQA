import json
import pandas as pd
from collections import Counter

# Load the JSON file
with open('monaco_version_1_release.json', 'r') as f:
    data = json.load(f)

# Extract QA pairs
qa_pairs = []
for question, info in data.items():
    question_text = info['question']
    validated_answer = info['validated_answer']
    
    # Handle both single answers (lists with nested lists) and multiple answers (flat lists)
    if validated_answer and isinstance(validated_answer[0], list):
        answer_str = str(validated_answer[0])
    else:
        answer_str = str(validated_answer)
    
    qa_pairs.append({
        'question': question_text,
        'answer': answer_str,
        'num_answers': len(validated_answer)
    })

# Create DataFrame
df = pd.DataFrame(qa_pairs)

# Sort by number of answers in ascending order
df_sorted = df.sort_values('num_answers', ascending=True)

# Save to CSV with only question and answer columns
df_sorted[['question', 'answer']].to_csv('Monaco.csv', index=False)

print("Monaco.csv created successfully!")
print(f"Total QA pairs: {len(df_sorted)}")
print(f"Answer counts range: {df_sorted['num_answers'].min()} to {df_sorted['num_answers'].max()}")
