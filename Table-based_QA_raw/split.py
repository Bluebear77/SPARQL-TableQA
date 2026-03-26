import pandas as pd
from pathlib import Path

input_file = Path("Complex_question.csv")
output_dir = Path("output")
output_dir.mkdir(exist_ok=True)

df = pd.read_csv(input_file)

summary = []
total_instances = len(df)

for source, group in df.groupby("source", dropna=False):
    source_name = "NaN" if pd.isna(source) else str(source)
    out_file = output_dir / f"{source_name}_complex.csv"
    group.to_csv(out_file, index=False)
    summary.append((source_name, len(group), out_file.name))

for source_name, count, file_name in summary:
    print(f"{file_name}: {count} instances")

print(f"Total instances: {total_instances}")
