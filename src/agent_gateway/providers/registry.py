from agent_gateway.canonical.models import CanonicalTurn
from agent_gateway.providers.base import BaseProviderAdapter


class AdapterRegistry:
    def __init__(
        self,
        default_adapter: BaseProviderAdapter,
        default_model: str,
        model_map: dict[str, str] | None = None,
        type_adapters: dict[str, BaseProviderAdapter] | None = None,
        model_adapters: dict[str, BaseProviderAdapter] | None = None,
        model_type_map: dict[str, str] | None = None,
    ) -> None:
        self._default = default_adapter
        self._default_model = default_model
        self._model_map = model_map or {}
        self._type_adapters = type_adapters or {}
        self._model_adapters = model_adapters or {}
        self._model_type_map = model_type_map or {}

    def _resolve_model(self, requested: str | None) -> str:
        if requested and requested in self._model_map:
            return self._model_map[requested]
        return requested or self._default_model

    def _resolve_adapter(self, resolved_model: str) -> BaseProviderAdapter:
        if resolved_model in self._model_adapters:
            return self._model_adapters[resolved_model]
        type_key = self._model_type_map.get(resolved_model)
        if type_key and type_key in self._type_adapters:
            return self._type_adapters[type_key]
        return self._default

    def build_request(
        self,
        turn: CanonicalTurn,
        reasoning_store: dict[str, str] | None = None,
    ) -> dict[str, object]:
        resolved_model = self._resolve_model(turn.model)
        adapter = self._resolve_adapter(resolved_model)
        resolved_turn = CanonicalTurn(
            turn_id=turn.turn_id,
            model=resolved_model,
            input_items=turn.input_items,
            tools=turn.tools,
            tool_choice=turn.tool_choice,
        )
        return adapter.build_request(resolved_turn, reasoning_store=reasoning_store)
