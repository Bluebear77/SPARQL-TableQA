import json
from collections import Counter

with open("monaco_time_dependent_questions.json", "r", encoding="utf-8") as f:
    data = json.load(f)

values = [item.get("is_time_dependent") for item in data.values()]
counts = Counter(values)
total = len(values)

labels = {
    True: "time dependent",
    False: "not time dependent",
    None: "missing/unknown"
}

for key in [True, False, None]:
    n = counts.get(key, 0)
    freq = n / total if total else 0
    print(f"{labels[key]}: {n} ({freq:.2%})")

print(f"total questions: {total}")
