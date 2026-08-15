"""Форматирование ячеек .xls при заполнении таблицы анализа."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import xlrd
import xlwt

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets" / "excel_styles"

# Alternating peach / mint styles for numeric columns
SCORE_FILL_A = {"pattern": 1, "fore": 9, "back": 31}
SCORE_FILL_B = {"pattern": 1, "fore": 43, "back": 27}


def rdbook_to_style_list(rdbook: xlrd.Book) -> list:
    if not rdbook.formatting_info:
        raise ValueError("Нужен xlrd.open_workbook(..., formatting_info=True)")
    style_list: list = []
    for rdxf in rdbook.xf_list:
        wtxf = xlwt.Style.XFStyle()
        wtxf.num_format_str = rdbook.format_map[rdxf.format_key].format_str
        wtf = wtxf.font
        rdf = rdbook.font_list[rdxf.font_index]
        wtf.height = rdf.height
        wtf.italic = rdf.italic
        wtf.struck_out = rdf.struck_out
        wtf.outline = rdf.outline
        wtf.shadow = rdf.outline
        wtf.colour_index = rdf.colour_index
        wtf.bold = rdf.bold
        wtf._weight = rdf.weight
        wtf.escapement = rdf.escapement
        wtf.underline = rdf.underline_type
        wtf.family = rdf.family
        wtf.charset = rdf.character_set
        wtf.name = rdf.name
        wtp = wtxf.protection
        rdp = rdxf.protection
        wtp.cell_locked = rdp.cell_locked
        wtp.formula_hidden = rdp.formula_hidden
        wtb = wtxf.borders
        rdb = rdxf.border
        wtb.left = rdb.left_line_style
        wtb.right = rdb.right_line_style
        wtb.top = rdb.top_line_style
        wtb.bottom = rdb.bottom_line_style
        wtb.diag = rdb.diag_line_style
        wtb.left_colour = rdb.left_colour_index
        wtb.right_colour = rdb.right_colour_index
        wtb.top_colour = rdb.top_colour_index
        wtb.bottom_colour = rdb.bottom_colour_index
        wtb.diag_colour = rdb.diag_colour_index
        wtb.need_diag1 = rdb.diag_down
        wtb.need_diag2 = rdb.diag_up
        wtpat = wtxf.pattern
        rdbg = rdxf.background
        wtpat.pattern = rdbg.fill_pattern
        wtpat.pattern_fore_colour = rdbg.pattern_colour_index
        wtpat.pattern_back_colour = rdbg.background_colour_index
        wta = wtxf.alignment
        rda = rdxf.alignment
        wta.horz = rda.hor_align
        wta.vert = rda.vert_align
        wta.dire = rda.text_direction
        wta.rota = rda.rotation
        wta.wrap = rda.text_wrapped
        wta.shri = rda.shrink_to_fit
        wta.inde = rda.indent_level
        style_list.append(wtxf)
    return style_list


def style_from_spec(spec: dict) -> xlwt.XFStyle:
    st = xlwt.XFStyle()
    st.num_format_str = spec.get("num_format", "General")

    font = spec.get("font", {})
    st.font.name = font.get("name", "Arial")
    st.font.bold = font.get("bold", False)
    st.font.height = font.get("height", 200)
    st.font.colour_index = font.get("colour_index", 32767)

    align = spec.get("alignment", {})
    st.alignment.horz = align.get("horz", 2)
    st.alignment.vert = align.get("vert", 2)
    st.alignment.wrap = align.get("wrap", 0)

    pat = spec.get("pattern", {})
    st.pattern.pattern = pat.get("pattern", 0)
    st.pattern.pattern_fore_colour = pat.get("fore", 64)
    st.pattern.pattern_back_colour = pat.get("back", 65)

    borders = spec.get("borders", {})
    st.borders.left = borders.get("left", 1)
    st.borders.right = borders.get("right", 1)
    st.borders.top = borders.get("top", 1)
    st.borders.bottom = borders.get("bottom", 1)
    st.borders.left_colour = borders.get("left_colour", 64)
    st.borders.right_colour = borders.get("right_colour", 64)
    st.borders.top_colour = borders.get("top_colour", 64)
    st.borders.bottom_colour = borders.get("bottom_colour", 64)
    return st


def load_style_profile(profile: str) -> Dict[int, xlwt.XFStyle]:
    path = ASSETS_DIR / f"{profile}_data_row.json"
    if not path.exists():
        raise FileNotFoundError(f"Профиль форматирования не найден: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    columns = data.get("columns", data)
    return {int(k): style_from_spec(v) for k, v in columns.items()}


def row_has_rich_formatting(rs: xlrd.sheet.Sheet, row: int, cols: List[int]) -> bool:
    if row >= rs.nrows:
        return False
    xfs = {rs.cell_xf_index(row, c) for c in cols if c < rs.ncols}
    return len(xfs) > 1


def styles_from_template_row(
    rs: xlrd.sheet.Sheet, styles: list, row: int, cols: List[int]
) -> Dict[int, xlwt.XFStyle]:
    out: Dict[int, xlwt.XFStyle] = {}
    for c in cols:
        if c < rs.ncols and row < rs.nrows:
            out[c] = styles[rs.cell_xf_index(row, c)]
    return out


def _generic_score_spec(alternate: bool, bold: bool = False) -> dict:
    fill = SCORE_FILL_A if alternate else SCORE_FILL_B
    return {
        "num_format": "General",
        "font": {"name": "Arial", "bold": bold, "height": 200, "colour_index": 8},
        "alignment": {"horz": 2, "vert": 2, "wrap": 0},
        "pattern": fill,
        "borders": {
            "left": 1,
            "right": 1,
            "top": 1,
            "bottom": 1,
            "left_colour": 64,
            "right_colour": 64,
            "top_colour": 64,
            "bottom_colour": 64,
        },
    }


def build_generic_column_styles(
    column_defs: list, max_col: int
) -> Dict[int, xlwt.XFStyle]:
    """Универсальное форматирование, если в шаблоне нет цветных ячеек."""
    specs: Dict[int, dict] = {}
    score_idx = 0
    for col_def in column_defs:
        c = col_def.col
        ctype = col_def.type
        if ctype == "name":
            specs[c] = {
                "num_format": "General",
                "font": {"name": "Arial", "bold": False, "height": 200, "colour_index": 32767},
                "alignment": {"horz": 5, "vert": 1, "wrap": 1},
                "pattern": {"pattern": 0, "fore": 64, "back": 65},
                "borders": {
                    "left": 1,
                    "right": 1,
                    "top": 1,
                    "bottom": 1,
                    "left_colour": 64,
                    "right_colour": 64,
                    "top_colour": 64,
                    "bottom_colour": 64,
                },
            }
        elif ctype in ("section", "total", "empty"):
            specs[c] = _generic_score_spec(score_idx % 2, bold=(ctype == "total"))
            score_idx += 1
        elif ctype in ("formula", "total_formula", "grade_formula"):
            if ctype == "grade_formula":
                specs[c] = {
                    "num_format": "General",
                    "font": {"name": "Arial", "bold": False, "height": 200, "colour_index": 32767},
                    "alignment": {"horz": 2, "vert": 2, "wrap": 0},
                    "pattern": {"pattern": 0, "fore": 64, "back": 65},
                    "borders": {
                        "left": 1,
                        "right": 1,
                        "top": 1,
                        "bottom": 1,
                        "left_colour": 64,
                        "right_colour": 64,
                        "top_colour": 64,
                        "bottom_colour": 64,
                    },
                }
            else:
                specs[c] = _generic_score_spec(score_idx % 2, bold=True)
                score_idx += 1

    for c in range(max_col + 1):
        specs.setdefault(c, _generic_score_spec(c % 2))

    return {c: style_from_spec(specs[c]) for c in specs}


def resolve_column_styles(
    rs: xlrd.sheet.Sheet,
    styles: list,
    column_defs: list,
    start_row: int,
    style_profile: str = "",
    style_row: Optional[int] = None,
) -> Dict[int, xlwt.XFStyle]:
    cols = [c.col for c in column_defs]
    max_col = max(cols) if cols else 6

    if style_profile:
        try:
            profile_styles = load_style_profile(style_profile)
            return {c: profile_styles.get(c, profile_styles[max(profile_styles)]) for c in range(max_col + 1)}
        except FileNotFoundError:
            pass

    probe_row = style_row if style_row is not None else start_row
    if row_has_rich_formatting(rs, probe_row, cols):
        from_template = styles_from_template_row(rs, styles, probe_row, cols)
        if from_template:
            return from_template

    return build_generic_column_styles(column_defs, max_col)


def write_styled_cell(ws, style: xlwt.XFStyle, r: int, c: int, value) -> None:
    ws.write(r, c, value, style)


def write_styled_formula(ws, style: xlwt.XFStyle, r: int, c: int, formula: str) -> None:
    ws.write(r, c, xlwt.Formula(formula), style)
