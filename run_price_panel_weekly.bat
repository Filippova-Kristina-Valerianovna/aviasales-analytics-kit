@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "CONDA_BAT=C:\Anaconda\condabin\conda.bat"
set "ENV_NAME=aviasales-analytics"

cd /d "%PROJECT_DIR%"

if not exist "logs" mkdir "logs"

call "%CONDA_BAT%" run -n "%ENV_NAME%" python src\collect_price_panel.py >> logs\price_panel_weekly.log 2>&1
call "%CONDA_BAT%" run -n "%ENV_NAME%" python src\prepare_price_panel.py >> logs\price_panel_weekly.log 2>&1

echo. >> logs\price_panel_weekly.log
echo ================================================== >> logs\price_panel_weekly.log
echo Run finished: %date% %time% >> logs\price_panel_weekly.log
echo ================================================== >> logs\price_panel_weekly.log

endlocal