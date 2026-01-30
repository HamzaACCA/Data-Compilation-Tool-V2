@echo off
color 0A
title Building Professional Installer - Data Analytical and Compilation Tool

echo.
echo ============================================================
echo.
echo      PROFESSIONAL INSTALLER BUILDER
echo      Data Analytical and Compilation Tool v1.0
echo.
echo ============================================================
echo.
echo This will create a single-file installer that:
echo   - Installs the software
echo   - Creates desktop icon
echo   - Creates start menu entry
echo   - Professional uninstaller
echo.
echo ============================================================
echo.
pause

echo.
echo [STEP 1/4] Checking requirements...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed!
    pause
    exit /b 1
)
echo   OK: Python found

REM Check if Inno Setup is installed
if not exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    echo.
    echo WARNING: Inno Setup not found!
    echo.
    echo Please install Inno Setup from:
    echo https://jrsoftware.org/isdl.php
    echo.
    echo After installing, run this script again.
    echo.
    pause
    exit /b 1
)
echo   OK: Inno Setup found

echo.
echo [STEP 2/4] Installing Python dependencies...
echo.
pip install --quiet flask pandas openpyxl werkzeug pywebview pyinstaller
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo   OK: Dependencies installed

echo.
echo [STEP 3/4] Building executable...
echo (This takes 3-5 minutes, please wait...)
echo.

REM Clean previous builds
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

REM Build the executable (using python -m to avoid PATH issues)
python -m PyInstaller --clean data_compilation.spec

if not exist "dist\DataCompilationTool.exe" (
    echo.
    echo ERROR: Failed to build executable!
    pause
    exit /b 1
)
echo   OK: Executable built successfully

echo.
echo [STEP 4/4] Creating installer...
echo.

REM Create installer output directory
if not exist "installer_output" mkdir installer_output

REM Build installer with Inno Setup
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer_config.iss

if not exist "installer_output\DataCompilationTool_Setup.exe" (
    echo.
    echo ERROR: Failed to create installer!
    pause
    exit /b 1
)

echo.
echo ============================================================
echo.
echo              BUILD SUCCESSFUL!
echo.
echo ============================================================
echo.
echo Your professional installer is ready:
echo.
echo   Location: installer_output\DataCompilationTool_Setup.exe
echo.

REM Get file size
for %%A in (installer_output\DataCompilationTool_Setup.exe) do (
    set size=%%~zA
    set /a sizeMB=%%~zA/1024/1024
)
echo   Size: %sizeMB% MB
echo.
echo ============================================================
echo.
echo WHAT YOU CAN DO NOW:
echo.
echo 1. TEST THE INSTALLER:
echo    - Run: installer_output\DataCompilationTool_Setup.exe
echo    - Test installation on your machine first
echo.
echo 2. DISTRIBUTE TO CUSTOMERS:
echo    - Share the DataCompilationTool_Setup.exe file
echo    - Users just double-click to install
echo    - Desktop icon created automatically
echo.
echo 3. SELL YOUR SOFTWARE:
echo    - Upload to your website
echo    - Sell on software marketplaces
echo    - Send to customers via email
echo.
echo ============================================================
echo.

REM Open the output folder
explorer installer_output

echo Press any key to exit...
pause >nul
