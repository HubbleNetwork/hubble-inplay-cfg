Run RF tests on an IN100 chip using BLE Direct Test Mode (DTM) or carrier wave.

## What this does
Controls the IN100's built-in RF test modes for BLE certification, frequency accuracy testing, and TX power verification.

## Required inputs
- **port** — serial port path (e.g. `/dev/tty.usbserial-0001`)
- **test type** — ask the user which test to run:
  - **DTM** — transmit BLE packets on a channel (measures TX power, packet error rate)
  - **Carrier** — continuous unmodulated carrier wave (measures frequency accuracy, used for FCC/CE)

## DTM workflow

### Start DTM
```bash
hubble-inplay-cfg dtm-start --port <PORT> --params "<FREQ_IDX>,<PKT_TYPE>,<PKT_LEN>,<PHY>,0,0"
```

Parameter guide:
| Parameter | Values | Description |
|---|---|---|
| FREQ_IDX | 0–39 | BLE channel index. 37=2402 MHz, 38=2426 MHz, 39=2480 MHz |
| PKT_TYPE | 0–3 | 0=PRBS9, 1=0x0F pattern, 2=0x55 pattern, 3=vendor |
| PKT_LEN | 0–255 | Packet payload length in bytes |
| PHY | 0–3 | 0=1M, 1=2M, 2=Coded S=8, 3=Coded S=2 |

Example — transmit PRBS9 on channel 37 (2402 MHz) with 37-byte packets at 1M PHY:
```bash
hubble-inplay-cfg dtm-start --port /dev/tty.usbserial-0001 --params "0,0,37,0,0,0"
```

### Stop DTM and read packet count
```bash
hubble-inplay-cfg dtm-stop --port <PORT>
```

## Carrier wave workflow

### Start carrier
```bash
hubble-inplay-cfg carrier-start --port <PORT> --params "<CHANNEL>,<CAP>,<TX_POWER>"
```

Parameter guide:
| Parameter | Values | Description |
|---|---|---|
| CHANNEL | 0–39 | BLE channel index |
| CAP | 0–15 | Crystal capacitor trim (affects frequency accuracy) |
| TX_POWER | -4–4 | TX power in dBm |

Example — carrier on channel 37 at 4 dBm:
```bash
hubble-inplay-cfg carrier-start --port /dev/tty.usbserial-0001 --params "37,7,4"
```

### Stop carrier
```bash
hubble-inplay-cfg carrier-stop --port <PORT>
```

## Notes
- DTM and carrier modes take over the chip — it will not advertise normally while a test is running
- Always call the matching stop command before starting a new test or powering off
- For frequency accuracy tuning, adjust the CAP value and observe frequency on a spectrum analyzer
- BLE advertising channels: 37 = 2402 MHz, 38 = 2426 MHz, 39 = 2480 MHz
- Data channels 0–36 map to 2404–2480 MHz (even spacing, skipping advertising channels)
