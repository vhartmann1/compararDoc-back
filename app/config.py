"""Configuração via variáveis de ambiente / backend/.env."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    anthropic_api_key: str | None = None
    # "auto": usa Claude se houver ANTHROPIC_API_KEY, senão mock
    extrator_modo: Literal["auto", "claude", "mock"] = "auto"
    modelo_claude: str = "claude-opus-5-5"

    storage_dir: Path = BASE_DIR / "storage"
    # padrão = Postgres local do docker-compose.yaml
    database_url: str = "postgresql+psycopg://comparardocs:comparardocs@localhost:5432/comparardocs"
    cors_origins: list[str] = ["http://localhost:3000"]

    max_arquivos: int = 20
    max_tamanho_mb: int = 32

    @property
    def modo_extrator_efetivo(self) -> Literal["claude", "mock"]:
        if self.extrator_modo == "auto":
            return "claude" if self.anthropic_api_key else "mock"
        return self.extrator_modo


settings = Settings()
