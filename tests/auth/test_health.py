import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from auth import health

REPO = Path(__file__).resolve().parents[2]
ENV_KEYS = [
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "GOOGLE_CLIENT_SECRET_PATH",
    "GOOGLE_CLIENT_SECRETS",
    "WORKSPACE_MCP_CREDENTIALS_DIR",
    "GOOGLE_MCP_CREDENTIALS_DIR",
]


@pytest.fixture
def clean_env(tmp_path, monkeypatch):
    for k in ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET_PATH", str(tmp_path / "client_secret.json"))
    monkeypatch.setenv("WORKSPACE_MCP_CREDENTIALS_DIR", str(tmp_path / "creds"))
    return tmp_path


def test_missing_names_env_vars_and_file(clean_env, capsys):
    assert health.run() == 1
    out = capsys.readouterr().out
    assert "GOOGLE_OAUTH_CLIENT_ID" in out
    assert "GOOGLE_OAUTH_CLIENT_SECRET" in out
    assert str(clean_env / "client_secret.json") in out
    assert "OK" not in out.splitlines()


def test_half_set_names_the_missing_one(clean_env, monkeypatch, capsys):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "dummy-id")
    assert health.run() == 1
    out = capsys.readouterr().out
    assert "Missing env var GOOGLE_OAUTH_CLIENT_SECRET" in out
    assert "dummy-id" not in out


def test_env_vars_ok_and_no_secret_printed(clean_env, monkeypatch, capsys):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "dummy-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "dummy-secret-value")
    assert health.run() == 0
    out = capsys.readouterr().out
    assert out.strip().endswith("OK")
    assert "dummy-secret-value" not in out


def test_secrets_file_ok(clean_env, capsys):
    (clean_env / "client_secret.json").write_text(json.dumps({"installed": {}}))
    assert health.run() == 0
    assert "OK" in capsys.readouterr().out


def test_bad_secrets_file_named(clean_env, capsys):
    (clean_env / "client_secret.json").write_text("not json")
    assert health.run() == 1
    assert str(clean_env / "client_secret.json") in capsys.readouterr().out


def test_module_exit_codes_subprocess(tmp_path):
    env = {k: v for k, v in os.environ.items() if k not in ENV_KEYS}
    env["GOOGLE_CLIENT_SECRET_PATH"] = str(tmp_path / "client_secret.json")
    env["WORKSPACE_MCP_CREDENTIALS_DIR"] = str(tmp_path / "creds")
    cmd = [sys.executable, "-m", "auth.health"]
    r = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True)
    assert r.returncode == 1 and "GOOGLE_OAUTH_CLIENT_ID" in r.stdout
    assert "Traceback" not in r.stdout + r.stderr
    env["GOOGLE_OAUTH_CLIENT_ID"] = "dummy"
    env["GOOGLE_OAUTH_CLIENT_SECRET"] = "dummy"
    r = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip().endswith("OK")
