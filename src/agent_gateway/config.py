import json
import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


_DEFAULT_MODEL_TYPE_MAP: dict[str, str] = {
    "deepseek-reasoner": "deepseek-thinking",
    "DeepSeek-V4-Flash": "deepseek-thinking",
    "DeepSeek-V4-Pro": "deepseek-thinking",
}


class GatewayConfig(BaseModel):
    deepseek_base_url: str = Field(default="https://api.deepseek.com")
    default_model: str = Field(default="deepseek-chat")
    model_map: dict[str, str] = Field(default_factory=dict)
    model_type_map: dict[str, str] = Field(default_factory=lambda: dict(_DEFAULT_MODEL_TYPE_MAP))
    reasoning_store_file: str = Field(default=".reasoning_store.json")

    def resolve_model(self, requested: str | None) -> str:
        if requested and requested in self.model_map:
            return self.model_map[requested]
        return self.default_model

    @classmethod
    def from_env(cls) -> "GatewayConfig":
        raw_map = os.environ.get("MODEL_MAP", "")
        model_map: dict[str, str] = json.loads(raw_map) if raw_map else {}
        raw_type_map = os.environ.get("MODEL_TYPE_MAP", "")
        model_type_map: dict[str, str] = (
            json.loads(raw_type_map) if raw_type_map else dict(_DEFAULT_MODEL_TYPE_MAP)
        )
        return cls(
            deepseek_base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            default_model=os.environ.get("DEFAULT_MODEL", "deepseek-chat"),
            model_map=model_map,
            model_type_map=model_type_map,
            reasoning_store_file=os.environ.get("REASONING_STORE_FILE", ".reasoning_store.json"),
        )
