#!/usr/bin/env python3
"""
Scan GRASP JSON outputs in three Qwen3 result directories, find JSON files whose
`result` text reports more than N rows, and write one TXT report grouped by model.

Expected model directories:
  - Qwen3-235B-A22B-Thinking-2507-AWQ
  - Qwen3-30B-A3B-Thinking-2507
  - Qwen3-4B-Instruct-2507

The input must be directories, not ZIP files. You can pass either:
  1) one parent directory containing the three model directories, or
  2) the three model directories directly.

Examples:
  python find_large_results.py /path/to/results_parent -o large_results_report.txt

  python find_large_results.py \
    /path/to/Qwen3-235B-A22B-Thinking-2507-AWQ \
    /path/to/Qwen3-30B-A3B-Thinking-2507 \
    /path/to/Qwen3-4B-Instruct-2507 \
    -o large_results_report.txt
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Optional


TARGET_MODELS = (
    "Qwen3-235B-A22B-Thinking-2507-AWQ",
    "Qwen3-30B-A3B-Thinking-2507",
    "Qwen3-4B-Instruct-2507",
)

QA_ROOTS = {"SimpleQA", "ComplexQA"}

ROW_RE = re.compile(
    r"\bGot\s+([0-9][0-9,]*)\s+rows?\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ScanSource:
    """One discovered model result directory."""

    model: str
    path: Path


@dataclass
class ScanResult:
    records: list[dict[str, Any]]
    per_model_dir: Counter[tuple[str, str]]
    per_model: Counter[str]
    per_qa_root: Counter[tuple[str, str]]
    stats_by_model: dict[str, Counter[str]]
    scanned_sources: list[ScanSource]
    missing_models: list[str]
    rejected_inputs: list[Path]


def normalize_model_name(name: str) -> Optional[str]:
    """
    Return one of TARGET_MODELS if `name` looks like that model directory.

    This tolerates copied directories such as:
      Qwen3-235B-A22B-Thinking-2507-AWQ(1)
      Qwen3-235B-A22B-Thinking-2507-AWQ_copy
    """
    for model in TARGET_MODELS:
        if name == model or name.startswith(model + "(") or name.startswith(model + "_"):
            return model
    return None


def get_nested_result(obj: Any) -> Optional[str]:
    """Return the most likely result string from a GRASP JSON object."""
    if not isinstance(obj, dict):
        return None

    output = obj.get("output")
    if isinstance(output, dict) and isinstance(output.get("result"), str):
        return output["result"]

    if isinstance(obj.get("result"), str):
        return obj["result"]

    return None


def parse_row_count(result: Optional[str]) -> Optional[int]:
    """Parse strings such as 'Got 75 rows and 2 columns...' into 75."""
    if not result:
        return None

    match = ROW_RE.search(result)
    if not match:
        return None

    return int(match.group(1).replace(",", ""))


def qa_directory_key(rel_path: str) -> Optional[str]:
    """
    Return a counting key like:
      SimpleQA/NQ_table_test_simple
      ComplexQA/CompMix_table_complex
    """
    parts = PurePosixPath(rel_path).parts

    for i, part in enumerate(parts):
        if part in QA_ROOTS:
            if i + 1 < len(parts):
                return f"{part}/{parts[i + 1]}"
            return part

    return None


def qa_root_from_key(directory_key: str) -> str:
    return directory_key.split("/", 1)[0]


def iter_json_from_directory(root: Path) -> Iterable[tuple[str, bytes]]:
    """
    Yield (relative_posix_path, bytes) for JSON files below SimpleQA/ComplexQA.

    Some extracted archives contain an extra top-level model directory, for example:
      Qwen3-.../Qwen3-.../SimpleQA/...

    Therefore this function searches for SimpleQA and ComplexQA anywhere under
    the model directory, while avoiding duplicate traversal if nested QA folders
    somehow exist.
    """
    seen_qa_roots: set[Path] = set()

    for qa_name in ("SimpleQA", "ComplexQA"):
        for qa_root in root.rglob(qa_name):
            if not qa_root.is_dir() or qa_root in seen_qa_roots:
                continue

            seen_qa_roots.add(qa_root)

            for path in qa_root.rglob("*.json"):
                if path.is_file():
                    yield path.relative_to(root).as_posix(), path.read_bytes()


def discover_sources(inputs: list[Path]) -> tuple[list[ScanSource], list[str], list[Path]]:
    """
    Find model directories from the given inputs.

    If a parent directory is provided, immediate children are checked for target
    model directories. Duplicate model sources are ignored after the first
    discovery to avoid double-counting copied directories.
    """
    discovered: list[ScanSource] = []
    seen_models: set[str] = set()
    rejected_inputs: list[Path] = []

    def add_candidate(path: Path) -> None:
        model = normalize_model_name(path.name)

        if model is None or model in seen_models:
            return

        if path.is_dir():
            discovered.append(ScanSource(model=model, path=path))
            seen_models.add(model)
        else:
            rejected_inputs.append(path)

    for input_path in inputs:
        input_path = input_path.expanduser().resolve()

        if not input_path.exists():
            rejected_inputs.append(input_path)
            continue

        if not input_path.is_dir():
            rejected_inputs.append(input_path)
            continue

        add_candidate(input_path)

        # If this is a parent directory, look one level down for target models.
        if normalize_model_name(input_path.name) is None:
            for child in sorted(input_path.iterdir()):
                add_candidate(child)

    missing = [model for model in TARGET_MODELS if model not in seen_models]
    return discovered, missing, rejected_inputs


def scan_sources(sources: list[ScanSource], threshold: int) -> ScanResult:
    records: list[dict[str, Any]] = []
    per_model_dir: Counter[tuple[str, str]] = Counter()
    per_model: Counter[str] = Counter()
    per_qa_root: Counter[tuple[str, str]] = Counter()
    stats_by_model: dict[str, Counter[str]] = defaultdict(Counter)

    for source in sources:
        for rel_path, raw in iter_json_from_directory(source.path):
            stats = stats_by_model[source.model]
            stats["json_scanned"] += 1

            try:
                obj = json.loads(raw)
                result = get_nested_result(obj)
                row_count = parse_row_count(result)
            except Exception:
                stats["json_read_errors"] += 1
                continue

            if row_count is None:
                stats["json_without_parseable_row_count"] += 1
                continue

            if row_count > threshold:
                directory = qa_directory_key(rel_path) or "<unknown>"
                qa_root = qa_root_from_key(directory)

                records.append(
                    {
                        "model": source.model,
                        "directory": directory,
                        "file": rel_path,
                        "rows": row_count,
                    }
                )

                per_model_dir[(source.model, directory)] += 1
                per_model[source.model] += 1
                per_qa_root[(source.model, qa_root)] += 1

    records.sort(
        key=lambda r: (
            r["model"],
            r["directory"],
            -r["rows"],
            r["file"],
        )
    )

    return ScanResult(
        records=records,
        per_model_dir=per_model_dir,
        per_model=per_model,
        per_qa_root=per_qa_root,
        stats_by_model=dict(stats_by_model),
        scanned_sources=sources,
        missing_models=[],
        rejected_inputs=[],
    )


def write_report(
    output_path: Path,
    result: ScanResult,
    threshold: int,
    inputs: list[Path],
) -> None:
    lines: list[str] = []

    total_scanned = sum(s["json_scanned"] for s in result.stats_by_model.values())
    total_without_rows = sum(
        s["json_without_parseable_row_count"]
        for s in result.stats_by_model.values()
    )
    total_errors = sum(s["json_read_errors"] for s in result.stats_by_model.values())

    lines.append("JSON files with result row count greater than threshold")
    lines.append("=" * 72)
    lines.append("Inputs:")

    for path in inputs:
        lines.append(f"  - {path}")

    lines.append(f"Threshold: > {threshold} rows")
    lines.append("")

    lines.append("Scanned model directories")
    lines.append("-" * 72)

    if result.scanned_sources:
        for source in result.scanned_sources:
            lines.append(f"{source.model}  {source.path}")
    else:
        lines.append("No target model directories were found.")

    lines.append("")

    if result.rejected_inputs:
        lines.append("Ignored non-directory or missing inputs")
        lines.append("-" * 72)

        for path in result.rejected_inputs:
            lines.append(str(path))

        lines.append("")

    if result.missing_models:
        lines.append("Missing target model directories")
        lines.append("-" * 72)

        for model in result.missing_models:
            lines.append(model)

        lines.append("")

    lines.append("Overall summary")
    lines.append("-" * 72)
    lines.append(f"JSON scanned: {total_scanned}")
    lines.append(f"JSON without parseable row count: {total_without_rows}")
    lines.append(f"JSON read/parse errors: {total_errors}")
    lines.append(f"Total matching JSON files: {len(result.records)}")
    lines.append("")

    lines.append("Summary by model")
    lines.append("-" * 72)

    width = max(len(m) for m in TARGET_MODELS)

    for model in TARGET_MODELS:
        stats = result.stats_by_model.get(model, Counter())

        lines.append(
            f"{model:<{width}}  "
            f"matches={result.per_model.get(model, 0):>5}  "
            f"scanned={stats.get('json_scanned', 0):>5}  "
            f"no_row_count={stats.get('json_without_parseable_row_count', 0):>5}  "
            f"errors={stats.get('json_read_errors', 0):>3}"
        )

    lines.append("")

    lines.append("Counts per model and QA root")
    lines.append("-" * 72)

    for model in TARGET_MODELS:
        simple = result.per_qa_root.get((model, "SimpleQA"), 0)
        complex_ = result.per_qa_root.get((model, "ComplexQA"), 0)

        lines.append(
            f"{model:<{width}}  "
            f"SimpleQA={simple:>5}  "
            f"ComplexQA={complex_:>5}  "
            f"Total={simple + complex_:>5}"
        )

    lines.append("")

    lines.append("Counts per model and directory")
    lines.append("-" * 72)

    for model in TARGET_MODELS:
        lines.append(model)

        model_items = [
            (directory, count)
            for (m, directory), count in result.per_model_dir.items()
            if m == model
        ]

        if model_items:
            dir_width = max(len(directory) for directory, _ in model_items)

            for directory, count in sorted(model_items):
                lines.append(f"  {directory:<{dir_width}}  {count}")
        else:
            lines.append("  No matching files found.")

        lines.append("")

    lines.append("Matching files")
    lines.append("-" * 72)

    if result.records:
        for record in result.records:
            lines.append(
                f"{record['model']}  "
                f"{record['rows']:>8} rows  "
                f"{record['directory']}  "
                f"{record['file']}"
            )
    else:
        lines.append("No matching files found.")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Scan three Qwen3 model result directories under SimpleQA and ComplexQA, "
            "then report JSON files whose result has more than N rows."
        )
    )

    parser.add_argument(
        "input_paths",
        nargs="+",
        type=Path,
        help=(
            "Parent directory containing model directories, or the model directories "
            "themselves. Directories only; ZIP files are ignored."
        ),
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("large_results_report.txt"),
        help="Output TXT report path.",
    )

    parser.add_argument(
        "-t",
        "--threshold",
        type=int,
        default=10,
        help="Record files with rows > threshold. Default: 10.",
    )

    args = parser.parse_args()

    sources, missing_models, rejected_inputs = discover_sources(args.input_paths)

    result = scan_sources(sources, args.threshold)
    result.missing_models = missing_models
    result.rejected_inputs = rejected_inputs

    write_report(args.output, result, args.threshold, args.input_paths)

    total_scanned = sum(s["json_scanned"] for s in result.stats_by_model.values())

    print(
        f"Discovered {len(sources)} target model "
        f"director{'y' if len(sources) == 1 else 'ies'}."
    )

    if rejected_inputs:
        print(f"Ignored {len(rejected_inputs)} non-directory or missing input(s).")

    if missing_models:
        print("Missing target directorie(s): " + ", ".join(missing_models))

    print(f"Scanned {total_scanned} JSON files.")
    print(f"Found {len(result.records)} JSON files with result > {args.threshold} rows.")
    print(f"Wrote report to: {args.output}")


if __name__ == "__main__":
    main()