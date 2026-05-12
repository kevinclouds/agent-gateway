from dataclasses import dataclass
from enum import StrEnum


class PermissionKind(StrEnum):
    COMMAND = "command"
    FILE = "file"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PermissionStatus(StrEnum):
    PENDING = "pending"
    ALLOWED = "allowed"
    DENIED = "denied"


class DecisionType(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class CapabilityMode(StrEnum):
    MANUAL = "manual"
    AUTO = "auto"


@dataclass(frozen=True)
class PermissionRequest:
    request_id: str
    kind: PermissionKind
    target: str
    source: str
    risk_level: RiskLevel
    status: PermissionStatus
    created_at: str
    raw_context_ref: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", PermissionKind(self.kind))
        object.__setattr__(self, "risk_level", RiskLevel(self.risk_level))
        object.__setattr__(self, "status", PermissionStatus(self.status))


@dataclass(frozen=True)
class PermissionDecision:
    request_id: str
    decision: DecisionType
    decided_by: str
    decided_at: str
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision", DecisionType(self.decision))


@dataclass(frozen=True)
class PermissionCapability:
    kinds: tuple[PermissionKind, ...]
    modes: tuple[CapabilityMode, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kinds", tuple(PermissionKind(kind) for kind in self.kinds))
        object.__setattr__(self, "modes", tuple(CapabilityMode(mode) for mode in self.modes))
