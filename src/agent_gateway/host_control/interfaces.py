from typing import Protocol

from agent_gateway.host_control.models import PermissionDecision, PermissionRequest


class PermissionHandler(Protocol):
    def normalize(self, raw_signal: dict[str, object]) -> PermissionRequest: ...


class PolicyEvaluator(Protocol):
    def evaluate(self, request: PermissionRequest) -> PermissionDecision | None: ...
