"""Native Windows machine-JSON contracts for the YASB integration."""

__version__ = "0.1.0"

from .config import CodexConfig, ConfigError, LocalConfig, OpenCodeGoConfig
from .model import (
    DocumentView,
    ProviderKey,
    ProviderOutcome,
    ProviderSnapshotView,
    ProviderState,
    ProviderView,
    PublicProviderState,
    QuotaAvailability,
    QuotaMetricKind,
    QuotaQuantity,
    QuotaWindowKind,
    QuotaWindowView,
    SafeError,
    SafeErrorCode,
    SnapshotFreshness,
)
from .projection import project_bytes, project_document
from .coordinator import ProviderCoordinator, RuntimeCoordinator, coordinate
