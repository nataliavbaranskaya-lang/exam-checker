# Exam Checker

Private portfolio project — a **desktop grading app** for handwritten English exam answer sheets.

Built with **Python** and **Streamlit**. Demonstrates a full workflow: upload scans and answer key → transcribe answers → review disputes → score → export filled Excel report.

## Highlights (for recruiters)

- Multi-step **Streamlit** wizard with session state and side-by-side scan review
- **Configurable scoring engine** — any question count, sections, Pass/Fail thresholds
- **Multi-format key parser** (DOC, DOCX, JSON, CSV, TXT, Python modules)
- **Excel template writer** that preserves existing `.xls` formatting
- Optional **Vision API** OCR (OpenAI / Anthropic) for handwriting
- Cross-platform launchers for **macOS** and **Windows**

## Quick start

```bash
pip install -r exam_checker/requirements.txt
python exam_checker/desktop/launch.py
```

Opens `http://localhost:8501` in your browser.

## Repository contents

| Path | Purpose |
|------|---------|
| `exam_checker/app.py` | Streamlit UI |
| `exam_checker/core/` | Scoring, keys, Excel export, reports, OCR |
| `exam_checker/presets/` | Demo level configs (35 / 45 / 60 questions) |
| `exam_checker/examples/` | Anonymized sample key + papers JSON |

**Not included:** real exam scans, student names, or production session data.

## Tech stack

Python 3.10+ · Streamlit · xlrd/xlwt/xlutils · Pillow · PyMuPDF · OpenAI / Anthropic SDK (optional)

## Author

Natalia Baranskaa

## License

MIT — see [LICENSE](LICENSE).
