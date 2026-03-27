import os
import shutil
from pathlib import Path

# Define the mapping of ranges to source names and counts
sources = [
    ("CompMix_infobox", 300),
    ("CompMix_table", 300),
    ("Monaco_time", 150),
    ("Monaco_non_time", 150),
    ("OTT_QA_dev", 400),
    ("Sportsreason_TANQ", 200)
]

# Paths
complex_qa_folder = Path("Complex_QA")
output_base = Path("ComplexQA")

# Create output base folder if it doesn't exist
output_base.mkdir(exist_ok=True)

current_idx = 0
for source_name, count in sources:
    # Output folder name: sourceCSVName_complex/
    output_folder = output_base / f"{source_name}_complex"
    output_folder.mkdir(exist_ok=True)
    
    print(f"Moving {count} files for {source_name} to {output_folder}")
    
    moved_count = 0
    for i in range(count):
        src_file = complex_qa_folder / f"{current_idx:05d}.json"
        dst_file = output_folder / f"{current_idx:05d}.json"
        
        if src_file.exists():
            shutil.move(str(src_file), str(dst_file))
            moved_count += 1
        else:
            print(f"Warning: File {src_file} not found")
        
        current_idx += 1
    
    print(f"Moved {moved_count}/{count} files for {source_name}")

print("All files moved successfully!")
print(f"Total files processed: {current_idx}")
