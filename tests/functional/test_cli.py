import json

import pytest
from typer.testing import CliRunner

from ffpolicy.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_cache(monkeypatch, tmp_path):
    monkeypatch.setattr("platformdirs.user_cache_dir", lambda *a, **k: str(tmp_path / "cache"))


@pytest.fixture
def valid_input(tmp_path):
    path = tmp_path / "input.yaml"
    path.write_text(
        "firefox_version: 130\n"
        "policies:\n"
        "  DisableTelemetry: true\n"
        "  ExtensionSettings:\n"
        "    ext@example.com:\n"
        "      installation_mode: force_installed\n"
        "      install_url: https://example.com/x.xpi\n"
    )
    return path


@pytest.fixture
def invalid_input(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        "policies:\n"
        "  ExtensionSettings:\n"
        "    ext@example.com:\n"
        "      installation_mode: force_installed\n"
    )
    return path


def test_validate_passes_for_valid_input(valid_input):
    result = runner.invoke(app, ["validate", str(valid_input), "--offline"])
    assert result.exit_code == 0
    assert "Validation OK" in result.stdout


def test_validate_fails_for_invalid_input(invalid_input):
    result = runner.invoke(app, ["validate", str(invalid_input), "--offline"])
    assert result.exit_code == 1


def test_generate_writes_output(valid_input, tmp_path):
    output = tmp_path / "policies.json"
    result = runner.invoke(
        app, ["generate", str(valid_input), "-o", str(output), "--offline"]
    )
    assert result.exit_code == 0, result.stdout
    written = json.loads(output.read_text())
    assert written["policies"]["DisableTelemetry"] is True


def test_generate_does_not_write_on_validation_failure(invalid_input, tmp_path):
    output = tmp_path / "policies.json"
    result = runner.invoke(
        app, ["generate", str(invalid_input), "-o", str(output), "--offline"]
    )
    assert result.exit_code == 1
    assert not output.exists()


def test_export_to_custom_target(valid_input, tmp_path):
    custom = tmp_path / "custom-dir"
    result = runner.invoke(
        app,
        [
            "export",
            str(valid_input),
            "--target",
            "custom",
            "--custom-path",
            str(custom),
            "--offline",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert (custom / "policies.json").exists()


def test_preview_prints_json_without_writing(valid_input):
    result = runner.invoke(app, ["preview", str(valid_input)])
    assert result.exit_code == 0
    assert '"DisableTelemetry": true' in result.stdout


def test_presets_command_lists_disa_stig():
    result = runner.invoke(app, ["presets"])
    assert result.exit_code == 0
    assert "disa_stig" in result.stdout
    assert "DISA STIG" in result.stdout
    assert "V-251545" in result.stdout  # manual/procedural item is called out


def test_preview_with_preset_and_no_input_file():
    result = runner.invoke(app, ["preview", "--preset", "disa_stig"])
    assert result.exit_code == 0
    assert '"DisableTelemetry": true' in result.stdout
    assert '"SSLVersionMin": "tls1.2"' in result.stdout


def test_preview_requires_input_file_or_preset():
    result = runner.invoke(app, ["preview"])
    assert result.exit_code != 0


def test_preview_unknown_preset_errors():
    result = runner.invoke(app, ["preview", "--preset", "not-a-real-preset"])
    assert result.exit_code != 0


def test_generate_with_preset_and_manual_override(tmp_path):
    """The preset+manual-settings workflow: apply the STIG baseline, then let
    an input file override/extend specific policies on top of it.
    """
    override = tmp_path / "override.yaml"
    override.write_text(
        "policies:\n"
        "  PopupBlocking:\n"
        "    Allow: [\"https://intranet.example.mil/\"]\n"
        "    Default: true\n"
        "    Locked: true\n"
    )
    output = tmp_path / "policies.json"

    result = runner.invoke(
        app,
        ["generate", str(override), "--preset", "disa_stig", "-o", str(output), "--offline"],
    )

    assert result.exit_code == 0, result.stdout
    written = json.loads(output.read_text())["policies"]
    # preset-derived value, untouched by the override file
    assert written["DisableTelemetry"] is True
    # override file's value for a key the preset also set
    assert written["PopupBlocking"]["Allow"] == ["https://intranet.example.mil/"]
