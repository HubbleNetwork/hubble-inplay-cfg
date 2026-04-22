"""Runtime calibration and BLE address processes for the IN100 chip.

These functions read calibration data from the chip's eFuse at programming
time and apply correction factors to the beacon config. They are called once
during the programming flow, between chip identification and config conversion.

Both `chip` and `beacon` arguments are raw beacon package objects created
internally by the programming flow — not the Chip adapter from chip.py.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from beacon.mis import (  # type: ignore[import]
    static_address_post_proc as _post_proc,
)
from beacon.mis import (
    static_address_pre_proc as _pre_proc,
)

_ERR_OK = 0
_OK_MSG = "ok"


def rt_calibration_process(chip: object, beacon: object) -> tuple[int, str]:
    """Read calibration eFuse registers and apply LDO/VCC/temperature/ADC corrections.

    Returns (0, 'ok') on success, or (error_code, error_message) on the first failure.
    """
    err = chip.NANO_BCN_ERR_NO_ERROR  # type: ignore[attr-defined]

    ret, efuse05 = chip.read_efuse(5)  # type: ignore[attr-defined]
    if ret == err:
        beacon.calibration.ldo_calibration_process(efuse05, beacon.tx_setting.tx_power)  # type: ignore[attr-defined]
    else:
        return ret, f"read efuse05 failed,{ret}"

    ret, efuse06 = chip.read_efuse(6)  # type: ignore[attr-defined]
    if ret != err:
        return ret, f"read efuse06 failed,{ret}"

    ret, efuse07 = chip.read_efuse(7)  # type: ignore[attr-defined]
    if ret != err:
        return ret, f"read efuse07 failed,{ret}"

    ret, efuse08 = chip.read_efuse(8)  # type: ignore[attr-defined]
    if ret == err:
        beacon.calibration.vcc_calibration_process(efuse06, efuse07, efuse08, beacon.adc.vcc_unit)  # type: ignore[attr-defined]
    else:
        return ret, f"read efuse08 failed,{ret}"

    ret, efuse09 = chip.read_efuse(9)  # type: ignore[attr-defined]
    if ret == err:
        beacon.calibration.temperature_calibration_process(efuse09, beacon.adc.temp_unit)  # type: ignore[attr-defined]
    else:
        return ret, f"read efuse09 failed,{ret}"

    ret, efuse0c = chip.read_efuse(12)  # type: ignore[attr-defined]
    if ret != err:
        return ret, f"read efuse0c failed,{ret}"

    ret, efuse0d = chip.read_efuse(13)  # type: ignore[attr-defined]
    if ret != err:
        return ret, f"read efuse0d failed,{ret}"

    beacon.calibration.adc_calibration_process(efuse0c, efuse0d, beacon.adc)  # type: ignore[attr-defined]
    return _ERR_OK, _OK_MSG


def rt_ble_static_address_process(chip: object, beacon: object) -> tuple[int, str]:
    """Generate or validate the static BLE address for all advertising sets.

    Internally uses AES-CTR (via pycryptodomex) when staticAddrGen=1.
    Returns (0, 'ok') on success, or (error_code, error_message) on failure.
    """
    for adv_set in (beacon.adv_set1, beacon.adv_set2, beacon.adv_set3):  # type: ignore[attr-defined]
        ret, ret_str = _pre_proc(adv_set, beacon, chip)
        if ret != 0:
            return ret, ret_str
    return _ERR_OK, _OK_MSG


def rt_ble_static_address_post_process(beacon: object) -> None:
    """Finalize static address fields in all advertising sets after conversion."""
    for adv_set in (beacon.adv_set1, beacon.adv_set2, beacon.adv_set3):  # type: ignore[attr-defined]
        _post_proc(adv_set)
