@echo off
setlocal

cd /d "%~dp0"

if not exist "logs" mkdir logs

echo ================================================== >> logs\daily_pipeline.log
echo [%date% %time%] Daily price pipeline started >> logs\daily_pipeline.log

call "C:\Anaconda\condabin\conda.bat" run -n aviasales-analytics python src\collect_price_panel.py >> logs\daily_pipeline.log 2>&1
set COLLECT_EXIT_CODE=%ERRORLEVEL%

if not "%COLLECT_EXIT_CODE%"=="0" (
    echo [%date% %time%] ERROR: collector failed. Exit code: %COLLECT_EXIT_CODE% >> logs\daily_pipeline.log
    exit /b %COLLECT_EXIT_CODE%
)

call "C:\Anaconda\condabin\conda.bat" run -n aviasales-analytics python src\load_price_panel_to_postgres.py >> logs\daily_pipeline.log 2>&1
set LOAD_EXIT_CODE=%ERRORLEVEL%

if not "%LOAD_EXIT_CODE%"=="0" (
    echo [%date% %time%] ERROR: PostgreSQL loader failed. Exit code: %LOAD_EXIT_CODE% >> logs\daily_pipeline.log
    exit /b %LOAD_EXIT_CODE%
)

echo [%date% %time%] Running dbt data tests >> logs\daily_pipeline.log

call "%~dp0dbt_local.bat" test >> logs\daily_pipeline.log 2>&1
set DBT_EXIT_CODE=%ERRORLEVEL%

if not "%DBT_EXIT_CODE%"=="0" (
    echo [%date% %time%] ERROR: dbt tests failed. Exit code: %DBT_EXIT_CODE% >> logs\daily_pipeline.log
    exit /b %DBT_EXIT_CODE%
)

echo [%date% %time%] dbt data tests completed successfully >> logs\daily_pipeline.log


echo [%date% %time%] Daily price pipeline completed successfully >> logs\daily_pipeline.log
endlocal
exit /b 0