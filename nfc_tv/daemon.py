"""NFC daemon: polls reader and triggers Plex playback.

Can run standalone or as a background thread managed by the FastAPI app.
"""

import logging
import threading
import time

from nfc_tv import load_config
from nfc_tv.plex import play_by_card
from nfc_tv.state import AppState

logger = logging.getLogger(__name__)


class NFCDaemon(threading.Thread):
    """NFC polling loop that runs in a background thread."""

    def __init__(self, state: AppState):
        super().__init__(daemon=True, name="nfc-daemon")
        self.state = state
        self._stop_event = threading.Event()
        self._reader = None

    def _init_reader(self):
        config = self.state.config
        nfc_cfg = config.get("nfc", {})
        try:
            from nfc_tv.nfc import NFCReader

            self._reader = NFCReader(
                interface=nfc_cfg.get("interface", "spi"),
                debounce_seconds=nfc_cfg.get("debounce_seconds", 5),
            )
            self.state.set_reader_status(True)
            logger.info("NFC reader initialized")
        except Exception as e:
            self.state.set_reader_status(False, str(e))
            logger.warning("NFC reader unavailable: %s", e)

    def run(self):
        self._init_reader()

        if self._reader is None:
            logger.info("No NFC reader — daemon idle")
            self._stop_event.wait()
            return

        logger.info("NFC daemon running. Tap a card...")
        while not self._stop_event.is_set():
            try:
                uid = self._reader.read_uid()
            except Exception as e:
                logger.error("NFC read error: %s", e)
                self.state.set_reader_status(False, str(e))
                time.sleep(1)
                continue

            if uid is None:
                continue

            logger.info("Card detected: %s", uid)

            # If the web UI is waiting for a scan, route there instead of playback
            if self.state.is_scan_requested():
                self.state.report_scan(uid)
                continue

            config = self.state.config
            card = config.get("cards", {}).get(uid)
            title = card["title"] if card else None

            try:
                success = play_by_card(config, uid)
                self.state.add_event(uid, title, success if success is not None else False)
            except Exception as e:
                logger.error("Playback error: %s", e)
                self.state.add_event(uid, title, False)

    def stop(self):
        self._stop_event.set()


def main():
    """Standalone entry point (no web UI)."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    config = load_config()
    state = AppState(config)
    daemon = NFCDaemon(state)
    daemon.daemon = False  # Keep process alive
    daemon.start()
    try:
        daemon.join()
    except KeyboardInterrupt:
        print("\nShutting down.")
        daemon.stop()


if __name__ == "__main__":
    main()
