"""UART adapter for the InPlay IN100 NanoBeacon chip.

Delegates all operations to beacon_bridge.py (running under Python 3.10)
so this module is importable on any Python ≥ 3.10.
"""

from __future__ import annotations

from typing import Any

from hubble_inplay_cfg._bridge_client import BridgeError, bridge_call

CHIP_NAMES = {0: "QFN18", 1: "WLCSP", 2: "KGD", 3: "DFN8", 255: "UNKNOWN"}
ERR_OK = 0

__all__ = ["CHIP_NAMES", "ERR_OK", "BridgeError", "Chip"]


class Chip:
    """UART adapter for the InPlay IN100 NanoBeacon chip.

    Each method opens a fresh serial connection via the beacon bridge,
    performs the operation, and closes the port. No persistent connection
    is held between calls.

    Usage::

        chip = Chip("/dev/ttyUSB0")
        ret, msg = chip.dtm_start([0, 0, 37, 0, 0, 0])
    """

    def __init__(self, port: str) -> None:
        self._port = port

    def _call(self, cmd: str, **kwargs: Any) -> dict:
        return bridge_call({"cmd": cmd, "port": self._port, **kwargs})

    # --- RF testing (Direct Test Mode) ---

    def dtm_start(self, params: list[int], infinite_tx: bool = False) -> tuple[int, str]:
        """Start BLE Direct Test Mode. Returns (error_code, message)."""
        result = self._call("dtm_start", params=params)
        return result["ret"], result["msg"]

    def dtm_stop(self) -> tuple[int, str]:
        """Stop BLE Direct Test Mode. Returns (error_code, message)."""
        result = self._call("dtm_stop")
        return result["ret"], result["msg"]

    def carrier_start(self, ch: int, cap: int, tx_power: int) -> tuple[int, str]:
        """Start a continuous carrier wave. Returns (error_code, message)."""
        result = self._call("carrier_start", ch=ch, cap=cap, tx_power=tx_power)
        return result["ret"], result["msg"]

    def carrier_stop(self) -> tuple[int, str]:
        """Stop the carrier wave. Returns (error_code, message)."""
        result = self._call("carrier_stop")
        return result["ret"], result["msg"]

    # --- Lifecycle ---

    def close(self) -> None:
        """No-op: the bridge closes the serial port after each call."""

    def __enter__(self) -> Chip:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
