from agent_gateway.canonical.events import CanonicalStreamEvent


class DeepSeekRectifier:
    def __init__(self) -> None:
        self._started_messages: set[tuple[str, str]] = set()

    def rectify(
        self,
        chunk: dict[str, object],
        *,
        response_id: str,
        message_id: str,
    ) -> list[CanonicalStreamEvent]:
        delta = chunk["choices"][0]["delta"]
        events: list[CanonicalStreamEvent] = []
        if "content" in delta:
            message_key = (response_id, message_id)
            if message_key not in self._started_messages:
                events.append(
                    CanonicalStreamEvent(
                        type="message.started",
                        data={
                            "response_id": response_id,
                            "message_id": message_id,
                            "role": "assistant",
                        },
                    )
                )
                self._started_messages.add(message_key)
            events.append(
                CanonicalStreamEvent(
                    type="content.delta",
                    data={
                        "response_id": response_id,
                        "message_id": message_id,
                        "text": str(delta["content"]),
                    },
                )
            )
        return events
