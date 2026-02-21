"""Allow running as `python -m nfc_tv` (starts the daemon)."""

from nfc_tv.daemon import main

try:
    main()
except KeyboardInterrupt:
    print("\nShutting down.")
