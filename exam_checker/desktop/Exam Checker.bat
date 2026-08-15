@echo off
REM Exam Checker — Windows
cd /d "%~dp0..\.."
python -m pip install -q -r exam_checker\requirements.txt 2>nul
python exam_checker\desktop\launch.py
pause
