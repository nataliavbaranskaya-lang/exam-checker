#!/bin/bash
# Exam Checker — macOS
cd "$(dirname "$0")/../.."
python3 -m pip install -q -r exam_checker/requirements.txt 2>/dev/null
python3 exam_checker/desktop/launch.py
