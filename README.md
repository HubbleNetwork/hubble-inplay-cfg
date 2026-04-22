# hubble-inplay-cfg

Generate IN100 NanoBeacon `.cfg` files and program chips over UART.

**Who this is for.** Engineers provisioning InPlay IN100 BLE beacon chips to
advertise on Hubble Network. The IN100 is configured via a JSON `.cfg` file
describing its registers, advertising payload, and timing behavior. This tool
generates that file and can flash it directly to a chip over a serial connection.

Given three inputs — `key0`, `rot_exp`, and advertising `interval` — the `generate`
command emits a ready-to-flash JSON config. It computes the EID timer-wrap register
(`write: 3 1 3 3284 …`) from `rot_exp` and `interval` so you don't have to.

## Requirements

- Python 3.10+
- `pyserial` and `pycryptodomex` (installed automatically)

Install Python 3.10 via Homebrew if you don't have it:

```bash
brew install python@3.10
```

## Installation

```bash
git clone <repo>
cd nanobeacon-cli
python3.10 -m pip install .
```

For development (changes to source take effect immediately):

```bash
python3.10 -m pip install -e ".[dev]"
```

Verify:

```bash
hubble-inplay-cfg version
```

---

## Generating a Hubble config

```
hubble-inplay-cfg generate [--key <hex-or-b64>] [--rot-exp <int>] [--interval <seconds>] [--payload <hex>] [-o <path>]
```

| Flag | Default | Description |
|---|---|---|
| `--key` | all-zeros | 16-byte AES-128 key. 32-char hex (e.g. `E00102030405060708090A0B0C0D0E0F`) or base64; auto-detected. The all-zeros default is intended for pipelines that inject the real key after generation — configs built with it won't decode at the Hubble backend. |
| `--rot-exp` | `15` | EID rotation period exponent (rotation period = 2^`rot_exp` seconds). Accepted 1–15; values 1–9 warn (the Hubble backend only accepts 10–15). |
| `--interval` | `2` | Advertising interval in seconds. |
| `--payload` | `FF` | Raw hex bytes (≥1 byte) embedded as a single `<EncRaw … 0 1>` token. |
| `--tx-power` | `4` | TX power in dBm (−4 to 4). |
| `-o`, `--output` | stdout | Write JSON to this file instead of stdout. |

### Examples

Generate a config with a 2 s advertising interval and a 1024 s EID rotation period:

```bash
hubble-inplay-cfg generate \
  --key AAECAwQFBgcICQoLDA0ODw== \
  --rot-exp 10 \
  --interval 2 \
  -o my-device.cfg
```

Pipe directly to a file:

```bash
hubble-inplay-cfg generate --key "$KEY" --rot-exp 12 --interval 1 > device.cfg
```

Use a multi-byte payload (e.g. a 3-byte tag identifier):

```bash
hubble-inplay-cfg generate --key "$KEY" --rot-exp 10 --interval 2 --payload FF01AB
```

### Python API

```python
import json
from hubble_inplay_cfg.builder import build_config

cfg = build_config(
    interval_ms=2000,
    key0="AAECAwQFBgcICQoLDA0ODw==",
    rot_exp=10,
    payload_hex="FF",
)

with open("my-device.cfg", "w") as f:
    json.dump(cfg, f, indent=4)
```

`build_config` returns a plain `dict` ready to serialize as IN100 `.cfg` JSON. Fields it sets:

- `advSet[0].interval`, `advSet[0].rot_exp`
- `advSet[0].payload[0].data` and `.len`
- `txSetting.key0` (hex-encoded from the hex or base64 input)
- The `3284` entry inside `regSettingCust`

Everything else passes through from the baked-in template.

### How the timer-wrap value is computed

The register `write: 3 1 3 3284 <val>` sets the number of advertisements before the
EID counter resets to 0. With a 128-entry EID pool (indices 0–127):

```
adv_count_to_reset = floor(2^rot_exp / (interval_ms / 1000) * 127)
```

Example: `rot_exp=10`, `interval=2000 ms` → `1024 / 2 · 127 = 65024 = 0xFE00`.

---

## Validating a config (no hardware needed)

Parses the JSON config and reports how many eFuse words it would consume:

```bash
hubble-inplay-cfg validate -c my-device.cfg
hubble-inplay-cfg validate -c my-device.cfg --verbose   # also dumps word values
```

Example output:

```
Config:      my-device.cfg
Word count:  183/256 OK
Non-zero:    115 words
```

If the word count exceeds 256, the config is too large for eFuse and the tool reports `OVERFLOW`.

---

## Programming a chip

### Find your serial port

**macOS:**

```bash
ls /dev/tty.usb*
ls /dev/tty.SLAB*
```

**Linux:**

```bash
ls /dev/ttyUSB*
ls /dev/ttyACM*
```

### Test connectivity

Opens the serial port, negotiates baud rate, and reads the chip type:

```bash
hubble-inplay-cfg connect -p /dev/tty.usbserial-0001
```

### Program from a config file

**RAM mode** (non-destructive — good for testing first):

```bash
hubble-inplay-cfg program -p /dev/tty.usbserial-0001 -c my-device.cfg --ram
```

**eFuse mode** (permanent — cannot be undone):

```bash
hubble-inplay-cfg program -p /dev/tty.usbserial-0001 -c my-device.cfg --efuse
```

**Generate and program in one shot** (no intermediate file):

```bash
hubble-inplay-cfg program \
  -p /dev/tty.usbserial-0001 \
  --key "$KEY" --rot-exp 10 --interval 2 \
  --efuse
```

**Manufacturing mode** — burn eFuse and send a `[0x00, 0xFF]` trigger signal to the test fixture:

```bash
hubble-inplay-cfg program \
  -p /dev/tty.usbserial-0001 \
  -c my-device.cfg \
  --efuse --trigger --log-file logs/run.txt
```

### `program` flags

| Flag | Description |
|---|---|
| `-p`, `--port` | Serial port (required) |
| `-c`, `--config` | JSON config file |
| `--key` | AES-128 key — generates config inline (cannot combine with `--config`) |
| `--rot-exp` | EID rotation exponent (used with `--key`) |
| `--interval` | Advertising interval in seconds (used with `--key`) |
| `--payload` | Hex payload bytes (used with `--key`) |
| `--tx-power` | TX power dBm (used with `--key`) |
| `--bdaddr` | Override BT address (e.g. `b8aa00000001`) |
| `--ram` | Run in RAM (non-destructive) |
| `--efuse` | Burn eFuse (permanent) |
| `--trigger` | Send `[0x00, 0xFF]` over serial after burn (manufacturing fixture signal) |
| `--no-autorate` | Skip baud rate negotiation, use fixed 115200 |
| `--debug` | Verbose output |
| `--log-file` | Write timestamped log to this file |

---

## RF testing (Direct Test Mode)

```bash
# Start DTM transmit: freq_idx, pkt_type, pkt_len, phy, ...
hubble-inplay-cfg dtm-start -p /dev/tty.usbserial-0001 --params "0,0,37,0,0,0"
hubble-inplay-cfg dtm-stop  -p /dev/tty.usbserial-0001

# Continuous carrier wave
hubble-inplay-cfg carrier-start -p /dev/tty.usbserial-0001 --params "37,7,4"
hubble-inplay-cfg carrier-stop  -p /dev/tty.usbserial-0001
```

---

## Global flags

These flags apply to all subcommands:

| Flag | Description |
|---|---|
| `--log-file PATH` | Write timestamped log lines to this file (in addition to stdout) |
| `--debug` | Enable verbose debug output |

---

## Read an eFuse register

```bash
hubble-inplay-cfg read-efuse -p /dev/tty.usbserial-0001 0x11
hubble-inplay-cfg read-efuse -p /dev/tty.usbserial-0001 17   # decimal also works
```

---

## Claude Code integration

This package ships two complementary agent integrations:

1. **Slash commands** (skill files) — high-level workflow guides for common tasks
2. **MCP server** — low-level programmatic tool access for any MCP-compatible agent

Both are included in the repo and require no extra setup beyond installation.

### Slash commands (Claude Code)

Three slash commands are bundled in `.claude/commands/`. They are available automatically
when Claude Code is opened inside this repo.

| Command | Description |
|---|---|
| `/hubble-generate` | Generate a config from key + rot_exp + interval, then validate |
| `/hubble-program` | Full chip programming workflow: connect → RAM test → eFuse burn |
| `/hubble-dtm` | BLE Direct Test Mode and carrier wave RF testing |

**Example:**
```
/hubble-generate
```
Claude will ask for your key, rot_exp, and interval, run the generate + validate commands,
and report the word count.

---

## MCP server (Claude Code / AI agent integration)

This package also ships an [MCP](https://modelcontextprotocol.io) server that exposes all
CLI commands as individual tools. Any MCP-compatible agent (Claude Code, Cursor, etc.) can
call these tools directly without going through the slash command workflow.

### Install with MCP support

```bash
python3.10 -m pip install ".[mcp]"
# or, if installing from PyPI:
pip install "hubble-inplay-cfg[mcp]"
```

### Add to Claude Code

**Project-level** — copy `.mcp.json` from the repo root, or create it:

```json
{
  "mcpServers": {
    "hubble-inplay-cfg": {
      "command": "hubble-inplay-cfg-mcp"
    }
  }
}
```

Place this file at the root of your project. Claude Code picks it up automatically.

**User-level** — add the same `mcpServers` block to `~/.claude.json` to make it
available in all projects.

### Available MCP tools

| Tool | Hardware needed | Description |
|---|---|---|
| `generate_config` | No | Generate a config from key + rot_exp + interval |
| `validate_config` | No | Check word count ≤256 |
| `list_serial_ports` | No | Find available serial ports |
| `connect_chip` | Yes | Verify chip is reachable, read chip type |
| `program_chip` | Yes | Flash config to chip (RAM or eFuse) |
| `read_efuse` | Yes | Read a single eFuse register |
| `dtm_start` | Yes | Start BLE Direct Test Mode |
| `dtm_stop` | Yes | Stop DTM and read packet count |
| `carrier_start` | Yes | Start continuous carrier wave |
| `carrier_stop` | Yes | Stop carrier wave |

### Example agent session

```
User: Generate a config for key E00102030405060708090A0B0C0D0E0F, rot_exp 10, interval 2,
      then validate it.

Agent:
  → generate_config(key="E00102030405060708090A0B0C0D0E0F", rot_exp=10, interval=2)
  → validate_config(config_path="/tmp/device.cfg")
  Result: Word count 183/256 OK
```

---

## Development

```bash
python3.10 -m pip install -e ".[dev,mcp]"
pytest
ruff check .
```

---

## Project structure

```
hubble-inplay-cfg/
├── pyproject.toml
├── requirements.txt
├── .mcp.json               # Claude Code project-level MCP config
├── .claude/
│   └── commands/
│       ├── hubble-generate.md   # /hubble-generate slash command
│       ├── hubble-program.md    # /hubble-program slash command
│       └── hubble-dtm.md        # /hubble-dtm slash command
└── src/
    └── hubble_inplay_cfg/
        ├── cli.py          # all subcommands
        ├── mcp_server.py   # MCP server (programmatic agent access)
        ├── builder.py      # Hubble config generator
        ├── template.py     # base IN100 register template
        ├── chip.py         # clean UART driver adapter
        ├── mis.py          # runtime calibration orchestration
        └── beacon/         # extracted .pyc modules from NanoBeacon Config Tool v3.3.4
```

## Chip types

| Code | Package |
|---|---|
| 0 | QFN18 |
| 1 | WLCSP |
| 2 | KGD |
| 3 | DFN8 |
| 255 | UNKNOWN |
