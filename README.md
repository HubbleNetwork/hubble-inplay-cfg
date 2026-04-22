# hubble-inplay-cfg

Generate IN100 NanoBeacon `.cfg` files for Hubble advertising packets.

**Who this is for.** Engineers provisioning InPlay IN100 BLE beacon chips to
advertise on Hubble Network. The IN100 is configured via a JSON `.cfg` file
describing its registers, advertising payload, and timing behavior.

Given three inputs — `key0`, `period_exponent`, and advertising `interval` — this tool emits a
ready-to-flash JSON config. It computes the EID timer-wrap register
(`write: 3 1 3 3284 …`) from `period_exponent` and `interval` so you don't have to.

## Install

Requires Python 3.10+. No third-party runtime dependencies.

```bash
pip install -e .
```

That registers the `hubble-inplay-cfg` entry point. You can also run the
module directly without installing:

```bash
PYTHONPATH=src python -m hubble_inplay_cfg ...
```

## CLI

```
hubble-inplay-cfg [--key <hex-or-b64>] [--period-exponent <int>] [--interval <seconds>] [--payload <hex>] [-o <path>]
```

| Flag | Default | Description |
|---|---|---|
| `--key` | all-zeros | 16-byte AES-128 key. 32-char hex (e.g. `E00102030405060708090A0B0C0D0E0F`) or base64; auto-detected. The all-zeros default is intended for pipelines that inject the real key after generation — configs built with it won't decode at the Hubble backend. |
| `--period-exponent` | `15` | EID rotation period exponent (rotation period = 2^`period_exponent` seconds). Accepted 1–15; values 1–9 warn (the Hubble backend only accepts 10–15). |
| `--interval` | `2` | Advertising interval in seconds. |
| `--payload` | `FF` | Raw hex bytes (≥1 byte) embedded as a single `<EncRaw … 0 1>` token. |
| `-o`, `--output` | stdout | Write JSON to this file instead of stdout. |

### Examples

Generate a config with a 2 s advertising interval and a 1024 s EID rotation period:

```bash
hubble-inplay-cfg \
  --key AAECAwQFBgcICQoLDA0ODw== \
  --period-exponent 10 \
  --interval 2 \
  -o my-device.cfg
```

Pipe to a file directly:

```bash
hubble-inplay-cfg --key "$KEY" --period-exponent 12 --interval 1 > device.cfg
```

Use a multi-byte payload (e.g. a 3-byte tag identifier):

```bash
hubble-inplay-cfg --key "$KEY" --period-exponent 10 --interval 2 --payload FF01AB
```

## Generate a config via GitHub Actions

Prefer not to install anything locally? Fork this repo and run the
**Generate config** workflow — it produces a `.cfg` file you can
download as an artifact. (`workflow_dispatch` requires write access, so
a fork is needed.)

1. **Fork** the repo on GitHub.
2. In your fork, open **Actions** → if prompted, enable workflows.
3. Select **Generate config**, click **Run workflow**, and fill in any
   inputs you want to override. Leaving a field blank uses the CLI
   default; `output_name` names the artifact.
4. When the run finishes, download the artifact from the run's summary
   page.

Or just run the CLI locally — see [Install](#install) and [CLI](#cli).

## Python API

```python
import json
from hubble_inplay_cfg import build_config

cfg = build_config(
    interval_ms=2000,
    key0="AAECAwQFBgcICQoLDA0ODw==",
    rot_exp=10,
    payload_hex="FF",
)

with open("my-device.cfg", "w") as f:
    json.dump(cfg, f, indent=4)
```

`build_config` returns a plain `dict` ready to serialize as IN100 `.cfg`
JSON. Fields it sets:

- `advSet[0].interval`, `advSet[0].rot_exp` (IN100 JSON field name)
- `advSet[0].payload[0].data` and `.len`
- `txSetting.key0` (hex-encoded from the hex or base64 input)
- The `3284` entry inside `regSettingCust`

Everything else passes through from the baked-in template.

## How the timer-wrap value is computed

The register `write: 3 1 3 3284 <val>` sets the number of advertisements
before the EID counter resets to 0. With a 128-entry EID pool (indices
0–127):

```
adv_count_to_reset = floor(2^period_exponent / (interval_ms / 1000) * 127)
```

Example: `period_exponent=10`, `interval=2000 ms` → `1024 / 2 · 127 = 65024 = 0xFE00`.

This tool always computes and writes this value — historic config files
had stale hardcoded values, which is part of why this builder exists.

## Flashing

This tool only emits `.cfg` JSON. Flash it to a device with InPlay's
`beacon_mp_cmd.exe` (Windows-only) or the NanoBeacon Config Tool GUI.
Scan emitted advertisements with
[`pyhubblenetwork`](https://github.com/HubbleNetwork/pyhubblenetwork) using
the same `key0` you passed here.

## Development

Install the package with dev extras (pulls in `pytest` and `ruff`):

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

CI runs `ruff check .` on every pull request and push to `main` via
`.github/workflows/lint.yml`. Fix any ruff findings locally before
pushing — the config lives under `[tool.ruff]` in `pyproject.toml`.
