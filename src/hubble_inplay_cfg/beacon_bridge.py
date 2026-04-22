"""Bridge script: must run under Python 3.10 to load beacon/*.pyc modules.

Called as a subprocess by _bridge_client.bridge_call(). Reads one JSON
command from stdin, streams {"type":"log"} lines to stdout during
execution, and closes with a {"type":"done"} line.
"""

from __future__ import annotations

import json
import os
import sys

# beacon/*.pyc files live next to this script; make them importable.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CHIP_NAMES = {0: "QFN18", 1: "WLCSP", 2: "KGD", 3: "DFN8", 255: "UNKNOWN"}


def _log(level: str, msg: str) -> None:
    print(json.dumps({"type": "log", "level": level, "msg": msg}), flush=True)


def _done(**kwargs: object) -> None:
    print(json.dumps({"type": "done", **kwargs}), flush=True)


def _open_serial(port: str, baud: int = 115200, timeout: float = 0.5):  # type: ignore[return]
    import serial  # type: ignore[import]

    return serial.Serial(
        port,
        baud,
        timeout=timeout,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        write_timeout=timeout,
        inter_byte_timeout=timeout,
    )


def _make_chip(ser):  # type: ignore[return]
    from beacon.chip import Chip as _BeaconChip  # type: ignore[import]

    class _MockProgress:
        def emit(self, value: int) -> None:
            pass

    chip = _BeaconChip(ser)
    chip.proc_progress = _MockProgress()
    return chip


# ── commands ─────────────────────────────────────────────────────────────────


def cmd_validate(data: dict) -> None:
    import beacon.beacon as bmod  # type: ignore[import]
    import beacon.beacon_efuse_format as ef  # type: ignore[import]

    config = data["config"]
    b = bmod.Beacon()
    b.load_config(config)
    packet = b.convert_to_packet(False, is_run_in_ram=False)
    word_array = [0] * 384
    word_cnt = ef.packet_to_raw(str(packet), word_array)
    _done(ok=True, word_count=word_cnt, word_array=word_array)


def cmd_connect(data: dict) -> None:
    ser = _open_serial(data["port"])
    try:
        chip = _make_chip(ser)
        ret, baud = chip.uart_rate_adaptive()
        if ret != 0:
            _done(ok=False, error=f"uart_rate_adaptive failed (error {ret})")
            return
        ret, chip_type = chip.get_chip_type()
        if ret != 0:
            _done(ok=False, error=f"get_chip_type failed (error {ret})")
            return
        _, h_flag = chip.is_full_range_industrial()
        _done(ok=True, baud=baud, chip_type=chip_type, h_flag=bool(h_flag))
    finally:
        ser.close()


def cmd_read_efuse(data: dict) -> None:
    ser = _open_serial(data["port"])
    try:
        chip = _make_chip(ser)
        ret, baud = chip.uart_rate_adaptive()
        if ret != 0:
            _done(ok=False, error=f"uart_rate_adaptive failed (error {ret})")
            return
        _ = baud
        ret, value = chip.read_efuse(data["addr"])
        if ret != 0:
            _done(ok=False, error=f"read_efuse failed (error {ret})")
            return
        _done(ok=True, value=value)
    finally:
        ser.close()


def cmd_dtm_start(data: dict) -> None:
    ser = _open_serial(data["port"])
    try:
        chip = _make_chip(ser)
        ret, msg = chip.dtm_start(data["params"], False)
        _done(ok=(ret == 0), ret=ret, msg=msg)
    finally:
        ser.close()


def cmd_dtm_stop(data: dict) -> None:
    ser = _open_serial(data["port"])
    try:
        chip = _make_chip(ser)
        ret, msg = chip.dtm_stop()
        _done(ok=(ret == 0), ret=ret, msg=msg)
    finally:
        ser.close()


def cmd_carrier_start(data: dict) -> None:
    ser = _open_serial(data["port"])
    try:
        chip = _make_chip(ser)
        ch, cap, tx_power = data["ch"], data["cap"], data["tx_power"]
        ret, msg = chip.carrier_test_start(ch, cap, tx_power)
        _done(ok=(ret == 0), ret=ret, msg=msg)
    finally:
        ser.close()


def cmd_carrier_stop(data: dict) -> None:
    ser = _open_serial(data["port"])
    try:
        chip = _make_chip(ser)
        ret, msg = chip.carrier_test_stop()
        _done(ok=(ret == 0), ret=ret, msg=msg)
    finally:
        ser.close()


def cmd_program(data: dict) -> None:  # noqa: C901
    import beacon.beacon as bmod  # type: ignore[import]
    import beacon.beacon_efuse_format as ef  # type: ignore[import]
    from beacon.mis import (  # type: ignore[import]
        static_address_post_proc as _post_proc,
    )
    from beacon.mis import (
        static_address_pre_proc as _pre_proc,
    )

    port = data["port"]
    config = data["config"]
    ram_mode = data.get("ram_mode", False)
    no_autorate = data.get("no_autorate", False)
    trigger = data.get("trigger", False)
    bdaddr = data.get("bdaddr")

    ser = _open_serial(port)
    try:
        chip = _make_chip(ser)

        if not no_autorate:
            _log("info", "Negotiating baud rate ...")
            ret, baud = chip.uart_rate_adaptive()
            if ret != 0:
                _done(ok=False, error=f"uart_rate_adaptive failed (error {ret})")
                return
            _log("info", f"  Baud rate: {baud}")

        _log("info", "Reading chip info ...")
        ret, efuse11 = chip.read_efuse(17)
        if ret != 0:
            _done(ok=False, error=f"read_efuse(0x11) failed (error {ret})")
            return

        ret, chip_type = chip.get_chip_type()
        if ret != 0:
            _done(ok=False, error=f"get_chip_type failed (error {ret})")
            return
        _log("info", f"  Chip type: {CHIP_NAMES.get(chip_type, chip_type)}")

        if bdaddr:
            config = dict(config)
            config["advSet"][0]["bdAddr"] = bdaddr.lower().replace(":", "")

        b = bmod.Beacon()
        b.load_config(config)
        b.rt_uart_pin_as_gpio_proc(efuse11, chip_type)

        _log("info", "Calibrating ...")
        err = chip.NANO_BCN_ERR_NO_ERROR

        ret, efuse05 = chip.read_efuse(5)
        if ret == err:
            b.calibration.ldo_calibration_process(efuse05, b.tx_setting.tx_power)
        else:
            _done(ok=False, error=f"read efuse05 failed,{ret}")
            return

        ret, efuse06 = chip.read_efuse(6)
        if ret != err:
            _done(ok=False, error=f"read efuse06 failed,{ret}")
            return

        ret, efuse07 = chip.read_efuse(7)
        if ret != err:
            _done(ok=False, error=f"read efuse07 failed,{ret}")
            return

        ret, efuse08 = chip.read_efuse(8)
        if ret == err:
            b.calibration.vcc_calibration_process(efuse06, efuse07, efuse08, b.adc.vcc_unit)
        else:
            _done(ok=False, error=f"read efuse08 failed,{ret}")
            return

        ret, efuse09 = chip.read_efuse(9)
        if ret == err:
            b.calibration.temperature_calibration_process(efuse09, b.adc.temp_unit)
        else:
            _done(ok=False, error=f"read efuse09 failed,{ret}")
            return

        ret, efuse0c = chip.read_efuse(12)
        if ret != err:
            _done(ok=False, error=f"read efuse0c failed,{ret}")
            return

        ret, efuse0d = chip.read_efuse(13)
        if ret != err:
            _done(ok=False, error=f"read efuse0d failed,{ret}")
            return

        b.calibration.adc_calibration_process(efuse0c, efuse0d, b.adc)

        _log("info", "Processing BLE static address ...")
        for adv_set in (b.adv_set1, b.adv_set2, b.adv_set3):
            ret, ret_str = _pre_proc(adv_set, b, chip)
            if ret != 0:
                _done(ok=False, error=f"static_addr_pre_proc failed: {ret_str}")
                return

        _, h_flag = chip.is_full_range_industrial()
        _log("debug", f"  Full-range industrial: {bool(h_flag)}")

        _log("info", "Converting config to packet ...")
        packet = b.convert_to_packet(h_flag, is_run_in_ram=ram_mode)

        for adv_set in (b.adv_set1, b.adv_set2, b.adv_set3):
            _post_proc(adv_set)

        word_array = [0] * 384
        word_cnt = ef.packet_to_raw(str(packet), word_array)
        _log("info", f"  Word count: {word_cnt}/256")

        if word_cnt > 256:
            _done(ok=False, error=f"eFuse overflow: {word_cnt} words (max 256)")
            return

        chip.wordArray = word_array

        if ram_mode:
            _log("info", "Running in RAM (test mode) ...")
            ret = chip.run_in_ram()
            if ret != 0:
                _done(ok=False, error=f"run_in_ram failed (error {ret})")
                return
            _log("info", "RAM test complete.")
        else:
            _log("info", "Burning eFuse ...")
            ret = chip.burn_efuse(reset_en=True, clear_uart_cache=False)
            if ret != 0:
                _done(ok=False, error=f"burn_efuse failed (error {ret})")
                return
            _log("info", "eFuse burn complete.")

        if trigger:
            _log("debug", "Sending post-burn trigger signal ...")
            ser.write(bytes([0x00, 0xFF]))
            ser.flush()

        _done(ok=True, word_count=word_cnt, chip_type=chip_type)

    finally:
        ser.close()


# ── dispatch ──────────────────────────────────────────────────────────────────

_HANDLERS = {
    "validate": cmd_validate,
    "connect": cmd_connect,
    "read_efuse": cmd_read_efuse,
    "dtm_start": cmd_dtm_start,
    "dtm_stop": cmd_dtm_stop,
    "carrier_start": cmd_carrier_start,
    "carrier_stop": cmd_carrier_stop,
    "program": cmd_program,
}


def main() -> None:
    line = sys.stdin.readline()
    if not line.strip():
        _done(ok=False, error="Empty command")
        return
    data = json.loads(line)
    cmd = data.pop("cmd", None)
    handler = _HANDLERS.get(cmd)
    if handler is None:
        _done(ok=False, error=f"Unknown command: {cmd!r}")
        return
    try:
        handler(data)
    except Exception as exc:
        _done(ok=False, error=f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
