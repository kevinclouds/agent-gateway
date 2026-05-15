from agent_gateway.canonical.models import CanonicalTurn
from agent_gateway.providers.base import BaseProviderAdapter


def _flatten_content(content: object) -> str:
    if isinstance(content, str):
        return content
    return ""


class DeepSeekBaseAdapter(BaseProviderAdapter):
    @staticmethod
    def _to_chat_tool(tool: dict) -> dict | None:
        if not isinstance(tool, dict) or tool.get("type") != "function":
            return None
        fn = tool.get("function") if isinstance(tool.get("function"), dict) else tool
        name = fn.get("name")
        if not name:
            return None
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters") or {"type": "object", "properties": {}},
            },
        }

    @staticmethod
    def _to_chat_tool_choice(tool_choice: object) -> object:
        if tool_choice in (None, "auto"):
            return "auto"
        if tool_choice in {"none", "required"}:
            return tool_choice
        if isinstance(tool_choice, dict) and tool_choice.get("type") == "function":
            name = tool_choice.get("name") or (tool_choice.get("function") or {}).get("name")
            if name:
                return {"type": "function", "function": {"name": name}}
        return None

    def _build_messages(
        self,
        turn: CanonicalTurn,
        reasoning_store: dict[str, str] | None,
    ) -> list[dict[str, object]]:
        messages: list[dict[str, object]] = []
        items = list(turn.input_items)
        i = 0
        while i < len(items):
            item = items[i]
            item_type = str(item.get("type", "message"))

            if item_type == "message":
                role = str(item["role"])
                if role == "developer":
                    role = "system"
                messages.append({"role": role, "content": str(item["content"])})
                i += 1

            elif item_type == "function_call":
                # Consecutive function_call items belong to the same assistant turn.
                # Group them into one message so DeepSeek receives a single assistant
                # message with all tool_calls, followed by the tool results.
                tool_calls: list[dict[str, object]] = []
                reasoning: str | None = None
                while i < len(items) and str(items[i].get("type", "message")) == "function_call":
                    fc = items[i]
                    call_id = str(fc["call_id"])
                    tool_calls.append(
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": str(fc["name"]),
                                "arguments": str(fc.get("arguments", "")),
                            },
                        }
                    )
                    if reasoning is None and reasoning_store and call_id in reasoning_store:
                        reasoning = reasoning_store[call_id]
                    i += 1
                assistant_msg: dict[str, object] = {"role": "assistant", "tool_calls": tool_calls}
                if reasoning is not None:
                    assistant_msg["reasoning_content"] = reasoning
                messages.append(assistant_msg)

            elif item_type == "function_call_output":
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(item["call_id"]),
                        "content": str(item.get("output", "")),
                    }
                )
                i += 1

            else:
                i += 1

        return messages

    def _build_payload(
        self,
        turn: CanonicalTurn,
        messages: list[dict[str, object]],
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": turn.model,
            "messages": messages,
            "stream": True,
        }
        if turn.tools:
            chat_tools = [self._to_chat_tool(t) for t in turn.tools]
            payload["tools"] = [t for t in chat_tools if t is not None]
        if turn.tools or turn.tool_choice is not None:
            tc = self._to_chat_tool_choice(turn.tool_choice)
            if tc is not None:
                payload["tool_choice"] = tc
        return payload


class DeepSeekStandardAdapter(DeepSeekBaseAdapter):
    def build_request(
        self,
        turn: CanonicalTurn,
        reasoning_store: dict[str, str] | None = None,
    ) -> dict[str, object]:
        messages = self._build_messages(turn, reasoning_store=None)
        return self._build_payload(turn, messages)


class DeepSeekThinkingAdapter(DeepSeekBaseAdapter):
    def build_request(
        self,
        turn: CanonicalTurn,
        reasoning_store: dict[str, str] | None = None,
    ) -> dict[str, object]:
        messages = self._build_messages(turn, reasoning_store=reasoning_store)
        return self._build_payload(turn, messages)
