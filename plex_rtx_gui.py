#!/usr/bin/env python3
"""
Plex RTX Player GUI
Launches an embedded WebView of Plex Web App and intercepts playbacks
to launch MPV with Nvidia RTX VSR and RTX HDR.
"""

import os
import sys
import urllib.parse
import logging
import threading
import webview
from plexapi.myplex import MyPlexAccount
from plex_rtx_player import PlexRTXPlayer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PlexRTXGUI")

# JavaScript to be injected into the Plex Web SPA.
# This script overrides the HTMLVideoElement.prototype.play method.
# Since Plex Web is an SPA, the override persists for the whole session.
JS_INTERCEPTOR = """
(function() {
    if (window.__plex_rtx_intercepted) {
        console.log("Plex RTX Interceptor is already active.");
        return;
    }
    window.__plex_rtx_intercepted = true;
    console.log("Plex RTX Interceptor successfully loaded!");

    const originalPlay = HTMLVideoElement.prototype.play;
    HTMLVideoElement.prototype.play = function() {
        const video = this;
        const src = video.src || "";
        console.log("Plex RTX Interceptor: Captured video.play() for source:", src);

        // Instantly pause and hide the native HTML5 player
        video.pause();
        video.style.display = 'none';

        // Hide standard Plex player controls if they appear to prevent overlay clutter
        const playerContainers = document.querySelectorAll('[class*="PlayerContainer"], [class*="VideoPlayer"]');
        playerContainers.forEach(container => {
            container.style.visibility = 'hidden';
        });

        // Gather Plex Web state information
        const url = window.location.href;
        const hash = window.location.hash;

        let token = null;
        try {
            token = window.localStorage.getItem('myPlexAccessToken');
        } catch (e) {
            console.error("Plex RTX Interceptor: Failed to retrieve token from localStorage:", e);
        }

        // Call the python backend api
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.on_play_intercepted({
                "video_src": src,
                "url": url,
                "hash": hash,
                "token": token
            }).then(function(response) {
                console.log("Plex RTX Interceptor: Python backend acknowledged:", response);
            }).catch(function(err) {
                console.error("Plex RTX Interceptor: Error calling python backend:", err);
            });
        } else {
            console.error("Plex RTX Interceptor: pywebview API is not available.");
        }

        return Promise.resolve();
    };
})();
"""

# Store player instance globally to keep the JS API class state-free and completely prevent .NET interop recursion crashes
_GLOBAL_PLAYER = None

class PlexRTXAPI:
    """
    Exposed JS API for pywebview. Keeps no instance state or attributes to prevent WPF/WinForms
    reflection/accessibility recursion depth exceeded errors under Windows.
    """
    def on_play_intercepted(self, data):
        """
        Invoked from Javascript when a video starts playing in the WebView.
        """
        logger.info("Play interception event received from WebView.")

        video_src = data.get("video_src", "")
        url = data.get("url", "")
        hash_val = data.get("hash", "")
        token = data.get("token", "")

        logger.info(f"Intercepted parameters: url='{url}', hash='{hash_val}', has_token={bool(token)}")

        # Run stream resolving and launching in a background thread so we don't block the WebView UI
        thread = threading.Thread(
            target=self._resolve_and_launch,
            args=(video_src, url, hash_val, token),
            daemon=True
        )
        thread.start()

        return {"status": "processing"}

    def _resolve_and_launch(self, video_src, url, hash_val, token):
        global _GLOBAL_PLAYER
        try:
            stream_url = None
            width = None
            height = None
            is_sdr = True

            # Attempt 1: Resolve stream URL using Plex API if token and details exist in URL
            machine_id, metadata_key = self._parse_plex_url(url, hash_val)

            if token and machine_id and metadata_key:
                logger.info(f"Connecting to Plex.tv to resolve machine_id='{machine_id}' and metadata_key='{metadata_key}'...")
                try:
                    account = MyPlexAccount(token=token)
                    server_resource = None
                    for resource in account.resources():
                        if resource.clientIdentifier == machine_id:
                            server_resource = resource
                            break

                    if server_resource:
                        plex = server_resource.connect()
                        item = plex.fetchItem(metadata_key)

                        # Handle case where the metadata key points to a container (Show/Season) instead of a playable item
                        from plexapi.video import Show, Season

                        if isinstance(item, Show):
                            logger.info("Metadata key points to a Show. Attempting to resolve onDeck or first episode...")
                            try:
                                on_deck = item.onDeck()
                                if on_deck:
                                    item = on_deck
                                else:
                                    episodes = item.episodes()
                                    if episodes:
                                        item = episodes[0]
                            except Exception as show_err:
                                logger.warning(f"Failed to resolve show episodes: {show_err}")

                        if isinstance(item, Season):
                            logger.info("Metadata key points to a Season. Resolving to first episode of the season...")
                            try:
                                episodes = item.episodes()
                                if episodes:
                                    item = episodes[0]
                            except Exception as season_err:
                                logger.warning(f"Failed to resolve season episodes: {season_err}")

                        if hasattr(item, "getStreamURL"):
                            stream_url = item.getStreamURL()
                            logger.info(f"Successfully resolved Plex direct play stream URL: {stream_url}")

                            # Extract video characteristics for accurate RTX configuration
                            if item.media:
                                media = item.media[0]
                                width = media.width
                                height = media.height

                                # Check video streams for color primaries (HDR vs SDR)
                                for part in media.parts:
                                    for stream in part.streams:
                                        if stream.streamType == 1:  # Video Stream
                                            color_primaries = getattr(stream, "colorPrimaries", "")
                                            color_space = getattr(stream, "colorSpace", "")
                                            if "2020" in color_primaries or "hdr" in color_space.lower():
                                                is_sdr = False
                            logger.info(f"Plex Metadata: resolution={width}x{height}, is_sdr={is_sdr}")
                        else:
                            logger.error(f"Resolved object '{type(item).__name__}' is not Playable.")
                    else:
                        logger.warning(f"Could not find matching Plex Server resource for machine ID '{machine_id}'")
                except Exception as api_err:
                    logger.error(f"Plex API stream resolution failed: {api_err}")

            # Attempt 2: Fallback to the intercepted direct source URL if available
            if not stream_url:
                if video_src and not video_src.startswith("blob:"):
                    logger.info("Using intercepted video source URL directly.")
                    stream_url = video_src
                else:
                    logger.error("Could not resolve video stream URL. Native stream is a blob and Plex API resolution failed/unavailable.")
                    return

            # Launch MPV with Nvidia RTX VSR and RTX HDR
            if _GLOBAL_PLAYER:
                _GLOBAL_PLAYER.launch_mpv(
                    video_url=stream_url,
                    video_width=width,
                    video_height=height,
                    is_sdr=is_sdr
                )
            else:
                logger.error("Global player instance is not initialized.")

        except Exception as e:
            logger.error(f"Error resolving or launching player: {e}", exc_info=True)

    def _parse_plex_url(self, url, hash_val):
        """
        Parses Plex Web URLs/hashes to extract machine ID and metadata key.
        Examples:
          https://app.plex.tv/desktop#!/server/ceea9bc59d682496a77d3f8295b77bfb3cbbe0ee/details?key=%2Flibrary%2Fmetadata%2F12345
          https://app.plex.tv/desktop#!/server/ceea9bc59d682496a77d3f8295b77bfb3cbbe0ee/play/player...
        """
        # Look in the hash fragment first as Plex Web is an SPA and stores routing in the hash
        target = hash_val if hash_val else url
        if not target:
            return None, None

        machine_id = None
        metadata_key = None

        # Extract machine ID (usually the path segment right after /server/)
        parts = target.split("/")
        for i, part in enumerate(parts):
            if part == "server" and i + 1 < len(parts):
                machine_id = parts[i + 1]
                break

        # Extract metadata key from query parameters
        parsed_url = urllib.parse.urlparse(target)
        # Handle the hash routing query parameters
        query = parsed_url.query
        if "#!" in target:
            hash_query_part = target.split("?")[-1]
            params = urllib.parse.parse_qs(hash_query_part)
        else:
            params = urllib.parse.parse_qs(query)

        if "key" in params:
            metadata_key = params["key"][0]

        return machine_id, metadata_key

def on_loaded(window):
    """
    Called when the DOM is ready. Inject our javascript interceptor immediately using evaluate_js.
    """
    logger.info("DOM loaded in WebView. Injecting RTX Interceptor...")
    window.evaluate_js(JS_INTERCEPTOR)

def main():
    global _GLOBAL_PLAYER
    display_w = int(os.environ.get("DISPLAY_WIDTH", 3840))
    display_h = int(os.environ.get("DISPLAY_HEIGHT", 2160))
    mpv_executable = os.environ.get("MPV_PATH", "mpv.exe")

    _GLOBAL_PLAYER = PlexRTXPlayer(mpv_path=mpv_executable, display_width=display_w, display_height=display_h)
    api = PlexRTXAPI()

    logger.info("Starting Custom Plex Player Webview on Windows 11...")
    logger.info(f"Target Display Resolution: {display_w}x{display_h}")

    # Create Webview window loading the Plex Web App
    window = webview.create_window(
        title="Custom Plex Player with Nvidia RTX",
        url="https://app.plex.tv/desktop",
        js_api=api,
        width=1280,
        height=720,
        text_select=True,
        confirm_close=True
    )

    # Subscribe to loaded events to ensure JS is injected whenever a page/SPA context loads
    window.events.loaded += lambda: on_loaded(window)

    # Start pywebview
    webview.start(debug=True)

if __name__ == "__main__":
    main()
