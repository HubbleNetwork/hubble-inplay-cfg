"""Build an IN100 NanoBeacon config dict for Hubble advertising."""

import base64
import contextlib
from typing import Any

from .template import base_config

KEY_LENGTH_BYTES = 16
EID_INDEX_MAX = 127  # pool is 128 entries, indices 0-127
TIMER_REG_PREFIX = "write: 3 1 3 3284 "

_FIXED_PREFIX = "0303a6fc"
_SERVICE_DATA_HEADER = "16a6fc08"
_SALT_EID_TOKENS = "<SALT 2byte 0 0><EID 8byte 1 0>"
_TAG_TOKEN = "<TAG 4byte 0 0>"

# Fixed byte counts inside the service data, excluding the variable payload.
_FIXED_SERVICE_DATA_BYTES = (
    4  # 16a6fc08
    + 2  # SALT
    + 8  # EID
    + 4  # TAG
)


def decode_key(key: str) -> str:
    """Decode an AES-128 key (32-char hex or base64) to lowercase hex."""
    stripped = key.strip()
    raw: bytes | None = None
    if len(stripped) == 32:
        with contextlib.suppress(ValueError):
            raw = bytes.fromhex(stripped)
    if raw is None:
        try:
            raw = base64.b64decode(stripped, validate=True)
        except ValueError as exc:
            raise ValueError(
                f"key is not valid base64 or 32-char hex: {exc}"
            ) from exc
    if len(raw) != KEY_LENGTH_BYTES:
        raise ValueError(
            f"key must decode to {KEY_LENGTH_BYTES} bytes, got {len(raw)}"
        )
    return raw.hex()


def parse_payload(payload_hex: str) -> bytes:
    """Parse a raw hex payload string into bytes. Requires >=1 byte."""
    try:
        raw = bytes.fromhex(payload_hex)
    except ValueError as exc:
        raise ValueError(f"payload is not valid hex: {exc}") from exc
    if len(raw) < 1:
        raise ValueError("payload must be at least 1 byte")
    return raw


def assemble_payload_data(payload: bytes) -> tuple[str, int]:
    """Assemble the `advSet[0].payload[0].data` string and its `len` field.

    Returns (data_string, payload_len).
    """
    n = len(payload)
    service_data_len = _FIXED_SERVICE_DATA_BYTES + n
    length_byte = f"{service_data_len:02X}"
    payload_hex = payload.hex().upper()
    enc_raw = f"<EncRaw {payload_hex} {n}byte 0 1>"
    data = (
        _FIXED_PREFIX
        + length_byte
        + _SERVICE_DATA_HEADER
        + _SALT_EID_TOKENS
        + enc_raw
        + _TAG_TOKEN
    )
    total_len = len(_FIXED_PREFIX) // 2 + 1 + service_data_len
    return data, total_len


def compute_adv_count_to_reset(rot_exp: int, interval_ms: int) -> int:
    """Number of advertisements before the EID timer should reset.

    adv_count = floor(2^rot_exp / (interval_ms / 1000) * EID_INDEX_MAX)
    """
    if interval_ms <= 0:
        raise ValueError("interval_ms must be positive")
    return (2**rot_exp * EID_INDEX_MAX * 1000) // interval_ms


def _update_timer_register(reg_list: list[str], adv_count: int) -> None:
    value_hex = f"{adv_count:x}"
    for i, entry in enumerate(reg_list):
        if entry.startswith(TIMER_REG_PREFIX):
            reg_list[i] = TIMER_REG_PREFIX + value_hex
            return
    raise RuntimeError(
        f"template is missing expected register write starting with {TIMER_REG_PREFIX!r}"
    )


def build_config(
    *,
    interval_ms: int,
    key0: str,
    rot_exp: int,
    payload_hex: str = "FF",
) -> dict[str, Any]:
    """Produce a fully-populated IN100 config dict ready to serialize as JSON."""
    key0_hex = decode_key(key0)
    payload_bytes = parse_payload(payload_hex)
    data_string, payload_len = assemble_payload_data(payload_bytes)
    adv_count = compute_adv_count_to_reset(rot_exp, interval_ms)

    cfg = base_config()
    adv = cfg["advSet"][0]
    adv["interval"] = interval_ms
    adv["rot_exp"] = rot_exp
    adv["payload"][0]["data"] = data_string
    adv["payload"][0]["len"] = payload_len
    cfg["txSetting"]["key0"] = key0_hex
    _update_timer_register(cfg["regSettingCust"], adv_count)

    return cfg
