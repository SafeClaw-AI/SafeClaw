@echo off
setlocal
call tools\mvp\safeclaw_mvp.cmd %*
exit /b %ERRORLEVEL%
