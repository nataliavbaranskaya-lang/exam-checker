# Exam Checker — user guide

Desktop app for grading handwritten English exam sheets (macOS / Windows).

## Run

```bash
pip install -r exam_checker/requirements.txt
python exam_checker/desktop/launch.py
```

Or double-click:
- **macOS:** `exam_checker/desktop/Exam Checker.command`
- **Windows:** `exam_checker/desktop/Exam Checker.bat`

## Workflow

1. **Upload** — scans (PNG/JPG/PDF/HEIC), answer key, Excel template (`.xls`)
2. **Transcribe** — enter answers manually or use optional Vision API OCR
3. **Disputes** — review missing names, empty cells, corrections
4. **Results** — scores, section breakdown, per-question errors
5. **Export** — filled spreadsheet, CSV, text reports, JSON

## Demo data

- `examples/sample_key.json` — 10-question demo key
- `examples/sample_papers.json` — two anonymized papers

## Optional OCR

Copy `.env.example` to `.env` in the project root and add `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`.

## Presets

| Preset | Questions |
|--------|-----------|
| Level A | 35 |
| Level B | 45 |
| Level C | 60 |
| Custom | editable in UI |

Answer key alternatives separated by `/` are scored automatically.
