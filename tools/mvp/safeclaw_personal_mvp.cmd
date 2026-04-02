@echo off
setlocal
python -X utf8 "%~dp0safeclaw_personal_mvp.py" %*
exit /b %ERRORLEVEL%
