@echo off
REM ============================================================
REM  release.bat ? One-click: build + upload to GitHub Release
REM
REM  Setup (once):
REM    set GH_TOKEN=your_github_token
REM    git remote add origin https://github.com/yyx20040712/Graduation_design.git
REM
REM  Usage:
REM    release.bat v5.4-s6
REM ============================================================
setlocal enabledelayedexpansion

set "GH=%LOCALAPPDATA%\gh\bin\gh.exe"
set "SPEC=ddesign_tool.spec"
set "EXE=dist\ddesign_tool.exe"
set "REPO=yyx20040712/Graduation_design"

if not defined GH_TOKEN (
    echo [ERROR] GH_TOKEN not set. Run: set GH_TOKEN=your_token
    exit /b 1
)
if "%~1"=="" (
    echo [ERROR] Usage: release.bat v1.2.3
    exit /b 1
)
set "TAG=%~1"

REM -- 1. Build EXE --
echo [1/4] Building EXE ...
.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm %SPEC%
if errorlevel 1 (echo [ERROR] Build failed & exit /b 1)

REM -- 2. Generate release notes from recent commits --
echo [2/4] Generating notes ...
echo # %TAG% > release_notes.tmp
echo. >> release_notes.tmp
for /f "delims=" %%c in ('git log --oneline -5 2^>nul') do (
    echo - %%c >> release_notes.tmp
)

REM -- 3. Create Release --
echo [3/4] Creating Release ...
%GH% release create "%TAG%" --title "%TAG%" --notes-file release_notes.tmp --target main 2>nul

REM -- 4. Upload EXE --
echo [4/4] Uploading EXE ...
%GH% release upload "%TAG%" "%EXE%" --clobber
if errorlevel 1 (
    echo [ERROR] Upload failed
    del release_notes.tmp 2>nul
    exit /b 1
)

del release_notes.tmp 2>nul
echo.
echo Done: https://github.com/%REPO%/releases/tag/%TAG%
