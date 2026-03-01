"""Allow running as `python -m nfc_tv`.

Starts the web UI + NFC daemon by default.
Use --no-web to run the NFC daemon only.
"""

import argparse
import logging


def main():
    parser = argparse.ArgumentParser(description="NFC-TV")
    parser.add_argument(
        "--no-web", action="store_true", help="Run NFC daemon only (no web UI)"
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Web UI bind address (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Web UI port (default: 8000)"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if args.no_web:
        from nfc_tv.daemon import main as daemon_main

        daemon_main()
    else:
        import uvicorn

        from nfc_tv import load_config

        config = load_config()
        web_cfg = config.get("web", {})
        host = web_cfg.get("host", args.host)
        port = web_cfg.get("port", args.port)

        uvicorn.run(
            "nfc_tv.app:create_app",
            factory=True,
            host=host,
            port=port,
            log_level="info",
        )


try:
    main()
except KeyboardInterrupt:
    print("\nShutting down.")
