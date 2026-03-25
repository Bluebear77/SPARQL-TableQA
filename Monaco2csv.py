import json
import pandas as pd

# Load the JSON file
with open('monaco_version_1_release.json', 'r') as f:
    data = json.load(f)

# Extract QA pairs and count actual number of answer elements
qa_pairs = []
for question_key, info in data.items():
    question_text = info['question']
    validated_answer = info['validated_answer']
    
    # Flatten nested structure and count actual answer elements
    if validated_answer:
        flat_answers = []
        for item in validated_answer:
            if isinstance(item, list):
                flat_answers.extend(item)
            else:
                flat_answers.append(item)
        num_answers = len(flat_answers)
        answer_str = str(validated_answer)  # Keep original format for output
    else:
        num_answers = 0
        answer_str = ''
    
    qa_pairs.append({
        'question': question_text,
        'answer': answer_str,
        'num_answers': num_answers
    })

# Create DataFrame and sort by actual number of answers (ascending)
df = pd.DataFrame(qa_pairs)
df_sorted = df.sort_values('num_answers', ascending=False)

# Save ONLY question and answer columns to CSV
df_sorted[['question', 'answer']].to_csv('Monaco.csv', index=False)

print("Monaco.csv created successfully!")
print(f"Total QA pairs: {len(df_sorted)}")
print("Sample of sorting (first 3 and last 3 rows by num_answers):")
print(df_sorted[['question', 'num_answers']].head(3))
print(df_sorted[['question', 'num_answers']].tail(3))
