"""App FastAPI do compararDocs."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from app.config import settings
from app import mongo
from app.db import criar_tabelas, engine
from app.models import AnaliseDB, agora_utc
from app.routes import analises


def _marcar_interrompidas() -> None:
    """Análises que ficaram PROCESSANDO quando o servidor caiu viram ERRO."""
    with Session(engine) as session:
        pendentes = session.exec(
            select(AnaliseDB).where(AnaliseDB.status_processamento == "PROCESSANDO")
        ).all()
        for analise in pendentes:
            analise.status_processamento = "ERRO"
            analise.erro = "Processamento interrompido; envie novamente"
            analise.concluido_em = agora_utc()
            session.add(analise)
        session.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    criar_tabelas()
    mongo.verificar()
    _marcar_interrompidas()
    yield


app = FastAPI(title="compararDocs", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analises.router)


@app.exception_handler(RequestValidationError)
async def erro_validacao(_: Request, exc: RequestValidationError) -> JSONResponse:
    campos = ", ".join(str(e["loc"][-1]) for e in exc.errors())
    return JSONResponse(status_code=422, content={"detail": f"Parâmetros inválidos: {campos}."})


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "modo_extrator": settings.modo_extrator_efetivo}
