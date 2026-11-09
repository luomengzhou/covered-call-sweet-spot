"""Extract the markdown tables in the results write-ups into CSV.

Several headline numbers only exist as markdown tables inside the audit notes
(the wing fit-quality table, the per-cell predictive table, the pooled
regression and the pooled backtest). This lifts them out verbatim so they can
be opened in a spreadsheet next to the CSVs the scripts already emit.

Usage: python3 tools/export_md_tables.py [out_dir]
Default out_dir: results/csv_exports
"""

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (source markdown, 0-based index of the table in that file, output name)
TABLES = [
    ("results/06_wing_signal_audit.md", 0, "wing_stale_summary_csv_check.csv"),
    ("results/06_wing_signal_audit.md", 1, "wing_fit_quality_by_ticker.csv"),
    ("results/06_wing_signal_audit.md", 2, "wing_predictive_by_cell.csv"),
    ("results/06_wing_signal_audit.md", 3, "wing_pooled_regression.csv"),
    ("results/06_wing_signal_audit.md", 4, "wing_rule_backtest_by_cell.csv"),
    ("results/06_wing_signal_audit.md", 5, "wing_pooled_equal_weight_backtest.csv"),
    ("results/06_skew_switch_results.md", 0, "delta_matched_headline.csv"),
    ("results/STORY_汇报主线.md", 0, "story_three_questions.csv"),
    ("results/STORY_汇报主线.md", 1, "story_payoff_segments.csv"),
]

CLEAN = re.compile(r"\*\*|`|\\")


def split_row(line):
    cells = line.strip().strip("|").split("|")
    return [CLEAN.sub("", c).strip() for c in cells]


def find_tables(text):
    """Return every contiguous run of pipe-rows that has a --- separator."""
    tables, current = [], []
    for line in text.splitlines():
        if line.lstrip().startswith("|"):
            current.append(line)
        else:
            if len(current) >= 2:
                tables.append(current)
            current = []
    if len(current) >= 2:
        tables.append(current)
    return [t for t in tables if set(t[1].replace("|", "").replace(" ", "")) <= set("-:")]


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results" / "csv_exports"
    out_dir.mkdir(parents=True, exist_ok=True)

    cache = {}
    for src, idx, name in TABLES:
        if src not in cache:
            cache[src] = find_tables((ROOT / src).read_text(encoding="utf-8"))
        tables = cache[src]
        if idx >= len(tables):
            print(f"skip {name}: {src} has only {len(tables)} tables")
            continue
        rows = [split_row(l) for l in tables[idx]]
        header, body = rows[0], rows[2:]
        with (out_dir / name).open("w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["# source: " + src])
            w.writerow(header)
            w.writerows(body)
        print(f"wrote {out_dir / name}  ({len(body)} rows)")


if __name__ == "__main__":
    main()
