@echo off
setlocal
set "TOOLCHAIN=stable-x86_64-pc-windows-gnu"
set "RUSTUP_TOOLCHAIN=%TOOLCHAIN%"
set "CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER=C:\Users\tianduan999\AppData\Local\Microsoft\WinGet\Packages\BrechtSanders.WinLibs.POSIX.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe\mingw64\bin\x86_64-w64-mingw32-gcc.exe"
pushd "%~dp0\..\.."
if "%~1"=="" (
    cargo +%TOOLCHAIN% run -p safeclaw-sqlite --example safeclaw_mvp_entry --quiet -- --help
) else (
    cargo +%TOOLCHAIN% run -p safeclaw-sqlite --example safeclaw_mvp_entry --quiet -- %*
)
set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%
