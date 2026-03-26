#!/usr/bin/env python3
"""
This script extracts a ZIP archive, finds every `.jsonl` file inside it, reads all
records line by line, and splits the records into two consolidated output files
based on the value of the `qid` field.

Detailed behavior:
1. Input handling:
   - The script takes a required positional argument: `zip_path`, which is the path
     to the input ZIP file.
   - It also takes an optional argument: `--output_dir`, which controls where the
     extracted contents and final output files will be written.
   - If `--output_dir` is not provided, it defaults to `split_output`.

2. ZIP extraction:
   - The ZIP file is fully extracted into a subdirectory called `extracted`
     inside the chosen output directory.
   - This preserves the original archive contents so the script can search through
     all extracted files.

3. JSONL discovery:
   - After extraction, the script recursively searches the extracted directory for
     all files ending in `.jsonl`.
   - This means it works even if the ZIP contains nested folders.

4. Record-by-record processing:
   - Each JSONL file is opened and read one line at a time.
   - Empty lines are skipped.
   - Every non-empty line is parsed as a JSON object.
   - If a line is not valid JSON, the script raises an error showing which file and
     which line number caused the problem.

5. Filtering logic:
   - For each parsed record, the script looks at the `qid` field.
   - If `qid` contains the substring `__wikitables_composition__`, that record is
     written to `wikitables_composition.jsonl`.
   - If `qid` contains the substring `__wikitables_simple__`, that record is
     written to `wikitables_simple.jsonl`.
   - Records with other `qid` values are ignored.

6. Output files:
   - The script creates two merged JSONL files in the output directory:
       * `wikitables_composition.jsonl`
       * `wikitables_simple.jsonl`
   - Each output line is written back as valid JSON with UTF-8 encoding.
   - The original record structure is preserved.

7. Final reporting:
   - After processing all files, the script prints how many records were written
     to each of the two output files.

Example usage:
    python extract_and_split_wikitables.py /path/to/qampari.zip --output_dir /path/to/output

Typical output structure:
    /path/to/output/
        extracted/
            ... all unzipped contents ...
        wikitables_composition.jsonl
        wikitables_simple.jsonl
"""

import argparse
import json
import zipfile
from pathlib import Path


def extract_and_split(zip_path: str, output_dir: str) -> None:
    output_dir = Path(output_dir)
    extract_dir = output_dir / "extracted"

    output_dir.mkdir(parents=True, exist_ok=True)
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    jsonl_files = sorted(extract_dir.rglob("*.jsonl"))

    composition_path = output_dir / "wikitables_composition.jsonl"
    simple_path = output_dir / "wikitables_simple.jsonl"

    composition_count = 0
    simple_count = 0

    with composition_path.open("w", encoding="utf-8") as composition_out, \
         simple_path.open("w", encoding="utf-8") as simple_out:

        for jsonl_file in jsonl_files:
            with jsonl_file.open("r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as e:
                        raise ValueError(
                            f"Invalid JSON in {jsonl_file} at line {line_num}: {e}"
                        ) from e

                    qid = str(record.get("qid", ""))

                    if "__wikitables_composition__" in qid:
                        composition_out.write(json.dumps(record, ensure_ascii=False) + "\n")
                        composition_count += 1
                    elif "__wikitables_simple__" in qid:
                        simple_out.write(json.dumps(record, ensure_ascii=False) + "\n")
                        simple_count += 1

    print(f"Wrote {composition_count} records to {composition_path}")
    print(f"Wrote {simple_count} records to {simple_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Extract a zip file and split all JSONL records into "
            "wikitables_composition and wikitables_simple outputs based on qid."
        )
    )
    parser.add_argument("zip_path", help="Path to the input zip file")
    parser.add_argument(
        "--output_dir",
        default="split_output",
        help="Directory where extracted files and output JSONL files will be written",
    )
    args = parser.parse_args()

    extract_and_split(args.zip_path, args.output_dir)
