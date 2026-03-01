# roku-plex-nfc

Tap an NFC card on a reader and a movie or TV show starts playing on your Roku TV via Plex. Built for a Raspberry Pi with a PN532 NFC reader.

Inspired by [this project](https://simplyexplained.com/blog/how-i-built-an-nfc-movie-library-for-my-kids/) but using Roku + Plex instead of Apple TV.

## How It Works

1. Tap an NFC card on the PN532 reader connected to a Raspberry Pi
2. The daemon looks up the card's UID in the config
3. It queries your Plex server for the mapped movie or TV show
4. Plex is launched on the Roku (waking it from screensaver if needed)
5. Playback starts via the Plex companion API on the Roku

## Hardware

- Raspberry Pi (any model with GPIO)
- PN532 NFC reader (SPI, I2C, or UART)
- NFC cards/tags (NTAG213 or similar)
- Roku TV on the same network as your Plex server

## Setup

### Install

```bash
git clone https://github.com/abguymon/roku-plex-nfc.git
cd roku-plex-nfc
uv sync
```

On the Raspberry Pi, also install the NFC hardware libraries:

```bash
uv add adafruit-circuitpython-pn532 adafruit-blinka
```

### Configure

Copy the example config and fill in your details:

```bash
cp config.example.yaml config.yaml
```

You'll need:
- **Roku IP** — found in Settings > Network > About on your Roku
- **Plex server IP and token** — see [Finding your Plex token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)
- **Plex machine ID** — visit `http://<plex-ip>:32400/identity` in your browser
- **Roku Plex client ID** — visit `http://<plex-ip>:32400/clients` while Plex is open on the Roku

### Register Cards

You can register cards via the **web UI** or the **CLI**.

**Web UI** — navigate to the Register page and follow the 3-step flow (tap card, search Plex, save).

**CLI** — tap a card, search for content, and save the mapping interactively:

```bash
uv run python -m nfc_tv.register
```

For each card you can map:
- **Movies** — plays the movie directly
- **TV Shows** — choose between:
  - `next` — plays the next unwatched episode (resumes where you left off)
  - `shuffle` — shuffles all episodes

You can also add cards manually in `config.yaml`:

```yaml
cards:
  "04a23b1c":
    type: "movie"
    title: "Ponyo"
    library: "Movies"
  "04b7ce2d":
    type: "show"
    title: "The Office"
    library: "TV Shows"
    mode: "next"
```

## Usage

### Run (Web UI + NFC Daemon)

```bash
uv run python -m nfc_tv
```

This starts a FastAPI web server on port 8000 with the NFC daemon running in a background thread. The web UI provides:

- **Dashboard** (`/`) — live status of NFC reader, Plex server, and Roku, plus recent scan history
- **Cards** (`/cards`) — view and delete registered card mappings
- **Register** (`/register`) — 3-step card registration flow (tap → search → save)

The host and port can be configured in `config.yaml`:

```yaml
web:
  host: "0.0.0.0"
  port: 8000
```

Or via CLI flags:

```bash
uv run python -m nfc_tv --host 0.0.0.0 --port 8080
```

### Run NFC Daemon Only (No Web UI)

```bash
uv run python -m nfc_tv --no-web
```

### Health Endpoint

`GET /health` returns `200` when all systems are up, or `503` when degraded:

```json
{
  "status": "healthy",
  "nfc_reader": true,
  "plex": true,
  "roku": true
}
```

Compatible with [Uptime Kuma](https://github.com/louislam/uptime-kuma) — use an HTTP keyword monitor checking for `healthy`.

### API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check (200/503) |
| `/api/status` | GET | Full system status |
| `/api/events` | GET | Recent scan events |
| `/api/cards` | GET | List registered cards |
| `/api/cards` | POST | Register a card |
| `/api/cards/{uid}` | DELETE | Delete a card |
| `/api/cards/scan` | POST | Long-poll for card tap (30s timeout) |
| `/api/plex/search?q=` | GET | Search Plex library |

### Test Without NFC Hardware

The web UI works without NFC hardware — the reader will show as unavailable on the dashboard, but you can still browse cards and search Plex.

You can also test Plex + Roku playback directly from any machine:

```bash
# Play a movie
uv run python -m nfc_tv.plex "Ponyo"

# Play a TV show (next unwatched episode)
uv run python -m nfc_tv.plex --show "The Office"

# Play a TV show (shuffled)
uv run python -m nfc_tv.plex --show "The Office" --mode shuffle
```

### Run on Boot (systemd)

```bash
sudo cp nfc-tv.service /etc/systemd/system/
sudo systemctl enable --now nfc-tv
```

The service starts the web UI + daemon by default. Edit the service file if your install path or username differs from the defaults.

## Notes

- Content is identified by **title + library name**, which survives Plex library rebuilds (unlike rating keys)
- The Roku's Plex companion port (8324) doesn't respond while the screensaver is active, so the daemon wakes the Roku first
- NFC reads are debounced — tapping the same card again within 5 seconds (configurable) is ignored, but removing and re-tapping works immediately
- The NFC reader gracefully degrades — if hardware isn't available (e.g., running on a dev machine), the web UI still works

## Roadmap

- **Card scan feedback** — audible buzzer and/or LED blink when a card is read, so you know the tap registered before the TV responds
- **Multi-platform deep links** — support launching content on other Roku apps (Netflix, Disney+, YouTube) in addition to Plex

## License

MIT
