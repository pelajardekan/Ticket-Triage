"""Shared pytest fixtures. Puts the function app root on sys.path."""

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


@pytest.fixture()
def seeds():
    return json.loads((ROOT / "data" / "seed_tickets.json").read_text(encoding="utf-8"))


@pytest.fixture()
def clean_env(monkeypatch):
    """Guarantee no Azure configuration leaks in from the developer's shell."""
    for name in [
        "COSMOS_ENDPOINT", "COSMOS_KEY", "COSMOS_DATABASE", "COSMOS_CONTAINER",
        "LANGUAGE_ENDPOINT", "LANGUAGE_KEY", "LANGUAGE_CTC_PROJECT",
        "LANGUAGE_CTC_DEPLOYMENT", "ADMIN_API_KEY", "ALLOW_ANONYMOUS_ADMIN",
    ]:
        monkeypatch.delenv(name, raising=False)

    from shared.config import get_settings
    from shared.repository import get_repository

    settings = get_settings(refresh=True)
    get_repository(settings, refresh=True)
    return settings
