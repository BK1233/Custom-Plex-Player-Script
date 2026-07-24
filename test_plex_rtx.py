#!/usr/bin/env python3
"""
Unit and Mock Tests for Plex RTX Player and GUI.
Verifies RTX video filter construction, scaling calculation,
URL parsing, and player launching logic.
"""

import unittest
from unittest.mock import MagicMock, patch
import sys

# Import our modules
from plex_rtx_player import PlexRTXPlayer
from plex_rtx_gui import PlexRTXAPI


class TestPlexRTXPlayer(unittest.TestCase):
    def setUp(self):
        # Default player initialized with 4K display size
        self.player = PlexRTXPlayer(mpv_path="mpv.exe", display_width=3840, display_height=2160)

    def test_calculate_scale_factor_1080p_to_4k(self):
        """1920x1080 video to 3840x2160 display should yield exactly 2.0x scaling."""
        scale = self.player.calculate_scale_factor(1920, 1080)
        self.assertEqual(scale, 2.0)

    def test_calculate_scale_factor_720p_to_4k(self):
        """1280x720 video to 3840x2160 display should yield exactly 3.0x scaling."""
        scale = self.player.calculate_scale_factor(1280, 720)
        self.assertEqual(scale, 3.0)

    def test_calculate_scale_factor_4k_to_4k(self):
        """3840x2160 video to 3840x2160 display should yield 1.0x scaling."""
        scale = self.player.calculate_scale_factor(3840, 2160)
        self.assertEqual(scale, 1.0)

    def test_calculate_scale_factor_aspect_ratio_difference(self):
        """Test upscaling with non-standard aspect ratio."""
        # Video is 1440x1080 upscaled to fit 3840x2160
        scale = self.player.calculate_scale_factor(1440, 1080)
        # 3840/1440 = 2.666, 2160/1080 = 2.0. Max scale is 2.666 -> floor to 2.6
        self.assertEqual(scale, 2.6)

    def test_build_rtx_filter_sdr_requires_upscale(self):
        """SDR 1080p to 4K upscaling should enable both VSR and RTX HDR combined."""
        filters, scale, use_vsr, use_hdr = self.player.build_rtx_filter(
            video_width=1920, video_height=1080, is_sdr=True
        )
        self.assertEqual(scale, 2.0)
        self.assertTrue(use_vsr)
        self.assertTrue(use_hdr)
        self.assertEqual(len(filters), 1)
        self.assertIn("scaling-mode=nvidia:scale=2.0:format=x2bgr10:nvidia-true-hdr", filters[0])

    def test_build_rtx_filter_native_hdr_requires_upscale(self):
        """Native HDR 1080p to 4K upscaling should enable VSR only (RTX HDR skipped)."""
        filters, scale, use_vsr, use_hdr = self.player.build_rtx_filter(
            video_width=1920, video_height=1080, is_sdr=False
        )
        self.assertEqual(scale, 2.0)
        self.assertTrue(use_vsr)
        self.assertFalse(use_hdr)
        self.assertEqual(len(filters), 1)
        self.assertIn("scaling-mode=nvidia:scale=2.0", filters[0])
        self.assertNotIn("nvidia-true-hdr", filters[0])

    def test_build_rtx_filter_sdr_no_upscale(self):
        """SDR 4K on 4K display should enable RTX HDR only (VSR skipped)."""
        filters, scale, use_vsr, use_hdr = self.player.build_rtx_filter(
            video_width=3840, video_height=2160, is_sdr=True
        )
        self.assertEqual(scale, 1.0)
        self.assertFalse(use_vsr)
        self.assertTrue(use_hdr)
        self.assertEqual(len(filters), 1)
        self.assertEqual(filters[0], "d3d11vpp=format=x2bgr10:nvidia-true-hdr")

    def test_build_rtx_filter_hdr_no_upscale(self):
        """Native HDR 4K on 4K display should enable no filter modifications."""
        filters, scale, use_vsr, use_hdr = self.player.build_rtx_filter(
            video_width=3840, video_height=2160, is_sdr=False
        )
        self.assertEqual(scale, 1.0)
        self.assertFalse(use_vsr)
        self.assertFalse(use_hdr)
        self.assertEqual(len(filters), 0)

    def test_get_mpv_arguments(self):
        """Test building complete command line arguments."""
        args, info = self.player.get_mpv_arguments(
            video_url="http://example.com/movie.mp4",
            video_width=1920,
            video_height=1080,
            is_sdr=True
        )
        # Verify base Windows 11 RTX API rendering properties are met
        self.assertIn("mpv.exe", args)
        self.assertIn("--vo=gpu-next", args)
        self.assertIn("--gpu-api=d3d11", args)
        self.assertIn("--hwdec=d3d11va", args)
        self.assertIn("--fs", args)
        self.assertIn("--d3d11-output-csp=srgb", args)
        self.assertIn("--vf=d3d11vpp=scaling-mode=nvidia:scale=2.0:format=x2bgr10:nvidia-true-hdr", args)
        self.assertIn("http://example.com/movie.mp4", args)

        self.assertEqual(info["scale"], 2.0)
        self.assertTrue(info["vsr_active"])
        self.assertTrue(info["rtx_hdr_active"])


class TestPlexRTXGUI(unittest.TestCase):
    def setUp(self):
        self.player_mock = MagicMock(spec=PlexRTXPlayer)
        self.api = PlexRTXAPI(self.player_mock)

    def test_parse_plex_url_hash_fragment(self):
        """Test extraction of metadata key and machine identifier from SPA hash URL."""
        url = "https://app.plex.tv/desktop"
        hash_val = "#!/server/ceea9bc59d682496a77d3f8295b77bfb3cbbe0ee/details?key=%2Flibrary%2Fmetadata%2F12345"

        machine_id, metadata_key = self.api._parse_plex_url(url, hash_val)
        self.assertEqual(machine_id, "ceea9bc59d682496a77d3f8295b77bfb3cbbe0ee")
        self.assertEqual(metadata_key, "/library/metadata/12345")

    def test_parse_plex_url_hash_player(self):
        """Test url parsing when playing inside a video player router link."""
        url = "https://app.plex.tv/desktop"
        hash_val = "#!/server/ceea9bc59d682496a77d3f8295b77bfb3cbbe0ee/play/player?key=%2Flibrary%2Fmetadata%2F98765"

        machine_id, metadata_key = self.api._parse_plex_url(url, hash_val)
        self.assertEqual(machine_id, "ceea9bc59d682496a77d3f8295b77bfb3cbbe0ee")
        self.assertEqual(metadata_key, "/library/metadata/98765")

    def test_parse_plex_url_no_hash(self):
        """Test url parsing when hash is not present but parameters are in URL query."""
        url = "https://app.plex.tv/desktop/server/abcdef123456/details?key=%2Flibrary%2Fmetadata%2F55555"
        hash_val = ""

        machine_id, metadata_key = self.api._parse_plex_url(url, hash_val)
        self.assertEqual(machine_id, "abcdef123456")
        self.assertEqual(metadata_key, "/library/metadata/55555")

    @patch("plex_rtx_gui.MyPlexAccount")
    def test_resolve_and_launch_with_plex_api(self, mock_my_plex_account):
        """Test successful direct play stream resolution and launch using the Plex API mock."""
        # Setup PlexAPI Mocks
        mock_account_instance = MagicMock()
        mock_my_plex_account.return_value = mock_account_instance

        mock_resource = MagicMock()
        mock_resource.clientIdentifier = "my_machine_id"
        mock_account_instance.resources.return_value = [mock_resource]

        mock_plex_server = MagicMock()
        mock_resource.connect.return_value = mock_plex_server

        mock_item = MagicMock()
        mock_item.getStreamURL.return_value = "http://192.168.1.10:32400/video.mp4?X-Plex-Token=token123"

        # Mock media metadata (1080p SDR)
        mock_media = MagicMock()
        mock_media.width = 1920
        mock_media.height = 1080
        mock_item.media = [mock_media]

        mock_stream = MagicMock()
        mock_stream.streamType = 1  # Video
        mock_stream.colorPrimaries = "bt709"  # SDR
        mock_part = MagicMock()
        mock_part.streams = [mock_stream]
        mock_media.parts = [mock_part]

        mock_plex_server.fetchItem.return_value = mock_item

        # Invoke resolve and launch
        self.api._resolve_and_launch(
            video_src="blob:http://app.plex.tv/abcdef",
            url="https://app.plex.tv/desktop#!/server/my_machine_id/details?key=my_metadata_key",
            hash_val="#!/server/my_machine_id/details?key=my_metadata_key",
            token="token123"
        )

        # Verify PlexAPI was called correctly
        mock_my_plex_account.assert_called_once_with(token="token123")
        mock_plex_server.fetchItem.assert_called_once_with("my_metadata_key")

        # Verify MPV was launched with the resolved parameters
        self.player_mock.launch_mpv.assert_called_once_with(
            video_url="http://192.168.1.10:32400/video.mp4?X-Plex-Token=token123",
            video_width=1920,
            video_height=1080,
            is_sdr=True
        )

    def test_resolve_and_launch_fallback_direct_src(self):
        """Test fallback when Plex API resolution fails/is empty but a direct play video src exists."""
        self.api._resolve_and_launch(
            video_src="http://192.168.1.10:32400/video.mp4?X-Plex-Token=token123",
            url="https://app.plex.tv/desktop",
            hash_val="",
            token=""
        )

        # Verify MPV was launched with direct video src fallback and default parameters
        self.player_mock.launch_mpv.assert_called_once_with(
            video_url="http://192.168.1.10:32400/video.mp4?X-Plex-Token=token123",
            video_width=None,
            video_height=None,
            is_sdr=True
        )


if __name__ == "__main__":
    unittest.main()
