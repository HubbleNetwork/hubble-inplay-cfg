"""MCP server — exposes hubble-inplay-cfg tools to Claude Code and other AI agents.

Install:  pip install "hubble-inplay-cfg[mcp]"
Run:      hubble-inplay-cfg-mcp          (stdio transport, for MCP clients)
          python -m hubble_inplay_cfg.mcp_server

Add to Claude Code (.mcp.json in project root or ~/.claude.json):

    {
      "mcpServers": {
        "hubble-inplay-cfg": {
          "command": "hubble-inplay-cfg-mcp"
        }
      }
    }
"""

from __future__ import annotations

import subprocess
import sys

from mcp.server.fastmcp import FastMCP  # type: ignore[import]

mcp = FastMCP(
    "hubble-inplay-cfg",
    instructions="""
Tools for generating and flashing Hubble Network IN100 NanoBeacon configs.

Typical no-hardware workflow:
  1. generate_config  — produce a JSON config from key + rot_exp + interval
  2. validate_config  — confirm word count <=256 before touching hardware

Typical hardware workflow:
  1. list_serial_ports — find the right serial port
  2. connect_chip      — verify the chip is reachable
  3. generate_config   — produce the config
  4. validate_config   — confirm it is valid
  5. program_chip      — flash (use mode='ram' first, then mode='efuse')

All hardware operations (program_chip, connect_chip, read_efuse, dtm_*,
carrier_*) require a connected IN100 chip on a serial port.

Parameter notes:
- key: 32-char hex (e.g. 'E00102030405060708090A0B0C0D0E0F') or base64.
       All-zeros default produces a config the Hubble backend cannot decode.
- rot_exp: 10-15 for Hubble backend compatibility (1-9 will warn).
- interval: advertising interval in whole seconds.
- port: '/dev/tty.usbserial-XXXX' on macOS, '/dev/ttyUSBX' on Linux, 'COMX' on Windows.
""",
)


def _cli(*args: str) -> tuple[int, str, str]:
    result = subprocess.run(
        [sys.executable, "-m", "hubble_inplay_cfg", *args],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


# ──────────────────────────────────────────────────────────────
# Config generation (no hardware)
# ──────────────────────────────────────────────────────────────


@mcp.tool()
def generate_config(
    key: str = "00000000000000000000000000000000",
    rot_exp: int = 15,
    interval: int = 2,
    payload: str = "FF",
    tx_power: int = 4,
) -> str:
    """Generate a Hubble IN100 NanoBeacon JSON config string.

    No hardware required. Returns the full config as a JSON string that can be
    written to a .cfg file or passed directly to program_chip.

    Args:
        key: 16-byte AES-128 key as 32-char hex or base64.
             Example: 'AAECAwQFBgcICQoLDA0ODw==' or 'E00102030405060708090A0B0C0D0E0F'.
             All-zeros default is safe for offline testing only.
        rot_exp: EID rotation period exponent (rotation period = 2^rot_exp seconds).
                 Use 10-15 for Hubble backend compatibility.
        interval: Advertising interval in seconds (default 2).
        payload: Raw hex bytes for the payload field, e.g. 'FF' or 'FF01AB'.
        tx_power: TX power in dBm, range -4 to 4 (default 4).

    Returns:
        JSON string representing the complete IN100 .cfg config.
    """
    ret, out, err = _cli(
        "generate",
        "--key", key,
        "--rot-exp", str(rot_exp),
        "--interval", str(interval),
        "--payload", payload,
        "--tx-power", str(tx_power),
    )
    if ret != 0:
        raise ValueError(f"generate failed: {err or out}")
    return out


@mcp.tool()
def validate_config(config_path: str, verbose: bool = False) -> str:
    """Validate a .cfg JSON file offline (no hardware needed).

    Checks that the config encodes to <=256 eFuse words. Run this before
    connecting hardware to catch bad configs early.

    Args:
        config_path: Absolute or relative path to the .cfg JSON file.
        verbose: If True, also prints the first 32 words and all non-zero words.

    Returns:
        Validation report showing word count and OK/OVERFLOW status.
    """
    args = ["validate", "--config", config_path]
    if verbose:
        args.append("--verbose")
    ret, out, err = _cli(*args)
    if ret != 0:
        raise ValueError(f"validate failed: {err or out}")
    return out


# ──────────────────────────────────────────────────────────────
# Hardware operations
# ──────────────────────────────────────────────────────────────


@mcp.tool()
def list_serial_ports() -> str:
    """List available serial ports on this machine.

    Call this first to find the right port before any hardware operation.

    Returns:
        Newline-separated list of serial ports with device path and description.
    """
    try:
        from serial.tools import list_ports  # type: ignore[import]
        ports = list(list_ports.comports())
        if not ports:
            return "No serial ports found."
        return "\n".join(f"{p.device}  —  {p.description}" for p in ports)
    except Exception as exc:
        return f"Error listing ports: {exc}"


@mcp.tool()
def connect_chip(port: str) -> str:
    """Test connectivity with an IN100 chip and read its identity.

    Negotiates baud rate and reports chip type (QFN18/WLCSP/KGD/DFN8) and
    temperature range. Use this to confirm the chip is reachable before programming.

    Args:
        port: Serial port path, e.g. '/dev/tty.usbserial-0001' or 'COM3'.

    Returns:
        Chip type, negotiated baud rate, and industrial-range flag.
    """
    ret, out, err = _cli("connect", "--port", port)
    if ret != 0:
        raise ValueError(f"connect failed: {err or out}")
    return out


@mcp.tool()
def program_chip(
    port: str,
    config_path: str | None = None,
    mode: str = "efuse",
    key: str | None = None,
    rot_exp: int = 15,
    interval: int = 2,
    payload: str = "FF",
    tx_power: int = 4,
    bdaddr: str | None = None,
    trigger: bool = False,
    log_file: str | None = None,
) -> str:
    """Flash an IN100 chip over UART.

    Provide either config_path (a pre-generated .cfg file) OR key (to generate
    inline). Providing both is an error. Providing neither uses all-zeros key.

    Always run with mode='ram' first to verify the config non-destructively,
    then with mode='efuse' to permanently burn.

    Args:
        port: Serial port path, e.g. '/dev/tty.usbserial-0001' or 'COM3'.
        config_path: Path to a pre-generated .cfg JSON file.
        mode: 'ram' for non-destructive RAM test, 'efuse' for permanent burn.
        key: AES-128 key (32-char hex or base64) to generate config inline.
        rot_exp: EID rotation exponent (only used with key).
        interval: Advertising interval in seconds (only used with key).
        payload: Hex payload bytes (only used with key).
        tx_power: TX power in dBm (only used with key).
        bdaddr: Override the BT address, e.g. 'b8aa00000001'.
        trigger: Send [0x00, 0xFF] serial trigger after burn for manufacturing fixtures.
        log_file: Path to write a timestamped log file alongside stdout.

    Returns:
        Programming result including chip type, word count, and success/failure.
    """
    if config_path and key:
        raise ValueError("Provide either config_path or key, not both.")

    args = ["program", "--port", port]
    if config_path:
        args += ["--config", config_path]
    elif key:
        args += [
            "--key", key,
            "--rot-exp", str(rot_exp),
            "--interval", str(interval),
            "--payload", payload,
            "--tx-power", str(tx_power),
        ]
    args.append("--ram" if mode == "ram" else "--efuse")
    if bdaddr:
        args += ["--bdaddr", bdaddr]
    if trigger:
        args.append("--trigger")
    if log_file:
        args += ["--log-file", log_file]

    ret, out, err = _cli(*args)
    if ret != 0:
        raise ValueError(f"program failed: {err or out}")
    return out


@mcp.tool()
def read_efuse(port: str, addr: str) -> str:
    """Read a single eFuse register from an IN100 chip.

    Args:
        port: Serial port path, e.g. '/dev/tty.usbserial-0001'.
        addr: eFuse address as decimal ('17') or hex ('0x11').

    Returns:
        eFuse value in both hex and decimal.
    """
    ret, out, err = _cli("read-efuse", "--port", port, addr)
    if ret != 0:
        raise ValueError(f"read-efuse failed: {err or out}")
    return out


# ──────────────────────────────────────────────────────────────
# RF testing (Direct Test Mode)
# ──────────────────────────────────────────────────────────────


@mcp.tool()
def dtm_start(port: str, params: str = "0,0,37,0,0,0") -> str:
    """Start BLE Direct Test Mode (RF transmit test).

    The chip transmits BLE packets continuously on the specified channel.
    Call dtm_stop to end the test and retrieve packet counts.

    Args:
        port: Serial port path, e.g. '/dev/tty.usbserial-0001'.
        params: Six comma-separated integers: freq_idx,pkt_type,pkt_len,phy,0,0
            freq_idx: 0-39, maps to BLE channels (37=2402 MHz, 38=2426 MHz, 39=2480 MHz).
            pkt_type: 0=PRBS9, 1=0x0F pattern, 2=0x55 pattern, 3=vendor-specific.
            pkt_len:  Packet payload length in bytes (0-255).
            phy:      0=1M, 1=2M, 2=Coded S=8, 3=Coded S=2.

    Returns:
        DTM start result message.
    """
    ret, out, err = _cli("dtm-start", "--port", port, "--params", params)
    if ret != 0:
        raise ValueError(f"dtm-start failed: {err or out}")
    return out


@mcp.tool()
def dtm_stop(port: str) -> str:
    """Stop BLE Direct Test Mode and retrieve the packet count.

    Args:
        port: Serial port path, e.g. '/dev/tty.usbserial-0001'.

    Returns:
        DTM stop result including received/transmitted packet count.
    """
    ret, out, err = _cli("dtm-stop", "--port", port)
    if ret != 0:
        raise ValueError(f"dtm-stop failed: {err or out}")
    return out


@mcp.tool()
def carrier_start(port: str, params: str = "37,7,4") -> str:
    """Start a continuous unmodulated carrier wave on a BLE channel.

    Used for RF certification testing (FCC/CE) and frequency accuracy measurement.
    Call carrier_stop to end the test.

    Args:
        port: Serial port path, e.g. '/dev/tty.usbserial-0001'.
        params: Three comma-separated values: channel,cap,tx_power
            channel:  BLE channel index 0-39.
            cap:      Crystal capacitor trim value (chip-specific, typically 0-15).
            tx_power: TX power in dBm (-4 to 4).

    Returns:
        Carrier start result message.
    """
    ret, out, err = _cli("carrier-start", "--port", port, "--params", params)
    if ret != 0:
        raise ValueError(f"carrier-start failed: {err or out}")
    return out


@mcp.tool()
def carrier_stop(port: str) -> str:
    """Stop the continuous carrier wave test.

    Args:
        port: Serial port path, e.g. '/dev/tty.usbserial-0001'.

    Returns:
        Carrier stop result message.
    """
    ret, out, err = _cli("carrier-stop", "--port", port)
    if ret != 0:
        raise ValueError(f"carrier-stop failed: {err or out}")
    return out


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
