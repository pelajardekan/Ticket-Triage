"""Central configuration, read once from environment / app settings."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _bool(value: str | None, default: bool = False) -> bool:
    raw = _clean(value).lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    # ---- Storage -------------------------------------------------------
    cosmos_endpoint: str = field(default_factory=lambda: _clean(os.environ.get("COSMOS_ENDPOINT")))
    cosmos_key: str = field(default_factory=lambda: _clean(os.environ.get("COSMOS_KEY")))
    cosmos_database: str = field(default_factory=lambda: _clean(os.environ.get("COSMOS_DATABASE")) or "tickettriage")
    cosmos_container: str = field(default_factory=lambda: _clean(os.environ.get("COSMOS_CONTAINER")) or "tickets")

    # ---- Azure AI Language --------------------------------------------
    language_endpoint: str = field(default_factory=lambda: _clean(os.environ.get("LANGUAGE_ENDPOINT")).rstrip("/"))
    language_key: str = field(default_factory=lambda: _clean(os.environ.get("LANGUAGE_KEY")))
    language_api_version: str = field(
        default_factory=lambda: _clean(os.environ.get("LANGUAGE_API_VERSION")) or "2024-11-01"
    )
    # Custom Text Classification (optional, bonus path)
    ctc_project: str = field(default_factory=lambda: _clean(os.environ.get("LANGUAGE_CTC_PROJECT")))
    ctc_deployment: str = field(default_factory=lambda: _clean(os.environ.get("LANGUAGE_CTC_DEPLOYMENT")))
    ctc_api_version: str = field(
        default_factory=lambda: _clean(os.environ.get("LANGUAGE_CTC_API_VERSION")) or "2023-04-01"
    )
    ctc_min_confidence: float = field(
        default_factory=lambda: float(_clean(os.environ.get("LANGUAGE_CTC_MIN_CONFIDENCE")) or "0.55")
    )

    # ---- Behaviour -----------------------------------------------------
    language_timeout_seconds: float = field(
        default_factory=lambda: float(_clean(os.environ.get("LANGUAGE_TIMEOUT_SECONDS")) or "6")
    )
    admin_api_key: str = field(default_factory=lambda: _clean(os.environ.get("ADMIN_API_KEY")))
    allow_anonymous_admin: bool = field(
        default_factory=lambda: _bool(os.environ.get("ALLOW_ANONYMOUS_ADMIN"), default=True)
    )
    max_page_size: int = field(default_factory=lambda: int(_clean(os.environ.get("MAX_PAGE_SIZE")) or "100"))

    # ---- Derived -------------------------------------------------------
    @property
    def cosmos_configured(self) -> bool:
        return bool(self.cosmos_endpoint and self.cosmos_key)

    @property
    def language_configured(self) -> bool:
        return bool(self.language_endpoint and self.language_key)

    @property
    def ctc_configured(self) -> bool:
        return bool(self.language_configured and self.ctc_project and self.ctc_deployment)

    def storage_mode(self) -> str:
        return "cosmos" if self.cosmos_configured else "in-memory"

    def classifier_chain(self) -> List[str]:
        chain: List[str] = []
        if self.ctc_configured:
            chain.append("azure-ai-language-custom")
        if self.language_configured:
            chain.append("azure-ai-language-keyphrase")
        chain.append("keyword-rules")
        return chain


_settings: Settings | None = None


def get_settings(refresh: bool = False) -> Settings:
    """Cached settings accessor. Pass refresh=True in tests."""
    global _settings
    if _settings is None or refresh:
        _settings = Settings()
    return _settings
