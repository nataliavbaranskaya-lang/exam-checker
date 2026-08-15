#!/usr/bin/env python3
"""Exam Checker — интерфейс проверки бланков (Mac / Windows / браузер)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from exam_checker.core.adapters import get_adapter
from exam_checker.core.disputes import find_disputes
from exam_checker.core.images import format_ingest_summary, ingest_scans
from exam_checker.core.key_parser import parse_key_bytes
from exam_checker.core.models import PaperData
from exam_checker.core.papers_import import load_papers_from_bytes
from exam_checker.core.paper_widgets import (
    answer_key,
    apply_imported_papers,
    merge_papers_with_images,
    name_key,
    notes_key,
    paper_has_transcription,
    push_paper_to_widgets,
    refresh_all_widgets_from_papers,
    repl_key,
    seed_paper_widgets,
    surname_key,
    sync_all_papers,
    sync_paper_from_widgets,
)
from exam_checker.core.reports import (
    format_errors_detailed,
    format_summary,
    results_summary_stats,
    results_table_rows,
    results_to_csv_bytes,
    section_column_name,
)
from exam_checker.core.session_config import (
    LEVEL_CHOICES,
    SessionConfig,
    load_preset,
)
from exam_checker.core.transcription import (
    DEFAULT_MODELS,
    TranscriptionError,
    apply_transcription,
    resolve_api_key,
    transcribe_image,
)

st.set_page_config(page_title="Exam Checker", page_icon="📋", layout="wide")


def show_scan_image(img: bytes, caption: str = "") -> None:
    """Показать скан; совместимо со старыми версиями Streamlit."""
    try:
        st.image(img, caption=caption, use_container_width=True)
    except TypeError:
        try:
            st.image(img, caption=caption, use_column_width=True)
        except TypeError:
            st.image(img, caption=caption)


STEP_LABELS = [
    "1. Загрузка",
    "2. Транскрипция",
    "3. Спорные",
    "4. Результаты",
    "5. Экспорт",
]

KEY_TYPES = ["doc", "docx", "py", "json", "csv", "txt"]


def init_state() -> None:
    defaults = {
        "step": 0,
        "level_code": "level_60",
        "session_config": load_preset("level_60"),
        "answer_key": {},
        "template_bytes": None,
        "template_name": "",
        "images": {},
        "papers": [],
        "results": None,
        "ocr_provider": "openai",
        "ocr_api_key": "",
        "ocr_model": "",
        "auto_ocr_done": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def cfg() -> SessionConfig:
    return st.session_state.session_config


def sidebar_nav() -> None:
    st.sidebar.title("Exam Checker")
    st.sidebar.caption("Upload key · score · export")
    step = st.sidebar.radio("Шаг", STEP_LABELS, index=min(st.session_state.step, len(STEP_LABELS) - 1))
    st.session_state.step = STEP_LABELS.index(step)
    c = cfg()
    st.sidebar.markdown(f"**{c.title}**")
    st.sidebar.markdown(f"Заданий: **{c.question_count}**")
    st.sidebar.markdown(f"Ключ: **{len(st.session_state.answer_key)}** ответов")
    st.sidebar.markdown(f"Работ: **{len(st.session_state.papers)}**")


def level_config_editor() -> None:
    c = cfg()
    with st.expander("Настройки уровня (можно изменить вручную)"):
        c.title = st.text_input("Название сессии", value=c.title)
        c.question_count = st.number_input(
            "Число заданий",
            min_value=1,
            max_value=120,
            value=c.question_count,
        )
        c.grade_fail_below = st.number_input(
            "Fail, если баллов меньше",
            min_value=0,
            value=c.grade_fail_below,
        )
        c.grade_pass_plus_from = st.number_input(
            "Pass +, если баллов от",
            min_value=0,
            value=c.grade_pass_plus_from,
        )
        st.caption("Части теста (для отчёта и таблицы)")
        for i, sec in enumerate(c.sections):
            cols = st.columns([2, 2, 1, 1])
            sec.label = cols[0].text_input(f"Название {i+1}", sec.label, key=f"sl_{i}")
            sec.id = cols[1].text_input(f"ID {i+1}", sec.id, key=f"si_{i}")
            sec.from_q = cols[2].number_input("с", 1, 120, sec.from_q, key=f"sf_{i}")
            sec.to_q = cols[3].number_input("по", 1, 120, sec.to_q, key=f"st_{i}")
        st.session_state.session_config = c


def step_upload() -> None:
    st.header("Загрузка материалов")

    labels = {code: label for code, label in LEVEL_CHOICES}
    level_code = st.selectbox(
        "Exam level",
        options=[code for code, _ in LEVEL_CHOICES],
        format_func=lambda k: labels[k],
        index=[code for code, _ in LEVEL_CHOICES].index(st.session_state.level_code),
    )
    if level_code != st.session_state.level_code:
        st.session_state.level_code = level_code
        st.session_state.session_config = load_preset(level_code)
        st.session_state.answer_key = {}
        st.session_state.results = None

    st.info(
        "Upload your **answer key** (DOC, DOCX, JSON, CSV, TXT, or PY). "
        "The preset sets question count, sections, and Excel formulas — edit below if needed."
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("Бланки")
        st.caption("PNG, JPG, WEBP, HEIC, PDF")
        scans = st.file_uploader(
            "Сканы (фото или PDF)",
            type=["png", "jpg", "jpeg", "webp", "heic", "heif", "pdf"],
            accept_multiple_files=True,
            help=(
                "Фото — один файл на работу. PDF — каждая страница = одна работа "
                "(удобно, если сканировали все бланки одним потоком в один файл). "
                "Можно загрузить несколько PDF и фото вместе."
            ),
        )
    with col2:
        st.subheader("Ключ ответов")
        st.caption("DOC, DOCX, JSON, CSV, TXT, PY")
        key_file = st.file_uploader(
            "Файл ключа",
            type=KEY_TYPES,
            help="DOCX and JSON usually parse best. You can also paste answers from a Python key module.",
        )
    with col3:
        st.subheader("Таблица анализа")
        st.caption("Шаблон .xls")
        xls = st.file_uploader("Excel", type=["xls"])

    cfg_file = st.file_uploader(
        "Дополнительно: свой config.json (структура частей / Excel)",
        type=["json"],
        key="upload_session_config",
        help="Не путать с papers.json — это настройки уровня, обычно не нужен.",
    )
    if cfg_file and st.button("Применить config.json", key="apply_session_config"):
        try:
            data = json.loads(cfg_file.getvalue().decode("utf-8"))
            if isinstance(data, list):
                st.error(
                    "Это файл **транскрипций** (список работ), а не config. "
                    "Загрузите его в блок «Импорт готовых транскрипций» ниже."
                )
            elif not isinstance(data, dict) or "question_count" not in data:
                st.error(
                    "Неверный config.json: ожидается объект с полем question_count. "
                    "Sample: exam_checker/presets/level_60.json"
                )
            else:
                st.session_state.session_config = SessionConfig.from_dict(data)
                st.success("Загружен config.json")
                st.rerun()
        except Exception as exc:
            st.error(f"Не удалось прочитать config.json: {exc}")

    level_config_editor()

    if scans:
        images, ingest_errors, ingest_stats = ingest_scans(
            (up.name, up.getvalue()) for up in scans
        )
        st.session_state.images = images
        st.session_state.ingest_stats = ingest_stats
        summary = format_ingest_summary(ingest_stats, len(images))
        if summary:
            st.success(summary)
        for err in ingest_errors:
            st.error(err)

        st.session_state.papers = merge_papers_with_images(
            st.session_state.papers,
            sorted(st.session_state.images),
        )
        st.session_state.auto_ocr_done = False
        refresh_all_widgets_from_papers(
            st, st.session_state.papers, cfg().question_count
        )
    elif st.session_state.images:
        stats = st.session_state.get("ingest_stats") or {}
        summary = format_ingest_summary(stats, len(st.session_state.images))
        if summary:
            st.caption(summary.replace("**", ""))

    if key_file:
        try:
            st.session_state.answer_key = parse_key_bytes(
                key_file.name, key_file.getvalue()
            )
            n = len(st.session_state.answer_key)
            if n == 0:
                st.error("Key not parsed (0 questions). Try DOCX or JSON.")
            else:
                st.success(f"Ключ: **{n}** заданий")
                with st.expander("Предпросмотр ключа"):
                    preview = {
                        str(k): v
                        for k, v in list(st.session_state.answer_key.items())[:30]
                    }
                    st.json(preview)
                    if n > 30:
                        st.caption(f"… и ещё {n - 30}")
        except Exception as exc:
            st.session_state.answer_key = {}
            st.error(f"Не удалось прочитать ключ: {exc}")

    if xls:
        st.session_state.template_bytes = xls.getvalue()
        st.session_state.template_name = xls.name

    if st.button("Далее → транскрипция", type="primary"):
        missing = []
        if not st.session_state.images:
            missing.append("бланки")
        if not st.session_state.template_bytes:
            missing.append("таблица .xls")
        if not st.session_state.answer_key:
            missing.append("ключ ответов")
        if missing:
            st.error("Не хватает: " + ", ".join(missing))
        else:
            qc = cfg().question_count
            covered = sum(1 for n in range(1, qc + 1) if n in st.session_state.answer_key)
            if covered < qc * 0.5:
                st.warning(
                    f"В ключе только {covered} из {qc} заданий — проверьте файл ключа."
                )
            st.session_state.step = 1
            refresh_all_widgets_from_papers(
                st, st.session_state.papers, cfg().question_count
            )
            st.rerun()

    with st.expander("Импорт готовых транскрипций (JSON или PY)", expanded=True):
        st.markdown(
            "**Upload** `papers.json` with transcribed answers.\n\n"
            "Sample: `exam_checker/examples/sample_papers.json`"
        )
        jf = st.file_uploader(
            "papers.json",
            type=["json", "py"],
            key="import_papers",
        )
        if jf and st.button("Загрузить транскрипции"):
            try:
                imported = load_papers_from_bytes(jf.name, jf.getvalue())
                image_ids = sorted(st.session_state.images) if st.session_state.images else None
                papers = apply_imported_papers(
                    st, imported, cfg().question_count, image_ids
                )
                st.session_state.auto_ocr_done = True
                st.success(
                    f"Загружено **{len(papers)}** работ из `{jf.name}`"
                )
                if image_ids and len(image_ids) != len(imported):
                    st.caption(
                        "Транскрипции сопоставлены со сканами по имени файла или по порядку."
                    )
                st.rerun()
            except Exception as exc:
                st.error(f"Не удалось загрузить: {exc}")


def ocr_settings_panel() -> None:
    with st.expander("Распознавание почерка (необязательно, нужен платный API)", expanded=False):
        st.caption(
            "Можно пропустить и заполнять ответы вручную по скану. "
            "Для автоматического OCR нужен API-ключ OpenAI или Anthropic."
        )
        provider = st.selectbox(
            "Провайдер",
            ["openai", "anthropic"],
            index=0 if st.session_state.ocr_provider == "openai" else 1,
            format_func=lambda p: "OpenAI (GPT-4o)" if p == "openai" else "Anthropic (Claude)",
        )
        st.session_state.ocr_provider = provider

        env_key = resolve_api_key(provider, "")
        api_key = st.text_input(
            "API-ключ",
            value=st.session_state.ocr_api_key,
            type="password",
            placeholder="из переменной окружения" if env_key else "sk-…",
        )
        st.session_state.ocr_api_key = api_key

        default_model = DEFAULT_MODELS[provider]
        model = st.text_input(
            "Модель (необязательно)",
            value=st.session_state.ocr_model or default_model,
        )
        st.session_state.ocr_model = model


def run_ocr_for_paper(paper: PaperData) -> None:
    img = st.session_state.images.get(paper.file)
    if not img:
        raise TranscriptionError(f"Нет изображения для {paper.file}")

    c = cfg()
    result = transcribe_image(
        img,
        c.question_count,
        c.title,
        provider=st.session_state.ocr_provider,
        api_key=st.session_state.ocr_api_key,
        model=st.session_state.ocr_model or None,
    )
    apply_transcription(paper, result)
    push_paper_to_widgets(st, paper, c.question_count)


def auto_transcribe_all_if_needed() -> None:
    """Автозаполнение с бланков при первом входе на шаг транскрипции."""
    if st.session_state.auto_ocr_done:
        return

    c = cfg()
    provider = st.session_state.ocr_provider
    api_key = resolve_api_key(provider, st.session_state.ocr_api_key)
    pending = [
        p
        for p in st.session_state.papers
        if not paper_has_transcription(p, c.question_count)
    ]
    if not pending:
        st.session_state.auto_ocr_done = True
        return

    if not api_key:
        st.info(
            "Чтобы **автоматически** заполнить поля с бланка, укажите API-ключ "
            "и нажмите «Распознать все работы». Или введите ответы вручную — "
            "поля ниже редактируемые."
        )
        for paper in st.session_state.papers:
            seed_paper_widgets(st, paper, c.question_count)
        return

    with st.spinner(f"Распознавание {len(pending)} бланков…"):
        errors: list[str] = []
        for paper in pending:
            try:
                run_ocr_for_paper(paper)
            except TranscriptionError as exc:
                errors.append(f"{paper.file}: {exc}")
        st.session_state.auto_ocr_done = True
        if errors:
            st.warning(
                "Часть бланков не распознана:\n"
                + "\n".join(f"- {e}" for e in errors)
            )
        else:
            st.success(
                f"Поля заполнены с бланков ({len(pending)} работ). "
                "Проверьте и исправьте при необходимости."
            )


def step_transcribe() -> None:
    st.header("Транскрипция бланков")
    c = cfg()
    if not st.session_state.papers:
        st.warning("Нет бланков.")
        return

    auto_transcribe_all_if_needed()
    refresh_all_widgets_from_papers(st, st.session_state.papers, c.question_count)

    ocr_settings_panel()

    idx = int(
        st.number_input(
            "Работа №",
            min_value=1,
            max_value=len(st.session_state.papers),
            value=1,
            key="transcribe_paper_idx",
        )
    )
    paper = st.session_state.papers[idx - 1]

    filled = sum(1 for v in paper.answers.values() if str(v).strip())
    if paper.surname or paper.name or filled:
        st.success(
            f"**{paper.surname} {paper.name}** — заполнено ответов: {filled}/{c.question_count}"
        )
    else:
        st.warning(
            "Поля пустые. Загрузите JSON на шаге 1 или заполните вручную / через OCR."
        )

    ocr_col1, ocr_col2 = st.columns(2)
    with ocr_col1:
        if st.button("Распознать эту работу (OCR)", key="ocr_one"):
            with st.spinner(f"Распознавание {paper.file}…"):
                try:
                    run_ocr_for_paper(paper)
                    st.success("Готово — проверьте поля и спорные ячейки.")
                    st.rerun()
                except TranscriptionError as exc:
                    st.error(str(exc))
    with ocr_col2:
        if st.button("Распознать все работы", key="ocr_all"):
            progress = st.progress(0.0, text="Распознавание…")
            errors: list[str] = []
            total = len(st.session_state.papers)
            for i, p in enumerate(st.session_state.papers):
                progress.progress((i) / total, text=f"{p.file} ({i + 1}/{total})")
                try:
                    run_ocr_for_paper(p)
                except TranscriptionError as exc:
                    errors.append(f"{p.file}: {exc}")
            progress.progress(1.0, text="Готово")
            st.session_state.auto_ocr_done = True
            if errors:
                st.error("Ошибки:\n" + "\n".join(f"- {e}" for e in errors))
            else:
                st.success(f"Распознано {total} работ — проверьте спорные ячейки.")
            st.rerun()

    if paper.uncertain:
        st.warning(f"Проверьте задания: **{paper.uncertain}** (модель не уверена)")

    st.caption(
        "Поля заполняются с бланка автоматически (если настроен OCR) "
        "или вручную. Все изменения сохраняются — можно править здесь."
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        img = st.session_state.images.get(paper.file)
        if img:
            show_scan_image(img, caption=paper.file)
    with col2:
        st.text_input("Фамилия", key=surname_key(paper.file))
        st.text_input("Имя", key=name_key(paper.file))
        st.text_area("Заметки", key=notes_key(paper.file))

        st.markdown(f"**Ответы (1–{c.question_count})**")
        cols = st.columns(5)
        for n in range(1, c.question_count + 1):
            col = cols[(n - 1) % 5]
            hint = st.session_state.answer_key.get(n, "")
            label = f"Q{n}"
            if n in paper.uncertain:
                label = f"Q{n} ⚠"
            col.text_input(
                label,
                key=answer_key(paper.file, n),
                help=f"Ключ: {hint}" if hint else None,
            )

        st.text_area("Замены (номер=ответ)", key=repl_key(paper.file), height=80)

    sync_paper_from_widgets(st, paper, c.question_count)
    st.session_state.papers[idx - 1] = paper

    if st.button("← Назад"):
        sync_all_papers(st, st.session_state.papers, c.question_count)
        st.session_state.step = 0
        st.rerun()
    if st.button("Далее → спорные", type="primary"):
        sync_all_papers(st, st.session_state.papers, c.question_count)
        st.session_state.step = 2
        st.rerun()


def step_disputes() -> None:
    st.header("Спорные моменты")
    c = cfg()
    any_flags = False
    for paper in st.session_state.papers:
        flags = find_disputes(paper, c.question_count)
        if flags:
            any_flags = True
            st.warning(f"**{paper.surname} {paper.name}** ({paper.file})")
            for f in flags:
                st.write(f"- {f}")
    if not any_flags:
        st.success("Явных спорных моментов нет.")

    if st.button("← Назад"):
        st.session_state.step = 1
        st.rerun()
    if st.button("Подсчитать баллы →", type="primary"):
        adapter = get_adapter(
            cfg(), st.session_state.answer_key, st.session_state.level_code
        )
        st.session_state.results = adapter.score_papers(st.session_state.papers)
        st.session_state.step = 3
        st.rerun()


def step_results() -> None:
    st.header("Результаты")
    results = st.session_state.results
    if not results:
        st.info("Сначала выполните подсчёт.")
        return

    c = cfg()
    stats = results_summary_stats(results)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Работ", stats["count"])
    m2.metric("Fail", stats["fail"])
    m3.metric("Pass", stats["pass"])
    m4.metric("Pass +", stats["pass_plus"])
    m5.metric("Средний балл", f"{stats['avg']:.1f}")

    st.subheader("Сводная таблица")
    table_rows = results_table_rows(results, c)
    try:
        import pandas as pd

        st.dataframe(
            pd.DataFrame(table_rows),
            use_container_width=True,
            hide_index=True,
        )
    except TypeError:
        st.table(table_rows)
    except ImportError:
        st.table(table_rows)

    st.subheader("Ошибки по работе")
    sel = st.selectbox(
        "Выберите работу",
        range(len(results)),
        format_func=lambda i: (
            f"{results[i].paper.surname} {results[i].paper.name} — "
            f"{results[i].total} ({results[i].grade})"
        ),
        label_visibility="collapsed",
    )
    r = results[sel]
    sec_parts = [
        f"**{section_column_name(s.id, s.label)}**={r.sections.get(s.id, 0)}"
        for s in c.sections
    ]
    st.caption(" · ".join(sec_parts) + f" · **Σ={r.total}** · {r.grade}")

    for err in r.errors:
        st.markdown(
            f"- **Q{err.number}**: `{err.student}` | ключ `{err.key}` | **{err.points}**"
            + (f" _{err.detail}_" if err.detail else "")
        )
    if not r.errors:
        st.success("Без ошибок.")

    with st.expander("Текстовый отчёт (как раньше)"):
        st.code(format_summary(results, c.title), language=None)
        st.code(format_errors_detailed(results), language=None)

    if st.button("← Назад"):
        st.session_state.step = 2
        st.rerun()
    if st.button("Далее → экспорт", type="primary"):
        st.session_state.step = 4
        st.rerun()


def step_export() -> None:
    st.header("Экспорт")
    results = st.session_state.results
    if not results:
        return

    adapter = get_adapter(cfg(), st.session_state.answer_key, st.session_state.level_code)

    st.download_button(
        "Сводка (.txt)",
        format_summary(results, cfg().title).encode("utf-8"),
        "verification_summary.txt",
    )
    st.download_button(
        "Ошибки (.txt)",
        format_errors_detailed(results).encode("utf-8"),
        "errors_detailed.txt",
    )
    st.download_button("CSV", results_to_csv_bytes(results), "scores.csv")

    if st.session_state.template_bytes:
        with tempfile.TemporaryDirectory() as td:
            tpath = Path(td) / st.session_state.template_name
            outpath = Path(td) / "analysis_filled.xls"
            tpath.write_bytes(st.session_state.template_bytes)
            adapter.fill_template(tpath, st.session_state.papers, outpath)
            st.download_button(
                "Таблица анализа (.xls)",
                outpath.read_bytes(),
                "analysis_filled.xls",
            )

    st.download_button(
        "Данные бланков (.json)",
        json.dumps([p.to_raw() for p in st.session_state.papers], ensure_ascii=False, indent=2).encode(
            "utf-8"
        ),
        "papers.json",
    )
    st.download_button(
        "Config сессии (.json)",
        json.dumps(cfg().to_dict(), ensure_ascii=False, indent=2).encode("utf-8"),
        "session_config.json",
    )

    if st.button("← К результатам"):
        st.session_state.step = 3
        st.rerun()


def main() -> None:
    init_state()
    sidebar_nav()
    [step_upload, step_transcribe, step_disputes, step_results, step_export][
        st.session_state.step
    ]()


if __name__ == "__main__":
    main()
