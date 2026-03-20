#!/usr/bin/env python3
"""Unzip CompMix train/dev/test archives and split instances by answer_src.

This script expects the CompMix zip files to be available locally. It will:
1. Unzip train/dev/test archives
2. Read all JSONL instances from the three splits
3. Group instances by the `answer_src` field
4. Write one JSONL file per non-empty answer source category:
   - CompMix_table.jsonl
   - CompMix_text.jsonl
   - CompMix_infobox.jsonl
   - CompMix_kb.jsonl

Records with a missing or empty `answer_src` are counted and reported, but not
included in the four requested output files.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import DefaultDict


def unzip_archives(zip_paths: list[Path], extract_dir: Path) -> list[Path]:
    extract_dir.mkdir(parents=True, exist_ok=True)
    extracted_jsonl_files: list[Path] = []

    for zip_path in zip_paths:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)
            for name in zf.namelist():
                path = extract_dir / name
                if path.suffix == ".jsonl" and not path.name.startswith("._"):
                    extracted_jsonl_files.append(path)

    # Deduplicate while preserving order
    unique_files: list[Path] = []
    seen: set[Path] = set()
    for path in extracted_jsonl_files:
        if path not in seen:
            seen.add(path)
            unique_files.append(path)
    return unique_files


def split_by_answer_src(jsonl_paths: list[Path], output_dir: Path) -> Counter:
    output_dir.mkdir(parents=True, exist_ok=True)

    grouped: DefaultDict[str, list[dict]] = defaultdict(list)
    counts: Counter = Counter()

    for jsonl_path in jsonl_paths:
        with jsonl_path.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON in {jsonl_path} line {line_num}: {exc}") from exc

                answer_src = (obj.get("answer_src") or "").strip()
                counts[answer_src] += 1
                if answer_src:
                    grouped[answer_src].append(obj)

    for answer_src, records in grouped.items():
        out_path = output_dir / f"CompMix_{answer_src}.jsonl"
        with out_path.open("w", encoding="utf-8") as out_f:
            for record in records:
                out_f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Split CompMix instances by answer_src")
    parser.add_argument(
        "zip_files",
        nargs="*",
        type=Path,
        default=[Path("train_set.zip"), Path("dev_set.zip"), Path("test_set.zip")],
        help="Paths to CompMix zip archives (default: train_set.zip dev_set.zip test_set.zip)",
    )
    parser.add_argument(
        "--extract-dir",
        type=Path,
        default=Path("compmix_extracted"),
        help="Directory to extract zip archives into",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("compmix_by_answer_src"),
        help="Directory where grouped output files will be written",
    )
    args = parser.parse_args()

    missing_zips = [str(p) for p in args.zip_files if not p.exists()]
    if missing_zips:
        raise FileNotFoundError(f"Missing zip files: {', '.join(missing_zips)}")

    jsonl_paths = unzip_archives(args.zip_files, args.extract_dir)
    if not jsonl_paths:
        raise FileNotFoundError("No JSONL files were found after extraction.")

    counts = split_by_answer_src(jsonl_paths, args.output_dir)

    print("Finished splitting CompMix by answer_src.")
    print("Counts by answer_src:")
    for key in sorted(counts.keys(), key=lambda x: (x == "", x)):
        label = key if key else "<empty>"
        print(f"  {label}: {counts[key]}")


if __name__ == "__main__":
    main()
