"""Синхронизация PaperData ↔ виджеты Streamlit (session_state)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, List, Sequence

from exam_checker.core.models import PaperData

if TYPE_CHECKING:
    import streamlit as st_module


def surname_key(file_id: str) -> str:
    return f"paper_{file_id}_surname"


def name_key(file_id: str) -> str:
    return f"paper_{file_id}_name"


def notes_key(file_id: str) -> str:
    return f"paper_{file_id}_notes"


def repl_key(file_id: str) -> str:
    return f"paper_{file_id}_repl"


def answer_key(file_id: str, question: int) -> str:
    return f"paper_{file_id}_q{question}"


def paper_widget_keys(file_id: str, question_count: int) -> List[str]:
    keys = [
        surname_key(file_id),
        name_key(file_id),
        notes_key(file_id),
        repl_key(file_id),
    ]
    keys.extend(answer_key(file_id, n) for n in range(1, question_count + 1))
    return keys


def clear_paper_widgets(
    st: st_module, file_id: str, question_count: int
) -> None:
    for key in paper_widget_keys(file_id, question_count):
        st.session_state.pop(key, None)


def paper_has_transcription(paper: PaperData, question_count: int) -> bool:
    if paper.surname.strip() or paper.name.strip():
        return True
    filled = sum(
        1 for n in range(1, question_count + 1) if str(paper.answers.get(n, "")).strip()
    )
    return filled >= max(3, question_count // 10)


def push_paper_to_widgets(
    st: st_module, paper: PaperData, question_count: int
) -> None:
    st.session_state[surname_key(paper.file)] = paper.surname
    st.session_state[name_key(paper.file)] = paper.name
    st.session_state[notes_key(paper.file)] = paper.notes
    for n in range(1, question_count + 1):
        st.session_state[answer_key(paper.file, n)] = paper.answers.get(n, "")
    st.session_state[repl_key(paper.file)] = "\n".join(
        f"{k}={v}" for k, v in sorted(paper.replacements.items())
    )


def seed_paper_widgets(
    st: st_module, paper: PaperData, question_count: int
) -> None:
    if paper_has_transcription(paper, question_count):
        push_paper_to_widgets(st, paper, question_count)
        return
    if surname_key(paper.file) not in st.session_state:
        st.session_state[surname_key(paper.file)] = paper.surname
    if name_key(paper.file) not in st.session_state:
        st.session_state[name_key(paper.file)] = paper.name
    if notes_key(paper.file) not in st.session_state:
        st.session_state[notes_key(paper.file)] = paper.notes
    for n in range(1, question_count + 1):
        ak = answer_key(paper.file, n)
        if ak not in st.session_state:
            st.session_state[ak] = paper.answers.get(n, "")
    if repl_key(paper.file) not in st.session_state:
        st.session_state[repl_key(paper.file)] = "\n".join(
            f"{k}={v}" for k, v in sorted(paper.replacements.items())
        )


def refresh_all_widgets_from_papers(
    st: st_module, papers: Iterable[PaperData], question_count: int
) -> None:
    """Записать данные из PaperData в виджеты (после импорта JSON и т.п.)."""
    for paper in papers:
        if paper_has_transcription(paper, question_count):
            push_paper_to_widgets(st, paper, question_count)
        else:
            seed_paper_widgets(st, paper, question_count)


def sync_paper_from_widgets(
    st: st_module, paper: PaperData, question_count: int
) -> None:
    sk = surname_key(paper.file)
    if sk in st.session_state:
        val = str(st.session_state[sk] or "")
        if val.strip() or not paper.surname.strip():
            paper.surname = val
    nk = name_key(paper.file)
    if nk in st.session_state:
        val = str(st.session_state[nk] or "")
        if val.strip() or not paper.name.strip():
            paper.name = val
    tk = notes_key(paper.file)
    if tk in st.session_state:
        val = str(st.session_state[tk] or "")
        if val.strip() or not paper.notes.strip():
            paper.notes = val

    answers: dict[int, str] = dict(paper.answers)
    for n in range(1, question_count + 1):
        ak = answer_key(paper.file, n)
        if ak not in st.session_state:
            continue
        val = str(st.session_state[ak] or "")
        if val.strip() or not str(answers.get(n, "")).strip():
            answers[n] = val
    paper.answers = answers

    rk = repl_key(paper.file)
    if rk in st.session_state and str(st.session_state[rk] or "").strip():
        paper.replacements = {}
        for line in str(st.session_state[rk] or "").splitlines():
            if "=" in line.strip():
                k, v = line.strip().split("=", 1)
                paper.replacements[int(k.strip())] = v.strip()


def sync_all_papers(
    st: st_module, papers: Iterable[PaperData], question_count: int
) -> None:
    for paper in papers:
        sync_paper_from_widgets(st, paper, question_count)


def merge_papers_with_images(
    papers: Sequence[PaperData], image_ids: Sequence[str]
) -> List[PaperData]:
    """Сопоставить импорт JSON с загруженными сканами (по имени или по порядку)."""
    from dataclasses import replace

    by_file = {p.file: p for p in papers}
    imported = list(papers)
    merged: List[PaperData] = []
    used_indices: set[int] = set()

    for i, fid in enumerate(sorted(image_ids)):
        if fid in by_file:
            merged.append(by_file[fid])
            continue

        donor: PaperData | None = None
        for j, candidate in enumerate(imported):
            if j in used_indices:
                continue
            if candidate.file not in image_ids:
                donor = candidate
                used_indices.add(j)
                break

        if donor is None and i < len(imported) and i not in used_indices:
            donor = imported[i]
            used_indices.add(i)

        if donor is not None:
            merged.append(replace(donor, file=fid))
        else:
            merged.append(PaperData(file=fid))

    return merged


def apply_imported_papers(
    st: st_module,
    papers: List[PaperData],
    question_count: int,
    image_ids: Sequence[str] | None = None,
) -> List[PaperData]:
    if image_ids:
        papers = merge_papers_with_images(papers, list(image_ids))
    st.session_state.papers = papers
    refresh_all_widgets_from_papers(st, papers, question_count)
    return papers
