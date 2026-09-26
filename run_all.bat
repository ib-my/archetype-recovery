@echo off
REM Score every tree in output\trees and build the overall table.
cd /d "%~dp0"
python evaluator\score_evaluator.py || exit /b 1
python evaluator\overall_evaluator.py
