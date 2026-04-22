Generate a Hubble IN100 NanoBeacon config and validate it.

## What this does
Runs `hubble-inplay-cfg generate` to produce a `.cfg` JSON file, then immediately validates it with `hubble-inplay-cfg validate` to confirm the word count is ≤256.

## Required inputs
Ask the user for any missing values before running:
- **key** — 16-byte AES-128 key as 32-char hex (e.g. `E00102030405060708090A0B0C0D0E0F`) or base64. Warn if all-zeros: the Hubble backend won't decode it.
- **output path** — where to write the `.cfg` file (e.g. `device.cfg`)

## Optional inputs (use defaults if not specified)
- **rot_exp** — EID rotation exponent, default `15`. Hubble backend requires 10–15; warn if outside that range.
- **interval** — advertising interval in seconds, default `2`
- **payload** — hex bytes, default `FF`
- **tx_power** — TX power in dBm, default `4`

## Steps

1. Generate the config:
```bash
hubble-inplay-cfg generate \
  --key <KEY> \
  --rot-exp <ROT_EXP> \
  --interval <INTERVAL> \
  --payload <PAYLOAD> \
  --tx-power <TX_POWER> \
  -o <OUTPUT_PATH>
```

2. Validate it immediately:
```bash
hubble-inplay-cfg validate --config <OUTPUT_PATH> --verbose
```

3. Report back:
   - The output file path
   - Word count (e.g. `183/256 OK`)
   - Warn if word count > 200 (leaves little headroom)
   - Error and stop if OVERFLOW

## Notes
- `rot_exp=10` → EID rotates every ~17 min; `rot_exp=15` → every ~9 hours
- The timer-wrap register (`0x3284`) is computed automatically: `floor(2^rot_exp / interval * 127)`
- If the user wants to program a chip next, suggest running `/hubble-program`
