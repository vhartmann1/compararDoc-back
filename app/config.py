"""Configuração via variáveis de ambiente / backend/.env."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    anthropic_api_key: str | None = None
    # "auto": usa Claude se houver ANTHROPIC_API_KEY, senão mock; "claude_code": CLI do Claude Code (teste local)
    extrator_modo: Literal["auto", "claude", "mock", "claude_code"] = "auto"
    modelo_claude: str = "claude-opus-5-5"
    claude_code_cli: str = "claude"

    storage_dir: Path = BASE_DIR / "storage"
    # padrão = Postgres local do docker-compose.yaml
    database_url: str = "postgresql+psycopg://comparardocs:comparardocs@localhost:5432/comparardocs"
    # padrão = MongoDB local do docker-compose.yaml
    # usuário da aplicação (só lê e grava no banco dela), não o administrador do container
    mongo_url: str = "mongodb://comparardocs_app:comparardocs_app@localhost:27017/?authSource=comparardocs"
    mongo_db: str = "comparardocs"
    cors_origins: list[str] = ["http://localhost:3000"]

    max_arquivos: int = 20
    max_tamanho_mb: int = 32

    @property
    def modo_extrator_efetivo(self) -> Literal["claude", "mock", "claude_code"]:
        if self.extrator_modo == "auto":
            return "claude" if self.anthropic_api_key else "mock"
        return self.extrator_modo


settings = Settings()
