import os

from pydantic import BaseModel, Field


class GatewayConfig(BaseModel):
    deepseek_base_url: str = Field(default="https://api.deepseek.com")
    deepseek_api_key: str = Field(default="")
    default_model: str = Field(default="deepseek-chat")

    @classmethod
    def from_env(cls) -> "GatewayConfig":
        return cls(
            deepseek_base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            default_model=os.environ.get("DEFAULT_MODEL", "deepseek-chat"),
        )
