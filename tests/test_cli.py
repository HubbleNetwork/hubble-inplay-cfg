import base64
import json

import pytest

from hubble_inplay_cfg.cli import main

VALID_KEY_B64 = base64.b64encode(bytes(range(16))).decode()
VALID_KEY_HEX = bytes(range(16)).hex()  # "000102030405060708090a0b0c0d0e0f"


def _args(**overrides):
    base = {
        "--key": VALID_KEY_B64,
        "--rot-exp": "10",
    }
    base.update(overrides)
    out = []
    for k, v in base.items():
        out.extend([k, v])
    return out


def test_stdout_output_is_valid_json(capsys):
    assert main(_args()) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    cfg = json.loads(captured.out)
    assert cfg["advSet"][0]["interval"] == 2000
    assert cfg["advSet"][0]["rot_exp"] == 10


def test_output_flag_matches_stdout(tmp_path, capsys):
    out_file = tmp_path / "config.cfg"
    main(_args() + ["-o", str(out_file)])
    stdout_capture = capsys.readouterr().out
    assert stdout_capture == ""

    main(_args())
    stdout_capture = capsys.readouterr().out

    file_contents = out_file.read_text()
    # File has a trailing newline; stdout print adds one too.
    assert file_contents.rstrip("\n") == stdout_capture.rstrip("\n")


def test_rot_exp_below_absolute_min_errors(capsys):
    with pytest.raises(SystemExit) as exc:
        main(_args(**{"--rot-exp": "0"}))
    assert exc.value.code == 2
    assert "rot-exp" in capsys.readouterr().err


def test_rot_exp_above_absolute_max_errors(capsys):
    with pytest.raises(SystemExit) as exc:
        main(_args(**{"--rot-exp": "16"}))
    assert exc.value.code == 2


def test_rot_exp_preferred_range_no_warning(capsys):
    assert main(_args(**{"--rot-exp": "12"})) == 0
    assert "warning" not in capsys.readouterr().err


def test_rot_exp_below_preferred_warns_but_succeeds(capsys):
    assert main(_args(**{"--rot-exp": "7"})) == 0
    err = capsys.readouterr().err
    assert "warning" in err
    assert "local testing only" in err
    assert "Hubble backend services" in err


def test_invalid_interval_errors(capsys):
    with pytest.raises(SystemExit) as exc:
        main(_args(**{"--interval": "0"}))
    assert exc.value.code == 2


def test_bad_key_errors(capsys):
    with pytest.raises(SystemExit) as exc:
        main(_args(**{"--key": "not!!base64"}))
    assert exc.value.code == 2


def test_custom_payload_flag(capsys):
    main(_args(**{"--payload": "AB12"}))
    cfg = json.loads(capsys.readouterr().out)
    assert "<EncRaw AB12 2byte 0 1>" in cfg["advSet"][0]["payload"][0]["data"]
    assert cfg["advSet"][0]["payload"][0]["len"] == 25


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
    bad = "!" + "0" * 31
    with pytest.raises(SystemExit) as exc:
        main(_args(**{"--key": bad}))
    assert exc.value.code == 2
