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
        self.mpv_path = mpv_path
        self.display_width = display_width
        self.display_height = display_height

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
        # Base requirements for RTX enhancements on Windows 11
        args = [
            self.mpv_path,
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

        try:
            # Launch without blocking the main thread
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return process, info
        except FileNotFoundError:
            logger.error(f"Could not find MPV at '{self.mpv_path}'. Please ensure it is installed and in your PATH.")
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
