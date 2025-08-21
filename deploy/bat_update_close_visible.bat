@echo off
cd /d "C:\close_apollo_integration"
call venv\Scripts\activate.bat
python test.py
echo Script completed. Window will close in 5 seconds...
timeout /t 5 /nobreak >nul
