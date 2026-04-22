# hubble-inplay-cfg

Generate IN100 NanoBeacon `.cfg` files for Hubble advertising packets.

**Who this is for.** Engineers provisioning InPlay IN100 BLE beacon chips to
advertise on Hubble Network. The IN100 is configured via a JSON `.cfg` file
describing its registers, advertising payload, and timing behavior.

Given four inputs — `key`, `period_exponent`, `tx-power` and advertising `interval` — this tool
emits a ready-to-flash JSON config.

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

If you'd rather not install Python locally, see
[Generate a config via GitHub Actions](#generate-a-config-via-github-actions)
below.

## Provisioning a device for Hubble Network

End-to-end instructions for programming an InPlay IN100 BLE chip to
advertise on Hubble Network.

> **Critical:** The configuration programmed onto the device **must match**
> the configuration set when the device was registered on the Hubble backend —
> specifically the **AES-128 key** and the **period exponent**. Any mismatch and
> the backend will silently drop the device's packets.

The flow is four steps:

1. **Register** the device with Hubble (REST API or `pyhubblenetwork`).
2. **Generate** a device `.cfg` with `hubble-inplay-cfg`.
3. **Load** the `.cfg` onto the chip — test in RAM, then burn to eFuse.
4. **Verify** the device is advertising and decodable.

A field in any step that differs from the others will break decoding silently at
the Hubble backend, so the matching fields are called out in each step and
summarised in the [table at the bottom of this section](#matching-fields-across-the-pipeline).

### Prerequisites

Before starting, make sure you have:

**Hubble account**

- A Hubble Network account with API access.
- An API **bearer token**.
- Your **organization ID**.

Contact Hubble if you don't have these yet — you'll need them for registration
(step 1) and backend verification (step 4).

**Hardware**

- One or more InPlay IN100 chips (typically on a NanoBeacon dev or programming board).
- A USB-UART connection to the chip, appearing as a COM port (e.g. `COM4` on Windows).

**Software**

- `hubble-inplay-cfg` — this tool. See [Install](#install).
- [`pyhubblenetwork`](https://github.com/HubbleNetwork/pyhubblenetwork) — used
  to register devices (step 1) and to scan/decode advertisements locally (step 4).
- One of: `beacon_mp_cmd.exe` (Windows CLI) **or** the NanoBeacon Config Tool
  GUI, from InPlay. See step 3 for links.

### 1. Register the device with Hubble

Every device must be registered before the Hubble backend will decode its
advertisements. Registration records the device's AES-128 key and the parameters
needed to decode its rotating identifier:

- **Encryption mode:** `AES-128-EAX`
- **Counter mode:** `DEVICE_UPTIME`
- **Period exponent** (optional, default 15): integer 10–15. This **must match**
  the `--period-exponent` you put in the config in step 2.

#### Option A — REST API

Use the Hubble cloud API directly. Full request/response spec:

<https://hubble.com/docs/api-specification/register-new-devices>

#### Option B — `pyhubblenetwork` CLI

```bash
# Default period exponent (15)
hubblenetwork org register-device -e AES-128-EAX -c DEVICE_UPTIME

# Or specify an explicit period exponent (must match --period-exponent in step 2)
hubblenetwork org register-device -e AES-128-EAX -c DEVICE_UPTIME --period-exponent 10
```

The command returns the newly-registered device's AES-128 key. **Save this
key** — you will pass it to `hubble-inplay-cfg --key` in step 2 and to the
scanner in step 4.

> **Note — key encoding:** Hubble's API returns the AES-128 key as a
> **base64** string (e.g. `AAECAwQFBgcICQoLDA0ODw==`). InPlay's programming
> tools take the key as a **byte array of hex bytes**
> (e.g. `000102030405060708090a0b0c0d0e0f`). `hubble-inplay-cfg --key` accepts
> either form and auto-detects; `beacon_mp_cmd.exe -k0` and the NanoBeacon
> Config Tool GUI need hex. Convert with `base64 -d | xxd -p` or equivalent
> if you're handing the key to the InPlay tool directly.

> **Note:** `--period-exponent` is the same quantity on both the backend and
> the config tool (`rotation period = 2^n seconds`). If they disagree,
> the backend cannot compute the expected EID and will drop the packet.

### 2. Generate the device configuration

```bash
hubble-inplay-cfg \
  --key <KEY_FROM_STEP_1> \
  --period-exponent 10 \
  --interval 2 \
  -o device.cfg
```

The key flags for provisioning:

| Flag | Notes |
|---|---|
| `--key` | 32-char hex or base64 (auto-detected). Becomes `txSetting.key0` in the `.cfg`. |
| `--period-exponent` | Must equal the backend's `period_exponent` from step 1. Range 10–15 for production. |
| `--interval` | Advertising interval in seconds. |
| `--tx-power` | Transmit power in dBm. Accepted: −4 to +4. Default: +4. |

See the [CLI reference](#cli-reference) below for the full flag list (payload,
output path) and defaults.

**Alternative — use a pre-made sample config.** If one of the
[sample configs](#sample-configurations) in `samples/` matches the interval and
TX power you need, you can skip generating and use it as-is. The samples ship
with an all-zeros key; you'll supply the real per-device key at programming
time using `-k0` (see step 3).

### 3. Load the configuration onto the chip

InPlay provides two programming tools. Pick one. Either way, **always test in
RAM first** — the burn step writes the eFuse (OTP) memory and is permanent.

#### Option A — CLI: `beacon_mp_cmd.exe`

Windows-only. Full tool reference: InPlay *NanoBeacon IN100 Command Tool
Application Notes* PDF from InPlay.

Required arguments:

| Flag | Meaning |
|---|---|
| `-c` | Command. Use `ram` for a non-persistent load, `burn` to write eFuse. |
| `-p` | UART port the programmer is on (e.g. `COM4`). |
| `-i` | Path to the `.cfg` file from step 2. |

Common optional arguments:

| Flag | Meaning |
|---|---|
| `-k0`, `--key0` | Override `key0` from the `.cfg` at programming time (32-char hex). `-k1` / `-k2` set the other two key slots if used. |
| `-a` | Set the Bluetooth device address (6 hex bytes MSB-first, e.g. `0605AE030201`). Separate multiple advertising sets with `;`. |
| `-d` | Set the Customer Product ID (6 hex bytes MSB-first). |
| `-r 1` | Reset the chip after burn. |

> **Tip — per-device key injection:** Generate a single template `.cfg` with
> `hubble-inplay-cfg` and leave `--key` at its all-zeros default, then inject
> the real per-device key with `-k0` on each programming call. This avoids
> writing real keys to disk and keeps one config reusable across a fleet.

> **Key hygiene:** AES-128 keys are secrets. Don't commit them to git, log them,
> or leave them in shell history. Prefer `-k0` injection at programming time
> over baking keys into `.cfg` files that land on disk or in a build artifact.

**Step 3a — RAM test (non-destructive, lost on power-cycle):**

```powershell
beacon_mp_cmd.exe -c ram -p COM4 -i device.cfg

:: Or, with per-device key injection (key0 as 16 hex bytes):
beacon_mp_cmd.exe -c ram -p COM4 -i device.cfg -k0 000102030405060708090a0b0c0d0e0f
```

Leave the chip running and proceed to step 4 to confirm advertisements decode
correctly. Power-cycling ends the RAM test.

**Step 3b — Burn to eFuse (permanent):**

```powershell
beacon_mp_cmd.exe -c burn -p COM4 -i device.cfg

:: Or, with per-device key injection (key0 as 16 hex bytes):
beacon_mp_cmd.exe -c burn -p COM4 -i device.cfg -k0 000102030405060708090a0b0c0d0e0f
```

> **Warning:** Burning writes the IN100's OTP eFuse and **can only be done once
> per chip**. Do not burn until the RAM test in step 3a has passed end-to-end
> verification in step 4.
>
> If you burn with a `key0` that does not match the key registered with Hubble
> in step 1, that chip will **never** decode at the backend — and because both
> the eFuse and the Hubble-side registration are immutable, the chip is bricked
> for Hubble use. Verify against the RAM-loaded config **before** burning.

#### Option B — GUI: NanoBeacon Config Tool

Download and user guide:

<https://inplay-tech.com/nanobeacon-config-tool>

In the GUI, open `device.cfg`, connect to the programmer, run the RAM test,
verify with step 4, and only then burn.

### 4. Verify the device is advertising

#### Option A — Scan locally with `pyhubblenetwork`

```bash
hubblenetwork ble scan \
  -k <KEY_FROM_STEP_1> \
  --counter-mode DEVICE_UPTIME \
  --period-exponent 10
```

- `-k` — the same AES-128 key used in steps 1 and 2.
- `--counter-mode` — must match registration (`DEVICE_UPTIME`).
- `--period-exponent` — must equal the value used in steps 1 and 2.

You should see the device appear with decoded payload bytes. If the packet is
seen but does not decode, the key or rotation exponent is mismatched somewhere
along the chain.

#### Option B — Verify via the Hubble backend

With the Hubble Connect app (or any Hubble gateway) scanning nearby, the device's
advertisements will be uplinked and decoded server-side. Use the organization
packets API to confirm recent reports from this device's ID:

<https://hubble.com/docs/api-specification/retrieve-organization-packets>

### Matching fields across the pipeline

All of these must agree for an advertisement to decode end-to-end:

| Field | Registration (step 1) | Config (step 2) | Scanner (step 4) |
|---|---|---|---|
| AES-128 key | returned by API / CLI | `--key` (or injected at burn with `-k0`) | `-k` |
| Rotation period exponent | `--period-exponent` | `--period-exponent` | `--period-exponent` |
| Counter mode | `-c DEVICE_UPTIME` | (implicit) | `--counter-mode DEVICE_UPTIME` |
| Encryption mode | `-e AES-128-EAX` | (implicit) | (implicit) |

If verification fails, check this table first.

## CLI reference

```
hubble-inplay-cfg [--key <hex-or-b64>] [--period-exponent <int>] [--interval <seconds>] [--payload <hex>] [--tx-power <dBm>] [-o <path>]
```

| Flag | Default | Description |
|---|---|---|
| `--key` | all-zeros | 16-byte AES-128 key. 32-char hex (e.g. `E00102030405060708090A0B0C0D0E0F`) or base64; auto-detected. The all-zeros default is intended for pipelines that inject the real key after generation — configs built with it won't decode at the Hubble backend. |
| `--period-exponent` | `15` | EID rotation period exponent (rotation period = 2^`period_exponent` seconds). Accepted 1–15; values 1–9 warn (the Hubble backend only accepts 10–15). |
| `--interval` | `2` | Advertising interval in seconds. |
| `--payload` | `FF` | Raw hex bytes (≥1 byte) embedded as a single `<EncRaw … 0 1>` token. |
| `--tx-power` | `4` | Transmit power in dBm (`txSetting.txPower`). Accepted: −4 to +4. |
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

## Sample configurations

Pre-built configs for common advertising intervals are in `samples/`:

| File | Interval |
|---|---|
| `hubble-in100-1s-advinterval.cfg` | 1 s |
| `hubble-in100-4s-advinterval.cfg` | 4 s |
| `hubble-in100-10s-advinterval.cfg` | 10 s |

All samples use TX power +4 dBm and rotation exponent 15 (~9 hrs). The key is set to
all-zeros — replace it with your provisioned key before flashing (see `--key` in the
CLI or the NanoBeacon Config Tool under Global Settings → Keys → Key 0).
See [`samples/README.md`](samples/README.md) for details.

> **Heads up on key format:** Hubble's API returns the AES-128 key as a
> **base64** string, but the InPlay programming tools (`beacon_mp_cmd.exe -k0`
> and the NanoBeacon Config Tool GUI) need it as **16 hex bytes**
> (e.g. `000102030405060708090a0b0c0d0e0f`). See
> [step 1's key-encoding note](#1-register-the-device-with-hubble) for
> conversion guidance.

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

Or just run the CLI locally — see [Install](#install) and
[CLI reference](#cli-reference).

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
- `txSetting.txPower`
- The `3284` entry inside `regSettingCust`

Everything else passes through from the baked-in template.

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

## Need help?

If you hit anything not covered here — registration errors, programming
failures, packets that don't decode — reach out to Hubble and we'll help
you work through it.
