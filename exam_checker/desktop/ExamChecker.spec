# -*- mode: python ; coding: utf-8 -*-
# Сборка standalone-приложения (опционально):
#   pip install pyinstaller
#   pyinstaller exam_checker/desktop/ExamChecker.spec

import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parents[1]

a = Analysis(
    [str(ROOT / 'exam_checker' / 'desktop' / 'launch.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / 'exam_checker' / 'app.py'), 'exam_checker'),
        (str(ROOT / 'exam_checker' / 'presets'), 'exam_checker/presets'),
        (str(ROOT / 'exam_checker' / 'assets'), 'exam_checker/assets'),
        (str(ROOT / 'exam_checker' / 'core'), 'exam_checker/core'),
    ],
    hiddenimports=['streamlit', 'altair', 'pandas', 'xlrd', 'xlwt', 'xlutils', 'olefile', 'PIL'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Exam-Checker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Exam-Checker',
)
