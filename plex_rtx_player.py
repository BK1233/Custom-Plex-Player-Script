#!/usr/bin/env python3
"""
Plex RTX Player Module
Handles calculations and launching logic for MPV with Nvidia RTX VSR and RTX HDR.
"""

import math
import subprocess
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PlexRTXPlayer")

class PlexRTXPlayer:
    def __init__(self, mpv_path="mpv.exe", display_width=3840, display_height=2160):
        """
        Initialize the RTX Player manager.
        :param mpv_path: Path to the mpv executable.
        :param display_width: Width of the display target (default 3840 for 4K).
        :param display_height: Height of the display target (default 2160 for 4K).
        """
        self.display_width = display_width
        self.display_height = display_height
        self.configured_mpv_path = mpv_path

    def _resolve_mpv_path(self, mpv_path):
        """
        Locates mpv.exe automatically across common Windows paths if not found on the default PATH.
        """
        # If user specified a custom path (e.g., in environment variables) and it exists, use it.
        if mpv_path and mpv_path != "mpv.exe":
            if os.path.exists(mpv_path):
                return mpv_path

        # 1. Check if mpv.exe is in the system PATH
        try:
            import shutil
            found_path = shutil.who("mpv.exe") or shutil.who("mpv")
            if found_path:
                logger.info(f"Automatically detected mpv in system PATH: {found_path}")
                return found_path
        except Exception:
            pass

        # 2. Check local running directory
        local_dir = os.path.dirname(os.path.abspath(__file__))
        local_mpv = os.path.join(local_dir, "mpv.exe")
        if os.path.exists(local_mpv):
            logger.info(f"Automatically detected mpv in local folder: {local_mpv}")
            return local_mpv

        # 3. Check current working directory
        cwd_mpv = os.path.join(os.getcwd(), "mpv.exe")
        if os.path.exists(cwd_mpv):
            logger.info(f"Automatically detected mpv in current working directory: {cwd_mpv}")
            return cwd_mpv

        # 4. Check standard system app execution aliases (where winget and modern apps register shims)
        app_aliases = [
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\mpv.exe"),
            r"C:\mpv\mpv.exe"
        ]
        for path in app_aliases:
            if os.path.exists(path):
                logger.info(f"Automatically detected mpv in WindowsApps/alias: {path}")
                return path

        # 5. Robust dynamic scanner for any folder containing "mpv" under standard directories
        search_roots = [
            r"C:\Program Files",
            r"C:\Program Files (x86)",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs"),
            os.path.expandvars(r"%APPDATA%")
        ]
        for root in search_roots:
            if os.path.exists(root):
                try:
                    for folder_name in os.listdir(root):
                        if "mpv" in folder_name.lower():
                            subfolder = os.path.join(root, folder_name)
                            if os.path.isdir(subfolder):
                                candidate = os.path.join(subfolder, "mpv.exe")
                                if os.path.exists(candidate):
                                    logger.info(f"Automatically scanned and found mpv.exe: {candidate}")
                                    return candidate
                except Exception:
                    pass

        # Fallback to the original value if not found (letting standard execution report the error)
        return mpv_path

    def calculate_scale_factor(self, video_width, video_height):
        """
        Calculate scale factor based on video size and display size.
        Returns the scale factor rounded to 1 decimal place.
        """
        if not video_width or not video_height or not self.display_width or not self.display_height:
            return 1.0

        scale_w = self.display_width / video_width
        scale_h = self.display_height / video_height

        # We take the maximum of width/height scaling to ensure we upscale to fit
        scale = max(scale_w, scale_h)
        # Round to nearest 0.1 for MPV compatibility
        scale = math.floor(scale * 10) / 10
        return max(1.0, scale)

    def build_rtx_filter(self, video_width, video_height, is_sdr=True, enable_vsr=True, enable_hdr=True):
        """
        Builds the d3d11vpp filter string for MPV based on RTX features.
        """
        scale = self.calculate_scale_factor(video_width, video_height)
        use_vsr = enable_vsr and (scale > 1.0)
        use_hdr = enable_hdr and is_sdr

        filter_parts = []
        if use_vsr and use_hdr:
            # Combined VSR + RTX HDR
            filter_parts.append(f"d3d11vpp=scaling-mode=nvidia:scale={scale}:format=x2bgr10:nvidia-true-hdr")
        elif use_vsr:
            # VSR only
            filter_parts.append(f"d3d11vpp=scaling-mode=nvidia:scale={scale}")
        elif use_hdr:
            # RTX HDR only
            filter_parts.append("d3d11vpp=format=x2bgr10:nvidia-true-hdr")

        return filter_parts, scale, use_vsr, use_hdr

    def get_mpv_arguments(self, video_url, video_width=None, video_height=None, is_sdr=True,
                          enable_vsr=True, enable_hdr=True, extra_args=None):
        """
        Build complete command line arguments for running MPV with RTX enabled.
        """
        resolved_mpv = self._resolve_mpv_path(self.configured_mpv_path)
        # Base requirements for RTX enhancements on Windows 11
        args = [
            resolved_mpv,
            "--vo=gpu-next",          # Or gpu, gpu-next is recommended for modern features
            "--gpu-api=d3d11",        # Required for Nvidia d3d11vpp
            "--hwdec=d3d11va",        # Required for direct hardware decoding with d3d11vpp
            "--fs",                   # Start in fullscreen by default
        ]

        filters, scale, use_vsr, use_hdr = self.build_rtx_filter(
            video_width, video_height, is_sdr, enable_vsr, enable_hdr
        )

        # Apply output color space for RTX HDR if active
        if use_hdr:
            args.append("--d3d11-output-csp=srgb")

        # Apply generated filters
        for f in filters:
            args.append(f"--vf={f}")

        # Add any user specific extra arguments
        if extra_args:
            args.extend(extra_args)

        # Add the video target URL / file path
        args.append(video_url)

        return args, {
            "scale": scale,
            "vsr_active": use_vsr,
            "rtx_hdr_active": use_hdr,
            "filters": filters
        }

    def launch_mpv(self, video_url, video_width=None, video_height=None, is_sdr=True,
                   enable_vsr=True, enable_hdr=True, extra_args=None):
        """
        Launch MPV with RTX enhancements in a non-blocking subprocess.
        """
        args, info = self.get_mpv_arguments(
            video_url, video_width, video_height, is_sdr, enable_vsr, enable_hdr, extra_args
        )

        logger.info(f"Launching MPV with RTX options: {info}")
        logger.info(f"Command line: {' '.join(args)}")

        resolved_mpv = args[0]
        try:
            # Launch without blocking the main thread and avoid pipe buffer deadlocks
            process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return process, info
        except FileNotFoundError:
            logger.error(f"Could not find MPV at '{resolved_mpv}'. Please ensure 'mpv.exe' is placed in your C:\\Users\\<username>\\PlexRTXPlayer folder or added to your system PATH.")
            raise
        except Exception as e:
            logger.error(f"Error launching MPV: {e}")
            raise

if __name__ == "__main__":
    # Quick self-test / CLI mode
    if len(sys.argv) < 2:
        print("Usage: python plex_rtx_player.py <video_url> [video_width] [video_height]")
        sys.exit(1)

    url = sys.argv[1]
    width = int(sys.argv[2]) if len(sys.argv) > 2 else 1920
    height = int(sys.argv[3]) if len(sys.argv) > 3 else 1080

    player = PlexRTXPlayer()
    args, info = player.get_mpv_arguments(url, width, height, is_sdr=True)
    print("Computed MPV Arguments:")
    for arg in args:
        print(f"  {arg}")
    print("\nRTX Detection Info:")
    print(info)
