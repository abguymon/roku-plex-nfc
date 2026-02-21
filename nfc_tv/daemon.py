"""Main daemon: poll NFC reader and trigger Plex playback."""

from nfc_tv import load_config
from nfc_tv.nfc import NFCReader
from nfc_tv.plex import play_by_card


def main():
    config = load_config()
    nfc_cfg = config.get("nfc", {})

    reader = NFCReader(
        interface=nfc_cfg.get("interface", "spi"),
        debounce_seconds=nfc_cfg.get("debounce_seconds", 5),
    )

    print("NFC-TV daemon running. Tap a card...")

    while True:
        uid = reader.read_uid()
        if uid is None:
            continue

        print(f"Card detected: {uid}")
        try:
            play_by_card(config, uid)
        except Exception as e:
            print(f"Playback error: {e}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nShutting down.")
