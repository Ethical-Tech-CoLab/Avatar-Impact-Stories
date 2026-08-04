@echo off
REM Starts the Many Voices kiosk and opens it in your browser.
setlocal
cd /d "%~dp0"

where py >nul 2>&1 && (
    py -3 tools\serve.py %*
    goto :eof
)
where python >nul 2>&1 && (
    python tools\serve.py %*
    goto :eof
)

echo Python 3 was not found on this machine.
echo Install it from https://www.python.org/downloads/ and run start.cmd again.
pause
