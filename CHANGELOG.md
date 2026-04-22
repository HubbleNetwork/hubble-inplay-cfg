# Changelog

## harora-vibed — combined config generator + chip programmer

This branch merges the config-generator-only `main` branch with the
`nanobeacon-cli` UART programming tool, producing a single package with
full feature parity with `beacon_mp_cmd.exe` (the Windows-only reference tool).

### New dependencies

| Dependency | Why |
|---|---|
| `pyserial>=3.5` | UART serial port communication with the IN100 chip |
| `pycryptodomex>=3.0` | AES-CTR used by `beacon/mis.pyc` for BLE static address generation (`staticAddrGen=1`). Previously a hidden/undeclared dependency — now explicit. |
| `mcp>=1.0` *(optional)* | MCP server for Claude Code / AI agent integration |

### New source files

| File | Description |
|---|---|
| `src/hubble_inplay_cfg/chip.py` | Clean UART adapter wrapping `beacon.chip.Chip`. Exposes `connect`, `read_efuse`, `get_chip_type`, `run_in_ram`, `burn_efuse`, `dtm_start`, `dtm_stop`, `carrier_start`, `carrier_stop`, `send_trigger`. |
| `src/hubble_inplay_cfg/mis.py` | Runtime calibration and BLE static address orchestration. Reads eFuse registers 5–9, 12–13 and applies LDO/VCC/temperature/ADC corrections. |
| `src/hubble_inplay_cfg/mcp_server.py` | MCP server with 10 tools: `generate_config`, `validate_config`, `list_serial_ports`, `connect_chip`, `program_chip`, `read_efuse`, `dtm_start`, `dtm_stop`, `carrier_start`, `carrier_stop`. |
| `src/hubble_inplay_cfg/beacon/` | 28 `.pyc` binary modules extracted from NanoBeacon Config Tool v3.3.4 (Python 3.10). Vendored binary dependency — not human-readable source. Required for eFuse encoding (`beacon_efuse_format`), chip communication (`chip`), and calibration (`mis`, `calibration`). |
| `tests/test_chip.py` | 18 unit tests for `chip.py` using mock serial (no hardware required). |
| `.mcp.json` | Project-level Claude Code MCP server config. Drop in your project root and Claude Code picks up all 10 tools automatically. |
| `.claude/commands/hubble-generate.md` | `/hubble-generate` slash command — guided generate + validate workflow. |
| `.claude/commands/hubble-program.md` | `/hubble-program` slash command — full chip programming workflow with safety gates (RAM test before eFuse burn). |
| `.claude/commands/hubble-dtm.md` | `/hubble-dtm` slash command — BLE Direct Test Mode and carrier wave RF testing. |
| `requirements.txt` | Pinned runtime dependencies for non-pip installs. |

### Modified files

#### `src/hubble_inplay_cfg/cli.py`

The original `main` CLI had a single flat argument parser for `generate` only.
This branch replaces it with a full subcommand parser:

| Subcommand | New? | Description |
|---|---|---|
| `generate` | extended | Unchanged behavior; now a proper subcommand |
| `validate` | new | Offline word-count check against the 256-word eFuse limit |
| `program` | new | Full programming flow: rate negotiation → calibration → convert → burn |
| `connect` | new | Test connectivity and read chip type |
| `read-efuse` | new | Read a single eFuse register |
| `dtm-start` | new | Start BLE Direct Test Mode |
| `dtm-stop` | new | Stop DTM and read packet count |
| `carrier-start` | new | Start continuous unmodulated carrier wave |
| `carrier-stop` | new | Stop carrier wave |
| `version` | new | Print package version |

Added global flags: `--log-file` (opt-in file logging with timestamps), `--debug`.

`program` accepts either `--config <file>` or inline `--key/--rot-exp/--interval`
(generate + program in one shot). Includes `--trigger` to send `[0x00, 0xFF]` post-burn
serial signal for manufacturing test fixtures, and `--bdaddr` to override the BT address.

#### `pyproject.toml`

- Added `dependencies` (`pyserial`, `pycryptodomex`)
- Added `hubble-inplay-cfg-mcp` entry point
- Added `mcp` optional dependency group
- Added `[tool.setuptools.package-data]` for `beacon/*.pyc`
- Updated description
- Preserved all `[tool.ruff]` and `[tool.pytest.ini_options]` settings from `main`

#### `README.md`

Fully rewritten to cover:
- Config generation (unchanged behavior, same flags)
- Validation (`validate` subcommand)
- Chip programming (`program` subcommand, RAM vs eFuse modes)
- RF testing (`dtm-start/stop`, `carrier-start/stop`)
- MCP server setup for Claude Code
- Slash command documentation (`/hubble-generate`, `/hubble-program`, `/hubble-dtm`)
- Updated project structure tree

#### `CLAUDE.md`

Updated with:
- All new CLI subcommands
- MCP server entry point
- Architecture section covering `chip.py`, `mis.py`, `mcp_server.py`, `beacon/`
- Dependency notes (especially the `pycryptodomex` caveat)
- `beacon/` sys.path convention
- `mis.py` raw-object boundary note
- Updated test count (57 tests across 3 files)

#### `tests/test_builder.py`

No logic changes. Updated import path from `hubble_inplay_cfg.builder`
(was importing from `hubble_inplay_cfg` directly, matched main's module structure).

#### `tests/test_cli.py`

Extended to cover the new subcommands: `validate`, `generate` defaults,
`program` (missing port), `connect`, `read-efuse`, `dtm-start`, `--log-file`.

#### `.gitignore`

Added `!src/hubble_inplay_cfg/beacon/*.pyc` exception so the vendored
binary modules are tracked by git despite the `*.py[cod]` exclusion rule.

### Programming flow

The `program` subcommand runs the same sequence as `beacon_mp_cmd.exe`:

```
uart_rate_adaptive()
read_efuse(0x11) + get_chip_type()
rt_calibration_process()         # eFuse 5,6,7,8,9,12,13 → LDO/VCC/temp/ADC
rt_ble_static_address_process()  # AES-CTR via pycryptodomex
is_full_range_industrial()
convert_to_packet()
rt_ble_static_address_post_process()
packet_to_raw()                  # → 16-bit word array, max 256 words
run_in_ram() or burn_efuse()
send_trigger() if --trigger      # [0x00, 0xFF] manufacturing fixture signal
```
