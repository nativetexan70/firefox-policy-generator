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
