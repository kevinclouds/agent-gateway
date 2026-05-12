import os

import uvicorn


def main() -> None:
    host = os.environ.get("AG_HOST", "0.0.0.0")
    port = int(os.environ.get("AG_PORT", "8000"))
    uvicorn.run(
        "agent_gateway.app:create_app",
        host=host,
        port=port,
        factory=True,
    )
