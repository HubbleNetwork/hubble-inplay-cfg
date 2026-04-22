# CLAUDE.md

## Commands

```bash
pip install -e ".[dev]"       # editable + dev extras (pytest, ruff)
pip install -e ".[dev,mcp]"   # also installs MCP server dependencies
pytest                        # run all tests (57 tests, no hardware required)
ruff check .                  # lint (CI gate on PRs and pushes to main)

# CLI — config generation (no hardware)
hubble-inplay-cfg generate [--key <hex-or-b64>] [--rot-exp <n>] [--interval <seconds>] [--payload <hex>] [-o <path>]
hubble-inplay-cfg validate --config <path> [--verbose]
hubble-inplay-cfg version

# CLI — chip programming (hardware required: IN100 over UART)
hubble-inplay-cfg connect --port <port>
hubble-inplay-cfg program  --port <port> --config <path> --ram
hubble-inplay-cfg program  --port <port> --config <path> --efuse [--trigger] [--log-file <path>]
hubble-inplay-cfg read-efuse --port <port> <addr>

# CLI — RF testing
hubble-inplay-cfg dtm-start    --port <port> --params "freq,pkt_type,pkt_len,phy,0,0"
hubble-inplay-cfg dtm-stop     --port <port>
hubble-inplay-cfg carrier-start --port <port> --params "ch,cap,tx_power"
hubble-inplay-cfg carrier-stop  --port <port>

# MCP server (stdio transport for Claude Code / other agents)
hubble-inplay-cfg-mcp
```

## Architecture

Src-layout package with two functional layers:

```
src/hubble_inplay_cfg/
  template.py     BASE_CONFIG dict (authoritative register settings)
  builder.py      build_config() and its helpers
  cli.py          all subcommands (generate, validate, program, connect, dtm-*, carrier-*, ...)
  chip.py         clean UART adapter wrapping beacon.chip.Chip
  mis.py          runtime calibration + BLE static address orchestration
  mcp_server.py   MCP server exposing all CLI commands as tools
  beacon/         extracted .pyc binary modules from NanoBeacon Config Tool v3.3.4
                  (28 files — not human-readable source, do not edit)
tests/
  test_builder.py   config generation tests (offline)
  test_chip.py      UART driver tests (mock serial)
  test_cli.py       CLI smoke tests (subprocess)
.claude/commands/
  hubble-generate.md   /hubble-generate slash command
  hubble-program.md    /hubble-program slash command
  hubble-dtm.md        /hubble-dtm slash command
```

## Dependencies

- **Runtime**: `pyserial>=3.5`, `pycryptodomex>=3.0`
- **`pycryptodomex`** is required for BLE static address generation (AES-CTR inside
  `beacon/mis.pyc`). Without it, any config with `staticAddrGen=1` will crash at runtime.
- **MCP extra**: `mcp>=1.0` — only needed for the `hubble-inplay-cfg-mcp` server.

## Gotchas

- **Timer-wrap formula** (encoded in `compute_adv_count_to_reset`):
  ```
  adv_count = (2**rot_exp * 127 * 1000) // interval_ms
  ```
  127 = `EID_INDEX_MAX` (pool is 128, indices 0–127). Use integer math.

- **Two length fields must stay in sync** (`assemble_payload_data`):
  - Length byte inside `data` string: `18 + N` as uppercase hex (e.g. `N=1` → `"13"`)
  - `payload[0].len`: `23 + N`
  where `N` = number of raw bytes in the `<EncRaw … Nbyte 0 1>` token.

- **`--key` accepts two input formats**: the CLI takes either a 32-char hex
  string (e.g. `E001020304...`) or base64, auto-detected by length and
  charset. The config always stores lowercase hex. `decode_key` handles the
  conversion.

- **`rot_exp` has two ranges**: 1–15 accepted (hard fail outside), 10–15 preferred
  (stderr warning between 1–9). Don't conflate them.

- **Fixed invariants in the data string**: `0303a6fc` prefix, `16a6fc08` service-data
  header, `<SALT 2byte 0 0><EID 8byte 1 0>`, `<TAG 4byte 0 0>` suffix. Only the
  length byte and the single `<EncRaw>` token vary.

- **beacon/ .pyc files**: These are extracted from the NanoBeacon Config Tool v3.3.4
  PyInstaller bundle (Python 3.10 bytecode). They are vendored as-is. The `sys.path`
  in `chip.py`, `mis.py`, and `cli.py` inserts `src/hubble_inplay_cfg/` so that
  `import beacon.xxx` resolves correctly.

- **`mis.py` clean boundary**: `rt_calibration_process` and `rt_ble_static_address_*`
  functions take raw beacon package objects (not the Chip adapter). Pass `chip._inner`
  and a freshly constructed `beacon.beacon.Beacon()` instance.

## Testing

Tests run offline — no hardware required. 57 tests across three files:
- `test_builder.py`: config generation and formula correctness (24 tests)
- `test_chip.py`: UART adapter with mock serial (18 tests)
- `test_cli.py`: CLI subprocess smoke tests (15 tests)
