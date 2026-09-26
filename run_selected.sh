# Examples of scoring only some trials. Each writes its own summary (--tag), so the
# full summary.csv is not overwritten. Uncomment the one you need.
set -euo pipefail
cd "$(dirname "$0")"

# One dataset, both settings, all runs and systems
python evaluator/score_evaluator.py --datasets cms --tag summary_cms
python evaluator/overall_evaluator.py --summary output/results/summary_cms.csv --out output/results/overall_table_cms.csv

# One-shot only, runs t1 and t2
# python evaluator/score_evaluator.py --settings osl --runs t1 t2 --tag summary_osl_t1_t2

# A single system on two datasets
# python evaluator/score_evaluator.py --systems system_A --datasets cms cprd_gold --tag summary_system_A

# Overall table on Coverage instead of Composite, from the full summary
# python evaluator/overall_evaluator.py --metric coverage --out output/results/overall_table_coverage.csv
