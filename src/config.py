"""Environment-driven settings.

Secrets and per-environment values come from .env / the deployment environment.
Non-secret fixed values are imported from constants.py as defaults.

WhatsApp variables default to "" so the app boots even when WhatsApp is not
configured — handlers read them lazily via get_settings() and error only when
actually invoked.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from .constants import CORS_ORIGINS as _DEFAULT_CORS_ORIGINS


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- SearchApi.io ---
    # No hardcoded fallback — a live API key doesn't belong in source/git
    # history. Must be set in .env; searchapi_repository already errors
    # gracefully (not a crash) if it's missing.
    SEARCHAPI_KEY: str = ""
    SEARCHAPI_TIMEOUT: int = 30

    # Timeout (seconds) for the lightweight og:title fetch used to recognise a
    # pasted product link. Kept short — it runs inline on every URL search and a
    # failure just falls through to slug extraction.
    LINK_TITLE_TIMEOUT: int = 5

    # --- WhatsApp (Meta Graph API) — all optional so the app boots unconfigured ---
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_VERIFY_TOKEN: str = "dealo_webhook_2026"

    # --- Caching / sessions (stateless, in-memory) ---
    SEARCH_CACHE_TTL_SECONDS: int = 86400  # 24h — protects the SearchApi budget
    WHATSAPP_SESSION_TTL_SECONDS: int = 600  # 10-min sliding TTL per phone

    # --- Cuelinks affiliate ---
    CUELINKS_CID: str = "297179"

    # --- This backend's own public URL, no trailing slash ---
    # Used to build /go redirect links (see api/routers/redirect.py) so
    # WhatsApp buttons point at our own domain instead of linksredirect.com
    # directly. Render URL in prod, ngrok URL for local WhatsApp testing.
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # --- CORS — comma-separated list of allowed origins ---
    CORS_ORIGINS: str = ",".join(_DEFAULT_CORS_ORIGINS)

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
