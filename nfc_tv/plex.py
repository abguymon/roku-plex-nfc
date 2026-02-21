"""Plex server queries and Roku playback control."""

import socket
import time

import requests
from plexapi.playqueue import PlayQueue
from plexapi.server import PlexServer

from nfc_tv import load_config


def _connect(config):
    """Connect to the Plex server."""
    base_url = f"http://{config['plex']['host']}:{config['plex']['port']}"
    return PlexServer(base_url, config["plex"]["token"])


def _roku_url(config, path):
    return f"http://{config['roku']['host']}:8060{path}"


def _companion_url(config, path):
    return f"http://{config['roku']['host']}:{config['companion']['port']}{path}"


def ensure_plex_running(config):
    """Make sure Plex is the active app on the Roku and ready to accept
    companion commands. Wakes the Roku from screensaver if needed."""
    roku_host = config["roku"]["host"]
    app_id = config["roku"]["plex_app_id"]

    # Check current active app — wake from screensaver if needed
    resp = requests.get(_roku_url(config, "/query/active-app"))
    if "<screensaver" in resp.text:
        print("Waking Roku from screensaver...")
        requests.post(_roku_url(config, "/keypress/Home"))
        time.sleep(2)

    # Launch Plex (re-launching is safe even if already running)
    print("Launching Plex on Roku...")
    requests.post(_roku_url(config, f"/launch/{app_id}"))

    # Wait for companion port to be reachable
    companion_port = config["companion"]["port"]
    for _ in range(30):
        try:
            s = socket.create_connection((roku_host, companion_port), timeout=1)
            s.close()
            print("Plex companion port ready.")
            # Give Plex a moment to fully initialize after port opens
            time.sleep(3)
            return
        except OSError:
            time.sleep(1)

    raise TimeoutError(f"Plex companion port {companion_port} not reachable after 30s")


def _play_via_companion(config, server, media_key, play_queue_id=None):
    """Send playMedia command directly to the Roku's Plex companion port.
    This is the proven curl-based approach."""
    plex_cfg = config["plex"]
    comp_cfg = config["companion"]

    params = {
        "providerIdentifier": "com.plexapp.plugins.library",
        "machineIdentifier": plex_cfg["machine_id"],
        "protocol": "http",
        "address": plex_cfg["host"],
        "port": str(plex_cfg["port"]),
        "key": media_key,
        "token": plex_cfg["token"],
        "type": "video",
        "commandID": "1",
        "X-Plex-Client-Identifier": comp_cfg["client_id"],
        "X-Plex-Device-Name": comp_cfg["device_name"],
        "X-Plex-Target-Client-Identifier": comp_cfg["target_client_id"],
    }

    if play_queue_id:
        params["containerKey"] = f"/playQueues/{play_queue_id}?window=100&own=1"

    resp = requests.get(
        _companion_url(config, "/player/playback/playMedia"),
        params=params,
        timeout=10,
    )
    resp.raise_for_status()
    return resp


def _play_via_client(server, media):
    """Try to play via plexapi client (requires Plex to expose a controllable client)."""
    clients = server.clients()
    if not clients:
        return False
    client = clients[0]
    client.playMedia(media)
    return True


def play_movie(config, title, library="Movies"):
    """Look up a movie by title and play it on the Roku."""
    server = _connect(config)
    ensure_plex_running(config)

    section = server.library.section(library)
    movie = section.get(title)
    print(f"Playing movie: {movie.title}")

    # Try plexapi client first, fall back to direct companion HTTP
    if not _play_via_client(server, movie):
        _play_via_companion(config, server, movie.key)


def play_show(config, title, mode="next", library="TV Shows"):
    """Play a TV show episode on the Roku.

    Modes:
        next: Play the next unwatched episode (onDeck), fall back to S01E01.
        shuffle: Create a shuffled PlayQueue of the entire show.
    """
    server = _connect(config)
    ensure_plex_running(config)

    section = server.library.section(library)
    show = section.get(title)

    if mode == "shuffle":
        print(f"Playing {show.title} (shuffled)")
        pq = PlayQueue.create(server, show, shuffle=1)
        if not _play_via_client(server, pq):
            first_item = pq.items[0]
            _play_via_companion(config, server, first_item.key, pq.playQueueID)
    else:
        # "next" mode — find the next unwatched episode
        episode = show.onDeck()
        if episode is None:
            # Fully watched or no on-deck; start from the beginning
            episodes = show.episodes()
            if not episodes:
                raise RuntimeError(f"No episodes found for '{title}'")
            episode = episodes[0]
        print(f"Playing {show.title} - {episode.seasonEpisode} - {episode.title}")
        if not _play_via_client(server, episode):
            _play_via_companion(config, server, episode.key)


def play_by_card(config, card_uid):
    """Look up a card UID in config and play the mapped content."""
    card = config["cards"].get(card_uid)
    if card is None:
        print(f"Unknown card: {card_uid}")
        return False

    media_type = card["type"]
    title = card["title"]
    library = card.get("library", "Movies" if media_type == "movie" else "TV Shows")

    if media_type == "movie":
        play_movie(config, title, library)
    elif media_type == "show":
        mode = card.get("mode", "next")
        play_show(config, title, mode, library)
    else:
        print(f"Unknown media type: {media_type}")
        return False

    return True


if __name__ == "__main__":
    import sys

    cfg = load_config()

    if len(sys.argv) < 2:
        print("Usage: python -m nfc_tv.plex <movie_title>")
        print("       python -m nfc_tv.plex --show <show_title> [--mode next|shuffle]")
        sys.exit(1)

    if sys.argv[1] == "--show":
        show_title = sys.argv[2]
        mode = "next"
        if "--mode" in sys.argv:
            mode = sys.argv[sys.argv.index("--mode") + 1]
        play_show(cfg, show_title, mode)
    else:
        play_movie(cfg, " ".join(sys.argv[1:]))
