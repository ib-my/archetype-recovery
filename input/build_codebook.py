
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple, TypedDict
import argparse

# Step 1: Ground truth builder

def split_top_level_commas(s: str) -> List[str]:
    """Split by commas ignoring those inside parentheses or quotes."""
    parts: List[str] = []
    current: List[str] = []
    depth = 0
    in_single = False
    in_double = False
    escape = False

    for ch in s:
        if escape:
            current.append(ch); escape = False; continue
        if ch == "\\":
            current.append(ch); escape = True; continue
        if ch == "'" and not in_double:
            in_single = not in_single; current.append(ch); continue
        if ch == '"' and not in_single:
            in_double = not in_double; current.append(ch); continue
        if not in_single and not in_double:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append("".join(current).strip()); current = []; continue
        current.append(ch)
    if current:
        parts.append("".join(current).strip())
    return parts


class GroundTruth(TypedDict):
    columns: List[str]
    types: Dict[str, str]
    table_comment: Optional[str]
    column_comments: Dict[str, str]
    original_column_names: Dict[str, str]


def build_ground_truth(sql: str, prefix_columns: bool = True) -> Tuple[Dict[str, List[str]], Dict[str, GroundTruth]]:
    create_table_blocks = re.findall(
        r"CREATE\s+TABLE\s+([A-Za-z_][\w]*)\s*\((.*?)\)\s*;",
        sql, flags=re.IGNORECASE | re.DOTALL,
    )
    tables: Dict[str, List[str]] = {}
    raw_types: Dict[str, Dict[str, str]] = defaultdict(dict)

    for table_name, body in create_table_blocks:
        items = split_top_level_commas(body.strip())
        cols: List[str] = []
        for item in items:
            m = re.match(r"^([A-Za-z_][\w]*)\s+(.+)$", item, flags=re.DOTALL)
            if m:
                col = m.group(1).strip()
                dtype = m.group(2).strip().rstrip(",")
                cols.append(col)
                raw_types[table_name][col] = dtype
        tables[table_name] = cols

    clean_sql = sql.replace("';';", "';")

    table_comments: Dict[str, str] = {}
    for m in re.finditer(
        r"COMMENT\s+ON\s+TABLE\s+([A-Za-z_][\w]*)\s+IS\s+'(.*?)';",
        clean_sql, flags=re.IGNORECASE | re.DOTALL
    ):
        tname, comment = m.group(1), m.group(2).strip()
        table_comments[tname] = comment

    column_comments_raw: Dict[str, Dict[str, str]] = defaultdict(dict)
    for m in re.finditer(
        r"COMMENT\s+ON\s+COLUMN\s+([A-Za-z_][\w]*)\.([A-Za-z_][\w]*)\s+IS\s+'(.*?)';",
        clean_sql, flags=re.IGNORECASE | re.DOTALL
    ):
        tname, cname, comment = m.group(1), m.group(2), m.group(3).strip()
        column_comments_raw[tname][cname] = comment

    if prefix_columns:
        rename_map: Dict[str, Dict[str, str]] = {t: {c: f"{t}_{c}" for c in cols} for t, cols in tables.items()}
        min_map: Dict[str, List[str]] = {t: [rename_map[t][c] for c in cols] for t, cols in tables.items()}
        full_map: Dict[str, GroundTruth] = {}
        for t, cols in tables.items():
            types_prefixed = {rename_map[t][c]: raw_types[t][c] for c in cols}
            col_comments_prefixed = {rename_map[t][c]: column_comments_raw.get(t, {}).get(c, "") for c in cols}
            full_map[t] = GroundTruth(
                columns=min_map[t],
                types=types_prefixed,
                table_comment=table_comments.get(t),
                column_comments=col_comments_prefixed,
                original_column_names={v: k for k, v in rename_map[t].items()},
            )
    else:
        min_map = tables
        full_map = {
            t: GroundTruth(
                columns=cols,
                types=raw_types[t],
                table_comment=table_comments.get(t),
                column_comments=column_comments_raw.get(t, {}),
                original_column_names={},
            )
            for t, cols in tables.items()
        }

    return min_map, full_map


def write_ground_truth_files(schema_sql_path: Path, prefix_columns: bool = True) -> Tuple[Path, Path]:
    sql = schema_sql_path.read_text(encoding="utf-8")
    min_map, full_map = build_ground_truth(sql, prefix_columns=prefix_columns)

    base = schema_sql_path.stem
    tag = "" if prefix_columns else "nopref_"
    min_out = schema_sql_path.with_name(f"{tag}{base}_ground_truth_min.json")
    full_out = schema_sql_path.with_name(f"{tag}{base}_ground_truth_full.json")

    min_out.write_text(json.dumps(min_map, indent=2, ensure_ascii=False), encoding="utf-8")
    full_out.write_text(json.dumps(full_map, indent=2, ensure_ascii=False), encoding="utf-8")
    return min_out, full_out

# Step 2: Codebook

def iter_variables(gt_full: Dict[str, GroundTruth], dedupe: bool = False) -> Iterator[Tuple[str, str, str]]:
    seen: set[str] = set()
    for _table, meta in gt_full.items():
        cols_order = meta.get("columns") or []
        types = meta.get("types", {})
        comments = meta.get("column_comments", {})

        if not cols_order:
            keys = set(types.keys()) | set(comments.keys())
            cols_order = sorted(keys)

        for col in cols_order:
            if dedupe and col in seen:
                continue
            seen.add(col)
            yield (col, (comments.get(col) or "").strip(), (types.get(col) or "").strip())


def write_codebook(gt_full_path: Path, out_path: Optional[Path] = None, dedupe: bool = False) -> Path:
    gt_full: Dict[str, GroundTruth] = json.loads(gt_full_path.read_text(encoding="utf-8"))
    out = out_path or gt_full_path.with_name(f"{gt_full_path.stem}_codebook.txt")

    title = f'Codebook "{gt_full_path.name}"'
    lines: List[str] = [title, ""]
    for name, desc, dtype in iter_variables(gt_full, dedupe=dedupe):
        lines.append(f"Variable Name: {name}")
        lines.append(f"Variable Description: {desc}")
        lines.append(f"Data Type: {dtype}")
        lines.append("###")

    out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return out


# Step 3: TXT to PDF

from reportlab.pdfgen import canvas  # type: ignore
from reportlab.lib.pagesizes import A4, LETTER  # type: ignore
from reportlab.pdfbase import pdfmetrics  # type: ignore
from reportlab.pdfbase.ttfonts import TTFont  # type: ignore
from reportlab.lib.utils import simpleSplit  # type: ignore

PAGE_SIZES = {"A4": A4, "LETTER": LETTER}

def _register_font(font_path: Optional[str]) -> str:
    if font_path:
        font_name = Path(font_path).stem
        pdfmetrics.registerFont(TTFont(font_name, font_path))
        return font_name
    return "Helvetica"


def txt_to_pdf(
    txt_path: Path,
    pdf_path: Path,
    *,
    page_size: str = "A4",
    margin_pt: float = 72.0,
    font_size: int = 11,
    leading_mult: float = 1.2,
    font_path: Optional[str] = None,
    add_page_numbers: bool = True,
) -> Path:
    size = PAGE_SIZES.get(page_size.upper(), A4)
    width, height = size

    text = txt_path.read_text(encoding="utf-8", errors="replace")
    c = canvas.Canvas(str(pdf_path), pagesize=size)
    font_name = _register_font(font_path)
    c.setFont(font_name, font_size)

    usable_w = width - 2 * margin_pt
    top_y = height - margin_pt
    line_h = font_size * leading_mult
    bottom_y = margin_pt

    lines = text.splitlines() or [""]
    wrapped: List[str] = []
    for raw in lines:
        wrapped.extend(simpleSplit(raw, font_name, font_size, usable_w) or [""])

    x = margin_pt
    y = top_y
    page_num = 1
    for line in wrapped:
        if y - line_h < bottom_y:
            if add_page_numbers:
                c.setFont(font_name, font_size - 1)
                c.drawCentredString(width / 2, bottom_y - (font_size * 0.5), f"{page_num}")
                c.setFont(font_name, font_size)
            c.showPage()
            c.setFont(font_name, font_size)
            y = top_y
            page_num += 1
        c.drawString(x, y, line)
        y -= line_h

    if add_page_numbers:
        c.setFont(font_name, font_size - 1)
        c.drawCentredString(width / 2, bottom_y - (font_size * 0.5), f"{page_num}")

    c.save()
    return pdf_path




def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build ground truth JSON, a codebook, and a PDF from a SQL schema."
    )
    parser.add_argument("schema_sql", type=Path, help="Path to the .sql schema file")
    parser.add_argument("--no-prefix", action="store_true",
                        help="Don't prefix column names with the table name")
    parser.add_argument("--dedupe", action="store_true",
                        help="Skip repeated column names in the codebook")
    parser.add_argument("--page-size", default="A4", choices=["A4", "LETTER"])
    parser.add_argument("--font-size", type=int, default=11)
    parser.add_argument("--font-path", default=None,
                        help="Optional .ttf font (needed for non-Latin characters)")
    parser.add_argument("--no-pdf", action="store_true", help="Stop after the codebook")
    args = parser.parse_args()

    if not args.schema_sql.is_file():
        parser.error(f"File not found: {args.schema_sql}")

    # Step 1
    min_path, full_path = write_ground_truth_files(
        args.schema_sql, prefix_columns=not args.no_prefix
    )
    print(f"Ground truth (min):  {min_path}")
    print(f"Ground truth (full): {full_path}")

    # Step 2
    codebook_path = write_codebook(full_path, dedupe=args.dedupe)
    print(f"Codebook:            {codebook_path}")

    # Step 3
    if not args.no_pdf:
        pdf_path = txt_to_pdf(
            codebook_path,
            codebook_path.with_suffix(".pdf"),
            page_size=args.page_size,
            font_size=args.font_size,
            font_path=args.font_path,
        )
        print(f"PDF:                 {pdf_path}")


if __name__ == "__main__":
    main()