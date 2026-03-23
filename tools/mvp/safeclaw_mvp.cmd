@echo off
setlocal
pushd "%~dp0\..\.."
python tools\mvp\safeclaw_mvp.py %*
set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%
