# Replication package: Coverage, Accuracy and Composite scores

This package recomputes the evaluation scores reported in the paper from the saved
graphs (trees). It needs no network access and no connection to the system that
produced the graphs.

## Layout

```
evaluator/
    score_evaluator.py      scores each tree -> per-tree reports + run summary
    overall_evaluator.py    run summary -> overall Zero-shot / One-shot table
input/
    <dataset>-original_ground_truth_full.json    ground truth, one per dataset
    model_names.csv                              system label -> model name shown in the table
output/
    trees/     <dataset>_<setting>_<run>_<system>.json    the graphs
    results/   written by the evaluators
requirements.txt
run_all.sh / run_all.bat     score everything and build the table
run_selected.sh              examples for scoring selected trials
```

Tree names: `setting` is `zero` (zero-shot) or `osl` (one-shot); `run` is `t1`, `t2`, ...;
`system` is an anonymised model label (`system_A`, ...). Dataset names may contain
underscores (e.g. `cprd_gold`); they are recognised from the file names in `input/`.

## Setup

Requires Python 3.11 or newer (tested on 3.11; the pinned libraries also have builds for 3.14).

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

Selected trials (any combination of filters; `--tag` keeps the full summary intact):

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
| `summary.csv` | one row per tree: dataset, setting, run, system, counts, coverage, accuracy, composite (6 dp) |
| `summary_by_model.csv` | mean over runs per dataset x setting x system (3 dp) |
| `overall_table.csv` / `.tex` | Model x {Zero-shot, One-shot}, plus Mean and Spread (max-min) |

In the overall table each cell is the mean of the metric for one model and setting:
runs are averaged within each dataset, then datasets are averaged with equal weight.
Mean and Spread are taken across models. Rounding to 3 dp happens only at the end.

## Metrics

Let V be the ground-truth variables, t(v) the table that owns v, L the leaves of a
tree and Anc(n) the ancestors of node n.

- **Coverage** = |M| / |V|, where M = variables that appear as a leaf (exact id or label match).
- **Accuracy** = share of v in M for which some ancestor a satisfies S(t(v), a) >= tau, with tau = 0.60.
- **Composite** = 0.5 * Coverage + 0.5 * Accuracy.

S is the table-name similarity: 1 if normalised names are equal (lower case, `_` to space
or removed, trailing `s` dropped); otherwise
min(1, 0.6 * RapidFuzz token-set ratio / 100 + 0.4 * TF-IDF cosine + bonus),
with +0.10 if one name is a prefix of the other and +0.05 if one contains the other.
The TF-IDF vectoriser (scikit-learn defaults) is fitted on each pair of names.