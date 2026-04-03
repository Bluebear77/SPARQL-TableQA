import pandas as pd
from datetime import datetime
import pytz
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os  # For output paths

# Define timezone (CEST/+0100 as given)
tz = pytz.timezone('Europe/Paris')

# SimpleQA timestamps and question counts
simple_times = {
    'Qampari': {
        'birth': tz.localize(datetime(2026, 3, 25, 11, 7, 28, 890934)),
        'complete': tz.localize(datetime(2026, 3, 25, 14, 6, 33)),
        'n_questions': 78
    },
    'NQ_table': {
        'birth': tz.localize(datetime(2026, 3, 24, 16, 10, 52, 934800)),
        'complete': tz.localize(datetime(2026, 3, 25, 11, 7, 28)),
        'n_questions': 966
    },
    'CompMix_simple': {
        'birth': tz.localize(datetime(2026, 3, 23, 17, 9, 22, 386360)),
        'complete': tz.localize(datetime(2026, 3, 24, 16, 10, 52)),
        'n_questions': 326
    }
}

# ComplexQA (single batch)
complex_time = {
    'birth': tz.localize(datetime(2026, 3, 25, 14, 12, 7, 338448)),
    'complete': tz.localize(datetime(2026, 3, 27, 3, 34, 50)),
    'n_questions': 1500
}

# Calculate durations
simple_results = {}
total_simple_questions = 0
total_simple_time = pd.Timedelta(0)

for name, data in simple_times.items():
    duration = data['complete'] - data['birth']
    avg_sec = duration.total_seconds() / data['n_questions']
    simple_results[name] = {'n_questions': data['n_questions'], 'avg_sec': avg_sec}
    total_simple_questions += data['n_questions']
    total_simple_time += duration

complex_duration = complex_time['complete'] - complex_time['birth']
complex_avg_sec = complex_duration.total_seconds() / complex_time['n_questions']
complex_results = {'ComplexQA': {'n_questions': 1500, 'avg_sec': complex_avg_sec}}

overall_simple_avg_sec = total_simple_time.total_seconds() / total_simple_questions

# Print results
print("SimpleQA Results:")
for name, res in simple_results.items():
    print(f"{name}: {res['n_questions']} questions, avg {res['avg_sec']:.2f}s ({res['avg_sec']/60:.2f}min)")
print(f"Overall SimpleQA: {total_simple_questions} questions, avg {overall_simple_avg_sec:.2f}s ({overall_simple_avg_sec/60:.2f}min)\n")

print("ComplexQA Results:")
for name, res in complex_results.items():
    print(f"{name}: {res['n_questions']} questions, avg {res['avg_sec']:.2f}s ({res['avg_sec']/60:.2f}min)")

# Plotting data
simple_plot = [{'dataset': k, 'avg_time_sec': v['avg_sec'], 'n_questions': v['n_questions'], 'type': 'SimpleQA'} 
               for k, v in simple_results.items()]
complex_plot = [{'dataset': k, 'avg_time_sec': v['avg_sec'], 'n_questions': v['n_questions'], 'type': 'ComplexQA'} 
                for k, v in complex_results.items()]
plot_data = simple_plot + complex_plot
df_plot = pd.DataFrame(plot_data)

# Create plots (bar + scatter for sample size)
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
sns.barplot(data=df_plot, x='dataset', y='avg_time_sec', hue='type', ax=ax1)
ax1.set_title('Average Processing Time per Question')
ax1.set_ylabel('Time (seconds)')
ax1.tick_params(axis='x', rotation=45)

sizes = df_plot['n_questions'] / 10  # Scale bubble by question count
sns.scatterplot(data=df_plot, x='dataset', y='avg_time_sec', size='n_questions', hue='type', 
                sizes=(50, 500), ax=ax2)
ax2.set_title('Avg Time (bubble size = # questions)')
ax2.set_ylabel('Time (seconds)')
ax2.tick_params(axis='x', rotation=45)

plt.tight_layout()
plt.savefig('processing_times.png', dpi=300, bbox_inches='tight')  # Saves locally[code_file:1][chart:4]
df_plot.to_csv('processing_stats.csv', index=False)  # CSV output[code_file:1]