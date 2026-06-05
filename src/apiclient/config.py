"""TOML profile config with environment-variable overrides."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

from apiclient.exceptions import ConfigError

DEFAULT_CONFIG_PATH = Path.home() / ".apiclient.toml"
DEFAULT_PROFILE_NAME = "default"


@dataclass(slots=True)
class ClientConfig:
    base_url: str | None = None
    transport: str = "raw"
    timeout: float | None = None
    connect_timeout: float | None = None
    read_timeout: float | None = None
    retries: int = 0
    retry_non_idempotent: bool = False
    backoff_factor: float | None = None
    retry_jitter: float | None = None
    retry_max_backoff: float | None = None
    max_redirects: int | None = None
    preserve_auth_across_hosts: bool = False
    keep_alive: bool = False
    pool_size: int = 4
    pool_idle: float = 30.0
    no_follow_redirects: bool = False
    fail: bool = False
    retry_statuses: str | None = None
    redirect_statuses: str | None = None
    output: str = "pretty"
    bearer_token: str | None = None
    api_key_header: str | None = None
    api_key_query: str | None = None


def load_config(profile: str | None = None, path: str | Path | None = None) -> ClientConfig:
    config = ClientConfig()
    config_path = _resolve_path(path)
    data: dict = {}
    if config_path.exists():
        try:
            data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ConfigError(f"Could not read config file {config_path}: {exc}") from exc
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"Invalid TOML config {config_path}: {exc}") from exc

    profiles = data.get("profiles", {})
    if (
        profile
        and profile not in profiles
        and profile != DEFAULT_PROFILE_NAME
    ):
        available = ", ".join(sorted(profiles)) if profiles else "(none)"
        raise ConfigError(
            f"Unknown profile {profile!r}; available profiles: {available}"
        )
    default_data = profiles.get(DEFAULT_PROFILE_NAME, {})
    _apply_mapping(config, default_data)
    if profile and profile != DEFAULT_PROFILE_NAME:
        profile_data = profiles.get(profile, {})
        _apply_mapping(config, profile_data)
    _apply_env(config)
    return config


def list_profiles(path: str | Path | None = None) -> list[str]:
    data = _read_data(_resolve_path(path))
    names = set(data.get("profiles", {}))
    names.add(DEFAULT_PROFILE_NAME)
    return sorted(names)


def parse_status_csv(value: str | None) -> frozenset[int] | None:
    """Parse a comma-separated list of HTTP status codes from config TOML."""

    if not value or not value.strip():
        return None
    codes: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            codes.add(int(part))
        except ValueError as exc:
            raise ConfigError(f"Invalid HTTP status code in list: {part!r}") from exc
    return frozenset(codes) if codes else None


def get_config_value(key: str, path: str | Path | None = None) -> str | None:
    data = _read_data(_resolve_path(path))
    profile, setting = _split_key(key)
    profile_data = data.get("profiles", {}).get(profile, {})
    value = profile_data.get(setting)
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def set_config_value(key: str, value: str, path: str | Path | None = None) -> Path:
    """Write a simple profile value, e.g. dev.base_url http://localhost:8000."""

    config_path = _resolve_path(path)
    profile, setting = _split_key(key)
    coerced = _coerce_value(value)
    _validate_profile_setting(setting, coerced)
    data = _read_data(config_path)
    data.setdefault("profiles", {}).setdefault(profile, {})[setting] = coerced
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(_dump_toml(data), encoding="utf-8")
    return config_path


def unset_config_value(key: str, path: str | Path | None = None) -> Path:
    config_path = _resolve_path(path)
    profile, setting = _split_key(key)
    data = _read_data(config_path)
    profile_data = data.get("profiles", {}).get(profile, {})
    profile_data.pop(setting, None)
    if not profile_data:
        data.get("profiles", {}).pop(profile, None)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(_dump_toml(data), encoding="utf-8")
    return config_path


def _resolve_path(path: str | Path | None) -> Path:
    return Path(path or os.getenv("APICLIENT_CONFIG") or DEFAULT_CONFIG_PATH)


def _split_key(key: str) -> tuple[str, str]:
    if "." not in key:
        raise ConfigError("Config key must look like profile.setting, for example dev.base_url")
    profile, setting = key.split(".", 1)
    profile = profile.strip()
    setting = setting.strip()
    if not profile or not setting:
        raise ConfigError("Config key parts cannot be empty")
    return profile, setting


def _read_data(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    try:
        return tomllib.loads(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"Could not read config file {config_path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML config {config_path}: {exc}") from exc


def _validate_profile_setting(setting: str, value: object) -> None:
    """Reject unknown keys or unsupported value types before writing TOML."""

    known = {f.name for f in fields(ClientConfig)}
    if setting not in known:
        raise ConfigError(
            f"Unknown config key {setting!r}; allowed keys: {sorted(known)}"
        )
    _render_toml_value(value)


def _apply_mapping(config: ClientConfig, values: dict) -> None:
    known = {f.name for f in fields(config)}
    for key, value in values.items():
        if key not in known:
            raise ConfigError(
                f"Unknown config key {key!r}; allowed keys: {sorted(known)}"
            )
        setattr(config, key, value)


def _apply_env(config: ClientConfig) -> None:
    env_map = {
        "APICLIENT_BASE_URL": "base_url",
        "APICLIENT_TRANSPORT": "transport",
        "APICLIENT_TIMEOUT": "timeout",
        "APICLIENT_CONNECT_TIMEOUT": "connect_timeout",
        "APICLIENT_READ_TIMEOUT": "read_timeout",
        "APICLIENT_RETRIES": "retries",
        "APICLIENT_RETRY_NON_IDEMPOTENT": "retry_non_idempotent",
        "APICLIENT_BACKOFF_FACTOR": "backoff_factor",
        "APICLIENT_RETRY_JITTER": "retry_jitter",
        "APICLIENT_RETRY_MAX_BACKOFF": "retry_max_backoff",
        "APICLIENT_MAX_REDIRECTS": "max_redirects",
        "APICLIENT_PRESERVE_AUTH_ACROSS_HOSTS": "preserve_auth_across_hosts",
        "APICLIENT_KEEP_ALIVE": "keep_alive",
        "APICLIENT_POOL_SIZE": "pool_size",
        "APICLIENT_POOL_IDLE": "pool_idle",
        "APICLIENT_NO_FOLLOW_REDIRECTS": "no_follow_redirects",
        "APICLIENT_FAIL": "fail",
        "APICLIENT_RETRY_STATUSES": "retry_statuses",
        "APICLIENT_REDIRECT_STATUSES": "redirect_statuses",
        "APICLIENT_OUTPUT": "output",
        "APICLIENT_BEARER_TOKEN": "bearer_token",
        "APICLIENT_API_KEY_HEADER": "api_key_header",
        "APICLIENT_API_KEY_QUERY": "api_key_query",
    }
    for env_name, attr in env_map.items():
        if env_name in os.environ:
            setattr(config, attr, _coerce_value(os.environ[env_name]))


def _coerce_value(value: str) -> str | int | float | bool:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _dump_toml(data: dict) -> str:
    """Emit a small subset of TOML.

    Preserves both `[profiles.*]` tables and any other top-level table that was
    already in the file. Root-level scalar key/value pairs are written *before*
    any `[table]` header so the round-trip keeps them at the document root
    instead of getting absorbed into the last emitted table.
    """

    lines: list[str] = []

    # Phase 1: root-level scalars and arrays.
    root_scalars = sorted(k for k, v in data.items() if not isinstance(v, dict))
    for key in root_scalars:
        lines.append(f"{key} = {_render_toml_value(data[key])}")
    if root_scalars:
        lines.append("")

    # Phase 2: profiles tables, then other tables.
    profiles = data.get("profiles", {})
    for profile_name in sorted(profiles):
        lines.append(f"[profiles.{profile_name}]")
        for key, value in sorted(profiles[profile_name].items()):
            lines.append(f"{key} = {_render_toml_value(value)}")
        lines.append("")

    other_tables = sorted(
        k for k, v in data.items() if k != "profiles" and isinstance(v, dict)
    )
    for table_name in other_tables:
        lines.append(f"[{table_name}]")
        for key, value in sorted(data[table_name].items()):
            lines.append(f"{key} = {_render_toml_value(value)}")
        lines.append("")

    return "\n".join(lines)


def _render_toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace("\"", "\\\"")
        return f"\"{escaped}\""
    raise ConfigError(
        f"Unsupported config value type {type(value).__name__}; only scalars are allowed"
    )
