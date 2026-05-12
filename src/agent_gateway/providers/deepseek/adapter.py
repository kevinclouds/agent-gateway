from agent_gateway.canonical.models import CanonicalTurn


class DeepSeekAdapter:
    def __init__(self, default_model: str) -> None:
        self._default_model = default_model

    def build_request(self, turn: CanonicalTurn) -> dict[str, object]:
        messages = []
        for item in turn.input_items:
            messages.append(
                {
                    "role": str(item["role"]),
                    "content": str(item["content"]),
                }
            )
        return {
            "model": self._default_model,
            "messages": messages,
            "stream": True,
        }
