@echo off
:: One-click Windows Launcher for Plex RTX Player
:: Installs requirements, downloads raw player scripts from GitHub, and runs the application.

title Plex RTX Player Launcher

echo ===================================================
echo   Plex RTX Player Launcher - Windows 11
echo ===================================================
echo.

:: 1. Verify Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your PATH.
    echo Please download and install Python from: https://www.python.org/
    echo Make sure to check the box "Add python.exe to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: 2. Setup run directory
set "RUN_DIR=%USERPROFILE%\PlexRTXPlayer"
if not exist "%RUN_DIR%" (
    echo Creating application folder at: %RUN_DIR%
    mkdir "%RUN_DIR%"
)
cd /d "%RUN_DIR%"

:: 3. Download the latest scripts from GitHub
echo Downloading latest scripts from GitHub...
set "REPO_RAW_URL=https://raw.githubusercontent.com/user/Custom-Plex-Player-Script/main"

echo Fetching plex_rtx_player.py...
powershell -Command "Invoke-WebRequest -Uri '%REPO_RAW_URL%/plex_rtx_player.py' -OutFile 'plex_rtx_player.py'"
if %errorlevel% neq 0 (
    echo [WARNING] Failed to download from main branch. Attempting fallback...
    powershell -Command "Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/user/Custom-Plex-Player-Script/rtx-plex-player-implementation/plex_rtx_player.py' -OutFile 'plex_rtx_player.py'"
)

echo Fetching plex_rtx_gui.py...
powershell -Command "Invoke-WebRequest -Uri '%REPO_RAW_URL%/plex_rtx_gui.py' -OutFile 'plex_rtx_gui.py'"
if %errorlevel% neq 0 (
    echo [WARNING] Failed to download from main branch. Attempting fallback...
    powershell -Command "Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/user/Custom-Plex-Player-Script/rtx-plex-player-implementation/plex_rtx_gui.py' -OutFile 'plex_rtx_gui.py'"
)

if not exist "plex_rtx_player.py" (
    echo [ERROR] Failed to obtain the player scripts. Please check your internet connection.
    pause
    exit /b 1
)

:: 4. Install dependencies
echo Installing required python packages (pywebview, plexapi)...
python -m pip install --upgrade pip
python -m pip install pywebview plexapi requests python-mpv

:: 5. Launch the application
echo.
echo ===================================================
echo   Launching Plex RTX Player!
echo ===================================================
echo.
python plex_rtx_gui.py

pause
