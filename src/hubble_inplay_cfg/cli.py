"""hubble-inplay-cfg CLI — generate IN100 configs and program chips over UART."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections.abc import Sequence
from typing import Any

from hubble_inplay_cfg.builder import build_config
from hubble_inplay_cfg.chip import CHIP_NAMES, Chip

_VERSION = "0.1.0"

# ──────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────

def _setup_logging(debug: bool, log_file: str | None) -> logging.Logger:
    logger = logging.getLogger("hubble_inplay_cfg")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")

    handler: logging.Handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)
    logger.addHandler(handler)

    if log_file:
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        fh = logging.FileHandler(log_file)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


# ──────────────────────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────────────────────

def _beacon_sys_path() -> None:
    """Ensure beacon/ is on sys.path so 'import beacon.*' works."""
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    if pkg_dir not in sys.path:
        sys.path.insert(0, pkg_dir)


def _load_config(path: str) -> dict[str, Any]:
    with open(path) as f:
        return json.load(f)


def _apply_bdaddr(config: dict[str, Any], bdaddr: str) -> None:
    config["advSet"][0]["bdAddr"] = bdaddr.lower().replace(":", "")


def _connect_chip(port: str, autorate: bool, logger: logging.Logger) -> Chip:
    logger.info(f"Opening {port} ...")
    chip = Chip(port)
    if autorate:
        logger.info("Negotiating baud rate ...")
        ret, baud = chip.connect()
        if ret != 0:
            chip.close()
            logger.error(f"Baud rate negotiation failed (error {ret})")
            sys.exit(1)
        logger.info(f"  Baud rate: {baud}")
    return chip


def _run_program_flow(
    chip: Chip,
    config: dict[str, Any],
    ram_mode: bool,
    logger: logging.Logger,
) -> None:
    """Execute the full programming flow: calibration → encode → burn."""
    _beacon_sys_path()
    import beacon.beacon as bmod  # type: ignore[import]
    import beacon.beacon_efuse_format as ef  # type: ignore[import]

    from hubble_inplay_cfg.mis import (
        rt_ble_static_address_post_process,
        rt_ble_static_address_process,
        rt_calibration_process,
    )

    _chip = chip._inner  # raw _BeaconChip for beacon package calls

    logger.info("Reading chip info ...")
    ret, efuse11_value = _chip.read_efuse(17)
    if ret != 0:
        logger.error(f"read_efuse(17) failed (error {ret})")
        sys.exit(1)

    ret, chip_type = _chip.get_chip_type()
    if ret != 0:
        logger.error(f"get_chip_type() failed (error {ret})")
        sys.exit(1)
    logger.info(f"  Chip type: {CHIP_NAMES.get(chip_type, chip_type)}")

    logger.debug("Loading beacon config ...")
    b = bmod.Beacon()
    b.load_config(config)

    logger.info("Running runtime processes ...")
    b.rt_uart_pin_as_gpio_proc(efuse11_value, chip_type)

    ret, msg = rt_calibration_process(_chip, b)
    if ret != 0:
        logger.error(f"Calibration failed: {msg}")
        sys.exit(1)

    ret, msg = rt_ble_static_address_process(_chip, b)
    if ret != 0:
        logger.error(f"Static address process failed: {msg}")
        sys.exit(1)

    _, h_flag = _chip.is_full_range_industrial()
    logger.debug(f"  Full-range industrial: {bool(h_flag)}")

    logger.info("Converting config to packet ...")
    packet = b.convert_to_packet(h_flag, is_run_in_ram=ram_mode)
    rt_ble_static_address_post_process(b)

    word_array = [0] * 384
    word_cnt = ef.packet_to_raw(str(packet), word_array)
    logger.info(f"  Word count: {word_cnt}/256")
    if word_cnt > 256:
        logger.error(f"eFuse overflow: {word_cnt} words (max 256)")
        sys.exit(1)

    chip.set_word_array(word_array)

    if ram_mode:
        logger.info("Running in RAM (test mode) ...")
        ret = _chip.run_in_ram()
        if ret != 0:
            logger.error(f"RAM test failed (error {ret})")
            sys.exit(1)
        logger.info("RAM test complete.")
    else:
        logger.info("Burning eFuse ...")
        ret = _chip.burn_efuse(reset_en=True, clear_uart_cache=False)
        if ret != 0:
            logger.error(f"eFuse burn failed (error {ret})")
            sys.exit(1)
        logger.info("eFuse burn complete.")


# ──────────────────────────────────────────────────────────────
# Subcommand handlers
# ──────────────────────────────────────────────────────────────

def cmd_generate(args: argparse.Namespace, logger: logging.Logger) -> None:
    cfg = build_config(
        interval_ms=args.interval * 1000,
        key0=args.key,
        rot_exp=args.rot_exp,
        payload_hex=args.payload,
        tx_power=args.tx_power,
    )
    rendered = json.dumps(cfg, indent=4)
    if args.output:
        with open(args.output, "w") as f:
            f.write(rendered + "\n")
        logger.info(f"Config written to {args.output}")
    else:
        print(rendered)


def cmd_validate(args: argparse.Namespace, logger: logging.Logger) -> None:
    _beacon_sys_path()
    import beacon.beacon as bmod  # type: ignore[import]
    import beacon.beacon_efuse_format as ef  # type: ignore[import]

    config = _load_config(args.config)
    b = bmod.Beacon()
    b.load_config(config)
    packet = b.convert_to_packet(False, is_run_in_ram=False)
    word_array = [0] * 384
    word_cnt = ef.packet_to_raw(str(packet), word_array)

    status = "OK" if word_cnt <= 256 else "OVERFLOW"
    non_zero = [(i, word_array[i]) for i in range(256) if word_array[i] != 0]
    logger.info(f"Config:      {args.config}")
    logger.info(f"Word count:  {word_cnt}/256 {status}")
    logger.info(f"Non-zero:    {len(non_zero)} words")

    if args.verbose:
        print("\nFirst 32 words:")
        for i in range(0, min(32, 256), 8):
            row = " ".join(f"{word_array[i + j]:04x}" for j in range(8))
            print(f"  [{i:3d}] {row}")
        if non_zero:
            print("\nNon-zero words:")
            for idx, val in non_zero:
                print(f"  [{idx:3d}] 0x{val:04x} ({val})")

    if word_cnt > 256:
        sys.exit(1)


def cmd_program(args: argparse.Namespace, logger: logging.Logger) -> None:
    has_config = bool(args.config)
    has_inline = bool(args.key)

    if has_config and has_inline:
        logger.error("--config and --key are mutually exclusive")
        sys.exit(1)
    if not has_config and not has_inline:
        logger.error("Provide either --config or --key (with --rot-exp, --interval)")
        sys.exit(1)

    if has_config:
        config = _load_config(args.config)
    else:
        config = build_config(
            interval_ms=args.interval * 1000,
            key0=args.key,
            rot_exp=args.rot_exp,
            payload_hex=args.payload,
            tx_power=args.tx_power,
        )

    if args.bdaddr:
        _apply_bdaddr(config, args.bdaddr)
        logger.debug(f"BT address overridden to {args.bdaddr}")

    with _connect_chip(args.port, not args.no_autorate, logger) as chip:
        _run_program_flow(chip, config, args.ram, logger)

        if not args.ram and args.trigger:
            logger.debug("Sending post-burn trigger signal ...")
            chip.send_trigger()


def cmd_connect(args: argparse.Namespace, logger: logging.Logger) -> None:
    with _connect_chip(args.port, True, logger) as chip:
        ret, chip_type = chip.get_chip_type()
        if ret != 0:
            logger.error(f"get_chip_type() failed (error {ret})")
            sys.exit(1)
        logger.info(f"  Chip type: {CHIP_NAMES.get(chip_type, chip_type)}")

        _, h_flag = chip.is_full_range_industrial()
        logger.info(f"  Full-range industrial: {bool(h_flag)}")
        logger.info("Connection OK.")


def cmd_read_efuse(args: argparse.Namespace, logger: logging.Logger) -> None:
    addr = int(args.address, 0)
    with _connect_chip(args.port, True, logger) as chip:
        ret, value = chip.read_efuse(addr)
        if ret != 0:
            logger.error(f"read_efuse(0x{addr:02x}) failed (error {ret})")
            sys.exit(1)
        print(f"eFuse[0x{addr:02x}] = 0x{value:04x} ({value})")


def cmd_dtm_start(args: argparse.Namespace, logger: logging.Logger) -> None:
    try:
        params = [int(x.strip()) for x in args.params.split(",")]
    except ValueError:
        logger.error("--params must be comma-separated integers")
        sys.exit(1)
    if len(params) != 6:
        logger.error(f"--params requires exactly 6 values, got {len(params)}")
        sys.exit(1)

    chip = Chip(args.port)
    logger.info(f"Starting DTM with params {params} ...")
    ret, msg = chip.dtm_start(params)
    chip.close()
    if ret != 0:
        logger.error(f"DTM start failed: {msg}")
        sys.exit(1)
    logger.info(f"DTM started: {msg}")


def cmd_dtm_stop(args: argparse.Namespace, logger: logging.Logger) -> None:
    chip = Chip(args.port)
    logger.info("Stopping DTM ...")
    ret, msg = chip.dtm_stop()
    chip.close()
    if ret != 0:
        logger.error(f"DTM stop failed: {msg}")
        sys.exit(1)
    logger.info(f"DTM stopped: {msg}")


def cmd_carrier_start(args: argparse.Namespace, logger: logging.Logger) -> None:
    try:
        ch, cap, tx_power = [int(x.strip()) for x in args.params.split(",")]
    except (ValueError, TypeError):
        logger.error("--params must be 3 comma-separated integers: ch,cap,tx_power")
        sys.exit(1)

    chip = Chip(args.port)
    logger.info(f"Starting carrier wave: ch={ch} cap={cap} tx_power={tx_power} ...")
    ret, msg = chip.carrier_start(ch, cap, tx_power)
    chip.close()
    if ret != 0:
        logger.error(f"Carrier start failed: {msg}")
        sys.exit(1)
    logger.info(f"Carrier wave started: {msg}")


def cmd_carrier_stop(args: argparse.Namespace, logger: logging.Logger) -> None:
    chip = Chip(args.port)
    logger.info("Stopping carrier wave ...")
    ret, msg = chip.carrier_stop()
    chip.close()
    if ret != 0:
        logger.error(f"Carrier stop failed: {msg}")
        sys.exit(1)
    logger.info(f"Carrier wave stopped: {msg}")


def cmd_version(_args: argparse.Namespace, _logger: logging.Logger) -> None:
    print(f"hubble-inplay-cfg {_VERSION}")


# ──────────────────────────────────────────────────────────────
# Argument parser
# ──────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hubble-inplay-cfg",
        description="Generate IN100 NanoBeacon configs and program chips over UART.",
    )
    parser.add_argument("--log-file", metavar="PATH", help="Write timestamped log to this file.")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug output.")

    sub = parser.add_subparsers(dest="command", required=True)

    # ── generate ──────────────────────────────────────────────
    p = sub.add_parser("generate", help="Generate a .cfg JSON file (no hardware required).")
    p.add_argument("--key", default="00000000000000000000000000000000",
                   help="16-byte AES-128 key: 32-char hex or base64. Default: all-zeros.")
    p.add_argument("--rot-exp", type=int, default=15,
                   help="EID rotation exponent (2^n seconds). Range 1–15. Default: 15.")
    p.add_argument("--interval", type=int, default=2,
                   help="Advertising interval in seconds. Default: 2.")
    p.add_argument("--payload", default="FF",
                   help="Raw hex payload bytes (≥1 byte). Default: FF.")
    p.add_argument("--tx-power", type=int, default=4,
                   help="TX power in dBm (−4 to 4). Default: 4.")
    p.add_argument("-o", "--output", metavar="PATH", help="Write config to file instead of stdout.")

    # ── validate ──────────────────────────────────────────────
    p = sub.add_parser("validate", help="Validate a config file offline (no hardware required).")
    p.add_argument("--config", "-c", required=True, metavar="PATH", help="JSON config file.")
    p.add_argument("--verbose", "-v", action="store_true", help="Show word dump.")

    # ── program ───────────────────────────────────────────────
    p = sub.add_parser("program", help="Program a chip from a config file or inline parameters.")
    p.add_argument(
        "--port", "-p", required=True, help="Serial port (e.g. /dev/tty.usbserial-0001)."
    )
    # Config source — mutually exclusive at runtime (validated in cmd_program)
    p.add_argument("--config", "-c", metavar="PATH", help="JSON config file.")
    p.add_argument("--key", help="AES-128 key to generate config inline.")
    p.add_argument("--rot-exp", type=int, default=15, help="EID rotation exponent.")
    p.add_argument("--interval", type=int, default=2, help="Advertising interval in seconds.")
    p.add_argument("--payload", default="FF", help="Raw hex payload bytes.")
    p.add_argument("--tx-power", type=int, default=4, help="TX power in dBm.")
    # Per-device overrides
    p.add_argument("--bdaddr", metavar="ADDR",
                   help="Override BT address (e.g. b8aa00000001 or b8:aa:00:00:00:01).")
    # Programming mode
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--ram", action="store_true", help="Run in RAM (non-destructive test).")
    mode.add_argument(
        "--efuse", action="store_true", default=True, help="Burn eFuse (default, permanent)."
    )
    # Manufacturing options
    p.add_argument("--trigger", action="store_true",
                   help="Send [0x00, 0xFF] post-burn trigger signal to test fixture.")
    p.add_argument("--no-autorate", action="store_true",
                   help="Skip baud rate negotiation (use fixed 115200).")

    # ── connect ───────────────────────────────────────────────
    p = sub.add_parser("connect", help="Test connectivity and identify the chip.")
    p.add_argument("--port", "-p", required=True, help="Serial port.")

    # ── read-efuse ────────────────────────────────────────────
    p = sub.add_parser("read-efuse", help="Read an eFuse register from the chip.")
    p.add_argument("--port", "-p", required=True, help="Serial port.")
    p.add_argument("address", help="eFuse address (decimal or 0x hex).")

    # ── dtm-start ─────────────────────────────────────────────
    p = sub.add_parser("dtm-start", help="Start BLE Direct Test Mode for RF testing.")
    p.add_argument("--port", "-p", required=True, help="Serial port.")
    p.add_argument("--params", "-x", required=True,
                   help="6 comma-separated integers: freq_idx,pkt_type,pkt_len,phy,p4,p5")

    # ── dtm-stop ──────────────────────────────────────────────
    p = sub.add_parser("dtm-stop", help="Stop BLE Direct Test Mode.")
    p.add_argument("--port", "-p", required=True, help="Serial port.")

    # ── carrier-start ─────────────────────────────────────────
    p = sub.add_parser("carrier-start", help="Start continuous carrier wave test.")
    p.add_argument("--port", "-p", required=True, help="Serial port.")
    p.add_argument("--params", "-x", required=True,
                   help="3 comma-separated integers: ch,cap,tx_power")

    # ── carrier-stop ──────────────────────────────────────────
    p = sub.add_parser("carrier-stop", help="Stop carrier wave test.")
    p.add_argument("--port", "-p", required=True, help="Serial port.")

    # ── version ───────────────────────────────────────────────
    sub.add_parser("version", help="Print tool version.")

    return parser


# ──────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────

def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    logger = _setup_logging(args.debug, getattr(args, "log_file", None))

    dispatch = {
        "generate": cmd_generate,
        "validate": cmd_validate,
        "program": cmd_program,
        "connect": cmd_connect,
        "read-efuse": cmd_read_efuse,
        "dtm-start": cmd_dtm_start,
        "dtm-stop": cmd_dtm_stop,
        "carrier-start": cmd_carrier_start,
        "carrier-stop": cmd_carrier_stop,
        "version": cmd_version,
    }
    dispatch[args.command](args, logger)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
