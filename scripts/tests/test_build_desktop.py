"""The release build runs in a clean environment: no PIP_* settings, no PYTHONPATH."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "release"))
import build_desktop  # noqa: E402


@pytest.fixture
def ran(monkeypatch, tmp_path):
    """The environment of every command the build would run, instead of running them."""
    envs = []
    monkeypatch.setattr(build_desktop, "WORK", tmp_path)
    monkeypatch.setattr(
        build_desktop, "run", lambda command, cwd, failure, env=None: envs.append(env)
    )
    monkeypatch.setattr(build_desktop, "install_locked", lambda *args: None)
    monkeypatch.setenv("PIP_INDEX_URL", "https://example.invalid/simple")
    monkeypatch.setenv("PYTHONPATH", "elsewhere")
    return envs


def test_the_build_venv_and_pyinstaller_get_a_clean_environment(ran, tmp_path):
    build_desktop.fresh_venv(tmp_path / "server", "x")
    build_desktop.pyinstaller(Path("python"), "home-base.spec", tmp_path)
    assert len(ran) == 2
    for env in ran:
        assert env is not None and "PIP_INDEX_URL" not in env and "PYTHONPATH" not in env


def test_the_build_venv_starts_empty(ran, tmp_path):
    left_over = tmp_path / "venv-server" / "Lib" / "site-packages" / "old.py"
    left_over.parent.mkdir(parents=True)
    left_over.write_text("")
    build_desktop.fresh_venv(tmp_path / "server", "x")
    assert not left_over.exists()
