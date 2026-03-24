@echo off
setlocal
pushd "%~dp0\..\.."

set "PYTHON_EXE="
if defined SAFECLAW_MVP_PYTHON if exist "%SAFECLAW_MVP_PYTHON%" set "PYTHON_EXE=%SAFECLAW_MVP_PYTHON%"
if not defined PYTHON_EXE for %%P in (python.exe) do if not "%%~$PATH:P"=="" set "PYTHON_EXE=%%~$PATH:P"
set "PY_LAUNCHER="
if not defined PYTHON_EXE for %%P in (py.exe) do if not "%%~$PATH:P"=="" set "PY_LAUNCHER=%%~$PATH:P"
if not defined PYTHON_EXE if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PYTHON_EXE=%CONDA_PREFIX%\python.exe"
if not defined PYTHON_EXE if exist "%USERPROFILE%\anaconda3\python.exe" set "PYTHON_EXE=%USERPROFILE%\anaconda3\python.exe"
if not defined PYTHON_EXE if exist "%USERPROFILE%\miniconda3\python.exe" set "PYTHON_EXE=%USERPROFILE%\miniconda3\python.exe"

if defined PYTHON_EXE goto run_python
if defined PY_LAUNCHER goto run_py_launcher
>&2 echo [mvp-wrapper] python resolver => error could not find python; set SAFECLAW_MVP_PYTHON or install python/py launcher
set "EXIT_CODE=9009"
goto done

:run_python
"%PYTHON_EXE%" tools\mvp\safeclaw_mvp.py %*
set "EXIT_CODE=%ERRORLEVEL%"
goto done

:run_py_launcher
"%PY_LAUNCHER%" -3 tools\mvp\safeclaw_mvp.py %*
set "EXIT_CODE=%ERRORLEVEL%"
goto done

:done
popd
exit /b %EXIT_CODE%
