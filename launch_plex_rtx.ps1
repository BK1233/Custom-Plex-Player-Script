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

# 5. Bootstrap mpv.exe if missing
$mpvInCwd = Test-Path "$Home\PlexRTXPlayer\mpv.exe"
$mpvInPath = Get-Command "mpv.exe" -ErrorAction SilentlyContinue

if (-not $mpvInCwd -and -not $mpvInPath) {
    $standardPaths = @(
        "C:\Program Files\mpv\mpv.exe",
        "C:\Program Files (x86)\mpv\mpv.exe",
        "C:\Program Files\mpv-player\mpv.exe",
        "C:\Program Files (x86)\mpv-player\mpv.exe",
        "C:\mpv\mpv.exe",
        "$env:LOCALAPPDATA\Programs\mpv\mpv.exe",
        "$env:LOCALAPPDATA\Programs\mpv-player\mpv.exe"
    )

    $foundStandard = $false
    foreach ($path in $standardPaths) {
        if (Test-Path $path) {
            $foundStandard = $true
            break
        }
    }

    if (-not $foundStandard) {
        Write-Host "mpv.exe was not detected in system PATH or standard folders." -ForegroundColor Yellow
        Write-Host "Attempting to install modern MPV automatically via Windows Package Manager (winget)..." -ForegroundColor Yellow

        $wingetInstalled = $false
        try {
            & winget --version >$null 2>&1
            if ($LastExitCode -eq 0) {
                Write-Host "winget detected. Installing MPV..." -ForegroundColor Gray
                & winget install -e --id mpv.mpv --silent --accept-source-agreements --accept-package-agreements
                if ($LastExitCode -eq 0) {
                    Write-Host "[OK] MPV has been successfully installed via winget!" -ForegroundColor Green
                    $wingetInstalled = $true
                }
            }
        } catch {
            Write-Host "[WARNING] Automated winget installation failed: $_" -ForegroundColor Yellow
        }

        if (-not $wingetInstalled) {
            Write-Host "Falling back to downloading precompiled binary..." -ForegroundColor Yellow
            try {
                $releasesUrl = "https://api.github.com/repos/zhongfly/mpv-winbuild/releases/latest"
                $releaseData = Invoke-RestMethod -Uri $releasesUrl -Headers @{"User-Agent"="Mozilla/5.0"}

                $asset = $releaseData.assets | Where-Object { $_.name -like "*x86_64*.7z" -and $_.name -notlike "*dev*" } | Select-Object -First 1
                if ($asset) {
                    $downloadUrl = $asset.browser_download_url
                    $fileName = $asset.name

                    Write-Host "Downloading $fileName..." -ForegroundColor Gray
                    Invoke-WebRequest -Uri $downloadUrl -OutFile $fileName -ErrorAction Stop

                    Write-Host "Extracting mpv.exe..." -ForegroundColor Gray
                    # Use 7zip if available, or fallback to native tar (modern Windows 11 builds support 7z natively)
                    if (Get-Command "7z" -ErrorAction SilentlyContinue) {
                        & 7z e $fileName "mpv.exe" -y | Out-Null
                    } else {
                        tar -xf $fileName --wildcards "*mpv.exe" -C .
                    }

                    Remove-Item -Path $fileName -Force -ErrorAction SilentlyContinue

                    if (Test-Path "mpv.exe") {
                        Write-Host "[OK] MPV has been successfully bootstrapped locally." -ForegroundColor Green
                    } else {
                        # Find and move nested mpv.exe to root if needed
                        $nestedMpv = Get-ChildItem -Path . -Filter "mpv.exe" -Recurse | Select-Object -First 1
                        if ($nestedMpv) {
                            Move-Item -Path $nestedMpv.FullName -Destination "." -Force
                            Write-Host "[OK] MPV has been successfully bootstrapped locally (nested fallback)." -ForegroundColor Green
                        } else {
                            throw "Could not find extracted mpv.exe"
                        }
                    }
                } else {
                    throw "No suitable x86_64 asset found in latest release."
                }
            } catch {
                Write-Host "[WARNING] Automated MPV download fallback failed: $_" -ForegroundColor Yellow
                Write-Host "Please download MPV manually from: https://mpv.io/" -ForegroundColor Yellow
                Write-Host "Extract and place 'mpv.exe' directly inside: $Home\PlexRTXPlayer" -ForegroundColor Yellow
                Write-Host ""
            }
        }
    }
}
}

# 6. Launch the application
Write-Host ""
Write-Host "===================================================" -ForegroundColor Green
Write-Host "   Launching Plex RTX Player!" -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Green
Write-Host ""

& python plex_rtx_gui.py
