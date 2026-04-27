#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, Tuple

INVALID_COLUMNS = [
    "file_path",
    "invalid_label",
    "question",
    "gold_answer",
    "sparql",
    "result",
    "answer",
    "explanation",
    "formatted",
]


def normalize_sparql(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\\n", "\n")
    match = re.search(r"(?is)\bSELECT\b.*", text)
    return match.group(0).strip() if match else ""


def extract_table(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\\n", "\n")
    lines = text.splitlines()
    table_lines = []
    started = False
    for line in lines:
        if line.strip().startswith("|"):
            started = True
            table_lines.append(line)
        elif started:
            break
    return "\n".join(table_lines).strip()


def classify_case(output_obj: Any, sparql_text: str, result_raw: str) -> Tuple[str, str]:
    if output_obj is None:
        return "null_output", ""
    if isinstance(output_obj, dict) and output_obj.get("sparql") is None and output_obj.get("result") is None:
        return "no_sparql_generated", ""
    if not sparql_text:
        return "no_sparql_generated", ""
    if isinstance(result_raw, str):
        if "SPARQL execution failed" in result_raw:
            return "sparql_execution_failed (execution)", ""
        if re.search(r"parse error", result_raw, re.IGNORECASE):
            return "sparql_execution_failed (preprocessing)", ""
        if re.search(r"Got no rows and \d+ columns?", result_raw):
            return "empty_sparql_result", ""
    table = extract_table(result_raw)
    if not table:
        return "empty_sparql_result", ""
    return "", table


def main():
    root_dir = Path.cwd()
    rows = []
    for json_path in sorted(root_dir.rglob("*.json")):
        if "extracted_output" in json_path.parts:
            continue
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            rows.append({
                "file_path": str(json_path.relative_to(root_dir)),
                "invalid_label": "invalid_json",
                "question": "",
                "gold_answer": "",
                "sparql": "",
                "result": "",
                "answer": "",
                "explanation": "",
                "formatted": "",
            })
            continue
        question = data.get("question", "")
        gold_answer = data.get("reference_answer", "")
        output_obj = data.get("output", None)
        if isinstance(output_obj, dict):
            sparql = normalize_sparql(output_obj.get("sparql", ""))
            result_raw = output_obj.get("result", "")
            answer = output_obj.get("answer", "")
            explanation = output_obj.get("explanation", "")
            formatted = output_obj.get("formatted", "")
        else:
            sparql = result_raw = answer = explanation = formatted = ""
        invalid_label, _ = classify_case(output_obj, sparql, result_raw)
        if invalid_label:
            rows.append({
                "file_path": str(json_path.relative_to(root_dir)),
                "invalid_label": invalid_label,
                "question": question,
                "gold_answer": gold_answer,
                "sparql": sparql,
                "result": result_raw,
                "answer": answer,
                "explanation": explanation,
                "formatted": formatted,
            })
    output_csv = root_dir / "all_invalid_cases.csv"
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=INVALID_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} invalid rows to {output_csv}")


if __name__ == "__main__":
    main()