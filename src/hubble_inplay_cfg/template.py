"""Authoritative base IN100 config dict for Hubble advertising.

Fields set by the builder (`interval`, `rot_exp`, `key0`, `payload[0].data`,
`payload[0].len`, and the `3284` entry in `regSettingCust`) are placeholders
here; all other fields pass through untouched.
"""

from copy import deepcopy
from typing import Any

_DEFAULT_GPIO = [
    {
        "id": i,
        "digital": "default",
        "pu-pd": 1,
        "wakeup": "disable",
        "advTrig": "disable",
        "latch": 0,
        "maskb": 0,
    }
    for i in range(8)
]


_BASE_CONFIG: dict[str, Any] = {
    "version": "3.16",
    "advSet": [
        {
            "id": 0,
            "bdAddr": "b8aa00000001",
            "addrType": "nonresolvable",
            "addrKey": 0,
            "staticAddrGen": 1,
            "addrGenInterval": 90,
            "interval": 2000,
            "authEn": 0,
            "authKey": 0,
            "rot_exp": 10,
            "authSaltType": 1,
            "authSaltValue": 0,
            "authEaxCountType": 0,
            "authEaxCountValue": 0,
            "ui_format": "custom",
            "uid2tlm_ratio": 0.0,
            "eddystoneTxPower": 0,
            "chCtrl": 0,
            "advModeTrigEn": 0,
            "is1MPhy": 1,
            "phyRate": "1M",
            "isStandardBle": 1,
            "cte": 0,
            "cteLen": 0,
            "randomDlyType": 0,
            "payloadVer": 3,
            "payload": [
                {
                    "len": 24,
                    "type": 254,
                    "data": "",
                }
            ],
        }
    ],
    "txSetting": {
        "txPower": -1,
        "txPaGain": -1,
        "sleepAftTx": 1,
        "uartSingleWire": 0,
        "uartPinSel": 0,
        "xoCap": 7,
        "xoStableTime": 36,
        "xoGm": 16,
        "ch0": 37,
        "ch1": 38,
        "ch2": 39,
        "custUUID": "000102030405",
        "key0": "",
    },
    "gpio": _DEFAULT_GPIO,
    "vccUnit": 0.03125,
    "tempUnit": 0.01,
    "adc": [{"ch": i, "enable": 0} for i in range(4)],
    "calibration": {},
    "i2c": {"coldBootEn": 0, "warmBootEn": 0},
    "i2c2": {"coldBootEn": 0, "warmBootEn": 0},
    "i2c3": {"coldBootEn": 0, "warmBootEn": 0},
    "pulse": {"enable": 0},
    "qdec": {
        "enable": 0,
        "runGpioEdgeDetect": 0,
        "clearCount": 0,
        "endCode": 15,
        "twoStep": 0,
        "interval": 999,
        "timeout": 1999,
        "gpio": [],
        "code": [],
    },
    "wdt": {
        "timerWraparound": 0,
        "enable": 0,
        "wakeupChip": 0,
        "initValue": 30,
    },
    "edgeCount": {"enable": 0},
    "sqWave": {"en": 0},
    "rtc": {"enable": 0, "clock": 0, "type": 0},
    "regSetting": [
        "write: 0 1 3 3480 2010000",
        "write: 0 1 3 3484 3030002",
        "write: 0 1 1 34c8 102",
        "write: 0 1 3 3494 10020018",
        "write: 3 1 0 1084 0",
        "write: 3 1 0 11C8 0",
        "write: 3 1 0 1c44 c6",
        "write: 3 1 0 1ad0 58",
        "write: 3 1 1 1d04 731",
        "write: 0 1 0 3240 42",
        "write: 0 1 0 3500 03",
    ],
    "regSettingCust": [
        "write: 3 1 3 3284 0",
        "write: 3 1 1 3280 123",
        "write: 3 1 0 3288 1",
        "write: 1 1 1 13A4 1",
        "write: 1 1 1 13A8 1",
        "write: 1 1 1 13A0 b481",
        "write: 1 1 3 1390 fa0001",
        "write: 3 f 0 3290 22",
        "write: 3 f 0 1288 ff",
        "delay: 3 f ff",
        "write: 3 f 0 1288 00",
        "write: 3 f 0 3290 23",
        "write: 3 f 1 3280 120",
    ],
    "guiRuntimeCfg": "tx_interval_max=30000;",
    "settingPolice": 0,
    "regValTrigEn": 1,
}


def base_config() -> dict[str, Any]:
    """Return a fresh deep copy of the base config so callers can mutate freely."""
    return deepcopy(_BASE_CONFIG)
