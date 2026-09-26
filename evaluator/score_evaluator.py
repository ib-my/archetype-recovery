from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from collections import defaultdict, deque
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# Fixed parameters
TAU = 0.60
W_RF, W_TFIDF = 0.6, 0.4
BONUS_PREFIX, BONUS_SUBSTRING = 0.10, 0.05
W_COV, W_ACC = 0.5, 0.5
MEAN_DP = 3

PINNED_VERSIONS = {"rapidfuzz": "3.14.6", "scikit-learn": "1.9.1"}

ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT / "input"
TREES_DIR = ROOT / "output" / "trees"
RESULTS_DIR = ROOT / "output" / "results"
GT_SUFFIX = "-original_ground_truth_full.json"
TREE_RE = re.compile(r"^(?P<setting>.+?)_(?P<run>t\d+)_(?P<system>.+)$")

from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def installed_versions() -> Dict[str, str]:
    return {pkg: _pkg_version(pkg) for pkg in PINNED_VERSIONS}


def check_versions(strict: bool) -> None:
    bad = {p: v for p, v in installed_versions().items() if v != PINNED_VERSIONS[p]}
    if bad:
        msg = "; ".join(f"{p}: pinned {PINNED_VERSIONS[p]}, installed {v}" for p, v in bad.items())
        if strict:
            sys.exit(f"Version mismatch ({msg}). Run: pip install -r requirements.txt "
                     f"or pass --allow-version-mismatch.")
        print(f"WARNING: version mismatch ({msg}); scores may not be reproducible.", file=sys.stderr)


# Loading
def load_ground_truth(path: Path) -> Dict[str, List[str]]:
    """{table: [variables]} from {table: {"columns": [...]}} or {table: [...]}."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return {t: list(v["columns"] if isinstance(v, dict) else v) for t, v in data.items()}


def load_graph(data: Dict[str, Any]) -> Tuple[Dict[str, Dict[str, str]], Dict[str, Set[str]], Dict[str, Set[str]]]:
    g = data.get("result", data)
    nodes = {str(n["id"]): {"id": str(n["id"]), "label": str(n.get("label") or n["id"])}
             for n in g.get("nodes", [])}
    children: Dict[str, Set[str]] = defaultdict(set)
    parents: Dict[str, Set[str]] = defaultdict(set)
    for e in g.get("edges", []):
        s, t = str(e["source"]), str(e["target"])
        children[s].add(t)
        parents[t].add(s)
    return nodes, children, parents


def ancestors(node: str, parents: Dict[str, Set[str]]) -> List[str]:
    seen: Set[str] = set()
    q = deque([node])
    while q:
        for p in parents.get(q.popleft(), ()):
            if p not in seen:
                seen.add(p); q.append(p)
    return sorted(seen)


# Similarity and metrics
def _norm(s: str) -> str:
    return " ".join(s.strip().lower().split())


def name_variants(s: str) -> List[str]:
    raw = (s or "").strip().lower()
    base = {_norm(raw), _norm(raw.replace("_", " ")), _norm(raw.replace("_", ""))}
    out = set(base) | {x[:-1] for x in base if x.endswith("s") and len(x) > 1}
    return sorted(v for v in out if v)


def tfidf_cosine(a: str, b: str) -> float:
    try:
        m = TfidfVectorizer().fit_transform([a, b])
    except ValueError:
        return 0.0
    return float(cosine_similarity(m[0:1], m[1:2])[0, 0])


def table_similarity(gt_table: str, candidate: str) -> Tuple[float, str, str]:
    best, best_g, best_a = 0.0, "", ""
    for g in name_variants(gt_table):
        for a in name_variants(candidate):
            if g == a:
                return 1.0, g, a
            score = W_RF * fuzz.token_set_ratio(g, a, processor=None) / 100.0 + W_TFIDF * tfidf_cosine(g, a)
            if a.startswith(g) or g.startswith(a):
                score += BONUS_PREFIX
            if g in a or a in g:
                score += BONUS_SUBSTRING
            score = min(1.0, score)
            if score > best:
                best, best_g, best_a = score, g, a
    return best, best_g, best_a


def evaluate(gt: Dict[str, List[str]], graph: Dict[str, Any], tau: float = TAU) -> Dict[str, Any]:
    var_to_table = {v: t for t, cols in gt.items() for v in cols}
    gt_vars = set(var_to_table)
    nodes, children, parents = load_graph(graph)

    leaves = sorted(n for n in nodes if not children.get(n))
    matched: Dict[str, str] = {}
    for nid in leaves:
        for name in (nodes[nid]["id"], nodes[nid]["label"]):
            if name in gt_vars:
                matched.setdefault(name, nid)
                break

    correct, incorrect = [], []
    for v in sorted(matched):
        nid, table = matched[v], var_to_table[v]
        best = {"similarity": 0.0, "ancestor": "", "ancestor_name": "", "gt_variant": "", "ancestor_variant": ""}
        for aid in ancestors(nid, parents):
            for cand in (nodes[aid]["label"], nodes[aid]["id"]):
                s, gv, av = table_similarity(table, cand)
                if s > best["similarity"]:
                    best = {"similarity": s, "ancestor": aid, "ancestor_name": cand,
                            "gt_variant": gv, "ancestor_variant": av}
        rec = {"variable": v, "gt_table": table, "leaf_node": nid, **best,
               "similarity": round(best["similarity"], 4)}
        (correct if best["similarity"] >= tau else incorrect).append(rec)

    coverage = len(matched) / max(1, len(gt_vars))
    accuracy = len(correct) / max(1, len(matched))
    composite = W_COV * coverage + W_ACC * accuracy

    return {
        "settings": {
            "tau": tau,
            "similarity": {"w_token_set_ratio": W_RF, "w_tfidf_cosine": W_TFIDF,
                           "bonus_prefix": BONUS_PREFIX, "bonus_substring": BONUS_SUBSTRING},
            "composite_weights": {"coverage": W_COV, "accuracy": W_ACC},
            "library_versions": installed_versions(),
            "python": sys.version.split()[0],
        },
        "counts": {"gt_tables": len(gt), "gt_variables": len(gt_vars),
                   "graph_nodes": len(nodes), "graph_leaves": len(leaves),
                   "matched_variables": len(matched), "correct_ancestor": len(correct)},
        "scores": {"coverage": coverage, "accuracy": accuracy, "composite": composite},
        "variables": {
            "matched": sorted(matched),
            "missing": sorted(gt_vars - set(matched)),
            "extra_leaves": [n for n in leaves
                             if nodes[n]["id"] not in gt_vars and nodes[n]["label"] not in gt_vars],
        },
        "ancestor_checks": {"correct": correct, "incorrect": incorrect},
    }


# Batch over output/trees
def parse_tree_name(stem: str, datasets: List[str]) -> Optional[Tuple[str, str, str, str]]:
    """'cprd_gold_osl_t2_system_C' -> ('cprd_gold', 'osl', 't2', 'system_C')."""
    for ds in sorted(datasets, key=len, reverse=True):
        if stem.startswith(ds + "_"):
            m = TREE_RE.match(stem[len(ds) + 1:])
            if m:
                return ds, m["setting"], m["run"], m["system"]
    return None


def write_csv(path: Path, records: List[Dict[str, Any]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(records[0]))
        w.writeheader(); w.writerows(records)


def main() -> None:
    p = argparse.ArgumentParser(description="Score the graphs in output/trees against input/ ground truth.")
    p.add_argument("--datasets", nargs="*", help="only these datasets (e.g. cms cprd_gold)")
    p.add_argument("--settings", nargs="*", help="only these settings (zero, osl)")
    p.add_argument("--runs", nargs="*", help="only these runs (e.g. t1 t2)")
    p.add_argument("--systems", nargs="*", help="only these systems (e.g. system_A)")
    p.add_argument("--tag", default="summary", help="name of the summary files (default: summary)")
    p.add_argument("--input-dir", type=Path, default=INPUT_DIR)
    p.add_argument("--trees-dir", type=Path, default=TREES_DIR)
    p.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    p.add_argument("--allow-version-mismatch", action="store_true")
    a = p.parse_args()

    check_versions(strict=not a.allow_version_mismatch)

    gt_files = {f.name[: -len(GT_SUFFIX)]: f for f in a.input_dir.glob(f"*{GT_SUFFIX}")}
    if not gt_files:
        sys.exit(f"No *{GT_SUFFIX} files in {a.input_dir}")

    selected = []
    for f in sorted(a.trees_dir.glob("*.json")):
        parsed = parse_tree_name(f.stem, list(gt_files))
        if not parsed:
            print(f"skip {f.name}: not <dataset>_<setting>_<run>_<system> for a dataset in input/")
            continue
        ds, setting, run, system = parsed
        if ((a.datasets and ds not in a.datasets) or (a.settings and setting not in a.settings)
                or (a.runs and run not in a.runs) or (a.systems and system not in a.systems)):
            continue
        selected.append((f, ds, setting, run, system))
    if not selected:
        sys.exit("No trees match the selection.")

    a.results_dir.mkdir(parents=True, exist_ok=True)
    gt_cache: Dict[str, Dict[str, List[str]]] = {}
    rows: List[Dict[str, Any]] = []

    print(f"{'dataset':<12} {'setting':<8} {'run':<5} {'system':<12} {'coverage':>9} {'accuracy':>9} {'composite':>10}")
    for f, ds, setting, run, system in sorted(selected, key=lambda x: (x[1], x[2], x[4], x[3])):
        gt = gt_cache.setdefault(ds, load_ground_truth(gt_files[ds]))
        report = evaluate(gt, json.loads(f.read_text(encoding="utf-8")))
        (a.results_dir / f"{f.stem}_eval.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        s, c = report["scores"], report["counts"]
        rows.append({"dataset": ds, "setting": setting, "run": run, "system": system,
                     "gt_variables": c["gt_variables"], "matched": c["matched_variables"],
                     "correct_ancestor": c["correct_ancestor"],
                     "coverage": f"{s['coverage']:.6f}", "accuracy": f"{s['accuracy']:.6f}",
                     "composite": f"{s['composite']:.6f}"})
        print(f"{ds:<12} {setting:<8} {run:<5} {system:<12} "
              f"{s['coverage']:>9.3f} {s['accuracy']:>9.3f} {s['composite']:>10.3f}")

    groups: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        groups[(r["dataset"], r["setting"], r["system"])].append(r)
    by_model = []
    for (ds, setting, system), rs in sorted(groups.items()):
        rec: Dict[str, Any] = {"dataset": ds, "setting": setting, "system": system, "n_runs": len(rs)}
        for k in ("coverage", "accuracy", "composite"):
            rec[f"{k}_mean"] = f"{statistics.mean(float(r[k]) for r in rs):.{MEAN_DP}f}"
        by_model.append(rec)

    write_csv(a.results_dir / f"{a.tag}.csv", rows)
    write_csv(a.results_dir / f"{a.tag}_by_model.csv", by_model)
    print(f"\n{len(rows)} graph(s) scored. Reports and {a.tag}.csv / {a.tag}_by_model.csv "
          f"written to {a.results_dir}")


if __name__ == "__main__":
    main()
