import base64

import pytest

from hubble_inplay_cfg.builder import (
    assemble_payload_data,
    build_config,
    compute_adv_count_to_reset,
    decode_key,
    parse_payload,
)

VALID_KEY_B64 = base64.b64encode(bytes(range(16))).decode()


def test_email_worked_example():
    # From the email: rot_exp=6, interval=2000ms, 128 EIDs -> 0xFE0 = 4064.
    assert compute_adv_count_to_reset(6, 2000) == 0xFE0


def test_adv_count_with_rot_exp_10_interval_2000():
    # 2^10 / 2 * 127 = 65024
    assert compute_adv_count_to_reset(10, 2000) == 65024


def test_decode_key_base64_round_trip():
    raw = bytes(range(16))
    assert decode_key(base64.b64encode(raw).decode()) == raw.hex()


def test_decode_key_rejects_wrong_length():
    short = base64.b64encode(b"short").decode()
    with pytest.raises(ValueError, match="16 bytes"):
        decode_key(short)


def test_decode_key_rejects_non_base64():
    with pytest.raises(ValueError, match="not valid base64 or 32-char hex"):
        decode_key("!!!not-base64!!!")


def test_decode_key_hex_uppercase():
    assert decode_key("000102030405060708090A0B0C0D0E0F") == "000102030405060708090a0b0c0d0e0f"


def test_decode_key_hex_lowercase():
    assert decode_key("000102030405060708090a0b0c0d0e0f") == "000102030405060708090a0b0c0d0e0f"


def test_decode_key_hex_mixed_case():
    assert decode_key("000102030405060708090A0b0C0d0E0f") == "000102030405060708090a0b0c0d0e0f"


def test_decode_key_strips_whitespace():
    assert decode_key("  000102030405060708090a0b0c0d0e0f\n") == "000102030405060708090a0b0c0d0e0f"


def test_decode_key_rejects_32_char_non_hex():
    # 32 chars but one char ('!') is neither hex nor in the base64 alphabet,
    # so both decode branches fail.
    with pytest.raises(ValueError, match="not valid base64 or 32-char hex"):
        decode_key("!0010203040506070809010203040506")


def test_decode_key_rejects_hex_wrong_length():
    # 30 hex chars — not 32, so hex branch skipped; base64 path rejects too.
    with pytest.raises(ValueError, match="not valid base64 or 32-char hex"):
        decode_key("000102030405060708090a0b0c0d0e")


def test_decode_key_rejects_32_char_hex_with_embedded_whitespace():
    # bytes.fromhex ignores ASCII whitespace: 32 chars with spaces decodes to
    # fewer than 16 bytes. The length check must still reject it.
    bad = "AA BB CC DD EE FF 00 11 22 33 44"
    assert len(bad) == 32
    with pytest.raises(ValueError, match="16 bytes"):
        decode_key(bad)


def test_parse_payload_default_single_byte():
    assert parse_payload("FF") == b"\xff"


def test_parse_payload_multi_byte():
    assert parse_payload("FF01AB") == b"\xff\x01\xab"


def test_parse_payload_rejects_empty():
    with pytest.raises(ValueError, match="at least 1 byte"):
        parse_payload("")


def test_parse_payload_rejects_odd_length():
    with pytest.raises(ValueError, match="not valid hex"):
        parse_payload("F")


def test_assemble_payload_default_single_byte():
    data, length = assemble_payload_data(b"\xff")
    assert data == (
        "0303a6fc1316a6fc08"
        "<SALT 2byte 0 0><EID 8byte 1 0>"
        "<EncRaw FF 1byte 0 1>"
        "<TAG 4byte 0 0>"
    )
    assert length == 24


def test_assemble_payload_three_bytes():
    data, length = assemble_payload_data(b"\xff\x01\xab")
    assert "<EncRaw FF01AB 3byte 0 1>" in data
    assert data.startswith("0303a6fc1516a6fc08")  # 18 + 3 = 21 = 0x15
    assert length == 26


def test_build_config_sets_all_fields():
    cfg = build_config(
        interval_ms=2000,
        key0=VALID_KEY_B64,
        rot_exp=10,
        payload_hex="FF",
    )
    adv = cfg["advSet"][0]
    assert adv["interval"] == 2000
    assert adv["rot_exp"] == 10
    assert adv["payload"][0]["len"] == 24
    assert "<EncRaw FF 1byte 0 1>" in adv["payload"][0]["data"]
    assert cfg["txSetting"]["key0"] == "000102030405060708090a0b0c0d0e0f"
    assert "write: 3 1 3 3284 fe00" in cfg["regSettingCust"]


def test_build_config_uses_email_timer_value():
    cfg = build_config(
        interval_ms=2000,
        key0=VALID_KEY_B64,
        rot_exp=6,
        payload_hex="FF",
    )
    assert "write: 3 1 3 3284 fe0" in cfg["regSettingCust"]


def test_build_config_rejects_bad_key():
    with pytest.raises(ValueError):
        build_config(
            interval_ms=2000,
            key0="not-base64!!",
            rot_exp=10,
            payload_hex="FF",
        )


def test_build_config_rejects_nonpositive_interval():
    with pytest.raises(ValueError):
        build_config(
            interval_ms=0,
            key0=VALID_KEY_B64,
            rot_exp=10,
            payload_hex="FF",
        )


def test_build_config_preserves_bd_addr():
    cfg = build_config(
        interval_ms=2000,
        key0=VALID_KEY_B64,
        rot_exp=10,
        payload_hex="FF",
    )
    assert cfg["advSet"][0]["bdAddr"] == "b8aa00000001"


def test_build_config_tx_power_defaults_to_4():
    cfg = build_config(
        interval_ms=2000,
        key0=VALID_KEY_B64,
        rot_exp=10,
        payload_hex="FF",
    )
    assert cfg["txSetting"]["txPower"] == 4


def test_build_config_tx_power_override():
    cfg = build_config(
        interval_ms=2000,
        key0=VALID_KEY_B64,
        rot_exp=10,
        payload_hex="FF",
        tx_power=-2,
    )
    assert cfg["txSetting"]["txPower"] == -2
