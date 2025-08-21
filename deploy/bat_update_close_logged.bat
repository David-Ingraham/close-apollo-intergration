@echo off
echo Starting Close CRM update at %date% %time% > scheduler_log.txt
cd /d "C:\close_apollo_integration"
call venv\Scripts\activate.bat
python update_close_leads.py >> scheduler_log.txt 2>&1
echo Finished Close CRM update at %date% %time% >> scheduler_log.txt
echo Return code: %ERRORLEVEL% >> scheduler_log.txt
