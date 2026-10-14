@echo off
setlocal

call "C:\Anaconda\condabin\conda.bat" run --no-capture-output -n aviasales-dbt python "%~dp0run_dbt.py" %*

exit /b %errorlevel%