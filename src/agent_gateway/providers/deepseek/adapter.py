from agent_gateway.canonical.models import CanonicalTurn


class DeepSeekAdapter:
    def __init__(self, default_model: str) -> None:
        self._default_model = default_model

    def build_request(self, turn: CanonicalTurn) -> dict[str, object]:
        messages = []
        for item in turn.input_items:
            item_type = str(item.get("type", "message"))
            if item_type == "message":
                messages.append(
                    {
                        "role": str(item["role"]),
                        "content": str(item["content"]),
                    }
                )
                continue
            if item_type == "function_call":
                messages.append(
                    {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": str(item["call_id"]),
                                "type": "function",
                                "function": {
                                    "name": str(item["name"]),
                                    "arguments": str(item.get("arguments", "")),
                                },
                            }
                        ],
                    }
                )
                continue
            if item_type == "function_call_output":
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(item["call_id"]),
                        "content": str(item.get("output", "")),
                    }
                )

        payload: dict[str, object] = {
            "model": self._default_model,
            "messages": messages,
            "stream": True,
        }
        if turn.tools:
            payload["tools"] = turn.tools
        if turn.tool_choice is not None:
            payload["tool_choice"] = turn.tool_choice
        return payload
