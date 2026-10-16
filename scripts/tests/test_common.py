"""The shared script helpers: paths per platform, and installing a part only when it changed."""

import hashlib

import pytest

import _common


def test_venv_python_matches_the_platform(tmp_path, monkeypatch):
    monkeypatch.setattr(_common, "WINDOWS", True)
    assert _common.venv_python(tmp_path) == tmp_path / ".venv" / "Scripts" / "python.exe"
    monkeypatch.setattr(_common, "WINDOWS", False)
    assert _common.venv_python(tmp_path) == tmp_path / ".venv" / "bin" / "python"


def test_command_for_says_how_to_run_a_script_here(monkeypatch):
    monkeypatch.setattr(_common, "WINDOWS", True)
    assert _common.command_for("scripts/testing/set_up.py") == "py scripts/testing/set_up.py"
    monkeypatch.setattr(_common, "WINDOWS", False)
    assert _common.command_for("scripts/testing/set_up.py") == "python3 scripts/testing/set_up.py"


@pytest.fixture
def part(tmp_path):
    """A part folder that looks installed: pyproject.toml, a .venv Python, a stamp for "dev"."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    python = _common.venv_python(tmp_path)
    python.parent.mkdir(parents=True)
    python.write_text("")
    digest = hashlib.sha256((tmp_path / "pyproject.toml").read_bytes()).hexdigest().upper()
    (tmp_path / ".venv" / "budget-buddy-install.txt").write_text(f"{digest} dev")
    return tmp_path


@pytest.fixture
def commands(monkeypatch):
    """What install_part would run, instead of running it."""
    ran = []

    def run(command, cwd, failure):
        ran.append([str(c) for c in command])
        if "venv" in ran[-1]:
            (cwd / ".venv").mkdir()

    monkeypatch.setattr(_common, "run", run)
    return ran


def test_nothing_is_installed_when_nothing_changed(part, commands):
    assert _common.install_part(part, ("dev",), "x") == _common.venv_python(part)
    fewer = _common.install_part(part, (), "x")  # fewer extras than installed
    assert fewer == _common.venv_python(part)
    assert commands == []


def test_new_extras_install_again_keeping_the_old_ones(part, commands):
    _common.install_part(part, ("build",), "x")  # building the app after a tester's setup
    assert commands[-1][-1] == ".[build,dev]"
    assert (part / ".venv" / "budget-buddy-install.txt").read_text().endswith(" build,dev")


def test_a_changed_pyproject_installs_again_with_the_same_extras(part, commands):
    (part / "pyproject.toml").write_text("[project]\nname = 'y'\n")
    _common.install_part(part, (), "x")
    assert commands[-1][-2:] == ["-e", ".[dev]"]


def test_a_new_venv_installs_just_what_was_asked(tmp_path, commands):
    (tmp_path / "pyproject.toml").write_text("")
    _common.install_part(tmp_path, (), "x")
    assert commands[-1][-2:] == ["-e", "."]


def test_windows_only_scripts_stop_elsewhere(monkeypatch):
    monkeypatch.setattr(_common, "WINDOWS", False)
    with pytest.raises(SystemExit):
        _common.require_windows("The desktop app")


def test_a_missing_venv_is_made_first(tmp_path, commands):
    (tmp_path / "pyproject.toml").write_text("")
    _common.install_part(tmp_path, (), "x")
    assert commands[0][1:] == ["-m", "venv", ".venv"]
