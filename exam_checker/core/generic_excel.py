from __future__ import annotations

from pathlib import Path
from typing import List

import xlrd
from xlutils.copy import copy

from exam_checker.core.excel_formatting import (
    rdbook_to_style_list,
    resolve_column_styles,
    write_styled_cell,
    write_styled_formula,
)
from exam_checker.core.models import PaperData, PaperResult
from exam_checker.core.session_config import SessionConfig


def fill_template(
    template_path: Path,
    papers: List[PaperData],
    results: List[PaperResult],
    config: SessionConfig,
    out_path: Path,
) -> None:
    by_file = {r.paper.file: r for r in results}
    sorted_papers = sorted(papers, key=lambda p: p.surname.lower())

    rb = xlrd.open_workbook(str(template_path), formatting_info=True, ragged_rows=True)
    styles = rdbook_to_style_list(rb)
    rs = rb.sheet_by_index(0)
    wb = copy(rb)
    sh = wb.get_sheet(0)
    max_col = max((c.col for c in config.excel.columns), default=6)

    col_styles = resolve_column_styles(
        rs,
        styles,
        config.excel.columns,
        config.excel.start_row,
        style_profile=config.excel.style_profile,
        style_row=config.excel.style_row,
    )

    for i, paper in enumerate(sorted_papers):
        r = config.excel.start_row + i
        excel_row = r + 1
        result = by_file[paper.file]
        full_name = f"{paper.surname.strip()} {paper.name.strip()}".strip()

        for col_def in config.excel.columns:
            c = col_def.col
            cell_style = col_styles.get(c, col_styles.get(max_col))
            if col_def.type == "name":
                write_styled_cell(sh, cell_style, r, c, full_name)
            elif col_def.type == "section":
                write_styled_cell(
                    sh, cell_style, r, c, result.sections.get(col_def.section, 0)
                )
            elif col_def.type == "total":
                write_styled_cell(sh, cell_style, r, c, result.total)
            elif col_def.type == "empty":
                write_styled_cell(sh, cell_style, r, c, None)
            elif col_def.type in ("formula", "total_formula", "grade_formula"):
                write_styled_formula(
                    sh, cell_style, r, c, col_def.formula.format(row=excel_row)
                )

    clear_from = config.excel.start_row + len(sorted_papers)
    blank_style = col_styles.get(0)
    for row in range(clear_from, rs.nrows):
        for c in range(max_col + 1):
            write_styled_cell(sh, col_styles.get(c, blank_style), row, c, None)

    wb.save(str(out_path))
