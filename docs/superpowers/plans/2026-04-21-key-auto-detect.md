# `--key` hex/base64 auto-detect Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `--key` accept either a 32-char hex string or a base64-encoded 16-byte AES-128 key, auto-detected, with length validation and clear errors.

**Architecture:** Single helper `decode_key(key)` in `builder.py` owns the detection. Rule: if the stripped input is 32 chars and all hex digits, decode as hex; otherwise decode as base64 and verify 16 bytes. CLI passes `--key` straight through; internal storage (lowercase hex in the output config) is unchanged.

**Tech Stack:** Python 3 stdlib only (`base64`, `bytes.fromhex`). pytest for tests.

**Spec:** `docs/superpowers/specs/2026-04-21-key-auto-detect-design.md`

---

## File Structure

All changes are in existing files. No new modules.

- `src/hubble_inplay_cfg/builder.py` — rename `decode_key0` → `decode_key`, rename `build_config` kwarg `key0_b64` → `key0`, add hex-detection branch.
- `src/hubble_inplay_cfg/cli.py` — update `--key` help text, pass through to renamed kwarg.
- `tests/test_builder.py` — rename references, add tests for the hex path and its edge cases.
- `tests/test_cli.py` — add a CLI-level hex-key acceptance test and a bad-hex rejection test.
- `CLAUDE.md` — update the "key0 changes encoding" gotcha.

---

### Task 1: Rename `decode_key0` → `decode_key` across codebase (no behavior change)

This isolates the rename so Task 2's diff is purely the new hex logic.

**Files:**
- Modify: `src/hubble_inplay_cfg/builder.py` (function `decode_key0` at line 28; `build_config` kwarg `key0_b64` at line 98; body of `build_config` at line 103)
- Modify: `src/hubble_inplay_cfg/cli.py` (`build_config` call at line 81-86)
- Modify: `tests/test_builder.py` (import at line 5-11; `test_decode_key0_*` tests; every `key0_b64=` call site)

- [ ] **Step 1: Rename in `builder.py`**

In `src/hubble_inplay_cfg/builder.py`, apply these edits:

Replace the `decode_key0` definition:

```python
def decode_key(key: str) -> str:
    """Decode a base64 AES-128 key and return it as lowercase hex."""
    try:
        raw = base64.b64decode(key, validate=True)
    except ValueError as exc:
        raise ValueError(f"key is not valid base64: {exc}") from exc
    if len(raw) != KEY_LENGTH_BYTES:
        raise ValueError(
            f"key must decode to {KEY_LENGTH_BYTES} bytes, got {len(raw)}"
        )
    return raw.hex()
```

Replace `build_config`'s signature and body:

```python
def build_config(
    *,
    interval_ms: int,
    key0: str,
    rot_exp: int,
    payload_hex: str = "FF",
) -> Dict[str, Any]:
    """Produce a fully-populated IN100 config dict ready to serialize as JSON."""
    key0_hex = decode_key(key0)
    payload_bytes = parse_payload(payload_hex)
    data_string, payload_len = assemble_payload_data(payload_bytes)
    adv_count = compute_adv_count_to_reset(rot_exp, interval_ms)

    cfg = base_config()
    adv = cfg["advSet"][0]
    adv["interval"] = interval_ms
    adv["rot_exp"] = rot_exp
    adv["payload"][0]["data"] = data_string
    adv["payload"][0]["len"] = payload_len
    cfg["txSetting"]["key0"] = key0_hex
    _update_timer_register(cfg["regSettingCust"], adv_count)

    return cfg
```

Note: error message strings in `decode_key` now say `"key ..."` instead of `"key0 ..."`. Tests in Task 1 Step 3 are updated to match.

- [ ] **Step 2: Rename in `cli.py`**

In `src/hubble_inplay_cfg/cli.py`, change the `build_config` call to pass `key0=args.key`:

```python
    try:
        cfg = build_config(
            interval_ms=interval_ms,
            key0=args.key,
            rot_exp=args.rot_exp,
            payload_hex=args.payload,
        )
    except ValueError as exc:
        parser.error(str(exc))
```

- [ ] **Step 3: Rename in `tests/test_builder.py`**

Update import block:

```python
from hubble_inplay_cfg.builder import (
    assemble_payload_data,
    build_config,
    compute_adv_count_to_reset,
    decode_key,
    parse_payload,
)
```

Rename the three key-related tests and update their bodies:

```python
def test_decode_key_base64_round_trip():
    raw = bytes(range(16))
    assert decode_key(base64.b64encode(raw).decode()) == raw.hex()


def test_decode_key_rejects_wrong_length():
    short = base64.b64encode(b"short").decode()
    with pytest.raises(ValueError, match="16 bytes"):
        decode_key(short)


def test_decode_key_rejects_non_base64():
    with pytest.raises(ValueError, match="not valid base64"):
        decode_key("!!!not-base64!!!")
```

Update every `build_config(... key0_b64=VALID_KEY_B64 ...)` call to `key0=VALID_KEY_B64`. This affects `test_build_config_sets_all_fields`, `test_build_config_uses_email_timer_value`, `test_build_config_rejects_bad_key`, `test_build_config_rejects_nonpositive_interval`, `test_build_config_preserves_bd_addr`. Example:

```python
def test_build_config_sets_all_fields():
    cfg = build_config(
        interval_ms=2000,
        key0=VALID_KEY_B64,
        rot_exp=10,
        payload_hex="FF",
    )
    ...
```

And:

```python
def test_build_config_rejects_bad_key():
    with pytest.raises(ValueError):
        build_config(
            interval_ms=2000,
            key0="not-base64!!",
            rot_exp=10,
            payload_hex="FF",
        )
```

- [ ] **Step 4: Run full test suite, verify green**

Run: `pytest -q`
Expected: all tests pass (same set as before, just renamed).

- [ ] **Step 5: Commit**

```bash
git add src/hubble_inplay_cfg/builder.py src/hubble_inplay_cfg/cli.py tests/test_builder.py
git commit -m "refactor: rename decode_key0 → decode_key, key0_b64 → key0"
```

---

### Task 2: Add hex-detection branch to `decode_key` (TDD)

**Files:**
- Modify: `src/hubble_inplay_cfg/builder.py` (`decode_key` function)
- Modify: `tests/test_builder.py` (add hex tests)

- [ ] **Step 1: Write failing tests**

Add these tests to `tests/test_builder.py` (after the existing `test_decode_key_rejects_non_base64`):

```python
def test_decode_key_hex_uppercase():
    assert decode_key("000102030405060708090A0B0C0D0E0F") == "000102030405060708090a0b0c0d0e0f"


def test_decode_key_hex_lowercase():
    assert decode_key("000102030405060708090a0b0c0d0e0f") == "000102030405060708090a0b0c0d0e0f"


def test_decode_key_hex_mixed_case():
    assert decode_key("000102030405060708090A0b0C0d0E0f") == "000102030405060708090a0b0c0d0e0f"


def test_decode_key_strips_whitespace():
    assert decode_key("  000102030405060708090a0b0c0d0e0f\n") == "000102030405060708090a0b0c0d0e0f"


def test_decode_key_rejects_32_char_non_hex():
    # 32 chars but one char ('!') is neither hex nor in the base64 alphabet,
    # so both decode branches fail and the format-error path is taken.
    # (A char like 'Z' would be rejected by hex but is valid base64, so it
    # would hit the length-error path instead, which is a different message.)
    with pytest.raises(ValueError, match="not valid base64 or 32-char hex"):
        decode_key("!0010203040506070809010203040506")


def test_decode_key_rejects_hex_wrong_length():
    # 30 hex chars — not 32, so hex branch skipped; base64 path rejects too.
    with pytest.raises(ValueError):
        decode_key("000102030405060708090a0b0c0d0e")
```

- [ ] **Step 2: Run new tests, verify they fail**

Run: `pytest tests/test_builder.py -q -k "hex or strip or 32_char_non_hex"`
Expected: all six new tests fail — the hex branch isn't implemented, and the error-message match `"not valid base64 or 32-char hex"` doesn't match the current `"not valid base64"`.

- [ ] **Step 3: Implement hex detection**

Replace the body of `decode_key` in `src/hubble_inplay_cfg/builder.py`:

```python
def decode_key(key: str) -> str:
    """Decode an AES-128 key (32-char hex or base64) to lowercase hex."""
    stripped = key.strip()
    if len(stripped) == 32:
        try:
            return bytes.fromhex(stripped).hex()
        except ValueError:
            pass  # fall through to base64 attempt
    try:
        raw = base64.b64decode(stripped, validate=True)
    except ValueError as exc:
        raise ValueError(
            f"key is not valid base64 or 32-char hex: {exc}"
        ) from exc
    if len(raw) != KEY_LENGTH_BYTES:
        raise ValueError(
            f"key must decode to {KEY_LENGTH_BYTES} bytes, got {len(raw)}"
        )
    return raw.hex()
```

Also update the existing `test_decode_key_rejects_non_base64` to match the new error text:

```python
def test_decode_key_rejects_non_base64():
    with pytest.raises(ValueError, match="not valid base64 or 32-char hex"):
        decode_key("!!!not-base64!!!")
```

- [ ] **Step 4: Run full test suite, verify green**

Run: `pytest -q`
Expected: all tests pass, including the six new ones and the updated `test_decode_key_rejects_non_base64`.

- [ ] **Step 5: Commit**

```bash
git add src/hubble_inplay_cfg/builder.py tests/test_builder.py
git commit -m "feat(key): accept 32-char hex in addition to base64"
```

---

### Task 3: Update CLI help text and add CLI-level tests

**Files:**
- Modify: `src/hubble_inplay_cfg/cli.py` (`--key` help string at line 26)
- Modify: `tests/test_cli.py` (add hex tests)

- [ ] **Step 1: Write failing CLI test for hex input**

Add to `tests/test_cli.py`:

```python
VALID_KEY_HEX = bytes(range(16)).hex()  # "000102030405060708090a0b0c0d0e0f"


def test_hex_key_accepted(capsys):
    assert main(_args(**{"--key": VALID_KEY_HEX})) == 0
    cfg = json.loads(capsys.readouterr().out)
    assert cfg["txSetting"]["key0"] == VALID_KEY_HEX


def test_hex_key_uppercase_accepted(capsys):
    assert main(_args(**{"--key": VALID_KEY_HEX.upper()})) == 0
    cfg = json.loads(capsys.readouterr().out)
    assert cfg["txSetting"]["key0"] == VALID_KEY_HEX  # stored lowercase


def test_bad_hex_key_errors(capsys):
    # 32 chars with a non-hex char, and not valid base64 either.
    bad = "Z" + "0" * 31
    with pytest.raises(SystemExit) as exc:
        main(_args(**{"--key": bad}))
    assert exc.value.code == 2
```

- [ ] **Step 2: Run the new tests, verify they pass**

Run: `pytest tests/test_cli.py -q -k "hex"`
Expected: all three new tests pass — Task 2 already put the detection logic in place, and the CLI just passes strings through.

Note: these tests are strictly exercising already-working behavior end-to-end via the CLI. They don't need to fail first to justify their existence; they are coverage for the user-facing surface.

- [ ] **Step 3: Update `--key` help text**

In `src/hubble_inplay_cfg/cli.py`, replace the `--key` argument block:

```python
    parser.add_argument(
        "--key",
        required=True,
        help=(
            "16-byte AES-128 key. Accepts 32-char hex "
            "(e.g. E001020304...0F) or base64; auto-detected."
        ),
    )
```

- [ ] **Step 4: Run full test suite**

Run: `pytest -q`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/hubble_inplay_cfg/cli.py tests/test_cli.py
git commit -m "feat(cli): document hex input in --key help; add CLI tests"
```

---

### Task 4: Sync `CLAUDE.md` and `README.md` with the new key handling

The repo's docs were stale before this work started — they reference
`--key0` even though the CLI flag has been `--key` since the initial
commit, and they mention `decode_key0` / `key0_b64`. Fold all of that
into one doc-sync commit now that the code is in its final shape.

**Files:**
- Modify: `CLAUDE.md` (usage line; the "`key0` changes encoding" gotcha)
- Modify: `README.md` (CLI syntax, argument table, example commands, Python API example, prose mentions)

- [ ] **Step 1: Update `CLAUDE.md`**

Change the usage line (currently `hubble-inplay-cfg --key0 <b64> ...`) to use `--key`:

```
hubble-inplay-cfg --key <hex-or-b64> --rot-exp <n> --interval <ms> [--payload <hex>] [-o <path>]
```

Replace the existing "`key0` changes encoding" bullet with:

```markdown
- **`--key` accepts two input formats**: the CLI takes either a 32-char hex
  string (e.g. `E001020304...`) or base64, auto-detected by length and
  charset. The config always stores lowercase hex. `decode_key` handles the
  conversion.
```

- [ ] **Step 2: Update `README.md`**

Replace every `--key0` with `--key`. This touches (at least): the CLI syntax line, the argument table header row, and every example invocation. In the argument table, update the description to: `"16-byte AES-128 key. 32-char hex (e.g. E001020304...0F) or base64; auto-detected."`.

In the Python API example, replace `key0_b64="..."` with `key0="..."` and update the surrounding prose to say the kwarg accepts hex or base64.

Prose mentions of "`key0`" as an input concept can remain where they refer to the *stored* config field (`txSetting.key0`) but should switch to `--key` when referring to the CLI input.

- [ ] **Step 3: Sanity-check**

Run: `grep -n "key0\|--key" CLAUDE.md README.md`
Review each line to confirm it either refers to the stored config field (`txSetting.key0`) — fine — or uses the new flag name `--key`. No surviving `--key0` / `decode_key0` / `key0_b64` references.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: sync CLAUDE.md and README with --key hex/base64 support"
```

---

## Self-Review Results

**Spec coverage:**
- Detection rule → Task 2 Step 3 ✓
- Length verification both paths → 32-char hex branch yields 16 bytes by construction; base64 branch checks `len(raw) != KEY_LENGTH_BYTES` ✓
- Clear dual-format error message → Task 2 Step 3 (`"not valid base64 or 32-char hex"`) ✓
- Tests for hex + edge cases → Task 2 Step 1 (six new tests) ✓
- CLI help text update → Task 3 Step 3 ✓
- `CLAUDE.md` gotcha → Task 4 ✓
- Rename `decode_key0` → `decode_key` and `key0_b64` → `key0` → Task 1 ✓
- Out-of-scope items (separators, `0x` prefix, file input) → correctly absent from all tasks ✓

**Placeholder scan:** No `TBD`, `TODO`, "handle edge cases", or "similar to task N" phrasing. Every code step shows the full code.

**Type/name consistency:** `decode_key`, `key0` (kwarg), `KEY_LENGTH_BYTES` used consistently. Error strings reused verbatim in regex matchers.
