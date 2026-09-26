# Replication package

This package recomputes the evaluation scores reported in the paper from the saved
graphs (trees). It requires no network access and no connection to the system that
produced the graphs.

## Layout

```
evaluator/
    score_evaluator.py
    overall_evaluator.py
input/
    <dataset>-original_ground_truth_full.json
    model_names.csv
output/
    trees/     <dataset>_<setting>_<run>_<system>.json
    results/   written by the evaluators
requirements.txt
run_all.sh / run_all.bat
run_selected.sh
```

Tree names: `setting` is `zero` (zero-shot) or `osl` (one-shot). `run` is `t1`, `t2`, ...,
`system` is an anonymised model label (`system_A`, ...), dataset names may contain
underscores (e.g. `cprd_gold`), they are recognised from the file names in `input/`.

## Setup

Requires Python 3.11 or newer (tested on 3.11, the pinned libraries also have builds for 3.14).

```bash
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

RapidFuzz and scikit-learn are pinned because Accuracy depends on their exact versions.
The evaluator stops if other versions are installed (override with
`--allow-version-mismatch`) and records the versions in every report.

## Run

Everything:

```bash
./run_all.sh          # Windows: run_all.bat
```

Selected trials (any combination of filters, `--tag` keeps the full summary intact):

```bash
python evaluator/score_evaluator.py --datasets cms cprd_gold
python evaluator/score_evaluator.py --settings osl --runs t1 t2 --tag summary_osl
python evaluator/score_evaluator.py --systems system_A --tag summary_A
```

Overall table:

```bash
python evaluator/overall_evaluator.py                                   # composite, all datasets
python evaluator/overall_evaluator.py --metric coverage                 # or accuracy
python evaluator/overall_evaluator.py --summary output/results/summary_osl.csv --out output/results/overall_osl.csv
```

## Outputs (`output/results/`)

| File | Contents |
|---|---|
| `<tree>_eval.json` | full report per tree: scores, counts, matched / missing variables, ancestor checks, library versions |
| `summary.csv` | one row per tree: dataset, setting, run, system, counts, coverage, accuracy, composite |
| `summary_by_model.csv` | mean over runs per dataset x setting x system |
| `overall_table.csv` / `.tex` | Model x {Zero-shot, One-shot}, plus Mean and Spread (max-min) |

In the overall table each cell is the mean of the metric for one model and setting:
runs are averaged within each dataset, then datasets are averaged with equal weight.
Mean and Spread are taken across models.