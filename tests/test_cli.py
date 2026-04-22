"""CLI smoke tests — no hardware required."""

from __future__ import annotations

import json
import subprocess
import sys


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "hubble_inplay_cfg", *args],
        capture_output=True,
        text=True,
    )


# --- version ---


def test_version_exits_zero():
    result = _run("version")
    assert result.returncode == 0


def test_version_contains_hubble():
    result = _run("version")
    assert "hubble-inplay" in result.stdout.lower() or "hubble" in result.stdout.lower()


# --- generate ---


def test_generate_creates_file(tmp_path):
    out = tmp_path / "device.cfg"
    result = _run(
        "generate",
        "--key", "00000000000000000000000000000000",
        "--rot-exp", "10",
        "--interval", "2",
        "-o", str(out),
    )
    assert result.returncode == 0, result.stderr
    assert out.exists()


def test_generate_output_is_valid_json(tmp_path):
    out = tmp_path / "device.cfg"
    _run(
        "generate",
        "--key", "00000000000000000000000000000000",
        "--rot-exp", "10",
        "--interval", "2",
        "-o", str(out),
    )
    data = json.loads(out.read_text())
    assert isinstance(data, dict)


def test_generate_uses_default_key(tmp_path):
    out = tmp_path / "device.cfg"
    result = _run("generate", "--rot-exp", "10", "--interval", "2", "-o", str(out))
    assert result.returncode == 0
    data = json.loads(out.read_text())
    assert "advSet" in data


def test_generate_uses_default_interval(tmp_path):
    out = tmp_path / "device.cfg"
    result = _run(
        "generate", "--key", "00000000000000000000000000000000", "--rot-exp", "10", "-o", str(out)
    )
    assert result.returncode == 0
    data = json.loads(out.read_text())
    assert data["advSet"][0]["interval"] == 2000


# --- validate ---


def test_validate_passes_for_valid_config(tmp_path):
    out = tmp_path / "device.cfg"
    _run(
        "generate",
        "--key", "00000000000000000000000000000000",
        "--rot-exp", "10",
        "--interval", "2",
        "-o", str(out),
    )
    result = _run("validate", "--config", str(out))
    assert result.returncode == 0, result.stderr


def test_validate_verbose(tmp_path):
    out = tmp_path / "device.cfg"
    _run(
        "generate",
        "--key", "00000000000000000000000000000000",
        "--rot-exp", "10",
        "--interval", "2",
        "-o", str(out),
    )
    result = _run("validate", "--config", str(out), "--verbose")
    assert result.returncode == 0
    assert "word" in result.stdout.lower() or "ok" in result.stdout.lower()


def test_validate_rejects_missing_file(tmp_path):
    result = _run("validate", "--config", str(tmp_path / "nonexistent.cfg"))
    assert result.returncode != 0


def test_validate_rejects_malformed_json(tmp_path):
    bad = tmp_path / "bad.cfg"
    bad.write_text("not json {{{")
    result = _run("validate", "--config", str(bad))
    assert result.returncode != 0


# --- program requires --port ---


def test_program_without_port_fails():
    result = _run("program", "--config", "x.cfg")
    assert result.returncode != 0


# --- connect requires --port ---


def test_connect_without_port_fails():
    result = _run("connect")
    assert result.returncode != 0


# --- read-efuse requires --port ---


def test_read_efuse_without_port_fails():
    result = _run("read-efuse", "5")
    assert result.returncode != 0


# --- dtm-start requires --port ---


def test_dtm_start_without_port_fails():
    result = _run("dtm-start", "--params", "0,0,37,0,0,0")
    assert result.returncode != 0


# --- log-file ---


def test_log_file_created(tmp_path):
    log = tmp_path / "run.log"
    out = tmp_path / "device.cfg"
    result = _run(
        "--log-file", str(log),
        "generate",
        "--key", "00000000000000000000000000000000",
        "--rot-exp", "10",
        "--interval", "2",
        "-o", str(out),
    )
    assert result.returncode == 0
    assert log.exists()
    assert log.stat().st_size > 0
