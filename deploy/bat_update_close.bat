@echo off
cd /d "C:\close_apollo_integration"
call venv\Scripts\activate.bat
python test.py
pause