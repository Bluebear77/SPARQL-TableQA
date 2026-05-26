# pip install pandas openpyxl

"""
split.py

Purpose
-------
Convert an input CSV annotation file into multiple balanced Excel annotation files.

Input CSV columns expected:
    question,gold_answer,KG answer,taxonomy_label,confidence,source

Output:
    annotation_outputs/annotation_group_1.xlsx
    annotation_outputs/annotation_group_2.xlsx
    annotation_outputs/annotation_group_3.xlsx

Each output file:
    - removes the confidence column
    - keeps a stable case_id for merging later
    - adds dropdown column: label_correctness
    - adds dropdown column: wikidata_cause
    - adds free-text column: note
    - uses alternating row colors for better readability

Important
---------
CSV files cannot store dropdown menus.
Therefore, this script outputs .xlsx files instead of .csv files.
"""

import pandas as pd
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


# ---------------------------------------------------------------------
# Dropdown options
# ---------------------------------------------------------------------

TAXONOMY_LABEL_CORRECT_OPTIONS = [
    "Correct",
    "Incorrect",
    "Unsure"
]

WIKIDATA_CAUSE_OPTIONS = [
    "Missing edge",
    "Missing node",
    "Missing property/qualifier",
    "Not applicable",
    "Unsure"
]


# ---------------------------------------------------------------------
# Helper 1: clean column names
# ---------------------------------------------------------------------

def clean_column_names(df):
    """
    Clean CSV column names.

    Example:
        ' taxonomy_label ' -> 'taxonomy_label'
        '\\ufeffquestion' -> 'question'
    """

    df.columns = (
        df.columns
        .astype(str)
        .str.replace("\ufeff", "", regex=False)
        .str.strip()
    )

    return df


# ---------------------------------------------------------------------
# Helper 2: balanced splitting
# ---------------------------------------------------------------------

def split_balanced(df, n_groups=3, stratify_cols=None):
    """
    Split a dataframe into n balanced groups.

    Parameters
    ----------
    df : pandas.DataFrame
        Full dataframe to split.

    n_groups : int
        Number of output groups.

    stratify_cols : list[str] or None
        Columns used for approximate stratified splitting.

    Returns
    -------
    list[pandas.DataFrame]
        A list of n_groups dataframes.
    """

    df = df.reset_index(drop=True).copy()

    groups = [[] for _ in range(n_groups)]

    if stratify_cols:
        for col in stratify_cols:
            if col not in df.columns:
                raise ValueError(
                    f"Stratification column not found: {col}\n"
                    f"Available columns: {list(df.columns)}"
                )

        grouped = df.groupby(stratify_cols, sort=False, dropna=False)

        pointer = 0

        for _, sub_df in grouped:
            sub_df = sub_df.reset_index(drop=True)

            for _, row in sub_df.iterrows():
                group_id = pointer % n_groups
                groups[group_id].append(row)
                pointer += 1

    else:
        for i, (_, row) in enumerate(df.iterrows()):
            group_id = i % n_groups
            groups[group_id].append(row)

    result = []

    for group_rows in groups:
        if len(group_rows) == 0:
            result.append(pd.DataFrame(columns=df.columns))
        else:
            result.append(
                pd.DataFrame(group_rows, columns=df.columns).reset_index(drop=True)
            )

    return result


# ---------------------------------------------------------------------
# Helper 3: robust Excel header lookup
# ---------------------------------------------------------------------

def find_column_index(header, target_name):
    """
    Find a column index in an Excel header row.

    Returns 1-based Excel column index.
    """

    cleaned_header = [
        str(h).replace("\ufeff", "").strip() if h is not None else ""
        for h in header
    ]

    if target_name not in cleaned_header:
        raise ValueError(
            f"Column '{target_name}' not found.\n"
            f"Available columns are:\n{cleaned_header}"
        )

    return cleaned_header.index(target_name) + 1


# ---------------------------------------------------------------------
# Helper 4: add dropdown menus and formatting to Excel
# ---------------------------------------------------------------------

def add_dropdowns_and_formatting(xlsx_path):
    """
    Add dropdown menus and formatting to one Excel annotation file.

    Formatting includes:
        - blue header row
        - alternating row colors for readability
        - yellow annotation columns
        - borders
        - wrapped text
        - frozen header
        - filters
    """

    wb = load_workbook(xlsx_path)
    ws = wb.active

    header = [cell.value for cell in ws[1]]
    max_row = ws.max_row
    max_col = ws.max_column

    taxonomy_col = find_column_index(header, "label_correctness")
    cause_col = find_column_index(header, "wikidata_cause")

    taxonomy_col_letter = get_column_letter(taxonomy_col)
    cause_col_letter = get_column_letter(cause_col)

    # -----------------------------------------------------------------
    # Dropdown validation
    # -----------------------------------------------------------------

    dv_taxonomy = DataValidation(
        type="list",
        formula1=f'"{",".join(TAXONOMY_LABEL_CORRECT_OPTIONS)}"',
        allow_blank=True
    )

    dv_cause = DataValidation(
        type="list",
        formula1=f'"{",".join(WIKIDATA_CAUSE_OPTIONS)}"',
        allow_blank=True
    )

    ws.add_data_validation(dv_taxonomy)
    ws.add_data_validation(dv_cause)

    if max_row >= 2:
        dv_taxonomy.add(f"{taxonomy_col_letter}2:{taxonomy_col_letter}{max_row}")
        dv_cause.add(f"{cause_col_letter}2:{cause_col_letter}{max_row}")

    # -----------------------------------------------------------------
    # Formatting colors
    # -----------------------------------------------------------------

    header_fill = PatternFill("solid", fgColor="1F4E79")       # dark blue
    header_font = Font(bold=True, color="FFFFFF")              # white text

    row_fill_odd = PatternFill("solid", fgColor="FFFFFF")      # white
    row_fill_even = PatternFill("solid", fgColor="EAF3F8")     # very light blue

    annotation_fill_odd = PatternFill("solid", fgColor="FFF2CC")   # light yellow
    annotation_fill_even = PatternFill("solid", fgColor="FCE4B2")  # slightly deeper yellow

    thin_side = Side(style="thin", color="D9D9D9")

    border = Border(
        top=thin_side,
        left=thin_side,
        right=thin_side,
        bottom=thin_side
    )

    # -----------------------------------------------------------------
    # Header formatting
    # -----------------------------------------------------------------

    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True
        )
        cell.border = border

    ws.row_dimensions[1].height = 30

    # Clean header for column lookup.
    cleaned_header = [
        str(h).replace("\ufeff", "").strip() if h is not None else ""
        for h in header
    ]

    annotation_col_names = [
        "label_correctness",
        "wikidata_cause",
        "note"
    ]

    annotation_col_indices = []

    for col_name in annotation_col_names:
        if col_name in cleaned_header:
            annotation_col_indices.append(cleaned_header.index(col_name) + 1)

    # -----------------------------------------------------------------
    # Body formatting with alternating row colors
    # -----------------------------------------------------------------

    for row_idx in range(2, max_row + 1):
        is_even_body_row = (row_idx % 2 == 0)

        normal_fill = row_fill_even if is_even_body_row else row_fill_odd
        annotation_fill = annotation_fill_even if is_even_body_row else annotation_fill_odd

        for col_idx in range(1, max_col + 1):
            cell = ws.cell(row=row_idx, column=col_idx)

            if col_idx in annotation_col_indices:
                cell.fill = annotation_fill
            else:
                cell.fill = normal_fill

            cell.alignment = Alignment(
                vertical="top",
                wrap_text=True
            )
            cell.border = border

    # -----------------------------------------------------------------
    # Keep annotation headers yellow-ish so annotators notice them
    # -----------------------------------------------------------------

    for col_idx in annotation_col_indices:
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = PatternFill("solid", fgColor="FFD966")
        cell.font = Font(bold=True, color="000000")
        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True
        )
        cell.border = border

    # -----------------------------------------------------------------
    # Column widths
    # -----------------------------------------------------------------

    widths = {
        "case_id": 10,
        "question": 45,
        "gold_answer": 35,
        "KG answer": 35,
        "taxonomy_label": 30,
        "source": 24,
        "label_correctness": 24,
        "wikidata_cause": 30,
        "note": 45,
    }

    for i, col_name in enumerate(cleaned_header, start=1):
        ws.column_dimensions[get_column_letter(i)].width = widths.get(col_name, 22)

    # -----------------------------------------------------------------
    # Row heights
    # -----------------------------------------------------------------

    for row_idx in range(2, max_row + 1):
        ws.row_dimensions[row_idx].height = 65

    # Freeze the header row.
    ws.freeze_panes = "A2"

    # Enable Excel filter.
    ws.auto_filter.ref = ws.dimensions

    wb.save(xlsx_path)


# ---------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------

def generate_annotation_files(
    input_csv,
    output_dir="annotation_outputs",
    n_groups=3,
    stratify_cols=None
):
    """
    Generate balanced annotation Excel files from one input CSV.

    Parameters
    ----------
    input_csv : str
        Path to the input CSV.

    output_dir : str
        Folder where output Excel files will be saved.

    n_groups : int
        Number of annotation files to create.

    stratify_cols : list[str] or None
        Recommended:
            ["taxonomy_label"]

        This keeps taxonomy label distribution more balanced across groups.
    """

    input_csv = Path(input_csv)
    output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_csv, header=0)

    df = clean_column_names(df)

    expected_cols = [
        "question",
        "gold_answer",
        "KG answer",
        "taxonomy_label",
        "confidence",
        "source"
    ]

    missing = [col for col in expected_cols if col not in df.columns]

    if missing:
        raise ValueError(
            f"Missing expected columns: {missing}\n"
            f"Actual columns are: {list(df.columns)}"
        )

    # Remove confidence column because annotators should not see it.
    df = df.drop(columns=["confidence"])

    # Add stable case_id for later merging.
    if "case_id" not in df.columns:
        df.insert(0, "case_id", range(1, len(df) + 1))

    # Add annotation columns before splitting.
    df["label_correctness"] = ""
    df["wikidata_cause"] = ""
    df["note"] = ""

    final_cols = [
        "case_id",
        "question",
        "gold_answer",
        "KG answer",
        "taxonomy_label",
        "source",
        "label_correctness",
        "wikidata_cause",
        "note"
    ]

    df = df[final_cols]

    print("Final columns before splitting:")
    print(list(df.columns))

    splits = split_balanced(
        df,
        n_groups=n_groups,
        stratify_cols=stratify_cols
    )

    output_paths = []

    for i, split_df in enumerate(splits, start=1):
        out_path = output_dir / f"annotation_group_{i}.xlsx"

        print(f"\nSaving group {i}: {len(split_df)} rows")
        print("Columns:", list(split_df.columns))

        split_df.to_excel(out_path, index=False)

        add_dropdowns_and_formatting(out_path)

        output_paths.append(out_path)

    print("\nFinished.")
    print(f"Total input data rows: {len(df)}")

    for i, split_df in enumerate(splits, start=1):
        print(f"group {i}: {len(split_df)} rows")

    print("\nOutput files:")

    for path in output_paths:
        print(path)

    return output_paths


# ---------------------------------------------------------------------
# Run script
# ---------------------------------------------------------------------

if __name__ == "__main__":
    generate_annotation_files(
        input_csv="annotation_cases_235B_main_inconsistent.csv",
        output_dir="annotation_outputs",
        n_groups=3,

        # Recommended:
        # balance the distribution of taxonomy labels across the 3 files.
        #
        # Do NOT stratify by source because source may be unique per row.
        stratify_cols=["taxonomy_label"]

        # Alternative:
        # Use this if you want pure round-robin splitting:
        # stratify_cols=None
    )