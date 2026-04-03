import re
from pathlib import Path
from collections import defaultdict
import matplotlib.pyplot as plt


# ------------------------------------------------------------
# Utilities
# ------------------------------------------------------------

def pct(value, total):
    """Safe percentage calculation."""
    return (value / total * 100) if total else 0


# ------------------------------------------------------------
# Parse markdown summary
# ------------------------------------------------------------

def parse_summary_md(md_path: Path):
    """
    Parse *_invalid_summary.md file.

    Extract:
        total
        valid
        invalid
        error breakdown
    """

    text = md_path.read_text(encoding="utf-8")

    total = int(re.search(r"Total JSON files:\s*(\d+)", text).group(1))
    valid = int(re.search(r"Valid cases:\s*(\d+)", text).group(1))
    invalid = int(re.search(r"Invalid cases:\s*(\d+)", text).group(1))

    errors = {}

    for label, count in re.findall(r"-\s*(.*?):\s*(\d+)", text):
        errors[label.strip()] = int(count)

    return {
        "total": total,
        "valid": valid,
        "invalid": invalid,
        "errors": errors
    }


# ------------------------------------------------------------
# Plot helpers
# ------------------------------------------------------------

def plot_valid_invalid_total(valid, invalid, output):

    total = valid + invalid

    plt.figure(figsize=(6,6))

    plt.pie(
        [valid, invalid],
        labels=["Valid", "Invalid"],
        autopct=lambda p: f"{p:.1f}%\n({int(round(p*total/100))})",
        startangle=90
    )

    plt.title("Valid vs Invalid (Total)")
    plt.savefig(output, dpi=150)
    plt.close()


def plot_valid_invalid_per_folder(data, output):

    folders = list(data.keys())

    valid = [data[f]["valid"] for f in folders]
    invalid = [data[f]["invalid"] for f in folders]
    totals = [data[f]["total"] for f in folders]

    x = range(len(folders))

    plt.figure(figsize=(12,6))

    plt.bar(x, valid, label="Valid")
    plt.bar(x, invalid, bottom=valid, label="Invalid")

    for i,(v,inv,t) in enumerate(zip(valid,invalid,totals)):

        plt.text(i, v/2, f"{pct(v,t):.1f}%", ha="center")
        plt.text(i, v + inv/2, f"{pct(inv,t):.1f}%", ha="center")

    plt.xticks(x, folders, rotation=45, ha="right")

    plt.ylabel("Cases")
    plt.title("Valid vs Invalid per folder")

    plt.legend()

    plt.tight_layout()

    plt.savefig(output, dpi=150)
    plt.close()


def plot_error_distribution_total(error_totals, total_invalid, output):

    labels = list(error_totals.keys())
    values = list(error_totals.values())

    plt.figure(figsize=(12,6))

    bars = plt.bar(labels, values)

    for bar,val in zip(bars,values):

        plt.text(
            bar.get_x() + bar.get_width()/2,
            bar.get_height(),
            f"{val}\n({pct(val,total_invalid):.1f}%)",
            ha="center",
            va="bottom"
        )

    plt.xticks(rotation=45, ha="right")

    plt.ylabel("Cases")
    plt.title("Error distribution (Total)")

    plt.tight_layout()

    plt.savefig(output, dpi=150)
    plt.close()


def plot_error_distribution_per_folder(data, output):

    labels = set()

    for d in data.values():
        labels.update(d["errors"].keys())

    labels = sorted(labels)

    folders = list(data.keys())

    x = range(len(folders))

    plt.figure(figsize=(14,7))

    bottom = [0]*len(folders)

    for label in labels:

        vals = [data[f]["errors"].get(label,0) for f in folders]

        plt.bar(x, vals, bottom=bottom, label=label)

        bottom = [bottom[i] + vals[i] for i in range(len(vals))]

    plt.xticks(x, folders, rotation=45, ha="right")

    plt.ylabel("Cases")
    plt.title("Error distribution per folder")

    plt.legend()

    plt.tight_layout()

    plt.savefig(output, dpi=150)
    plt.close()


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():

    base_dir = Path.cwd()

    statistics_dir = base_dir / "statistics"
    statistics_dir.mkdir(exist_ok=True)

    summary_files = list(base_dir.rglob("*_invalid_summary.md"))

    if not summary_files:
        print("No summary files found.")
        return

    data = {}

    total_valid = 0
    total_invalid = 0
    total_all = 0

    error_totals = defaultdict(int)

    # --------------------------------------------------------
    # Read summaries
    # --------------------------------------------------------

    for md in summary_files:

        folder = md.stem.replace("_invalid_summary","")

        stats = parse_summary_md(md)

        data[folder] = stats

        total_valid += stats["valid"]
        total_invalid += stats["invalid"]
        total_all += stats["total"]

        for label,count in stats["errors"].items():
            error_totals[label] += count


    # --------------------------------------------------------
    # Generate plots
    # --------------------------------------------------------

    plot_valid_invalid_total(
        total_valid,
        total_invalid,
        statistics_dir / "valid_vs_invalid_total.png"
    )

    plot_valid_invalid_per_folder(
        data,
        statistics_dir / "valid_vs_invalid_per_folder.png"
    )

    plot_error_distribution_total(
        error_totals,
        total_invalid,
        statistics_dir / "error_distribution_total.png"
    )

    plot_error_distribution_per_folder(
        data,
        statistics_dir / "error_distribution_per_folder.png"
    )

    # --------------------------------------------------------
    # Markdown report
    # --------------------------------------------------------

    md = []

    md.append("# Global SPARQL QA Statistics\n")

    md.append("## Overall valid vs invalid\n")

    md.append("| Metric | Count | Percentage |")
    md.append("|---|---|---|")

    md.append(f"| Valid | {total_valid} | {pct(total_valid,total_all):.2f}% |")
    md.append(f"| Invalid | {total_invalid} | {pct(total_invalid,total_all):.2f}% |\n")

    md.append("![](valid_vs_invalid_total.png)\n")
    md.append("![](valid_vs_invalid_per_folder.png)\n")

    # --------------------------------------------------------

    md.append("## Error distribution (Total)\n")

    md.append("| Error type | Count | % of invalid |")
    md.append("|---|---|---|")

    for label,count in sorted(error_totals.items()):

        md.append(
            f"| {label} | {count} | {pct(count,total_invalid):.2f}% |"
        )

    md.append("\n![](error_distribution_total.png)\n")

    # --------------------------------------------------------

    md.append("## Per-folder summary\n")

    md.append("| Folder | Total | Valid | Valid % | Invalid | Invalid % |")
    md.append("|---|---|---|---|---|---|")

    for folder,stats in data.items():

        md.append(
            f"| {folder} | {stats['total']} | {stats['valid']} | {pct(stats['valid'],stats['total']):.2f}% | "
            f"{stats['invalid']} | {pct(stats['invalid'],stats['total']):.2f}% |"
        )

    # TOTAL ROW
    md.append(
        f"| **Total** | {total_all} | {total_valid} | {pct(total_valid,total_all):.2f}% | "
        f"{total_invalid} | {pct(total_invalid,total_all):.2f}% |"
    )

    md.append("\n![](error_distribution_per_folder.png)\n")

    (statistics_dir / "summary.md").write_text("\n".join(md), encoding="utf-8")

    print("✓ Statistics generated in:", statistics_dir)


if __name__ == "__main__":
    main()
