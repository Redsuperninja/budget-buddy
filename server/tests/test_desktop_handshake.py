"""The Home Base's half of the desktop handshake matches the published example
(docs/api/desktop-handshake.md). The desktop's tests read the same example."""

import json
import re
from pathlib import Path

from app import instance_proof
from app.config import Settings, default_data_dir

DOC = Path(__file__).resolve().parents[2] / "docs" / "api" / "desktop-handshake.md"
EXAMPLE = json.loads(re.search(r"```json\n(.*?)```", DOC.read_text(encoding="utf-8"), re.S)[1])


def test_running_file_name():
    assert instance_proof.FILE_NAME == EXAMPLE["running_file"]


def test_proof_of_the_example_nonce():
    assert instance_proof.NONCE.fullmatch(EXAMPLE["nonce"])
    assert instance_proof.proof(EXAMPLE["key"], EXAMPLE["nonce"]) == EXAMPLE["proof"]


def test_the_proof_route_answers_the_example(client):
    client.app.state.instance_key = EXAMPLE["key"]
    reply = client.get(EXAMPLE["proof_path"], params={"nonce": EXAMPLE["nonce"]})
    assert reply.json() == {"proof": EXAMPLE["proof"]}


def test_data_folder_rule(monkeypatch, tmp_path):
    rule = EXAMPLE["data_folder"]
    monkeypatch.setenv(rule["override_variable"], str(tmp_path / "chosen"))
    assert Settings().data_dir == tmp_path / "chosen"
    monkeypatch.setattr("app.config.sys.platform", "win32")
    variable, *rest = rule["windows"]
    monkeypatch.setenv(variable, str(tmp_path))
    assert default_data_dir() == tmp_path.joinpath(*rest)
    monkeypatch.setattr("app.config.sys.platform", "linux")
    monkeypatch.setattr("app.config.Path.home", lambda: tmp_path)
    assert default_data_dir() == tmp_path.joinpath(*rule["elsewhere"])
