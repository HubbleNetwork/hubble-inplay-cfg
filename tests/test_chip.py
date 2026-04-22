"""Tests for hubble_inplay_cfg.chip — uses mock serial to avoid hardware."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from hubble_inplay_cfg.chip import CHIP_NAMES, Chip


@pytest.fixture()
def mock_chip():
    """Return a Chip instance with fully mocked internals (no real serial port)."""
    with patch("hubble_inplay_cfg.chip.serial.Serial") as mock_serial_cls, patch(
        "hubble_inplay_cfg.chip._BeaconChip"
    ) as mock_beacon_cls:
        mock_serial = MagicMock()
        mock_serial_cls.return_value = mock_serial
        mock_inner = MagicMock()
        mock_beacon_cls.return_value = mock_inner

        chip = Chip("/dev/ttyUSB0")
        chip._serial = mock_serial
        chip._inner = mock_inner
        yield chip, mock_serial, mock_inner


# --- CHIP_NAMES ---


def test_chip_names_coverage():
    assert CHIP_NAMES[0] == "QFN18"
    assert CHIP_NAMES[1] == "WLCSP"
    assert CHIP_NAMES[255] == "UNKNOWN"


# --- connect ---


def test_connect_delegates(mock_chip):
    chip, _, inner = mock_chip
    inner.uart_rate_adaptive.return_value = (0, 115200)
    assert chip.connect() == (0, 115200)
    inner.uart_rate_adaptive.assert_called_once()


# --- read_efuse ---


def test_read_efuse_delegates(mock_chip):
    chip, _, inner = mock_chip
    inner.read_efuse.return_value = (0, 0xAB)
    ret, val = chip.read_efuse(5)
    assert ret == 0
    assert val == 0xAB
    inner.read_efuse.assert_called_once_with(5)


def test_read_efuse_error_propagated(mock_chip):
    chip, _, inner = mock_chip
    inner.read_efuse.return_value = (1, 0)
    ret, _ = chip.read_efuse(99)
    assert ret == 1


# --- get_chip_type ---


def test_get_chip_type_delegates(mock_chip):
    chip, _, inner = mock_chip
    inner.get_chip_type.return_value = (0, 0)
    ret, chip_type = chip.get_chip_type()
    assert ret == 0
    assert CHIP_NAMES[chip_type] == "QFN18"


# --- set_word_array / run_in_ram / burn_efuse ---


def test_set_word_array(mock_chip):
    chip, _, inner = mock_chip
    chip.set_word_array([1, 2, 3])
    assert inner.wordArray == [1, 2, 3]


def test_run_in_ram_delegates(mock_chip):
    chip, _, inner = mock_chip
    inner.run_in_ram.return_value = 0
    assert chip.run_in_ram() == 0


def test_burn_efuse_default_args(mock_chip):
    chip, _, inner = mock_chip
    inner.burn_efuse.return_value = 0
    chip.burn_efuse()
    inner.burn_efuse.assert_called_once_with(reset_en=True, clear_uart_cache=False)


def test_burn_efuse_no_reset(mock_chip):
    chip, _, inner = mock_chip
    inner.burn_efuse.return_value = 0
    chip.burn_efuse(reset=False)
    inner.burn_efuse.assert_called_once_with(reset_en=False, clear_uart_cache=False)


# --- DTM ---


def test_dtm_start_delegates(mock_chip):
    chip, _, inner = mock_chip
    inner.dtm_start.return_value = (0, "ok")
    ret, msg = chip.dtm_start([0, 0, 37, 0, 0, 0])
    assert ret == 0
    inner.dtm_start.assert_called_once_with([0, 0, 37, 0, 0, 0], False)


def test_dtm_stop_delegates(mock_chip):
    chip, _, inner = mock_chip
    inner.dtm_stop.return_value = (0, "ok")
    ret, _ = chip.dtm_stop()
    assert ret == 0


# --- Carrier ---


def test_carrier_start_delegates(mock_chip):
    chip, _, inner = mock_chip
    inner.carrier_test_start.return_value = (0, "ok")
    ret, _ = chip.carrier_start(37, 7, 4)
    inner.carrier_test_start.assert_called_once_with(37, 7, 4)


def test_carrier_stop_delegates(mock_chip):
    chip, _, inner = mock_chip
    inner.carrier_test_stop.return_value = (0, "ok")
    ret, _ = chip.carrier_stop()
    assert ret == 0


# --- send_trigger ---


def test_send_trigger_writes_bytes(mock_chip):
    chip, serial, _ = mock_chip
    chip.send_trigger()
    serial.write.assert_called_once_with(bytes([0x00, 0xFF]))
    serial.flush.assert_called_once()


# --- close / context manager ---


def test_close_when_open(mock_chip):
    chip, serial, _ = mock_chip
    serial.is_open = True
    chip.close()
    serial.close.assert_called_once()


def test_close_when_already_closed(mock_chip):
    chip, serial, _ = mock_chip
    serial.is_open = False
    chip.close()
    serial.close.assert_not_called()


def test_context_manager_closes(mock_chip):
    chip, serial, _ = mock_chip
    serial.is_open = True
    with chip:
        pass
    serial.close.assert_called_once()
