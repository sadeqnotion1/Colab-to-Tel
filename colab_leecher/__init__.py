# ================================================================
# FILE: colab_leecher/__init__.py
# ================================================================

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

try:
    from uvloop import install as uvloop_install
except ImportError:
    uvloop_install = None

from pyrogram.client import Client

from .utility.variables import BOT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)


class ConfigError(RuntimeError):
    """Raised when runtime configuration is missing or invalid."""


class _UnconfiguredBotClient:
    """Decorator-safe placeholder used when credentials are unavailable."""

    @staticmethod
    def passthrough_decorator(*_args: Any, **_kwargs: Any):
        def decorator(func):
            return func

        return decorator


class _LazyBotClient:
    """Proxy that initializes the real Pyrogram client on first use."""

    def __bool__(self) -> bool:
        return is_runtime_configured()

    def _client(self) -> Client:
        return _get_or_create_client()

    def on_message(self, *args: Any, **kwargs: Any):
        try:
            return self._client().on_message(*args, **kwargs)
        except ConfigError:
            return _UnconfiguredBotClient.passthrough_decorator(*args, **kwargs)

    def on_callback_query(self, *args: Any, **kwargs: Any):
        try:
            return self._client().on_callback_query(*args, **kwargs)
        except ConfigError:
            return _UnconfiguredBotClient.passthrough_decorator(*args, **kwargs)

    def on_edited_message(self, *args: Any, **kwargs: Any):
        try:
            return self._client().on_edited_message(*args, **kwargs)
        except ConfigError:
            return _UnconfiguredBotClient.passthrough_decorator(*args, **kwargs)

    def run(self, *args: Any, **kwargs: Any):
        return self._client().run(*args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self._client(), name)


_repo_root = Path(__file__).resolve().parent.parent
credentials_path = str(_repo_root / "credentials.json")
credentials: dict[str, Any] = {}
_config_error: str | None = None
_runtime_initialized = False
_uvloop_initialized = False
_client_instance: Client | None = None

# Required runtime fields expected by existing modules.
API_ID: int | None = None
API_HASH: str | None = None
BOT_TOKEN: str | None = None
OWNER: int | None = None
DUMP_ID: int | None = None

colab_bot = _LazyBotClient()


def _read_credentials(path: str) -> tuple[dict[str, Any], str | None]:
    try:
        with open(path, "r", encoding="utf-8") as file_handle:
            return json.load(file_handle), None
    except FileNotFoundError:
        return {}, f"Credentials file not found at {path}."
    except json.JSONDecodeError as exc:
        return {}, f"Invalid credentials JSON in {path}: {exc}"
    except Exception as exc:  # pragma: no cover - defensive path
        return {}, f"Unexpected error loading credentials from {path}: {exc}"


def _apply_optional_settings(source: dict[str, Any]) -> None:
    BOT.Setting.nzb_cf_clearance = source.get("NZBCLOUD_CF_CLEARANCE", "")
    BOT.Setting.bitso_identity_cookie = source.get("BITSO_IDENTITY_COOKIE", "")
    BOT.Setting.bitso_phpsessid_cookie = source.get("BITSO_PHPSESSID_COOKIE", "")
    BOT.Setting.instagram_username = source.get("INSTAGRAM_USERNAME", "")
    BOT.Setting.instagram_password = source.get("INSTAGRAM_PASSWORD", "")
    BOT.Setting.instagram_sessionid = source.get("INSTAGRAM_SESSIONID", "")
    BOT.Setting.instagram_cookies_file = source.get("INSTAGRAM_COOKIES_FILE", "")
    BOT.Setting.terabox_cookie = source.get("TERABOX_COOKIE", "")
    BOT.Setting.nzb_providers = source.get("NZB_PROVIDERS", {}) or {}
    BOT.Setting.nzb_active_provider = source.get("NZB_DEFAULT_PROVIDER", "")


def _ensure_event_loop() -> None:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("Event loop is closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)


def _initialize_runtime() -> None:
    global credentials, API_ID, API_HASH, BOT_TOKEN, OWNER, DUMP_ID, _config_error, _runtime_initialized
    if _runtime_initialized:
        return

    credentials, read_error = _read_credentials(credentials_path)
    if read_error:
        _config_error = read_error
        log.warning(read_error)
        _apply_optional_settings({})
        _runtime_initialized = True
        return

    API_ID = credentials.get("API_ID")
    API_HASH = credentials.get("API_HASH")
    BOT_TOKEN = credentials.get("BOT_TOKEN")
    
    # Explicitly cast OWNER and DUMP_ID to int for reliable authorization checks
    try:
        OWNER = int(credentials.get("USER_ID")) if credentials.get("USER_ID") else None
    except (ValueError, TypeError):
        OWNER = credentials.get("USER_ID")
        
    try:
        DUMP_ID = int(credentials.get("DUMP_ID")) if credentials.get("DUMP_ID") else None
    except (ValueError, TypeError):
        DUMP_ID = credentials.get("DUMP_ID")

    required = {
        "API_ID": API_ID,
        "API_HASH": API_HASH,
        "BOT_TOKEN": BOT_TOKEN,
        "USER_ID": OWNER,
        "DUMP_ID": DUMP_ID,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        _config_error = f"Missing required credentials: {', '.join(missing)}"
        log.warning(_config_error)
        _apply_optional_settings(credentials)
        _runtime_initialized = True
        return

    _apply_optional_settings(credentials)
    _config_error = None
    _runtime_initialized = True


def _get_or_create_client() -> Client:
    global _client_instance, _uvloop_initialized
    ensure_runtime_config()
    if _client_instance is not None:
        return _client_instance

    if uvloop_install and not _uvloop_initialized:
        try:
            uvloop_install()
            log.info("uvloop installed.")
        except Exception as exc:
            log.warning(f"Could not install uvloop: {exc}")
        finally:
            _uvloop_initialized = True
    elif not uvloop_install and not _uvloop_initialized:
        log.info("uvloop not available on this platform; using asyncio default loop.")
        _uvloop_initialized = True

    _ensure_event_loop()

    try:
        _client_instance = Client(
            "colab_bot",
            api_id=int(API_ID),
            api_hash=str(API_HASH),
            bot_token=str(BOT_TOKEN),
            workers=16,
        )
        log.info("Pyrogram client initialized.")
        return _client_instance
    except Exception as exc:
        raise ConfigError(f"Failed to initialize Pyrogram client: {exc}") from exc


def ensure_runtime_config() -> None:
    _initialize_runtime()
    if _config_error:
        raise ConfigError(_config_error)


def is_runtime_configured() -> bool:
    _initialize_runtime()
    return _config_error is None


_initialize_runtime()

__all__ = [
    "API_HASH",
    "API_ID",
    "BOT_TOKEN",
    "ConfigError",
    "DUMP_ID",
    "OWNER",
    "colab_bot",
    "credentials",
    "credentials_path",
    "ensure_runtime_config",
    "is_runtime_configured",
]
