from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "output" / "results"
MODEL_NAMES = ROOT / "input" / "model_names.csv"

SETTING_COLUMNS = [("zero", "Zero-shot"), ("osl", "One-shot")]
DP = 3


def fmt(x: Optional[float]) -> str:
    return "" if x is None else f"{x:.{DP}f}"


def load_model_names(path: Path) -> Dict[str, str]:
    """Read system -> display name. Tolerates Excel-saved files: a byte-order mark,
    ';' or tab separators, extra spaces and any capitalisation of the header.
    The first column is the system label, the second the name shown in the table."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8-sig")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return {}
    delim = max([",", ";", "\t"], key=lines[0].count)
    rows = [[c.strip() for c in r] for r in csv.reader(lines, delimiter=delim)]
    header = [h.lower() for h in rows[0]]
    if len(header) < 2:
        raise SystemExit(f"{path}: expected two columns 'system,model', found header {rows[0]}")
    if header[0] != "system":
        print(f"note: {path.name} header is {rows[0]}; using column 1 as system and column 2 as model name")
    names = {}
    for r in rows[1:]:
        if len(r) >= 2 and r[0]:
            names[r[0]] = r[1] or r[0]
    return names


def main() -> None:
    p = argparse.ArgumentParser(description="Overall Zero-shot / One-shot table from the run summary.")
    p.add_argument("--summary", type=Path, default=RESULTS_DIR / "summary.csv")
    p.add_argument("--metric", choices=["composite", "coverage", "accuracy"], default="composite")
    p.add_argument("--datasets", nargs="*", help="only these datasets (default: all in the summary)")
    p.add_argument("--model-names", type=Path, default=MODEL_NAMES)
    p.add_argument("--out", type=Path, default=RESULTS_DIR / "overall_table.csv")
    a = p.parse_args()

    with open(a.summary, newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if not a.datasets or r["dataset"] in a.datasets]
    if not rows:
        raise SystemExit(f"No rows in {a.summary} for the selected datasets.")

    runs: Dict[str, Dict[str, Dict[str, List[float]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in rows:
        runs[r["system"]][r["setting"]][r["dataset"]].append(float(r[a.metric]))

    names = load_model_names(a.model_names)
    systems = [s for s in names if s in runs] + sorted(s for s in runs if s not in names)

    cell: Dict[str, Dict[str, Optional[float]]] = {}
    for s in systems:
        cell[s] = {}
        for key, _ in SETTING_COLUMNS:
            per_ds = runs[s].get(key, {})
            cell[s][key] = statistics.mean(statistics.mean(v) for v in per_ds.values()) if per_ds else None

    header = ["Model"] + [label for _, label in SETTING_COLUMNS]
    body = [[names.get(s, s)] + [fmt(cell[s][k]) for k, _ in SETTING_COLUMNS] for s in systems]
    mean_row, spread_row = ["Mean"], ["Spread (max-min)"]
    for k, _ in SETTING_COLUMNS:
        vals = [cell[s][k] for s in systems if cell[s][k] is not None]
        mean_row.append(fmt(statistics.mean(vals)) if vals else "")
        spread_row.append(fmt(max(vals) - min(vals)) if vals else "")

    a.out.parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header); w.writerows(body); w.writerow(mean_row); w.writerow(spread_row)

    tex = ["\\begin{tabular}{l|" + "|".join("c" for _ in SETTING_COLUMNS) + "}", "\\hline",
           " & ".join(header) + "\\\\", "\\hline"]
    tex += [" & ".join(r) + "\\\\" for r in body]
    tex += ["\\hline", " & ".join(mean_row) + "\\\\",
            " & ".join(["Spread (max$-$min)"] + spread_row[1:]) + "\\\\", "\\hline", "\\end{tabular}"]
    a.out.with_suffix(".tex").write_text("\n".join(tex) + "\n", encoding="utf-8")

    width = max(len(r[0]) for r in body + [spread_row]) + 2
    print(f"metric: {a.metric}   datasets: {', '.join(sorted({r['dataset'] for r in rows}))}\n")
    for r in [header] + body + [mean_row, spread_row]:
        print(f"{r[0]:<{width}}" + "".join(f"{c:>12}" for c in r[1:]))
    print(f"\nWritten: {a.out} and {a.out.with_suffix('.tex')}")


if __name__ == "__main__":
    main()