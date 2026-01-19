@echo off
color 0A
title Fix PyInstaller and Build Installer

echo.
echo ============================================================
echo           FIXING PYINSTALLER ISSUE
echo ============================================================
echo.
echo Installing PyInstaller and all dependencies...
echo.

REM Install PyInstaller with user flag to avoid permission issues
pip install --user pyinstaller flask pandas openpyxl werkzeug pywebview

if errorlevel 1 (
    echo.
    echo Trying alternative installation method...
    python -m pip install --user pyinstaller flask pandas openpyxl werkzeug pywebview
)

echo.
echo ============================================================
echo Testing PyInstaller installation...
echo ============================================================
echo.

python -m PyInstaller --version

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller still not working.
    echo.
    echo Please try:
    echo 1. Close this window
    echo 2. Open NEW Command Prompt as Administrator
    echo 3. Run: pip install pyinstaller
    echo 4. Run this script again
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   SUCCESS! PyInstaller is now installed!
echo ============================================================
echo.
echo Now building your installer...
echo.
pause

REM Now run the actual build
call BUILD_INSTALLER.bat

exit /b 0
