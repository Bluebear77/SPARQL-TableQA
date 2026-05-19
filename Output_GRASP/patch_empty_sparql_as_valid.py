#!/usr/bin/env python3
"""
Patch an existing Qwen3-235B-A22B-Thinking-2507-AWQ output tree so that
`empty_sparql_result` is counted as VALID rather than INVALID.

This version is tailored to the layout produced by your output.py:

MODEL_ROOT/
  all_valid_cases.csv
  all_invalid_cases.csv
  all_valid_empty.csv
  SimpleQA/
    all_valid_cases.csv
    all_invalid_cases.csv
    <dataset>/
      *.json
      extracted_output/
        <dataset>_valid_cases.csv
        <dataset>_invalid_cases.csv
        <dataset>_invalid_summary.md
  ComplexQA/
    ...
  statistics/
    summary.md
    per_folder_breakdown.csv
    error_distribution_total.csv

What --apply does:
  1. For each dataset extracted_output/:
       - remove rows with invalid_label == empty_sparql_result from *_invalid_cases.csv
       - write those rows to extracted_output/<dataset>_valid_empty.csv
       - rewrite *_invalid_summary.md with updated valid/invalid counts
  2. For SimpleQA/ and ComplexQA/:
       - remove empty_sparql_result rows from all_invalid_cases.csv
       - write those rows to all_valid_empty.csv
       - write/update summary.md from child dataset totals
  3. For MODEL_ROOT/:
       - remove empty_sparql_result rows from all_invalid_cases.csv
       - write those rows to all_valid_empty.csv
       - rewrite statistics/summary.md
       - rewrite statistics/per_folder_breakdown.csv
       - rewrite statistics/error_distribution_total.csv
  4. Delete stale accidental files created by older patch attempts:
       - MODEL_ROOT/<model_name>_invalid_summary.csv
       - MODEL_ROOT/<model_name>_invalid_summary.md
  5. Write exactly one report:
       - MODEL_ROOT/patch_summary.md

No patched_* files are generated.

Usage:
  Dry run:
    python patch_empty_sparql_as_valid_real_layout.py Qwen3-235B-A22B-Thinking-2507-AWQ --dry-run

  Apply:
    python patch_empty_sparql_as_valid_real_layout.py Qwen3-235B-A22B-Thinking-2507-AWQ --apply

  Apply with backups:
    python patch_empty_sparql_as_valid_real_layout.py Qwen3-235B-A22B-Thinking-2507-AWQ --apply --backup
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


EMPTY_LABEL = "empty_sparql_result"

ERROR_ORDER = [
    "null_output",
    "no_sparql_generated",
    "empty_sparql_result",
    "sparql_execution_failed (execution)",
    "sparql_execution_failed (preprocessing)",
    "invalid_json",
]

ERROR_ORDER_WITHOUT_EMPTY = [x for x in ERROR_ORDER if x != EMPTY_LABEL]


@dataclass
class DatasetStats:
    group: str
    dataset: str
    dataset_dir: Path
    extracted_dir: Path
    valid_csv: Path
    invalid_csv: Path
    summary_md: Path

    total_json: int = 0
    original_valid: int = 0
    original_invalid: int = 0
    moved_empty: int = 0
    new_valid: int = 0
    new_invalid: int = 0
    invalid_breakdown: Counter = field(default_factory=Counter)

    changed_files: List[Path] = field(default_factory=list)

    @property
    def rel_dataset_path(self) -> str:
        return f"{self.group}/{self.dataset}"


@dataclass
class GroupStats:
    name: str
    path: Path
    datasets: List[DatasetStats]

    total_json: int = 0
    original_valid: int = 0
    original_invalid: int = 0
    moved_empty: int = 0
    new_valid: int = 0
    new_invalid: int = 0
    invalid_breakdown: Counter = field(default_factory=Counter)
    changed_files: List[Path] = field(default_factory=list)


@dataclass
class RootStats:
    root: Path
    groups: List[GroupStats]
    datasets: List[DatasetStats]

    total_json: int = 0
    original_valid: int = 0
    original_invalid: int = 0
    moved_empty: int = 0
    new_valid: int = 0
    new_invalid: int = 0
    invalid_breakdown: Counter = field(default_factory=Counter)
    changed_files: List[Path] = field(default_factory=list)


def pct(n: int, d: int) -> float:
    return (100.0 * n / d) if d else 0.0


def fmt_pct(n: int, d: int, percent_sign: bool = True) -> str:
    s = f"{pct(n, d):.2f}"
    return s + "%" if percent_sign else s


def latex_pct(n: int, d: int) -> str:
    return fmt_pct(n, d, True).replace("%", r"\%")


def read_csv_dicts(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    return fields, rows


def write_csv_dicts(path: Path, fields: Sequence[str], rows: Sequence[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def maybe_backup(path: Path, apply: bool, backup: bool) -> None:
    if apply and backup and path.exists():
        bak = path.with_name(path.name + ".bak")
        if not bak.exists():
            shutil.copy2(path, bak)


def write_text(path: Path, text: str, apply: bool, backup: bool, changed: List[Path]) -> None:
    if not apply:
        return
    maybe_backup(path, apply, backup)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    changed.append(path)


def write_csv(path: Path, fields: Sequence[str], rows: Sequence[Dict[str, str]], apply: bool, backup: bool, changed: List[Path]) -> None:
    if not apply:
        return
    maybe_backup(path, apply, backup)
    write_csv_dicts(path, fields, rows)
    changed.append(path)


def remove_file(path: Path, apply: bool, backup: bool, changed: List[Path]) -> None:
    if not path.exists():
        return
    if not apply:
        return
    maybe_backup(path, apply, backup)
    path.unlink()
    changed.append(path)


def find_label_col(fields: Sequence[str]) -> Optional[str]:
    preferred = ["invalid_label", "error_category", "invalid_reason", "reason", "category", "error_type", "error"]
    lower = {f.lower(): f for f in fields}
    for c in preferred:
        if c in lower:
            return lower[c]
    for f in fields:
        lf = f.lower()
        if "label" in lf or "category" in lf or "reason" in lf or "error" in lf:
            return f
    return None


def row_label(row: Dict[str, str], label_col: Optional[str]) -> str:
    if label_col and row.get(label_col, "").strip():
        return row[label_col].strip()
    for v in row.values():
        if isinstance(v, str) and v.strip() in ERROR_ORDER:
            return v.strip()
    return "unknown"


def is_empty_row(row: Dict[str, str], label_col: Optional[str]) -> bool:
    return row_label(row, label_col) == EMPTY_LABEL


def count_case_jsons(dataset_dir: Path) -> int:
    total = 0
    for p in dataset_dir.glob("*.json"):
        name = p.name.lower()
        if name.endswith(".tmp"):
            continue
        if "summary" in name or "timing" in name or "report" in name:
            continue
        total += 1
    return total


def find_dataset_dirs(root: Path) -> List[Tuple[str, Path, Path]]:
    """
    Return (group_name, dataset_dir, extracted_dir) for all dataset dirs that
    contain extracted_output/*_invalid_cases.csv.
    """
    out = []
    for group in ["SimpleQA", "ComplexQA"]:
        group_dir = root / group
        if not group_dir.is_dir():
            continue
        for dataset_dir in sorted([p for p in group_dir.iterdir() if p.is_dir()]):
            extracted = dataset_dir / "extracted_output"
            if not extracted.is_dir():
                continue
            if list(extracted.glob("*_invalid_cases.csv")):
                out.append((group, dataset_dir, extracted))
    return out


def valid_csv_for(extracted: Path, dataset: str) -> Path:
    preferred = extracted / f"{dataset}_valid_cases.csv"
    if preferred.exists():
        return preferred
    matches = list(extracted.glob("*_valid_cases.csv"))
    return matches[0] if matches else preferred


def invalid_csv_for(extracted: Path, dataset: str) -> Path:
    preferred = extracted / f"{dataset}_invalid_cases.csv"
    if preferred.exists():
        return preferred
    matches = list(extracted.glob("*_invalid_cases.csv"))
    return matches[0] if matches else preferred


def summary_md_for(extracted: Path, dataset: str) -> Path:
    preferred = extracted / f"{dataset}_invalid_summary.md"
    if preferred.exists():
        return preferred
    matches = list(extracted.glob("*_invalid_summary.md"))
    return matches[0] if matches else preferred


def merge_rows(existing_fields: Sequence[str], existing_rows: Sequence[Dict[str, str]], new_fields: Sequence[str], new_rows: Sequence[Dict[str, str]]) -> Tuple[List[str], List[Dict[str, str]]]:
    fields = list(existing_fields)
    for f in new_fields:
        if f not in fields:
            fields.append(f)
    if not fields:
        fields = list(new_fields)

    def key(row: Dict[str, str]) -> str:
        for k in ["file_path", "filename", "file", "json_file", "row_index"]:
            if k in row and row.get(k, "").strip():
                return f"{k}:{row[k].strip()}"
        return json.dumps(row, ensure_ascii=False, sort_keys=True)

    merged = []
    seen = set()
    for r in list(existing_rows) + list(new_rows):
        k = key(r)
        if k not in seen:
            seen.add(k)
            merged.append(r)
    return fields, merged


def split_invalid_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]], List[Dict[str, str]], Counter]:
    fields, rows = read_csv_dicts(path)
    label_col = find_label_col(fields)

    kept = []
    moved = []
    breakdown = Counter()

    for row in rows:
        label = row_label(row, label_col)
        if label == EMPTY_LABEL:
            moved.append(row)
        else:
            kept.append(row)
            breakdown[label] += 1

    return fields, kept, moved, breakdown


def patch_invalid_csv_to_valid_empty(invalid_csv: Path, valid_empty_csv: Path, apply: bool, backup: bool, changed: List[Path]) -> Tuple[int, int, int, Counter]:
    """
    Returns original_invalid_count, new_invalid_count, moved_empty_count, new_breakdown.
    """
    fields, kept, moved, breakdown = split_invalid_csv(invalid_csv)
    original_invalid = len(kept) + len(moved)

    if moved:
        write_csv(invalid_csv, fields, kept, apply, backup, changed)

        if valid_empty_csv.exists():
            existing_fields, existing_rows = read_csv_dicts(valid_empty_csv)
        else:
            existing_fields, existing_rows = [], []
        merged_fields, merged_rows = merge_rows(existing_fields, existing_rows, fields, moved)
        write_csv(valid_empty_csv, merged_fields, merged_rows, apply, backup, changed)

    return original_invalid, len(kept), len(moved), breakdown


def render_dataset_summary_md(s: DatasetStats) -> str:
    lines = []
    lines.append(f"# Invalid case summary for {s.dataset}")
    lines.append("")
    lines.append(f"Total JSON files: {s.total_json}")
    lines.append("")
    lines.append(f"Valid cases: {s.new_valid} ({fmt_pct(s.new_valid, s.total_json)})")
    lines.append(f"Invalid cases: {s.new_invalid} ({fmt_pct(s.new_invalid, s.total_json)})")
    lines.append("")
    lines.append("## Valid empty SPARQL results")
    lines.append("")
    lines.append(f"- {EMPTY_LABEL}: {s.moved_empty} ({fmt_pct(s.moved_empty, s.total_json)})")
    lines.append("")
    lines.append("## Invalid case breakdown")
    lines.append("")
    for cat in ERROR_ORDER_WITHOUT_EMPTY:
        n = int(s.invalid_breakdown.get(cat, 0))
        lines.append(f"- {cat}: {n} ({fmt_pct(n, s.total_json)})")
    for cat in sorted(s.invalid_breakdown):
        if cat not in ERROR_ORDER and cat != EMPTY_LABEL:
            n = int(s.invalid_breakdown.get(cat, 0))
            lines.append(f"- {cat}: {n} ({fmt_pct(n, s.total_json)})")
    lines.append("")
    return "\n".join(lines)



def dataset_valid_empty_csv_for(extracted: Path, dataset: str) -> Path:
    """
    Dataset-level valid-empty file name.

    Example:
      extracted_output/CompMix_table_simple_qa_valid_empty.csv

    Older script versions wrote:
      extracted_output/all_valid_empty.csv

    patch_dataset() migrates that old file into the dataset-prefixed file and
    removes the old file in --apply mode.
    """
    return extracted / f"{dataset}_valid_empty.csv"


def migrate_old_dataset_valid_empty(
    old_csv: Path,
    new_csv: Path,
    apply: bool,
    backup: bool,
    changed: List[Path],
) -> None:
    """
    If an older run created extracted_output/all_valid_empty.csv, merge it into
    extracted_output/<dataset>_valid_empty.csv and remove the old file.

    This is safe to call before/after adding newly moved rows because
    patch_invalid_csv_to_valid_empty() deduplicates rows.
    """
    if old_csv == new_csv or not old_csv.exists():
        return

    old_fields, old_rows = read_csv_dicts(old_csv)

    if new_csv.exists():
        new_fields, new_rows = read_csv_dicts(new_csv)
    else:
        new_fields, new_rows = [], []

    merged_fields, merged_rows = merge_rows(new_fields, new_rows, old_fields, old_rows)

    if apply:
        maybe_backup(old_csv, apply=True, backup=backup)
        if new_csv.exists():
            maybe_backup(new_csv, apply=True, backup=backup)
        write_csv(new_csv, merged_fields, merged_rows, apply=True, backup=False, changed=changed)
        old_csv.unlink()
        changed.append(old_csv)


def patch_dataset(group: str, dataset_dir: Path, extracted: Path, apply: bool, backup: bool) -> DatasetStats:
    dataset = dataset_dir.name
    valid_csv = valid_csv_for(extracted, dataset)
    invalid_csv = invalid_csv_for(extracted, dataset)
    summary_md = summary_md_for(extracted, dataset)

    stats = DatasetStats(
        group=group,
        dataset=dataset,
        dataset_dir=dataset_dir,
        extracted_dir=extracted,
        valid_csv=valid_csv,
        invalid_csv=invalid_csv,
        summary_md=summary_md,
    )

    if valid_csv.exists():
        _, valid_rows = read_csv_dicts(valid_csv)
        stats.original_valid = len(valid_rows)

    if not invalid_csv.exists():
        raise RuntimeError(f"Missing invalid cases CSV: {invalid_csv}")

    valid_empty_csv = dataset_valid_empty_csv_for(extracted, dataset)
    old_valid_empty_csv = extracted / "all_valid_empty.csv"
    migrate_old_dataset_valid_empty(old_valid_empty_csv, valid_empty_csv, apply, backup, stats.changed_files)
    orig_inv, new_inv, moved, breakdown = patch_invalid_csv_to_valid_empty(
        invalid_csv=invalid_csv,
        valid_empty_csv=valid_empty_csv,
        apply=apply,
        backup=backup,
        changed=stats.changed_files,
    )

    stats.original_invalid = orig_inv
    stats.moved_empty = moved
    stats.new_valid = stats.original_valid + stats.moved_empty
    stats.new_invalid = new_inv
    stats.invalid_breakdown = breakdown
    stats.total_json = count_case_jsons(dataset_dir)
    if stats.total_json == 0:
        stats.total_json = stats.original_valid + stats.original_invalid

    write_text(summary_md, render_dataset_summary_md(stats), apply, backup, stats.changed_files)

    return stats


def aggregate_group(group_name: str, group_path: Path, datasets: List[DatasetStats]) -> GroupStats:
    g = GroupStats(name=group_name, path=group_path, datasets=datasets)
    g.total_json = sum(d.total_json for d in datasets)
    g.original_valid = sum(d.original_valid for d in datasets)
    g.original_invalid = sum(d.original_invalid for d in datasets)
    g.moved_empty = sum(d.moved_empty for d in datasets)
    g.new_valid = sum(d.new_valid for d in datasets)
    g.new_invalid = sum(d.new_invalid for d in datasets)
    for d in datasets:
        g.invalid_breakdown.update(d.invalid_breakdown)
    return g


def aggregate_root(root: Path, groups: List[GroupStats], datasets: List[DatasetStats]) -> RootStats:
    r = RootStats(root=root, groups=groups, datasets=datasets)
    r.total_json = sum(g.total_json for g in groups)
    r.original_valid = sum(g.original_valid for g in groups)
    r.original_invalid = sum(g.original_invalid for g in groups)
    r.moved_empty = sum(g.moved_empty for g in groups)
    r.new_valid = sum(g.new_valid for g in groups)
    r.new_invalid = sum(g.new_invalid for g in groups)
    for g in groups:
        r.invalid_breakdown.update(g.invalid_breakdown)
    return r


def patch_group_case_csvs(group: GroupStats, apply: bool, backup: bool) -> None:
    invalid_csv = group.path / "all_invalid_cases.csv"
    valid_empty_csv = group.path / "all_valid_empty.csv"
    if invalid_csv.exists():
        patch_invalid_csv_to_valid_empty(invalid_csv, valid_empty_csv, apply, backup, group.changed_files)


def patch_root_case_csvs(root_stats: RootStats, apply: bool, backup: bool) -> None:
    invalid_csv = root_stats.root / "all_invalid_cases.csv"
    valid_empty_csv = root_stats.root / "all_valid_empty.csv"
    if invalid_csv.exists():
        patch_invalid_csv_to_valid_empty(invalid_csv, valid_empty_csv, apply, backup, root_stats.changed_files)


def render_group_summary_md(g: GroupStats) -> str:
    lines = []
    lines.append(f"# {g.name} SPARQL QA Statistics")
    lines.append("")
    lines.append("## Overall valid vs invalid")
    lines.append("")
    lines.append("| Metric | Count | Percentage |")
    lines.append("|---|---:|---:|")
    lines.append(f"| Valid | {g.new_valid} | {fmt_pct(g.new_valid, g.total_json)} |")
    lines.append(f"| Invalid | {g.new_invalid} | {fmt_pct(g.new_invalid, g.total_json)} |")
    lines.append(f"| Valid empty SPARQL results moved from invalid | {g.moved_empty} | {fmt_pct(g.moved_empty, g.total_json)} |")
    lines.append("")
    lines.append("## Error distribution after patch")
    lines.append("")
    lines.append("| Error type | Count | % of invalid |")
    lines.append("|---|---:|---:|")
    for cat in ERROR_ORDER_WITHOUT_EMPTY:
        n = int(g.invalid_breakdown.get(cat, 0))
        lines.append(f"| {cat} | {n} | {fmt_pct(n, g.new_invalid)} |")
    lines.append("")
    lines.append("## Per-folder summary")
    lines.append("")
    lines.append("| Folder | Total | Valid | Valid % | Invalid | Invalid % | Moved empty |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for d in sorted(g.datasets, key=lambda x: x.dataset):
        lines.append(
            f"| {d.dataset} | {d.total_json} | {d.new_valid} | {fmt_pct(d.new_valid, d.total_json)} | "
            f"{d.new_invalid} | {fmt_pct(d.new_invalid, d.total_json)} | {d.moved_empty} |"
        )
    lines.append(f"| **Total** | {g.total_json} | {g.new_valid} | {fmt_pct(g.new_valid, g.total_json)} | {g.new_invalid} | {fmt_pct(g.new_invalid, g.total_json)} | {g.moved_empty} |")
    lines.append("")
    return "\n".join(lines)


def write_group_summaries(groups: List[GroupStats], apply: bool, backup: bool) -> None:
    for g in groups:
        write_text(g.path / "summary.md", render_group_summary_md(g), apply, backup, g.changed_files)


def write_statistics(root_stats: RootStats, apply: bool, backup: bool) -> None:
    statistics_dir = root_stats.root / "statistics"
    changed = root_stats.changed_files

    # per_folder_breakdown.csv
    per_fields = ["folder", "total", "valid", "valid_pct", "invalid", "invalid_pct", "valid_empty_sparql_result"]
    per_rows = []
    for d in sorted(root_stats.datasets, key=lambda x: x.dataset):
        per_rows.append({
            "folder": d.dataset,
            "total": str(d.total_json),
            "valid": str(d.new_valid),
            "valid_pct": fmt_pct(d.new_valid, d.total_json, percent_sign=False),
            "invalid": str(d.new_invalid),
            "invalid_pct": fmt_pct(d.new_invalid, d.total_json, percent_sign=False),
            "valid_empty_sparql_result": str(d.moved_empty),
        })
    write_csv(statistics_dir / "per_folder_breakdown.csv", per_fields, per_rows, apply, backup, changed)

    # error_distribution_total.csv, excluding empty_sparql_result
    err_fields = ["error_type", "count", "pct_of_invalid"]
    err_rows = []
    for cat in ERROR_ORDER_WITHOUT_EMPTY:
        n = int(root_stats.invalid_breakdown.get(cat, 0))
        err_rows.append({"error_type": cat, "count": str(n), "pct_of_invalid": fmt_pct(n, root_stats.new_invalid, percent_sign=False)})
    write_csv(statistics_dir / "error_distribution_total.csv", err_fields, err_rows, apply, backup, changed)

    # summary.md
    write_text(statistics_dir / "summary.md", render_statistics_summary_md(root_stats), apply, backup, changed)


def render_statistics_summary_md(r: RootStats) -> str:
    lines = []
    lines.append("# Global SPARQL QA Statistics")
    lines.append("")
    lines.append("## Overall valid vs invalid")
    lines.append("")
    lines.append("| Metric | Count | Percentage |")
    lines.append("|---|---:|---:|")
    lines.append(f"| Valid | {r.new_valid} | {fmt_pct(r.new_valid, r.total_json)} |")
    lines.append(f"| Invalid | {r.new_invalid} | {fmt_pct(r.new_invalid, r.total_json)} |")
    lines.append(f"| Valid empty SPARQL results moved from invalid | {r.moved_empty} | {fmt_pct(r.moved_empty, r.total_json)} |")
    lines.append("")
    lines.append("## Error distribution after patch")
    lines.append("")
    lines.append("| Error type | Count | % of invalid |")
    lines.append("|---|---:|---:|")
    for cat in ERROR_ORDER_WITHOUT_EMPTY:
        n = int(r.invalid_breakdown.get(cat, 0))
        lines.append(f"| {cat} | {n} | {fmt_pct(n, r.new_invalid)} |")
    for cat in sorted(r.invalid_breakdown):
        if cat not in ERROR_ORDER and cat != EMPTY_LABEL:
            n = int(r.invalid_breakdown.get(cat, 0))
            lines.append(f"| {cat} | {n} | {fmt_pct(n, r.new_invalid)} |")
    lines.append("")
    lines.append("## Per-folder summary")
    lines.append("")
    lines.append("| Folder | Total | Valid | Valid % | Invalid | Invalid % | Moved empty |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for d in sorted(r.datasets, key=lambda x: x.dataset):
        lines.append(
            f"| {d.dataset} | {d.total_json} | {d.new_valid} | {fmt_pct(d.new_valid, d.total_json)} | "
            f"{d.new_invalid} | {fmt_pct(d.new_invalid, d.total_json)} | {d.moved_empty} |"
        )
    lines.append(f"| **Total** | {r.total_json} | {r.new_valid} | {fmt_pct(r.new_valid, r.total_json)} | {r.new_invalid} | {fmt_pct(r.new_invalid, r.total_json)} | {r.moved_empty} |")
    lines.append("")
    return "\n".join(lines)


def delete_stale_generated_files(root: Path, apply: bool, backup: bool, changed: List[Path]) -> None:
    # These are files the earlier buggy script could create at root. They are not part
    # of your original output.py statistics layout.
    model_name = root.name
    for p in [
        root / f"{model_name}_invalid_summary.csv",
        root / f"{model_name}_invalid_summary.md",
        root / "patched_validity_summary.csv",
        root / "patched_validity_summary.md",
        root / "patched_235B_latex_rows.md",
    ]:
        remove_file(p, apply, backup, changed)


def render_patch_summary(r: RootStats, apply: bool) -> str:
    lines = []
    lines.append("# Patch summary")
    lines.append("")
    lines.append(f"Mode: {'APPLY' if apply else 'DRY RUN'}")
    lines.append("")
    lines.append("## Root totals")
    lines.append("")
    lines.append("| Metric | Before | After |")
    lines.append("|---|---:|---:|")
    lines.append(f"| Valid | {r.original_valid} | {r.new_valid} |")
    lines.append(f"| Invalid | {r.original_invalid} | {r.new_invalid} |")
    lines.append(f"| Total | {r.total_json} | {r.total_json} |")
    lines.append(f"| empty_sparql_result moved to valid-empty | 0 | {r.moved_empty} |")
    lines.append("")
    lines.append("## Dataset changes")
    lines.append("")
    lines.append("| Group | Dataset | Total | Original valid | Original invalid | Moved empty | New valid | New invalid |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for d in sorted(r.datasets, key=lambda x: (x.group, x.dataset)):
        lines.append(
            f"| {d.group} | {d.dataset} | {d.total_json} | {d.original_valid} | {d.original_invalid} | "
            f"{d.moved_empty} | {d.new_valid} | {d.new_invalid} |"
        )
    lines.append("")
    lines.append("## Files overwritten/deleted")
    lines.append("")
    all_changed = []
    all_changed.extend(r.changed_files)
    for g in r.groups:
        all_changed.extend(g.changed_files)
    for d in r.datasets:
        all_changed.extend(d.changed_files)
    if all_changed:
        for p in sorted(set(all_changed)):
            try:
                rel = p.relative_to(r.root)
            except Exception:
                rel = p
            lines.append(f"- `{rel}`")
    else:
        lines.append("- Dry run: no files modified.")
    lines.append("")
    lines.append("## Updated 235B values for LaTeX table")
    lines.append("")
    lines.append("```latex")
    for group_name in ["SimpleQA", "ComplexQA"]:
        group = next((g for g in r.groups if g.name == group_name), None)
        if not group:
            continue
        for d in sorted(group.datasets, key=lambda x: x.dataset):
            lines.append(f"% {group_name} / {d.dataset}")
            lines.append(f"& {d.new_valid} ({latex_pct(d.new_valid, d.total_json)}) & {d.new_invalid} ({latex_pct(d.new_invalid, d.total_json)}) \\\\")
        lines.append(f"% {group_name} Total")
        lines.append(f"& {group.new_valid} ({latex_pct(group.new_valid, group.total_json)}) & {group.new_invalid} ({latex_pct(group.new_invalid, group.total_json)}) \\\\")
    lines.append("% Overall Total")
    lines.append(f"& {r.new_valid} ({latex_pct(r.new_valid, r.total_json)}) & {r.new_invalid} ({latex_pct(r.new_invalid, r.total_json)}) \\\\")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model_root", type=Path)
    m = parser.add_mutually_exclusive_group()
    m.add_argument("--dry-run", action="store_true")
    m.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", action="store_true")
    args = parser.parse_args()

    root = args.model_root.resolve()
    if not root.is_dir():
        raise SystemExit(f"Not a directory: {root}")

    apply = bool(args.apply)
    if not args.apply and not args.dry_run:
        print("[INFO] Neither --apply nor --dry-run was passed; defaulting to dry run.")
        apply = False

    dataset_specs = find_dataset_dirs(root)
    if not dataset_specs:
        raise SystemExit(f"No dataset extracted_output/*_invalid_cases.csv files found under {root}")

    datasets: List[DatasetStats] = []
    for group, dataset_dir, extracted in dataset_specs:
        ds = patch_dataset(group, dataset_dir, extracted, apply=apply, backup=args.backup)
        datasets.append(ds)

    groups: List[GroupStats] = []
    for group_name in ["SimpleQA", "ComplexQA"]:
        group_datasets = [d for d in datasets if d.group == group_name]
        if not group_datasets:
            continue
        group = aggregate_group(group_name, root / group_name, group_datasets)
        patch_group_case_csvs(group, apply=apply, backup=args.backup)
        groups.append(group)

    root_stats = aggregate_root(root, groups, datasets)
    patch_root_case_csvs(root_stats, apply=apply, backup=args.backup)
    write_group_summaries(groups, apply=apply, backup=args.backup)
    write_statistics(root_stats, apply=apply, backup=args.backup)
    delete_stale_generated_files(root, apply=apply, backup=args.backup, changed=root_stats.changed_files)

    summary_text = render_patch_summary(root_stats, apply=apply)
    if apply:
        summary_path = root / "patch_summary.md"
        summary_path.write_text(summary_text, encoding="utf-8")
        root_stats.changed_files.append(summary_path)
    else:
        print(f"[DRY RUN] Would write: {root / 'patch_summary.md'}")

    print("")
    print("Patch summary")
    print("-------------")
    print(f"Mode                         : {'APPLY' if apply else 'DRY RUN'}")
    print(f"Model root                   : {root}")
    print(f"Datasets found               : {len(datasets)}")
    print(f"Total JSON files             : {root_stats.total_json}")
    print(f"Original valid / invalid     : {root_stats.original_valid} / {root_stats.original_invalid}")
    print(f"Moved empty_sparql_result    : {root_stats.moved_empty}")
    print(f"New valid / invalid          : {root_stats.new_valid} / {root_stats.new_invalid}")
    print(f"New valid % / invalid %      : {fmt_pct(root_stats.new_valid, root_stats.total_json)} / {fmt_pct(root_stats.new_invalid, root_stats.total_json)}")
    print("")
    for d in sorted(datasets, key=lambda x: (x.group, x.dataset)):
        print(
            f"{d.group}/{d.dataset}: moved={d.moved_empty}, "
            f"valid={d.new_valid}/{d.total_json} ({fmt_pct(d.new_valid, d.total_json)}), "
            f"invalid={d.new_invalid}/{d.total_json} ({fmt_pct(d.new_invalid, d.total_json)})"
        )

    if apply:
        print(f"\nWrote report: {root / 'patch_summary.md'}")
    else:
        print("\nNo files modified in dry-run mode.")


if __name__ == "__main__":
    main()
