"""Application settings, loaded from environment variables / `.env` (12-factor style)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# src/workflow_agent/core/config.py -> project root is three levels above the package dir
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def resolve_path(value: str | Path) -> Path:
    """Resolve a path relative to the project root (absolute paths are kept)."""
    path = Path(value)
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    anthropic_api_key: SecretStr | None = None
    claude_model: str = "claude-sonnet-5-5"
    claude_refusal_fallback: bool = True
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 3
    llm_enabled: bool = True

    # Workflow sources and folders
    workflow_excel_path: Path = Path("data/AI_Agent_Workflow_Assessment.xlsx")
    workflow_config_path: Path = Path("config/workflows.yaml")
    prompts_dir: Path = Path("prompts")
    data_dir: Path = Path("data")
    upload_dir: Path = Path("data/uploads")
    output_dir: Path = Path("outputs")
    log_dir: Path = Path("logs")

    # Behaviour
    summary_enabled: bool = True
    max_clarification_rounds: int = 3
    mock_api_failure_rate: float = 0.0

    # Logging
    log_level: str = "INFO"
    log_json_console: bool = False

    @field_validator(
        "workflow_excel_path",
        "workflow_config_path",
        "prompts_dir",
        "data_dir",
        "upload_dir",
        "output_dir",
        "log_dir",
        mode="after",
    )
    @classmethod
    def _resolve(cls, value: Path) -> Path:
        return resolve_path(value)

    @property
    def llm_available(self) -> bool:
        key = self.anthropic_api_key.get_secret_value().strip() if self.anthropic_api_key else ""
        return self.llm_enabled and bool(key)

    @property
    def execution_log_path(self) -> Path:
        return self.log_dir / "executions.jsonl"


@lru_cache
def get_settings() -> Settings:
    return Settings()
