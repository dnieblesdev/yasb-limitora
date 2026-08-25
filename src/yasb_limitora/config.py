"""Immutable, local-only configuration contracts for provider execution."""

from collections.abc import Mapping, MutableSet
from dataclasses import dataclass
import math
import ntpath
import re

from .model import ProviderKey


class ConfigError(ValueError):
    """Raised when local configuration is malformed or unsafe."""

DEFAULT_TIMEOUT_SECONDS = 7.0
MAX_CODEX_TIMEOUT_SECONDS = 120.0
MAX_OPENCODE_TIMEOUT_SECONDS = 10.0
DEFAULT_DEADLINE_SECONDS = 7.0
MIN_DEADLINE_SECONDS = 1.0
MAX_DEADLINE_SECONDS = 120.0
_INVALID_TIMEOUT = "invalid timeout_seconds"
_CREDENTIAL_KEY = re.compile(
    r"(?:auth.?cookie|cookie|token|password|secret|credential|api.?key|authorization)",
    re.IGNORECASE,
)


def _reject_credential_keys(value: object) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if isinstance(key, str) and _CREDENTIAL_KEY.search(key):
                raise ConfigError("credential-like configuration is not accepted")
            _reject_credential_keys(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _reject_credential_keys(nested)


def _reject_nested_provider_credentials(value: object) -> None:
    if isinstance(value, Mapping):
        for nested in value.values():
            if isinstance(nested, (Mapping, list, tuple)):
                _reject_credential_keys(nested)
    elif isinstance(value, (list, tuple)):
        _reject_credential_keys(value)


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ConfigError("provider configuration must be an object")
    return value

def _fields(value: Mapping[str, object], allowed: set[str]) -> None:
    if any(not isinstance(key, str) or key not in allowed for key in value):
        raise ConfigError("unsupported provider configuration field")

def _timeout(value: object, maximum: float) -> float:
    if isinstance(value, bool):
        raise ConfigError(_INVALID_TIMEOUT)
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ConfigError(_INVALID_TIMEOUT) from None
    if not math.isfinite(result) or not 0 < result <= maximum:
        raise ConfigError(_INVALID_TIMEOUT)
    return result


def _strict_timeout(value: object, maximum: float) -> float:
    if type(value) not in (int, float):
        raise ConfigError(_INVALID_TIMEOUT)
    return _timeout(value, maximum)


def _deadline(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError("invalid deadline_seconds")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ConfigError("invalid deadline_seconds") from None
    if not math.isfinite(result) or not MIN_DEADLINE_SECONDS <= result <= MAX_DEADLINE_SECONDS:
        raise ConfigError("invalid deadline_seconds")
    return result

def _runner(value: object, enabled: bool) -> str | None:
    if value is None:
        if enabled:
            raise ConfigError("enabled Codex requires an absolute runner")
        return None
    if not isinstance(value, str) or not value:
        raise ConfigError("Codex runner must be fully qualified")
    drive, tail = ntpath.splitdrive(value)
    drive_absolute = len(drive) == 2 and drive[1] == ":" and tail.startswith(("\\", "/"))
    unc_parts = value[2:].split("\\") if value.startswith("\\\\") else []
    unc_absolute = len(unc_parts) >= 2 and all(unc_parts[:2])
    if not (drive_absolute or unc_absolute):
        raise ConfigError("Codex runner must be fully qualified")
    return value

@dataclass(frozen=True, slots=True)
class CodexConfig:
    enabled: bool = False
    runner: str | None = None
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ConfigError("enabled must be a boolean")
        object.__setattr__(self, "runner", _runner(self.runner, self.enabled))
        object.__setattr__(self, "timeout_seconds", _timeout(self.timeout_seconds, MAX_CODEX_TIMEOUT_SECONDS))

    @classmethod
    def from_mapping(cls, value: object) -> "CodexConfig":
        fields = _mapping(value)
        _fields(fields, {"enabled", "runner", "timeout_seconds"})
        return cls(**fields)

    @classmethod
    def from_v2_mapping(cls, value: object) -> "CodexConfig":
        fields = _mapping(value)
        _fields(fields, {"enabled", "runner", "timeout_seconds"})
        if "timeout_seconds" in fields:
            _strict_timeout(fields["timeout_seconds"], MAX_CODEX_TIMEOUT_SECONDS)
        return cls(**fields)

    def __repr__(self) -> str:
        return f"CodexConfig(enabled={self.enabled!r}, runner=<redacted>, timeout_seconds={self.timeout_seconds!r})"

@dataclass(frozen=True, slots=True)
class OpenCodeGoConfig:
    enabled: bool = False
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ConfigError("enabled must be a boolean")
        object.__setattr__(self, "timeout_seconds", _timeout(self.timeout_seconds, MAX_OPENCODE_TIMEOUT_SECONDS))

    @classmethod
    def from_mapping(cls, value: object) -> "OpenCodeGoConfig":
        fields = _mapping(value)
        _fields(fields, {"enabled", "timeout_seconds"})
        return cls(**fields)

    @classmethod
    def from_v2_mapping(cls, value: object) -> "OpenCodeGoConfig":
        fields = _mapping(value)
        _fields(fields, {"enabled", "timeout_seconds"})
        if "timeout_seconds" in fields:
            _strict_timeout(fields["timeout_seconds"], MAX_OPENCODE_TIMEOUT_SECONDS)
        return cls(**fields)

    def __repr__(self) -> str:
        return f"OpenCodeGoConfig(enabled={self.enabled!r}, timeout_seconds={self.timeout_seconds!r})"

@dataclass(frozen=True, slots=True)
class LocalConfig:
    codex: CodexConfig = CodexConfig()
    opencode_go: OpenCodeGoConfig = OpenCodeGoConfig()
    deadline_seconds: float = DEFAULT_DEADLINE_SECONDS

    def __post_init__(self) -> None:
        if not isinstance(self.codex, CodexConfig) or not isinstance(self.opencode_go, OpenCodeGoConfig):
            raise ConfigError("provider configuration has an invalid shape")
        object.__setattr__(self, "deadline_seconds", _deadline(self.deadline_seconds))

    @classmethod
    def from_mapping(cls, value: object) -> "LocalConfig":
        _reject_credential_keys(value)
        fields = _mapping(value)
        _fields(fields, {"codex", "opencode_go"})
        return cls(
            codex=CodexConfig.from_mapping(fields.get("codex", {})),
            opencode_go=OpenCodeGoConfig.from_mapping(fields.get("opencode_go", {})),
        )

    @classmethod
    def from_v2_mapping(
        cls,
        value: object,
        provider_errors: MutableSet[ProviderKey] | None = None,
    ) -> "LocalConfig":
        fields = _mapping(value)
        _fields(fields, {"deadline_seconds", "codex", "opencode_go"})
        for key, nested in fields.items():
            if key in {"codex", "opencode_go"}:
                _reject_nested_provider_credentials(nested)
            else:
                _reject_credential_keys(nested)
        if any(isinstance(key, str) and _CREDENTIAL_KEY.search(key) for key in fields):
            raise ConfigError("credential-like configuration is not accepted")

        try:
            codex = CodexConfig.from_v2_mapping(fields.get("codex", {}))
        except ConfigError:
            if provider_errors is None:
                raise
            provider_errors.add(ProviderKey.CODEX)
            codex = CodexConfig()

        try:
            opencode_go = OpenCodeGoConfig.from_v2_mapping(fields.get("opencode_go", {}))
        except ConfigError:
            if provider_errors is None:
                raise
            provider_errors.add(ProviderKey.OPENCODE_GO)
            opencode_go = OpenCodeGoConfig()

        return cls(
            codex=codex,
            opencode_go=opencode_go,
            deadline_seconds=fields.get("deadline_seconds", DEFAULT_DEADLINE_SECONDS),
        )

    def __repr__(self) -> str:
        return "LocalConfig(codex=<redacted>, opencode_go=<redacted>)"
