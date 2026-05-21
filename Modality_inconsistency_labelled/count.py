from pathlib import Path
import pandas as pd

FILES = [
    Path("Output_GRASP/merged_taxonomy_answers_4B.csv"),
    Path("Output_GRASP/merged_taxonomy_answers_30B.csv"),
    Path("Output_GRASP/merged_taxonomy_answers_235B.csv"),
]

TAXONOMY_ORDER = [
    "Same",
    "Different answer",
    "Higher accuracy in KG than in Table",
    "Higher accuracy in Table than in KG",
    "Temporal changes",
]


def group_csv_in_place(csv_path: Path):
    if not csv_path.exists():
        print(f"[SKIP] Missing file: {csv_path}")
        return

    df = pd.read_csv(csv_path)

    if "taxonomy_label" not in df.columns:
        raise ValueError(f"{csv_path} does not contain taxonomy_label")

    # Preserve original row order inside each taxonomy group
    df["_original_order"] = range(len(df))

    # Sort taxonomy labels using your preferred order
    order_map = {label: i for i, label in enumerate(TAXONOMY_ORDER)}
    df["_taxonomy_order"] = df["taxonomy_label"].map(order_map).fillna(len(TAXONOMY_ORDER))

    df = df.sort_values(
        by=["_taxonomy_order", "taxonomy_label", "_original_order"],
        kind="mergesort",
    )

    df = df.drop(columns=["_taxonomy_order", "_original_order"])

    # Overwrite the original integrated CSV
    df.to_csv(csv_path, index=False)

    counts = df["taxonomy_label"].value_counts(sort=False)
    total = len(df)

    print(f"[OK] Grouped in place: {csv_path.name}")
    print(counts)
    print(f"Total rows: {total}")
    print()


def main():
    for csv_path in FILES:
        group_csv_in_place(csv_path)


if __name__ == "__main__":
    main()
