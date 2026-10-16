"""A leitura em segundo plano não segura a conexão do banco nem as threads que atendem as telas."""

import asyncio
import threading

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings
from app.db import get_session
from app.main import app
from app.routes import analises


def test_sessao_do_envio_fecha_antes_da_leitura_em_segundo_plano(monkeypatch, tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    eventos: list[str] = []

    def sessao():
        with Session(engine) as s:
            yield s
        eventos.append("sessão fechada")

    monkeypatch.setattr(settings, "storage_dir", tmp_path)
    monkeypatch.setattr(analises, "processar_analise", lambda analise_id: eventos.append("leitura"))
    app.dependency_overrides[get_session] = sessao
    try:
        resposta = TestClient(app).post(
            "/api/analises", files=[("arquivos", ("a.pdf", b"%PDF-1.4 teste", "application/pdf"))]
        )
    finally:
        app.dependency_overrides.clear()
    assert resposta.status_code == 202
    assert eventos == ["sessão fechada", "leitura"]


def test_leitura_roda_nas_threads_proprias_e_nao_nas_das_requisicoes(monkeypatch):
    threads: list[str] = []
    monkeypatch.setattr(analises, "processar_analise", lambda analise_id: threads.append(threading.current_thread().name))
    asyncio.run(analises.agendar_processamento("a1"))
    assert threads[0].startswith("leitura")
