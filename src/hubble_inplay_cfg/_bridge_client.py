"""Client for beacon_bridge.py — spawns a Python 3.10 subprocess to access beacon .pyc modules."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

_BRIDGE_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "beacon_bridge.py")


class BridgeError(RuntimeError):
    pass


def _find_python310() -> str:
    """Return path to a Python 3.10 interpreter, or raise BridgeError."""
    if sys.version_info[:2] == (3, 10):
        return sys.executable
    env_override = os.environ.get("HUBBLE_PYTHON310")
    if env_override:
        return env_override
    path = shutil.which("python3.10")
    if path:
        return path
    raise BridgeError(
        "Python 3.10 is required for chip programming (beacon .pyc bytecode is 3.10-only).\n"
        "Install it:  brew install python@3.10      (macOS)\n"
        "             apt install python3.10         (Linux)\n"
        "Or set HUBBLE_PYTHON310=/path/to/python3.10 to point to your install."
    )


def bridge_call(cmd: dict, logger: logging.Logger | None = None) -> dict:
    """Spawn beacon_bridge.py under Python 3.10, send cmd as JSON, return the done payload.

    Log lines streamed by the bridge are forwarded to *logger* if provided.
    Raises BridgeError on any non-ok result or subprocess failure.
    """
    py310 = _find_python310()
    proc = subprocess.Popen(
        [py310, _BRIDGE_SCRIPT],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None

    proc.stdin.write(json.dumps(cmd) + "\n")
    proc.stdin.close()

    result: dict | None = None
    for raw in proc.stdout:
        line = raw.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            if logger:
                logger.debug("bridge non-JSON: %s", line)
            continue

        if msg.get("type") == "log":
            if logger:
                level = msg.get("level", "info")
                getattr(logger, level, logger.info)(msg.get("msg", ""))
        elif msg.get("type") == "done":
            result = msg
            break

    proc.wait(timeout=5)

    if result is None:
        stderr = (proc.stderr.read() if proc.stderr else "").strip()
        raise BridgeError(
            f"Bridge exited without sending a done message "
            f"(exit {proc.returncode}){': ' + stderr if stderr else ''}"
        )

    if not result.get("ok"):
        raise BridgeError(result.get("error", "Bridge command failed"))

    return result
