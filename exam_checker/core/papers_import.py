from __future__ import annotations

import json
from pathlib import Path
from typing import List

from exam_checker.core.models import PaperData


def load_papers_from_bytes(filename: str, data: bytes) -> List[PaperData]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".py":
        return _load_from_py_text(data.decode("utf-8", errors="replace"))
    if suffix == ".json":
        return _load_from_json_text(data.decode("utf-8"))
    # попытка по содержимому
    text = data.decode("utf-8", errors="replace").lstrip()
    if text.startswith("[") or text.startswith("{"):
        return _load_from_json_text(text)
    if "PAPERS_RAW" in text:
        return _load_from_py_text(text)
    raise ValueError(
        f"Unknown format «{filename}». Expected .json or a Python export module."
    )


def _load_from_json_text(text: str) -> List[PaperData]:
    raw = json.loads(text)
    if isinstance(raw, dict) and "papers" in raw:
        raw = raw["papers"]
    if not isinstance(raw, list):
        raise ValueError("JSON: ожидается список работ [...]")
    return [PaperData.from_raw(item) for item in raw]


def _load_from_py_text(text: str) -> List[PaperData]:
    ns: dict = {}
    exec(text, ns)
    raw = ns.get("PAPERS_RAW")
    if not isinstance(raw, list):
        raise ValueError("В .py файле не найден список PAPERS_RAW")
    papers: List[PaperData] = []
    for item in raw:
        papers.append(
            PaperData(
                file=item["file"],
                surname=item.get("surname", ""),
                name=item.get("name", ""),
                answers={int(k): str(v) for k, v in item.get("a", {}).items()},
                replacements={
                    int(k): str(v) for k, v in item.get("repl", {}).items()
                },
            )
        )
    return papers
