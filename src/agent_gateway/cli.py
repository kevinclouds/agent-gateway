import os

import uvicorn


def _build_log_config() -> dict:
    log_level = os.environ.get("AG_LOG_LEVEL", "INFO").upper()
    log_file = os.environ.get("AG_LOG_FILE", "")

    fmt = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"

    handlers = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        }
    }
    handler_names = ["console"]

    if log_file:
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "default",
            "filename": log_file,
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
        }
        handler_names.append("file")

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"default": {"format": fmt}},
        "handlers": handlers,
        "root": {"level": log_level, "handlers": handler_names},
        "loggers": {
            "uvicorn": {"handlers": handler_names, "level": log_level, "propagate": False},
            "uvicorn.error": {"handlers": handler_names, "level": log_level, "propagate": False},
            "uvicorn.access": {"handlers": handler_names, "level": log_level, "propagate": False},
        },
    }


def main() -> None:
    host = os.environ.get("AG_HOST", "0.0.0.0")
    port = int(os.environ.get("AG_PORT", "9321"))
    uvicorn.run(
        "agent_gateway.app:create_app",
        host=host,
        port=port,
        factory=True,
        log_config=_build_log_config(),
    )
