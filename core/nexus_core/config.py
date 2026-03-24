from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings for the local-first control plane."""

    model_config = SettingsConfigDict(
        env_prefix="NEXUS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = Field(default=Path(".nexus"))

    @property
    def resolved_data_dir(self) -> Path:
        if self.data_dir.is_absolute():
            return self.data_dir
        return REPO_ROOT / self.data_dir

    @property
    def state_dir(self) -> Path:
        return self.resolved_data_dir / "state"

    @property
    def workspace_root(self) -> Path:
        return self.resolved_data_dir / "workspaces"

    @property
    def database_path(self) -> Path:
        return self.state_dir / "nexus.db"

    def ensure_directories(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
