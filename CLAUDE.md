# CLAUDE.md

## Commands

```bash
pip install -e ".[dev]"    # editable + dev extras (pytest, ruff); runtime itself is stdlib-only
pytest                     # run all tests
ruff check .               # lint (CI gate on PRs and pushes to main)
hubble-inplay-cfg [--key <hex-or-b64>] [--rot-exp <n>] [--interval <seconds>] [--payload <hex>] [-o <path>]
PYTHONPATH=src python -m hubble_inplay_cfg ...   # run without installing
```

## Architecture

Src-layout package. Single transformation: inputs → IN100 `.cfg` JSON.

```
src/hubble_inplay_cfg/
  template.py   BASE_CONFIG dict (authoritative)
  builder.py    build_config() and its helpers
  cli.py        argparse + validation + I/O
tests/          pytest, stdlib-only
```

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

## Testing

Tests run offline, no device needed. `test_builder.py` includes the original design's
worked example (`rot_exp=6, interval=2000 → 0xfe0`) as a regression guard on the formula.
