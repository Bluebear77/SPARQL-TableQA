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

# Annotators use this column to verify whether the assigned taxonomy label
# is correct according to answer-level comparison.
TAXONOMY_LABEL_CORRECT_OPTIONS = [
    "Correct",
    "Incorrect",
    "Unsure"
]

# Annotators use this column after checking the corresponding Wikidata page.
# These are the three structural KG incompleteness causes.
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

    Why this is needed:
    Sometimes CSV files contain invisible characters such as BOM '\\ufeff',
    or spaces around column names.

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

        Recommended:
            stratify_cols=["taxonomy_label"]

        Not recommended:
            stratify_cols=["source"]

        Why not use source?
            In your file, source may be unique or almost unique for every row.
            If we group by source directly, each source group has only one row.
            A bad splitting function may then put every row into group 1.

    Returns
    -------
    list[pandas.DataFrame]
        A list of n_groups dataframes.
    """

    # Reset index to make row order clean and stable.
    df = df.reset_index(drop=True).copy()

    # Create empty containers for each group.
    groups = [[] for _ in range(n_groups)]

    if stratify_cols:
        # Check that every stratification column exists.
        for col in stratify_cols:
            if col not in df.columns:
                raise ValueError(
                    f"Stratification column not found: {col}\n"
                    f"Available columns: {list(df.columns)}"
                )

        # Group rows by taxonomy label, or by any other selected columns.
        grouped = df.groupby(stratify_cols, sort=False, dropna=False)

        # Global pointer ensures rows are distributed across all groups.
        # This is the key fix.
        #
        # Bad behavior:
        #     resetting i inside every tiny group can send all rows to group 1.
        #
        # Good behavior:
        #     pointer keeps increasing across all groups.
        pointer = 0

        for _, sub_df in grouped:
            sub_df = sub_df.reset_index(drop=True)

            for _, row in sub_df.iterrows():
                group_id = pointer % n_groups
                groups[group_id].append(row)
                pointer += 1

    else:
        # Simple round-robin split without stratification.
        #
        # Example with 296 rows and 3 groups:
        #     group 1 gets rows 1, 4, 7, ...
        #     group 2 gets rows 2, 5, 8, ...
        #     group 3 gets rows 3, 6, 9, ...
        for i, (_, row) in enumerate(df.iterrows()):
            group_id = i % n_groups
            groups[group_id].append(row)

    # Convert each group back into a dataframe.
    # Even if a group is empty, preserve the original columns.
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

    This function is more robust than:
        header.index("label_correctness")

    because it cleans hidden BOM characters and surrounding spaces.
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
    Add dropdown menus and simple formatting to one Excel annotation file.

    Dropdown columns:
        label_correctness
        wikidata_cause

    Free-text column:
        note
    """

    wb = load_workbook(xlsx_path)
    ws = wb.active

    # Read the first row as header.
    header = [cell.value for cell in ws[1]]
    max_row = ws.max_row

    # Find target annotation columns.
    taxonomy_col = find_column_index(header, "label_correctness")
    cause_col = find_column_index(header, "wikidata_cause")

    # Convert column numbers to Excel letters.
    taxonomy_col_letter = get_column_letter(taxonomy_col)
    cause_col_letter = get_column_letter(cause_col)

    # Create dropdown validation for taxonomy label correctness.
    dv_taxonomy = DataValidation(
        type="list",
        formula1=f'"{",".join(TAXONOMY_LABEL_CORRECT_OPTIONS)}"',
        allow_blank=True
    )

    # Create dropdown validation for Wikidata cause.
    dv_cause = DataValidation(
        type="list",
        formula1=f'"{",".join(WIKIDATA_CAUSE_OPTIONS)}"',
        allow_blank=True
    )

    # Add validations to worksheet.
    ws.add_data_validation(dv_taxonomy)
    ws.add_data_validation(dv_cause)

    # Apply dropdowns from row 2 to the final row.
    # Row 1 is the header row.
    if max_row >= 2:
        dv_taxonomy.add(f"{taxonomy_col_letter}2:{taxonomy_col_letter}{max_row}")
        dv_cause.add(f"{cause_col_letter}2:{cause_col_letter}{max_row}")

    # -----------------------------------------------------------------
    # Formatting
    # -----------------------------------------------------------------

    header_fill = PatternFill("solid", fgColor="D9EAF7")      # light blue
    annotation_fill = PatternFill("solid", fgColor="FFF2CC")  # light yellow
    thin_side = Side(style="thin", color="D9D9D9")

    # Format header row.
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True
        )
        cell.border = Border(
            top=thin_side,
            left=thin_side,
            right=thin_side,
            bottom=thin_side
        )

    # Format body cells.
    for row in ws.iter_rows(min_row=2, max_row=max_row):
        for cell in row:
            cell.alignment = Alignment(
                vertical="top",
                wrap_text=True
            )
            cell.border = Border(
                top=thin_side,
                left=thin_side,
                right=thin_side,
                bottom=thin_side
            )

    # Clean header again for formatting lookup.
    cleaned_header = [
        str(h).replace("\ufeff", "").strip() if h is not None else ""
        for h in header
    ]

    # Highlight annotation columns in yellow.
    for col_name in [
        "label_correctness",
        "wikidata_cause",
        "note"
    ]:
        if col_name in cleaned_header:
            col_idx = cleaned_header.index(col_name) + 1

            for row_idx in range(1, max_row + 1):
                ws.cell(row=row_idx, column=col_idx).fill = annotation_fill

    # Column widths.
    # Text-heavy columns are made wider.
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

    # Freeze the header row.
    ws.freeze_panes = "A2"

    # Enable Excel filter.
    ws.auto_filter.ref = ws.dimensions

    # Save changes.
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

        Use None if you only want simple round-robin balancing.
    """

    input_csv = Path(input_csv)
    output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Read CSV.
    #
    # header=0 means:
    #     The first row is the column title/header row.
    #     It is NOT treated as data.
    df = pd.read_csv(input_csv, header=0)

    # Clean column names.
    df = clean_column_names(df)

    # Expected input columns.
    expected_cols = [
        "question",
        "gold_answer",
        "KG answer",
        "taxonomy_label",
        "confidence",
        "source"
    ]

    # Validate input columns.
    missing = [col for col in expected_cols if col not in df.columns]

    if missing:
        raise ValueError(
            f"Missing expected columns: {missing}\n"
            f"Actual columns are: {list(df.columns)}"
        )

    # Remove confidence column because the annotation task should not show it.
    df = df.drop(columns=["confidence"])

    # Add stable case_id.
    #
    # This is very useful later when merging annotations from different files.
    # It preserves the original row identity.
    if "case_id" not in df.columns:
        df.insert(0, "case_id", range(1, len(df) + 1))

    # Add annotation columns BEFORE splitting.
    #
    # These are empty at first.
    # Annotators fill them in Excel.
    df["label_correctness"] = ""
    df["wikidata_cause"] = ""
    df["note"] = ""

    # Final column order in output files.
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

    # Split into balanced groups.
    splits = split_balanced(
        df,
        n_groups=n_groups,
        stratify_cols=stratify_cols
    )

    output_paths = []

    # Save each group to an Excel file.
    for i, split_df in enumerate(splits, start=1):
        out_path = output_dir / f"annotation_group_{i}.xlsx"

        print(f"\nSaving group {i}: {len(split_df)} rows")
        print("Columns:", list(split_df.columns))

        # Save dataframe to Excel.
        split_df.to_excel(out_path, index=False)

        # Add dropdowns and formatting.
        add_dropdowns_and_formatting(out_path)

        output_paths.append(out_path)

    # Print summary.
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

        # Recommended for your task:
        # balance the distribution of taxonomy labels across the 3 files.
        #
        # Do NOT stratify by source because source may be unique per row.
        stratify_cols=["taxonomy_label"]

        # Alternative:
        # Use this if you want pure round-robin splitting:
        # stratify_cols=None
    )