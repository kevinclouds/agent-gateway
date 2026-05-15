from agent_gateway.canonical.events import CanonicalStreamEvent


class DeepSeekRectifier:
    def __init__(self) -> None:
        self._started_messages: set[tuple[str, str]] = set()
        self._tool_call_state: dict[tuple[str, str, int], dict[str, object]] = {}
        self._reasoning_content: str = ""

    def rectify(
        self,
        chunk: dict[str, object],
        *,
        response_id: str,
        message_id: str,
    ) -> list[CanonicalStreamEvent]:
        choice = chunk["choices"][0]
        delta = choice.get("delta", {})
        events: list[CanonicalStreamEvent] = []
        if delta.get("reasoning_content"):
            self._reasoning_content += str(delta["reasoning_content"])
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
        raw_tool_calls = delta.get("tool_calls", [])
        for raw_tool_call in raw_tool_calls:
            tool_call = dict(raw_tool_call)
            index = int(tool_call.get("index", 0))
            key = (response_id, message_id, index)
            state = self._tool_call_state.setdefault(
                key,
                {
                    "call_id": str(tool_call.get("id") or f"{response_id}-{message_id}-{index}"),
                    "name": "",
                    "completed": False,
                    "started": False,
                },
            )
            if tool_call.get("id"):
                state["call_id"] = str(tool_call["id"])
            function = tool_call.get("function", {})
            if isinstance(function, dict) and function.get("name"):
                state["name"] = str(function["name"])
            if not state["started"]:
                events.append(
                    CanonicalStreamEvent(
                        type="tool_call.started",
                        data={
                            "response_id": response_id,
                            "call_id": str(state["call_id"]),
                            "name": str(state["name"]),
                        },
                    )
                )
                state["started"] = True
            if isinstance(function, dict) and function.get("arguments"):
                events.append(
                    CanonicalStreamEvent(
                        type="tool_call.arguments.delta",
                        data={
                            "response_id": response_id,
                            "call_id": str(state["call_id"]),
                            "text": str(function["arguments"]),
                        },
                    )
                )

        if choice.get("finish_reason") == "tool_calls":
            for key, state in self._tool_call_state.items():
                if key[:2] != (response_id, message_id):
                    continue
                if state["started"] and not state["completed"]:
                    event_data: dict[str, object] = {
                        "response_id": response_id,
                        "call_id": str(state["call_id"]),
                    }
                    if self._reasoning_content:
                        event_data["reasoning_content"] = self._reasoning_content
                    events.append(
                        CanonicalStreamEvent(type="tool_call.completed", data=event_data)
                    )
                    state["completed"] = True
        return events
