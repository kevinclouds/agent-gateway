import pytest
from dataclasses import FrozenInstanceError

from agent_gateway.host_control.models import (
    CapabilityMode,
    DecisionType,
    PermissionCapability,
    PermissionDecision,
    PermissionKind,
    PermissionRequest,
    PermissionStatus,
    RiskLevel,
)


def test_permission_request_preserves_context() -> None:
    request = PermissionRequest(
        request_id="p1",
        kind="command",
        target="pytest -q",
        source="codex",
        risk_level="high",
        status="pending",
        created_at="2026-05-12T10:00:00Z",
        raw_context_ref="log://req-1",
    )

    assert request.kind is PermissionKind.COMMAND
    assert request.risk_level is RiskLevel.HIGH
    assert request.status is PermissionStatus.PENDING
    assert request.raw_context_ref == "log://req-1"


def test_permission_decision_links_to_request() -> None:
    decision = PermissionDecision(
        request_id="p1",
        decision="allow",
        decided_by="user",
        decided_at="2026-05-12T10:01:00Z",
        reason="approved for test",
    )

    capability = PermissionCapability(kinds=["command", "file"], modes=["manual"])

    assert decision.request_id == "p1"
    assert decision.decision is DecisionType.ALLOW
    assert capability.kinds == (PermissionKind.COMMAND, PermissionKind.FILE)
    assert capability.modes == (CapabilityMode.MANUAL,)


def test_permission_request_rejects_invalid_state_values() -> None:
    with pytest.raises(ValueError):
        PermissionRequest(
            request_id="p1",
            kind="invalid",
            target="pytest -q",
            source="codex",
            risk_level="high",
            status="pending",
            created_at="2026-05-12T10:00:00Z",
            raw_context_ref="log://req-1",
        )

    with pytest.raises(ValueError):
        PermissionRequest(
            request_id="p1",
            kind="command",
            target="pytest -q",
            source="codex",
            risk_level="critical",
            status="pending",
            created_at="2026-05-12T10:00:00Z",
            raw_context_ref="log://req-1",
        )

    with pytest.raises(ValueError):
        PermissionRequest(
            request_id="p1",
            kind="command",
            target="pytest -q",
            source="codex",
            risk_level="high",
            status="waiting",
            created_at="2026-05-12T10:00:00Z",
            raw_context_ref="log://req-1",
        )


def test_permission_decision_and_capability_reject_invalid_values() -> None:
    with pytest.raises(ValueError):
        PermissionDecision(
            request_id="p1",
            decision="maybe",
            decided_by="user",
            decided_at="2026-05-12T10:01:00Z",
            reason="approved for test",
        )

    with pytest.raises(ValueError):
        PermissionCapability(kinds=["network"], modes=["manual"])

    with pytest.raises(ValueError):
        PermissionCapability(kinds=["command"], modes=["guided"])


def test_permission_models_are_immutable() -> None:
    request = PermissionRequest(
        request_id="p1",
        kind="command",
        target="pytest -q",
        source="codex",
        risk_level="high",
        status="pending",
        created_at="2026-05-12T10:00:00Z",
        raw_context_ref="log://req-1",
    )
    capability = PermissionCapability(kinds=["command"], modes=["manual"])

    with pytest.raises(FrozenInstanceError):
        request.status = PermissionStatus.ALLOWED

    with pytest.raises(AttributeError):
        capability.modes += (CapabilityMode.AUTO,)
