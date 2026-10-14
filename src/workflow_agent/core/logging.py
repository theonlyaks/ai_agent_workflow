"""Structured logging with per-run correlation ids.

* Console: human readable (or JSON with LOG_JSON_CONSOLE=true)
* File:    logs/app.log, JSON lines, rotated at 5 MB x 5 files
* Every record carries `run_id` and `workflow_id` from context variables, so all
  log lines of one user request can be traced end-to-end.
"""

from __future__ import annotations

import contextvars
import json
import logging
import logging.handlers
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

run_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("run_id", default="-")
workflow_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("workflow_id", default="-")

_STANDARD_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {
    "message",
    "asctime",
    "run_id",
    "workflow_id",
}
_configured = False


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = run_id_var.get()
        record.workflow_id = workflow_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "run_id": getattr(record, "run_id", "-"),
            "workflow_id": getattr(record, "workflow_id", "-"),
            "message": record.getMessage(),
        }
        extra = {k: v for k, v in record.__dict__.items() if k not in _STANDARD_ATTRS}
        if extra:
            payload["extra"] = extra
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__(
            "%(asctime)s | %(levelname)-7s | run=%(run_id)s wf=%(workflow_id)s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )


def setup_logging(level: str = "INFO", log_dir: Path | None = None, json_console: bool = False) -> None:
    """Configure root logging once (safe to call repeatedly, e.g. on Streamlit reruns)."""
    global _configured
    if _configured:
        return

    root = logging.getLogger()
    root.setLevel(level.upper())
    context_filter = ContextFilter()

    console = logging.StreamHandler()
    console.setFormatter(JsonFormatter() if json_console else ConsoleFormatter())
    console.addFilter(context_filter)
    root.addHandler(console)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "app.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(JsonFormatter())
        file_handler.addFilter(context_filter)
        root.addHandler(file_handler)

    # Keep third-party noise down
    for noisy in ("httpx", "httpx2", "httpcore", "anthropic", "urllib3", "watchdog", "langgraph"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True


@contextmanager
def log_context(run_id: str | None = None, workflow_id: str | None = None) -> Iterator[None]:
    """Bind run/workflow ids to every log record emitted inside the block."""
    tokens = []
    if run_id is not None:
        tokens.append((run_id_var, run_id_var.set(run_id)))
    if workflow_id is not None:
        tokens.append((workflow_id_var, workflow_id_var.set(workflow_id)))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)
