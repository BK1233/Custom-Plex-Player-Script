# Custom Plex Player for Windows 11 (with Nvidia RTX VSR & RTX HDR)

A high-performance custom Plex player for Windows 11 designed to leverage Nvidia's advanced **RTX Video Super Resolution (VSR)** upscaling and **RTX HDR** (SDR-to-HDR conversion) enhancements.

The player renders content through a native Windows 11 Direct3D 11 backend using an embedded, customizable MPV instance. It loads the official Plex Web App interface directly inside a secure window, allowing you to browse and manage your Plex libraries natively. When you click play, it automatically intercepts the media, queries the Plex server API for the highest-quality stream, calculates the ideal RTX upscaling filters based on your display's resolution, and opens a full-quality MPV player with active RTX processing.

---

## ⚡ Quick Start (No Repository Download Required)

To run the player instantly without downloading or cloning this repository, you can use the **Single-Click Windows Launcher**:

1. Ensure **Python 3** is installed on your Windows 11 machine. (If not, download it from [python.org](https://www.python.org/) and remember to check **"Add python.exe to PATH"** during installation).
2. Download the batch script directly:
   👉 **[Click here to download launch_plex_rtx.bat](https://raw.githubusercontent.com/user/Custom-Plex-Player-Script/main/launch_plex_rtx.bat)** *(or copy-paste its content to a file named `launch_plex_rtx.bat`)*.
3. Double-click **`launch_plex_rtx.bat`** to run. It will automatically download the player modules, install required dependencies, and launch the player!

---

## 🔧 Prerequisites & Requirements

To enable NVIDIA's RTX enhancements, ensure your system meets the following specifications:

1. **OS:** Windows 11 (build 22621 or newer).
2. **GPU:** NVIDIA GeForce RTX 20-series, 30-series, 40-series, or 50-series graphics card.
3. **Drivers:** Latest NVIDIA Game Ready or Studio drivers.
4. **NVIDIA App/Control Panel Configuration:**
   - Under **RTX Video Enhancements**, ensure both **Super Resolution** (VSR) and **RTX Video HDR** are enabled.
5. **Windows HDR:** Active in Windows display settings (required for RTX HDR SDR-to-HDR upconversion).
6. **MPV Player:**
   - Ensure a modern build of `mpv.exe` (minimum version `0.39` for VSR, `0.40+` for RTX HDR) is installed on your system.
   - You can download nightly builds from [mpv.io](https://mpv.io/) or [shinchiro's builds](https://sourceforge.net/projects/mpv-player-windows/files/64bit/).
   - Add `mpv.exe` to your Windows System PATH, or specify its exact path using the environment variable: `set MPV_PATH=C:\path\to\mpv.exe` before launching.

---

## 🚀 Technical Architecture & Features

### 1. Embedded WebView Interface
The application loads the clean, official Plex web frontend (`https://app.plex.tv/desktop`). It injects a highly optimized JavaScript event interceptor into the page:
- Overrides `HTMLVideoElement.prototype.play` to capture native SPA playback triggers.
- Automatically pauses and hides the default low-quality browser player.
- Extracts the user's active `myPlexAccessToken` and the item's routing metadata key.

### 2. Automatic RTX Enhancement Calculations
The Python backend connects to your Plex server via `plexapi` using the token to fetch full metadata for the target video. It analyzes the stream and your target display resolution:
- **RTX Video Super Resolution (VSR):** Calculates the exact required scale multiplier (`target_resolution / video_resolution`) and rounds it to the nearest `0.1` for compatibility. VSR is applied via the `d3d11vpp=scaling-mode=nvidia:scale=X` video filter.
- **RTX HDR:** Automatically detects whether the playing content is SDR or native HDR. If the video is SDR and Windows HDR is active, it injects the `nvidia-true-hdr` filter along with `--d3d11-output-csp=srgb` colorspace mapping to perform real-time, AI-powered SDR-to-HDR conversion. If the video is already native HDR, it passes through the native HDR metadata to prevent over-saturation.

---

## 🛠 Manual Installation & Developer Guide

If you prefer to run the codebase manually or customize the player:

### 1. Clone the repository
```bash
git clone https://github.com/user/Custom-Plex-Player-Script.git
cd Custom-Plex-Player-Script
```

### 2. Install Python dependencies
```bash
pip install pywebview plexapi requests python-mpv
```

### 3. Run the player
```bash
python plex_rtx_gui.py
```

### 4. Running the Tests
To verify all RTX calculations and stream-resolution mock logic, execute the unit test suite:
```bash
python -m unittest test_plex_rtx.py
```

---

## ⚙️ Environment Configuration

You can customize the player dynamically using Windows environment variables:

| Variable | Description | Default |
|---|---|---|
| `MPV_PATH` | Exact path to your custom `mpv.exe` executable | `mpv.exe` (searches PATH) |
| `DISPLAY_WIDTH` | Target width of your RTX monitor | `3840` (4K) |
| `DISPLAY_HEIGHT` | Target height of your RTX monitor | `2160` (4K) |

For example, to run on a 1440p monitor:
```cmd
set DISPLAY_WIDTH=2560
set DISPLAY_HEIGHT=1440
python plex_rtx_gui.py
```
