# `--key` auto-detect: hex or base64

**Date:** 2026-04-21
**Status:** Approved, ready for implementation plan

## Problem

`--key` currently accepts only base64. Users often have the 16-byte AES-128
key as a plain hex string (e.g. `E001020304...`). Requiring them to re-encode
as base64 before invoking the CLI is friction. The tool should accept either
format and verify the key is exactly 128 bits (16 bytes).

## Scope

In scope:
- CLI `--key` accepts base64 **or** 32-char hex; format is auto-detected.
- Length verification in both paths: decoded value must be exactly 16 bytes.
- Clear error messages that name both accepted formats on failure.
- Tests for both input formats and edge cases.
- Updated help text and `CLAUDE.md` gotcha.

Out of scope:
- Separators (`:`, spaces) or prefixes (`0x`) in hex input.
- Reading the key from a file.
- Any change to how the key is stored in the output config (stays lowercase
  hex).

## Detection rule

Applied inside a renamed helper `decode_key` in `builder.py`:

1. Strip surrounding whitespace from the input.
2. If length is exactly 32 **and** every character is in `[0-9a-fA-F]`:
   decode as hex. Result is 16 bytes by construction.
3. Otherwise: attempt `base64.b64decode(..., validate=True)`. Result must
   decode to exactly 16 bytes; reject otherwise.
4. On failure, raise `ValueError`. Message wording matches the table in
   the "Error messages" section below — both the format-failure case and
   the wrong-length case name the key role so the user knows which arg
   went wrong.

Why length 32 is a safe discriminator: a 16-byte base64 value is 24 chars
with `=` padding or 22 chars unpadded. Neither overlaps with 32, so there
is no ambiguity between the two formats.

## Code changes

### `src/hubble_inplay_cfg/builder.py`
- Rename `decode_key0(key0_b64: str) -> str` → `decode_key(key: str) -> str`.
  Same return semantics (lowercase hex).
- Implement the detection rule above.
- In `build_config`, rename parameter `key0_b64` → `key0` and pass through
  to `decode_key`. Docstring updated to say "auto-detected hex or base64".

### `src/hubble_inplay_cfg/cli.py`
- Update `--key` help text to:
  `"16-byte AES-128 key, as 32-char hex (e.g. E001020304...0F) or base64."`
- Pass `args.key` into `build_config` as the renamed `key0` kwarg.

### `tests/test_builder.py`
- Keep existing base64 round-trip test (rename to `test_decode_key_base64`).
- Add `test_decode_key_hex_uppercase`, `test_decode_key_hex_lowercase`,
  `test_decode_key_hex_mixed_case`.
- Add `test_decode_key_strips_whitespace` (leading/trailing spaces/newlines
  accepted).
- Keep rejection tests; add `test_decode_key_rejects_32_char_non_hex`
  (32 chars but contains non-hex char → falls through to base64 path and
  fails there with a clear error) and `test_decode_key_rejects_hex_wrong_length`
  (e.g. 30 chars of hex → not 32 so falls through to base64, fails).
- Update `build_config` tests to use the renamed kwarg.

### `tests/test_cli.py`
- Keep base64 path test.
- Add `test_hex_key_accepted` using a 32-char hex string.
- Add `test_bad_hex_key_errors` (invalid hex of length 32 with a non-hex
  char).

### `CLAUDE.md`
- Update the "`key0` changes encoding" gotcha: CLI now accepts 32-char hex
  or base64; internal storage is still lowercase hex.

## Error messages

| Input shape                                  | Path taken | Error                                                                       |
|----------------------------------------------|------------|-----------------------------------------------------------------------------|
| 32 hex chars                                 | hex        | — (success)                                                                 |
| 24-char base64 decoding to 16 bytes          | base64     | — (success)                                                                 |
| 32 chars with a non-hex char                 | base64     | `"key is not valid base64 or 32-char hex: <reason>"`                        |
| Base64 decoding to ≠ 16 bytes                | base64     | `"key must decode to 16 bytes, got N"`                                      |
| Garbage                                      | base64     | `"key is not valid base64 or 32-char hex: <reason>"`                        |

The CLI already surfaces `ValueError` from `build_config` via
`parser.error`, so no CLI-layer changes are needed for error plumbing.

## Testing

- `pytest` — all existing tests must continue to pass after the rename.
- New tests cover: hex accepted, hex case-insensitive, whitespace stripped,
  32-char non-hex rejected, short/long hex rejected, good base64 still
  accepted, bad base64 still rejected.
- No device or network access required (unchanged from today).

## Migration

`decode_key0` and the `key0_b64` kwarg are renamed, not deprecated. This is
a pre-1.0 internal API; direct callers are only the CLI and tests in this
repo. No external consumers to warn.
