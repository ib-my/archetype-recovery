# Score every tree in output/trees and build the overall table.
set -euo pipefail
cd "$(dirname "$0")"

python evaluator/score_evaluator.py
python evaluator/overall_evaluator.py
