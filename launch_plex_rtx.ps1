# PowerShell Launcher for Plex RTX Player
# Automatically verifies Python, downloads latest player scripts from GitHub,
# installs required dependencies, and starts the application.

$Host.UI.RawUI.WindowTitle = "Plex RTX Player Launcher"

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "   Plex RTX Player Launcher - Windows 11 (PowerShell)" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Verify Python installation
try {
    $pythonVer = & python --version 2>&1
    Write-Host "[OK] Python detected: $pythonVer" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python is not installed or not in your PATH." -ForegroundColor Red
    Write-Host "Please download and install Python from: https://www.python.org/" -ForegroundColor Yellow
    Write-Host "Ensure you check 'Add python.exe to PATH' during installation." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit..."
    Exit 1
}

# 2. Setup run directory
$runDir = "$Home\PlexRTXPlayer"
if (-not (Test-Path $runDir)) {
    Write-Host "Creating application folder at: $runDir" -ForegroundColor Gray
    New-Item -ItemType Directory -Force -Path $runDir | Out-Null
}
Set-Location -Path $runDir

# 3. Download the latest scripts from GitHub
Write-Host "Downloading latest player scripts from GitHub..." -ForegroundColor Yellow
$repoRawUrl = "https://raw.githubusercontent.com/BK1233/Custom-Plex-Player-Script/main"

# Download player.py
Write-Host "Fetching plex_rtx_player.py..." -ForegroundColor Gray
try {
    Invoke-WebRequest -Uri "$repoRawUrl/plex_rtx_player.py" -OutFile "plex_rtx_player.py" -ErrorAction Stop
} catch {
    Write-Host "[WARNING] Failed to download from main branch. Trying implementation branch fallback..." -ForegroundColor Yellow
    try {
        Invoke-WebRequest -Uri "https://raw.githubusercontent.com/BK1233/Custom-Plex-Player-Script/rtx-plex-player-implementation/plex_rtx_player.py" -OutFile "plex_rtx_player.py" -ErrorAction Stop
    } catch {
        Write-Host "[ERROR] Failed to fetch plex_rtx_player.py. Please verify your internet connection." -ForegroundColor Red
        Read-Host "Press Enter to exit..."
        Exit 1
    }
}

# Download gui.py
Write-Host "Fetching plex_rtx_gui.py..." -ForegroundColor Gray
try {
    Invoke-WebRequest -Uri "$repoRawUrl/plex_rtx_gui.py" -OutFile "plex_rtx_gui.py" -ErrorAction Stop
} catch {
    Write-Host "[WARNING] Failed to download from main branch. Trying implementation branch fallback..." -ForegroundColor Yellow
    try {
        Invoke-WebRequest -Uri "https://raw.githubusercontent.com/BK1233/Custom-Plex-Player-Script/rtx-plex-player-implementation/plex_rtx_gui.py" -OutFile "plex_rtx_gui.py" -ErrorAction Stop
    } catch {
        Write-Host "[ERROR] Failed to fetch plex_rtx_gui.py. Please verify your internet connection." -ForegroundColor Red
        Read-Host "Press Enter to exit..."
        Exit 1
    }
}

Write-Host "[OK] Player scripts downloaded successfully." -ForegroundColor Green

# 4. Install dependencies
Write-Host "Installing required python packages (pywebview, plexapi, requests)..." -ForegroundColor Yellow
& python -m pip install --upgrade pip | Out-Null
& python -m pip install pywebview plexapi requests

if ($LastExitCode -ne 0) {
    Write-Host "[ERROR] Pip dependency installation failed." -ForegroundColor Red
    Read-Host "Press Enter to exit..."
    Exit 1
}

# 5. Launch the application
Write-Host ""
Write-Host "===================================================" -ForegroundColor Green
Write-Host "   Launching Plex RTX Player!" -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Green
Write-Host ""

& python plex_rtx_gui.py
