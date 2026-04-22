"""Tests for hubble_inplay_cfg.chip — mocks bridge_call, no hardware required."""

from __future__ import annotations

from unittest.mock import patch

from hubble_inplay_cfg.chip import CHIP_NAMES, Chip

# --- CHIP_NAMES ---


def test_chip_names_coverage():
    assert CHIP_NAMES[0] == "QFN18"
    assert CHIP_NAMES[1] == "WLCSP"
    assert CHIP_NAMES[255] == "UNKNOWN"


# --- dtm_start ---


def test_dtm_start_success():
    with patch("hubble_inplay_cfg.chip.bridge_call") as mock_call:
        mock_call.return_value = {"ok": True, "ret": 0, "msg": "ok"}
        chip = Chip("/dev/ttyUSB0")
        ret, msg = chip.dtm_start([0, 0, 37, 0, 0, 0])
    assert ret == 0
    assert msg == "ok"
    mock_call.assert_called_once_with(
        {"cmd": "dtm_start", "port": "/dev/ttyUSB0", "params": [0, 0, 37, 0, 0, 0]}
    )


def test_dtm_start_error_propagated():
    with patch("hubble_inplay_cfg.chip.bridge_call") as mock_call:
        mock_call.return_value = {"ok": False, "ret": 1, "msg": "fail"}
        chip = Chip("/dev/ttyUSB0")
        ret, msg = chip.dtm_start([0, 0, 37, 0, 0, 0])
    assert ret == 1
    assert msg == "fail"


# --- dtm_stop ---


def test_dtm_stop_success():
    with patch("hubble_inplay_cfg.chip.bridge_call") as mock_call:
        mock_call.return_value = {"ok": True, "ret": 0, "msg": "stopped"}
        chip = Chip("/dev/ttyUSB0")
        ret, msg = chip.dtm_stop()
    assert ret == 0
    assert msg == "stopped"
    mock_call.assert_called_once_with({"cmd": "dtm_stop", "port": "/dev/ttyUSB0"})


# --- carrier_start ---


def test_carrier_start_success():
    with patch("hubble_inplay_cfg.chip.bridge_call") as mock_call:
        mock_call.return_value = {"ok": True, "ret": 0, "msg": "ok"}
        chip = Chip("/dev/ttyUSB0")
        ret, msg = chip.carrier_start(37, 7, 4)
    assert ret == 0
    mock_call.assert_called_once_with(
        {"cmd": "carrier_start", "port": "/dev/ttyUSB0", "ch": 37, "cap": 7, "tx_power": 4}
    )


# --- carrier_stop ---


def test_carrier_stop_success():
    with patch("hubble_inplay_cfg.chip.bridge_call") as mock_call:
        mock_call.return_value = {"ok": True, "ret": 0, "msg": "ok"}
        chip = Chip("/dev/ttyUSB0")
        ret, msg = chip.carrier_stop()
    assert ret == 0
    mock_call.assert_called_once_with({"cmd": "carrier_stop", "port": "/dev/ttyUSB0"})


# --- close / context manager ---


def test_close_is_noop():
    chip = Chip("/dev/ttyUSB0")
    chip.close()  # must not raise


def test_context_manager_enters_and_exits():
    chip = Chip("/dev/ttyUSB0")
    with chip as c:
        assert c is chip
