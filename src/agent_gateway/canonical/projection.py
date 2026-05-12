from copy import deepcopy

from agent_gateway.canonical.events import CanonicalStreamEvent
from agent_gateway.canonical.models import CanonicalBlock, CanonicalMessage, CanonicalResponse


class ResponseProjection:
    def __init__(self) -> None:
        self._response = CanonicalResponse(response_id="pending")
        self._message_index: dict[str, CanonicalMessage] = {}

    def apply(self, event: CanonicalStreamEvent) -> None:
        if event.type == "response.started":
            self._response.response_id = str(event.data["response_id"])
            self._response.status = "in_progress"
            return

        if event.type == "message.started":
            message = CanonicalMessage(
                message_id=str(event.data["message_id"]),
                role=str(event.data["role"]),
            )
            self._message_index[message.message_id] = message
            self._response.messages.append(message)
            return

        if event.type == "content.delta":
            message = self._message_index[str(event.data["message_id"])]
            text = str(event.data["text"])
            if message.segments and message.segments[-1]["type"] == "text":
                message.segments[-1]["text"] += text
            else:
                message.segments.append({"type": "text", "text": text})
            return

        if event.type == "permission.blocked":
            self._response.response_id = str(event.data["response_id"])
            self._response.block = CanonicalBlock(
                kind="blocked_by_permission",
                permission_request_id=str(event.data["permission_request_id"]),
                permission_kind=str(event.data["permission_kind"]),
            )
            self._response.status = "blocked"
            return

        if event.type == "response.completed":
            self._response.status = "completed"
            return

    def snapshot(self) -> CanonicalResponse:
        return deepcopy(self._response)
