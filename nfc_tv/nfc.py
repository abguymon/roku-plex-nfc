"""PN532 NFC reader with debouncing."""

import time


class NFCReader:
    """Read NFC card UIDs from a PN532 via SPI (default) or I2C/UART."""

    def __init__(self, interface="spi", debounce_seconds=5):
        self._debounce_seconds = debounce_seconds
        self._last_uid = None
        self._last_read_time = 0
        self._pn532 = self._init_reader(interface)

    def _init_reader(self, interface):
        import board
        import busio
        from digitalio import DigitalInOut

        if interface == "spi":
            from adafruit_pn532.spi import PN532_SPI

            spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
            cs = DigitalInOut(board.D5)
            pn532 = PN532_SPI(spi, cs, debug=False)
        elif interface == "i2c":
            from adafruit_pn532.i2c import PN532_I2C

            i2c = busio.I2C(board.SCL, board.SDA)
            pn532 = PN532_I2C(i2c, debug=False)
        elif interface == "uart":
            from adafruit_pn532.uart import PN532_UART

            uart = busio.UART(board.TX, board.RX, baudrate=115200, timeout=0.1)
            pn532 = PN532_UART(uart, debug=False)
        else:
            raise ValueError(f"Unknown NFC interface: {interface}")

        ic, ver, rev, support = pn532.firmware_version
        print(f"PN532 firmware: {ver}.{rev}")
        pn532.SAM_configuration()
        return pn532

    def read_uid(self):
        """Read a card UID. Returns hex string or None.

        Handles debouncing: returns None if the same card is still present
        within the cooldown period. Resets when the card is removed.
        """
        uid = self._pn532.read_passive_target(timeout=0.5)

        if uid is None:
            # Card removed — reset so the same card can trigger again
            self._last_uid = None
            return None

        uid_hex = uid.hex()
        now = time.time()

        if uid_hex == self._last_uid and (now - self._last_read_time) < self._debounce_seconds:
            return None

        self._last_uid = uid_hex
        self._last_read_time = now
        return uid_hex
