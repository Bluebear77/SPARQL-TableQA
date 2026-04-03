import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os
from pathlib import Path

# Create output directory
output_dir = Path("Compare")
output_dir.mkdir(exist_ok=True)

# Read the CSV file
df = pd.read_csv("all_valid_cases_with_similarity.csv")

print(f"Loaded {len(df)} rows from CSV")

# 1. Calculate counts for comparison_label
label_counts = df['comparison_label'].value_counts()
total_cases = len(df)

# 2. Summary statistics for similarity_score by label
summary_stats = df.groupby('comparison_label')['similarity_score'].agg([
    'count', 'mean', 'std', 'min', 'max'
]).round(4)

# 3. Generate Markdown summary table
md_content = f"""# Comparison Analysis Summary
*Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}*
*Total cases: {total_cases}*

## Comparison Label Distribution
| Label    | Count | Percentage |
|----------|-------|------------|
"""
for label, count in label_counts.items():
    pct = (count/total_cases)*100
    md_content += f"| {label:<8} | {count:<5} | {pct:>7.1f}% |\n"

md_content += "\n## Similarity Score Statistics\n"
md_content += summary_stats.to_markdown()

# Save Markdown file
with open(output_dir / "summary_table.md", 'w') as f:
    f.write(md_content)

print("✅ Saved summary_table.md")

# 4. Create visualizations
plt.style.use('default')
fig, axes = plt.subplots(2, 2, figsize=(15, 12))

# Bar chart: Comparison label distribution
label_counts.plot(kind='bar', ax=axes[0,0], color=['skyblue', 'lightcoral'])
axes[0,0].set_title('Comparison Label Distribution')
axes[0,0].set_ylabel('Count')
axes[0,0].tick_params(axis='x', rotation=0)

# Bar chart: Similarity score by comparison label (mean)
mean_scores = df.groupby('comparison_label')['similarity_score'].mean()
mean_scores.plot(kind='bar', ax=axes[0,1], color=['skyblue', 'lightcoral'])
axes[0,1].set_title('Mean Similarity Score by Label')
axes[0,1].set_ylabel('Mean Similarity Score')
axes[0,1].tick_params(axis='x', rotation=0)

# Histogram: Similarity score distribution
df['similarity_score'].hist(bins=20, ax=axes[1,0], alpha=0.7, edgecolor='black')
axes[1,0].set_title('Similarity Score Distribution')
axes[1,0].set_xlabel('Similarity Score')
axes[1,0].set_ylabel('Frequency')

# Box plot: Similarity score by comparison label
sns.boxplot(data=df, x='comparison_label', y='similarity_score', ax=axes[1,1])
axes[1,1].set_title('Similarity Score Box Plot by Label')
axes[1,1].tick_params(axis='x', rotation=0)

plt.tight_layout()
plt.savefig(output_dir / 'comparison_analysis.png', dpi=300, bbox_inches='tight')
plt.close()

print("✅ Saved comparison_analysis.png")

# 5. Additional line chart for similarity score trends (if ordered data exists)
plt.figure(figsize=(12, 6))
plt.plot(df['similarity_score'].sort_values().values, marker='o', linewidth=1, markersize=3)
plt.title('Similarity Score Distribution (Sorted)')
plt.xlabel('Case Index (Sorted)')
plt.ylabel('Similarity Score')
plt.grid(True, alpha=0.3)
plt.savefig(output_dir / 'similarity_score_line.png', dpi=300, bbox_inches='tight')
plt.close()

print("✅ Saved similarity_score_line.png")

# 6. Print summary to console
print("\n" + "="*50)
print("SUMMARY")
print("="*50)
print(f"Total cases: {total_cases}")
print("\nLabel Distribution:")
print(label_counts)
print("\nSimilarity Score Stats by Label:")
print(summary_stats)
print(f"\nFiles saved in: {output_dir.absolute()}")

print("\n🎉 Analysis complete! Check the 'Compare' directory.")
