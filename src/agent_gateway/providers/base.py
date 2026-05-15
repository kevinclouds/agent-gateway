from abc import ABC, abstractmethod

from agent_gateway.canonical.models import CanonicalTurn


class BaseProviderAdapter(ABC):
    @abstractmethod
    def build_request(
        self,
        turn: CanonicalTurn,
        reasoning_store: dict[str, str] | None = None,
    ) -> dict[str, object]:
        ...
