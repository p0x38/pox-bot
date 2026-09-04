@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0.."

title Development Helper

REM --------------------------------------------------
REM Project information
REM --------------------------------------------------

set "PROJECT_NAME="

for /f "tokens=2 delims==" %%A in ('findstr /b "name =" pyproject.toml') do (
    set "PROJECT_NAME=%%~A"
)

if not defined PROJECT_NAME (
    set "PROJECT_NAME=Python Project"
)

echo ========================================
echo  %PROJECT_NAME% Development Helper
echo ========================================
echo.

REM --------------------------------------------------
REM Tool detection
REM --------------------------------------------------

echo [*] Checking development tools...

where py >nul 2>&1

if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=py"
    goto :python_found
)

where python >nul 2>&1

if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=python"
    goto :python_found
)

echo [!] Python was not found.
echo     Please install a supported Python version.
exit /b 1

:python_found

for /f "tokens=*" %%V in ('%PYTHON_CMD% --version 2^>^&1') do (
    echo [+] Python: %%V
)

where uv >nul 2>&1

if %ERRORLEVEL% NEQ 0 (
    echo [!] uv was not found.
    echo     Please install uv and try again.
    exit /b 1
)

for /f "tokens=*" %%V in ('uv --version') do (
    echo [+] uv: %%V
)

echo.

REM --------------------------------------------------
REM Menu
REM --------------------------------------------------

:menu

echo.
echo ========================================
echo  Development Menu
echo ========================================
echo.
echo  1^) Sync environment
echo  2^) Lint
echo  3^) Format check
echo  4^) Format
echo  5^) Type check
echo  6^) Test
echo  7^) Run all checks
echo  8^) Build package
echo  9^) Show tool versions
echo  0^) Exit
echo.

set "choice="
set /p "choice=Select an option: "

if "%choice%"=="1" goto :sync
if "%choice%"=="2" goto :lint
if "%choice%"=="3" goto :format_check
if "%choice%"=="4" goto :format
if "%choice%"=="5" goto :typecheck
if "%choice%"=="6" goto :test
if "%choice%"=="7" goto :all
if "%choice%"=="8" goto :build
if "%choice%"=="9" goto :versions
if "%choice%"=="0" goto :exit

echo.
echo [!] Invalid option.
goto :pause_menu

REM --------------------------------------------------
REM Commands
REM --------------------------------------------------

:sync

echo.
echo ----------------------------------------
echo [^>] uv sync
echo ----------------------------------------
echo.

uv sync
if errorlevel 1 goto :failed

echo.
echo [+] Environment synchronized.
goto :pause_menu


:lint

echo.
echo ----------------------------------------
echo [^>] uv run ruff check .
echo ----------------------------------------
echo.

uv run ruff check .
if errorlevel 1 goto :failed

echo.
echo [+] Lint passed.
goto :pause_menu


:format_check

echo.
echo ----------------------------------------
echo [^>] uv run ruff format --check .
echo ----------------------------------------
echo.

uv run ruff format --check .
if errorlevel 1 goto :failed

echo.
echo [+] Format check passed.
goto :pause_menu


:format

echo.
echo ----------------------------------------
echo [^>] uv run ruff format .
echo ----------------------------------------
echo.

uv run ruff format .
if errorlevel 1 goto :failed

echo.
echo [+] Formatting completed.
goto :pause_menu


:typecheck

echo.
echo ----------------------------------------
echo [^>] uv run pyright
echo ----------------------------------------
echo.

uv run pyright
if errorlevel 1 goto :failed

echo.
echo [+] Type check passed.
goto :pause_menu


:test

echo.
echo ----------------------------------------
echo [^>] uv run pytest
echo ----------------------------------------
echo.

uv run pytest
if errorlevel 1 goto :failed

echo.
echo [+] Tests passed.
goto :pause_menu


:all

echo.
echo ========================================
echo  Running all checks
echo ========================================
echo.

echo [1/5] Sync environment...
uv sync
if errorlevel 1 goto :failed

echo.
echo [2/5] Ruff...
uv run ruff check .
if errorlevel 1 goto :failed

echo.
echo [3/5] Format check...
uv run ruff format --check .
if errorlevel 1 goto :failed

echo.
echo [4/5] Pyright...
uv run pyright
if errorlevel 1 goto :failed

echo.
echo [5/5] Pytest...
uv run pytest
if errorlevel 1 goto :failed

echo.
echo ========================================
echo  All checks passed!
echo ========================================
goto :pause_menu


:build

echo.
echo ----------------------------------------
echo [^>] uv build
echo ----------------------------------------
echo.

uv build
if errorlevel 1 goto :failed

echo.
echo [+] Package built successfully.
goto :pause_menu


:versions

echo.
echo Python:
%PYTHON_CMD% --version

echo.
echo uv:
uv --version

echo.
echo Project Python:
uv run python --version

goto :pause_menu


REM --------------------------------------------------
REM Error handling
REM --------------------------------------------------

:failed

set "STATUS=%ERRORLEVEL%"

echo.
echo ========================================
echo  Command failed
echo ========================================
echo.
echo Exit code: %STATUS%

goto :pause_menu


:pause_menu

echo.
pause
goto :menu


:exit

echo.
echo Bye!
exit /b 0
