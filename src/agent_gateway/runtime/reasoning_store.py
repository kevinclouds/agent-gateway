import json
import logging
import os

logger = logging.getLogger("agent_gateway")


class ReasoningStore(dict):
    """A dict[str, str] that persists to a JSON file on every write."""

    def __init__(self, path: str | None = None) -> None:
        super().__init__()
        self._path = path
        if path:
            try:
                if os.path.exists(path):
                    with open(path) as f:
                        self.update(json.load(f))
                    logger.debug("reasoning_store: loaded %d entries from %s", len(self), path)
            except Exception as exc:
                logger.warning("reasoning_store: failed to load %s: %s", path, exc)

    def __setitem__(self, key: str, value: str) -> None:
        super().__setitem__(key, value)
        if self._path:
            try:
                with open(self._path, "w") as f:
                    json.dump(dict(self), f)
            except Exception as exc:
                logger.warning("reasoning_store: failed to save %s: %s", self._path, exc)
