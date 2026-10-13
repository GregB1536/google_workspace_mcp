"""Credential health check: ``python -m auth.health`` or ``workspace-mcp --health``.

Verifies, without starting the server, that the OAuth client credentials can be
found and that the credentials directory is usable. Every problem names the
exact env var or file. Values are never printed, only names and paths.

Exit code 0 = OK, 1 = at least one required item is missing.
"""

import json
import os
import sys
from typing import List, Optional, Tuple

from auth.client_secrets import get_client_secrets_path

_ID_ENV = "GOOGLE_OAUTH_CLIENT_ID"
_SECRET_ENV = "GOOGLE_OAUTH_CLIENT_SECRET"


def _credentials_dir() -> Tuple[str, str]:
    """Return (path, source) using the same priority as auth.google_auth."""
    for name in ("WORKSPACE_MCP_CREDENTIALS_DIR", "GOOGLE_MCP_CREDENTIALS_DIR"):
        value = os.getenv(name)
        if value:
            return os.path.expanduser(value), name
    home = os.path.expanduser("~")
    if home and home != "~":
        return os.path.join(home, ".google_workspace_mcp", "credentials"), "default"
    return os.path.join(os.getcwd(), ".credentials"), "default"


def check_credentials() -> Tuple[List[str], List[str]]:
    """Return (errors, notes). Errors make the health check fail."""
    errors: List[str] = []
    notes: List[str] = []

    has_id = bool(os.getenv(_ID_ENV))
    has_secret = bool(os.getenv(_SECRET_ENV))
    secrets_path = get_client_secrets_path()
    secrets_file_ok = False
    # Why the file cannot be used; None when it is usable.
    file_problem: Optional[str] = (
        f"client secrets file {secrets_path} does not exist"
    )

    if os.path.isfile(secrets_path):
        try:
            with open(secrets_path, "r") as f:
                data = json.load(f)
            if isinstance(data, dict) and ("web" in data or "installed" in data):
                secrets_file_ok = True
                file_problem = None
            else:
                file_problem = (
                    f"client secrets file {secrets_path} has no 'web' or 'installed' "
                    "section (re-download it from Google Cloud Console)"
                )
        except (OSError, ValueError) as exc:
            file_problem = (
                f"client secrets file {secrets_path} is unreadable or not valid JSON "
                f"({type(exc).__name__})"
            )

    # Env vars take precedence over the file (auth.oauth_config), so a broken
    # file only fails the check when the env vars do not cover for it.
    if has_id and has_secret:
        notes.append(f"OAuth client: {_ID_ENV} and {_SECRET_ENV} are set.")
        if file_problem and os.path.isfile(secrets_path):
            notes.append(f"Warning: {file_problem}; not used while the env vars are set.")
    elif secrets_file_ok:
        notes.append(f"OAuth client: client secrets file found at {secrets_path}.")
    else:
        if has_id:
            env_problem = f"env var {_SECRET_ENV} is not set ({_ID_ENV} is set)"
        elif has_secret:
            env_problem = f"env var {_ID_ENV} is not set ({_SECRET_ENV} is set)"
        else:
            env_problem = f"env vars {_ID_ENV} and {_SECRET_ENV} are not set"
        errors.append(
            f"Missing OAuth client credentials: {env_problem}, and {file_problem}. "
            "Fix either one (path override: GOOGLE_CLIENT_SECRET_PATH)."
        )

    creds_dir, source = _credentials_dir()
    if os.path.isdir(creds_dir):
        if not os.access(creds_dir, os.R_OK | os.W_OK):
            errors.append(
                f"Credentials directory {creds_dir} (from {source}) is not "
                "readable and writable by this user."
            )
        else:
            tokens = [n for n in os.listdir(creds_dir) if n.endswith(".json")]
            if tokens:
                notes.append(f"Stored tokens: {len(tokens)} file(s) in {creds_dir}.")
            else:
                notes.append(
                    f"No stored token files in {creds_dir}; they are created at "
                    "first authorization."
                )
    else:
        notes.append(
            f"Credentials directory {creds_dir} (from {source}) does not exist yet; "
            "it is created at first authorization."
        )
    return errors, notes


def run(argv: Optional[List[str]] = None) -> int:
    try:
        errors, notes = check_credentials()
    except Exception as exc:  # never a stack trace from a health check
        print(f"ERROR: health check failed unexpectedly: {type(exc).__name__}: {exc}")
        return 1
    for note in notes:
        print(f"  {note}")
    if errors:
        for err in errors:
            print(f"ERROR: {err}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(run())
