@echo off
setlocal
set "SAFECLAW_MVP_DISPLAY_ENTRY=safeclaw.cmd"
call tools\mvp\safeclaw_mvp.cmd %*
exit /b %ERRORLEVEL%
