"""CLI entry point for generating IN100 Hubble configs."""

import argparse
import json
import sys
from collections.abc import Sequence

from .builder import build_config

ROT_EXP_PREFERRED_MIN = 10
ROT_EXP_PREFERRED_MAX = 15
ROT_EXP_ABSOLUTE_MIN = 1
ROT_EXP_ABSOLUTE_MAX = 15


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hubble-inplay-cfg",
        description="Generate an IN100 NanoBeacon .cfg file for Hubble advertising.",
    )
    parser.add_argument(
        "--key",
        default="00000000000000000000000000000000",
        help=(
            "16-byte AES-128 key. Accepts 32-char hex "
            "(e.g. E001020304...0F) or base64; auto-detected. "
            "Defaults to all-zeros key."
        ),
    )
    parser.add_argument(
        "--rot-exp",
        type=int,
        default=ROT_EXP_PREFERRED_MAX,
        help=(
            f"EID rotation period exponent (2^rot_exp seconds). "
            f"Accepted: {ROT_EXP_ABSOLUTE_MIN}-{ROT_EXP_ABSOLUTE_MAX}; "
            f"preferred: {ROT_EXP_PREFERRED_MIN}-{ROT_EXP_PREFERRED_MAX}. "
            f"Default: {ROT_EXP_PREFERRED_MAX}."
        ),
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=2,
        help="Advertising interval in seconds (matches advSet[0].interval). Default: 2.",
    )
    parser.add_argument(
        "--payload",
        default="FF",
        help="Raw hex payload bytes (>=1 byte, even number of hex chars). Default: FF.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Write config to this path instead of stdout.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not (ROT_EXP_ABSOLUTE_MIN <= args.rot_exp <= ROT_EXP_ABSOLUTE_MAX):
        parser.error(
            f"--rot-exp must be between {ROT_EXP_ABSOLUTE_MIN} and "
            f"{ROT_EXP_ABSOLUTE_MAX} (got {args.rot_exp})"
        )
    if not (ROT_EXP_PREFERRED_MIN <= args.rot_exp <= ROT_EXP_PREFERRED_MAX):
        print(
            f"warning: --rot-exp {args.rot_exp} is outside the range "
            f"{ROT_EXP_PREFERRED_MIN}-{ROT_EXP_PREFERRED_MAX}. "
            "This should be used for local testing only. "
            "This will not be compatible with the Hubble backend services.",
            file=sys.stderr,
        )

    if args.interval <= 0:
        parser.error(f"--interval must be positive (got {args.interval})")

    interval_ms = args.interval * 1000

    try:
        cfg = build_config(
            interval_ms=interval_ms,
            key0=args.key,
            rot_exp=args.rot_exp,
            payload_hex=args.payload,
        )
    except ValueError as exc:
        parser.error(str(exc))

    rendered = json.dumps(cfg, indent=4)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(rendered)
            f.write("\n")
    else:
        print(rendered)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
