Flash a Hubble IN100 NanoBeacon config to a chip over UART.

## What this does
Full chip programming workflow: find port → verify connection → generate/validate config → RAM test → eFuse burn.

## Required inputs
Ask the user for any missing values before running:
- **port** — serial port path. If unknown, run `hubble-inplay-cfg connect --port <port>` to find it. Common paths:
  - macOS: `/dev/tty.usbserial-XXXX` or `/dev/tty.SLAB_USBtoUART`
  - Linux: `/dev/ttyUSB0`
  - Windows: `COM3`
- **config source** — one of:
  - A pre-generated `.cfg` file path (`--config path/to/device.cfg`)
  - Or inline: `--key <KEY> --rot-exp <ROT_EXP> --interval <INTERVAL>`

## Optional inputs
- **bdaddr** — override BT address, e.g. `b8aa00000001`
- **trigger** — send `[0x00, 0xFF]` post-burn signal for manufacturing fixtures (`--trigger`)
- **log_file** — path to write a timestamped log (`--log-file logs/run.txt`)

## Steps

### 1. Verify connectivity
```bash
hubble-inplay-cfg connect --port <PORT>
```
Stop if this fails. Check the port path and that the chip is powered.

### 2. If using inline generation, validate first
```bash
hubble-inplay-cfg generate --key <KEY> --rot-exp <ROT_EXP> --interval <INTERVAL> -o /tmp/hubble_preview.cfg
hubble-inplay-cfg validate --config /tmp/hubble_preview.cfg
```
Stop if word count OVERFLOW.

### 3. RAM test (non-destructive — always run this first)
```bash
hubble-inplay-cfg program --port <PORT> --config <CONFIG> --ram
# or inline:
hubble-inplay-cfg program --port <PORT> --key <KEY> --rot-exp <ROT_EXP> --interval <INTERVAL> --ram
```
Stop and report the error if RAM test fails.

### 4. eFuse burn (permanent — confirm with user before running)
Tell the user: "RAM test passed. Ready to permanently burn eFuse — this cannot be undone. Confirm?"

Only proceed after confirmation:
```bash
hubble-inplay-cfg program --port <PORT> --config <CONFIG> --efuse [--trigger] [--log-file <PATH>]
```

### 5. Report
- Chip type and baud rate
- Word count burned
- Success/failure
- If `--trigger` was used, confirm the fixture signal was sent

## Notes
- Never skip the RAM test before eFuse burn
- eFuse is one-time programmable — a failed or wrong config cannot be corrected
- Use `--bdaddr` when programming individual chips with unique MAC addresses
- Use `--trigger` + `--log-file` in manufacturing line environments
