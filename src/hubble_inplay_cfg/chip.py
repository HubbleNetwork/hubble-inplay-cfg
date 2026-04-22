"""Clean adapter for the InPlay IN100 chip UART driver.

Wraps the proprietary beacon.chip.Chip implementation to provide a
stable, testable interface. All serial framing and register-level
logic lives in the beacon package.
"""

from __future__ import annotations

import os
import sys
from typing import Any

import serial

# Make the beacon package importable: beacon/*.pyc lives alongside this file
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from beacon.chip import Chip as _BeaconChip  # type: ignore[import]

CHIP_NAMES = {0: "QFN18", 1: "WLCSP", 2: "KGD", 3: "DFN8", 255: "UNKNOWN"}
ERR_OK = 0


class _MockProgress:
    """Stub for the PyQt5 Signal.emit() that _BeaconChip expects internally."""

    def emit(self, value: int) -> None:
        pass


class Chip:
    """UART adapter for the InPlay IN100 NanoBeacon chip.

    Usage::

        with Chip("/dev/ttyUSB0") as chip:
            ret, baud = chip.connect()
            ret, chip_type = chip.get_chip_type()
    """

    def __init__(self, port: str, baud: int = 115200, timeout: float = 0.5) -> None:
        self._serial = serial.Serial(
            port,
            baud,
            timeout=timeout,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            write_timeout=timeout,
            inter_byte_timeout=timeout,
        )
        self._inner = _BeaconChip(self._serial)
        self._inner.proc_progress = _MockProgress()

    # --- Connection ---

    def connect(self) -> tuple[int, int]:
        """Negotiate baud rate with the chip. Returns (error_code, baud_rate)."""
        return self._inner.uart_rate_adaptive()

    # --- eFuse ---

    def read_efuse(self, addr: int) -> tuple[int, int]:
        """Read one eFuse word at addr. Returns (error_code, value)."""
        return self._inner.read_efuse(addr)

    # --- Chip identity ---

    def get_chip_type(self) -> tuple[int, int]:
        """Returns (error_code, chip_type). 0=QFN18 1=WLCSP 2=KGD 3=DFN8 255=UNKNOWN."""
        return self._inner.get_chip_type()

    def is_full_range_industrial(self) -> tuple[int, bool]:
        """Returns (error_code, is_high_temp_range)."""
        return self._inner.is_full_range_industrial()

    # --- Programming ---

    def set_word_array(self, words: list[int]) -> None:
        """Load the encoded config word array before calling run_in_ram or burn_efuse."""
        self._inner.wordArray = words

    def run_in_ram(self) -> int:
        """Run config from RAM (non-destructive). Returns error code."""
        return self._inner.run_in_ram()

    def burn_efuse(self, reset: bool = True) -> int:
        """Permanently burn eFuse. Returns error code."""
        return self._inner.burn_efuse(reset_en=reset, clear_uart_cache=False)

    # --- RF testing (Direct Test Mode) ---

    def dtm_start(self, params: list[int], infinite_tx: bool = False) -> tuple[int, str]:
        """Start BLE Direct Test Mode.

        params: 6 integers — [freq_idx, pkt_type, pkt_len, phy, ...]
        Returns (error_code, message).
        """
        return self._inner.dtm_start(params, infinite_tx)

    def dtm_stop(self) -> tuple[int, str]:
        """Stop BLE Direct Test Mode. Returns (error_code, message)."""
        return self._inner.dtm_stop()

    def carrier_start(self, ch: int, cap: int, tx_power: int) -> tuple[int, str]:
        """Start a continuous carrier wave on the given BLE channel.

        Returns (error_code, message).
        """
        return self._inner.carrier_test_start(ch, cap, tx_power)

    def carrier_stop(self) -> tuple[int, str]:
        """Stop the carrier wave test. Returns (error_code, message)."""
        return self._inner.carrier_test_stop()

    # --- Manufacturing ---

    def send_trigger(self) -> None:
        """Send [0x00, 0xFF] post-burn trigger signal to a manufacturing test fixture."""
        self._serial.write(bytes([0x00, 0xFF]))
        self._serial.flush()

    # --- Lifecycle ---

    def close(self) -> None:
        """Close the serial port."""
        if self._serial.is_open:
            self._serial.close()

    def __enter__(self) -> Chip:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
