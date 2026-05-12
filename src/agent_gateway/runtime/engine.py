from agent_gateway.canonical.events import CanonicalStreamEvent
from agent_gateway.canonical.models import CanonicalResponse
from agent_gateway.canonical.projection import ResponseProjection


class RuntimeEngine:
    def consume(self, events: list[CanonicalStreamEvent]) -> CanonicalResponse:
        projection = ResponseProjection()
        for event in events:
            projection.apply(event)
        return projection.snapshot()
