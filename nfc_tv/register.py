"""Interactive CLI to map NFC cards to Plex content."""

import yaml

from nfc_tv import CONFIG_PATH, load_config
from nfc_tv.nfc import NFCReader
from plexapi.server import PlexServer


def _connect(config):
    base_url = f"http://{config['plex']['host']}:{config['plex']['port']}"
    return PlexServer(base_url, config["plex"]["token"])


def _search_content(server):
    """Interactive search for a movie or TV show."""
    query = input("Search for a title: ").strip()
    if not query:
        return None

    results = []
    for section in server.library.sections():
        if section.type in ("movie", "show"):
            results.extend(section.search(query, limit=10))

    if not results:
        print("No results found.")
        return None

    print("\nResults:")
    for i, item in enumerate(results, 1):
        section = item.section()
        label = f"[{section.title}]"
        if item.type == "show":
            eps = len(item.episodes())
            print(f"  {i}. {label} {item.title} ({eps} episodes)")
        else:
            year = getattr(item, "year", "")
            print(f"  {i}. {label} {item.title} ({year})")

    choice = input(f"\nSelect (1-{len(results)}): ").strip()
    try:
        return results[int(choice) - 1]
    except (ValueError, IndexError):
        print("Invalid selection.")
        return None


def _pick_show_mode():
    """Choose playback mode for a TV show."""
    print("\nPlayback mode:")
    print("  1. next     - Play next unwatched episode")
    print("  2. shuffle  - Shuffle all episodes")
    choice = input("Select (1-2) [1]: ").strip()
    return "shuffle" if choice == "2" else "next"


def _save_config(config):
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def main():
    config = load_config()
    server = _connect(config)
    nfc_cfg = config.get("nfc", {})

    reader = NFCReader(
        interface=nfc_cfg.get("interface", "spi"),
        debounce_seconds=1,  # Short debounce for registration
    )

    if "cards" not in config:
        config["cards"] = {}

    while True:
        print("\n--- Card Registration ---")
        print("Tap an NFC card (Ctrl+C to quit)...")

        uid = None
        while uid is None:
            uid = reader.read_uid()

        print(f"Card UID: {uid}")

        if uid in config["cards"]:
            existing = config["cards"][uid]
            print(f"Already mapped to: {existing['title']} ({existing['type']})")
            if input("Overwrite? (y/N): ").strip().lower() != "y":
                continue

        item = _search_content(server)
        if item is None:
            continue

        section = item.section()
        entry = {
            "type": item.type,
            "title": item.title,
            "library": section.title,
        }

        if item.type == "show":
            entry["mode"] = _pick_show_mode()

        config["cards"][uid] = entry
        _save_config(config)
        print(f"Saved: {uid} -> {item.title}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDone.")
