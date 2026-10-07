"""Endpoints de /api/analises."""

import asyncio
import inspect
import json
import logging
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError
from pypdf import PdfReader
from sqlmodel import Session, func, select, text

from app.config import settings
from app.db import engine, get_session
from app.models import AnaliseDB, ArquivoDB, agora_utc
from app.schemas import Analise, AnaliseResumo, Arquivo, ArquivoEntrada, Modalidade, ResultadoComparacao, Uso

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analises", tags=["analises"])

MEDIA_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MEDIA_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# media_type -> extensões aceitas
TIPOS_ACEITOS: dict[str, tuple[str, ...]] = {
    "application/pdf": (".pdf",),
    "image/jpeg": (".jpg", ".jpeg"),
    "image/png": (".png",),
    MEDIA_DOCX: (".docx",),
    MEDIA_XLSX: (".xlsx",),
}
# Word/Excel: browsers às vezes mandam content-type genérico; aceitamos pela extensão + assinatura ZIP.
OFFICE_POR_EXTENSAO = {".docx": MEDIA_DOCX, ".xlsx": MEDIA_XLSX}
CONTENT_TYPES_GENERICOS = {"", "application/octet-stream", "application/zip", "application/x-zip-compressed"}
ASSINATURA_ZIP = b"PK\x03\x04"
EXTENSOES_ANTIGAS = {".doc", ".xls"}
TIPOS_INLINE = {"application/pdf", "image/jpeg", "image/png"}
TAMANHO_BLOCO = 1024 * 1024

ERRO_RESULTADO_ANTIGO = "Análise feita em versão anterior; envie novamente"

SessionDep = Annotated[Session, Depends(get_session)]


# ---------------------------------------------------------------------------
# Conversão banco -> resposta
# ---------------------------------------------------------------------------

def _utc(dt: datetime | None) -> datetime | None:
    # SQLite não guarda fuso; tudo é gravado em UTC.
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _ler_resultado(analise: AnaliseDB) -> ResultadoComparacao | None:
    """Resultado gravado; None se vazio ou em formato antigo (v1) que não valida mais."""
    if not analise.resultado_json:
        return None
    try:
        return ResultadoComparacao.model_validate_json(analise.resultado_json)
    except ValidationError:
        return None


def _para_analise(analise: AnaliseDB, arquivos: list[ArquivoDB]) -> Analise:
    resultado = _ler_resultado(analise)
    erro = analise.erro
    if analise.resultado_json and resultado is None:
        erro = ERRO_RESULTADO_ANTIGO
    return Analise(
        id=analise.id,
        processo=analise.processo,
        modalidade=analise.modalidade,
        usuario_id=analise.usuario_id,
        status_processamento=analise.status_processamento,
        etapa=analise.etapa,
        erro=erro,
        criado_em=_utc(analise.criado_em),
        concluido_em=_utc(analise.concluido_em),
        arquivos=[
            Arquivo(id=a.id, nome=a.nome, media_type=a.media_type, tamanho_bytes=a.tamanho_bytes, paginas=a.paginas)
            for a in arquivos
        ],
        resultado=resultado,
        uso=_ler_uso(analise),
    )


def _ler_uso(analise: AnaliseDB) -> Uso | None:
    if not analise.uso_json:
        return None
    try:
        return Uso.model_validate_json(analise.uso_json)
    except ValidationError:
        return None


def _arquivos_da_analise(session: Session, analise_id: str) -> list[ArquivoDB]:
    return list(session.exec(select(ArquivoDB).where(ArquivoDB.analise_id == analise_id).order_by(text("arquivos.rowid"))).all())


def _buscar_analise(session: Session, analise_id: str) -> AnaliseDB:
    analise = session.get(AnaliseDB, analise_id)
    if analise is None:
        raise HTTPException(status_code=404, detail="Análise não encontrada")
    return analise


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def _validar_tipo(arquivo: UploadFile) -> tuple[str, str]:
    """Retorna (media_type canônico, extensão) ou levanta 400."""
    nome = arquivo.filename or ""
    ext = Path(nome).suffix.lower()
    media_type = (arquivo.content_type or "").split(";")[0].strip().lower()

    if ext in EXTENSOES_ANTIGAS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato antigo não suportado: salve como .docx/.xlsx ('{nome}').",
        )

    if ext in OFFICE_POR_EXTENSAO:
        canonico = OFFICE_POR_EXTENSAO[ext]
        if media_type != canonico and media_type not in CONTENT_TYPES_GENERICOS:
            raise HTTPException(status_code=400, detail=f"Tipo de arquivo não aceito: '{nome}'.")
        # .docx/.xlsx são ZIP: confere a assinatura para não aceitar arquivo renomeado.
        inicio = arquivo.file.read(len(ASSINATURA_ZIP))
        arquivo.file.seek(0)
        if inicio != ASSINATURA_ZIP:
            raise HTTPException(
                status_code=400,
                detail=f"Arquivo '{nome}' não é um {ext} válido (salve novamente no Word/Excel).",
            )
        return canonico, ext

    if media_type not in TIPOS_ACEITOS or ext not in TIPOS_ACEITOS[media_type]:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de arquivo não aceito: '{nome}'. Envie PDF, JPG, PNG, Word (.docx) ou Excel (.xlsx).",
        )
    return media_type, ext


def _salvar(arquivo: UploadFile, destino: Path) -> int:
    """Grava em disco respeitando o limite de tamanho. Retorna o tamanho em bytes."""
    limite = settings.max_tamanho_mb * 1024 * 1024
    tamanho = 0
    with destino.open("wb") as saida:
        while bloco := arquivo.file.read(TAMANHO_BLOCO):
            tamanho += len(bloco)
            if tamanho > limite:
                raise HTTPException(
                    status_code=400,
                    detail=f"Arquivo '{arquivo.filename}' excede o limite de {settings.max_tamanho_mb} MB.",
                )
            saida.write(bloco)
    if tamanho == 0:
        raise HTTPException(status_code=400, detail=f"Arquivo '{arquivo.filename}' está vazio.")
    return tamanho


def _contar_paginas(caminho: Path, media_type: str) -> int | None:
    if media_type in (MEDIA_DOCX, MEDIA_XLSX):
        return None  # Word/Excel não têm páginas fixas
    if media_type != "application/pdf":
        return 1
    try:
        return len(PdfReader(caminho).pages)
    except Exception:
        logger.warning("Não foi possível contar as páginas de %s", caminho, exc_info=True)
        return None


@router.post("", status_code=202, response_model=Analise)
def criar_analise(
    session: SessionDep,
    background_tasks: BackgroundTasks,
    arquivos: Annotated[list[UploadFile] | None, File()] = None,
    processo: Annotated[str | None, Form()] = None,
    modalidade: Annotated[Modalidade | None, Form()] = None,
    x_usuario_id: Annotated[str | None, Header()] = None,
) -> Analise:
    arquivos = [a for a in (arquivos or []) if a.filename]
    if not arquivos:
        raise HTTPException(status_code=400, detail="Envie pelo menos um arquivo.")
    if len(arquivos) > settings.max_arquivos:
        raise HTTPException(status_code=400, detail=f"Envie no máximo {settings.max_arquivos} arquivos por análise.")

    tipos = [_validar_tipo(a) for a in arquivos]

    analise = AnaliseDB(
        processo=(processo or "").strip() or None,
        modalidade=modalidade,
        usuario_id=(x_usuario_id or "").strip() or None,
        status_processamento="PROCESSANDO",
        etapa="RECEBIDO",
    )
    pasta = settings.storage_dir / analise.id
    pasta.mkdir(parents=True, exist_ok=True)

    registros: list[ArquivoDB] = []
    try:
        for arquivo, (media_type, ext) in zip(arquivos, tipos, strict=True):
            arquivo_id = str(uuid.uuid4())
            caminho = pasta / f"{arquivo_id}{ext}"
            tamanho = _salvar(arquivo, caminho)
            registros.append(
                ArquivoDB(
                    id=arquivo_id,
                    analise_id=analise.id,
                    nome=Path(arquivo.filename).name,
                    media_type=media_type,
                    tamanho_bytes=tamanho,
                    paginas=_contar_paginas(caminho, media_type),
                    caminho=str(caminho),
                )
            )
    except BaseException:
        shutil.rmtree(pasta, ignore_errors=True)
        raise

    session.add(analise)
    session.commit()  # análise antes dos arquivos (chave estrangeira)
    session.add_all(registros)
    session.commit()
    session.refresh(analise)

    background_tasks.add_task(processar_analise, analise.id)
    return _para_analise(analise, registros)


# ---------------------------------------------------------------------------
# Processamento em background
# ---------------------------------------------------------------------------

def _atualizar_etapa(analise_id: str, etapa: str) -> None:
    with Session(engine) as session:
        analise = session.get(AnaliseDB, analise_id)
        if analise is not None:
            analise.etapa = etapa
            session.add(analise)
            session.commit()


def processar_analise(analise_id: str) -> None:
    """Roda o pipeline e grava o resultado. Executa fora do request (sessão própria)."""
    with Session(engine) as session:
        entradas = [
            ArquivoEntrada(id=a.id, nome=a.nome, caminho=Path(a.caminho), media_type=a.media_type)
            for a in _arquivos_da_analise(session, analise_id)
        ]
        analise = session.get(AnaliseDB, analise_id)
        modalidade = analise.modalidade if analise else None

    try:
        from app.services.pipeline import processar

        retorno = processar(entradas, lambda etapa: _atualizar_etapa(analise_id, etapa), modalidade)
        if inspect.isawaitable(retorno):
            retorno = asyncio.run(retorno)
    except Exception as e:
        logger.exception("Falha ao processar a análise %s", analise_id)
        from app.services.extrator import ErroExtracao

        # ErroExtracao já traz mensagem pronta para o usuário; o resto fica genérico.
        mensagem = str(e) if isinstance(e, ErroExtracao) else "Não foi possível processar os documentos. Tente novamente."
        with Session(engine) as session:
            analise = session.get(AnaliseDB, analise_id)
            if analise is not None:
                analise.status_processamento = "ERRO"
                analise.erro = mensagem
                analise.concluido_em = agora_utc()
                session.add(analise)
                session.commit()
        return

    with Session(engine) as session:
        analise = session.get(AnaliseDB, analise_id)
        if analise is None:
            return
        analise.status_processamento = "CONCLUIDA"
        analise.etapa = "FINALIZADO"
        analise.erro = None
        analise.resultado_json = retorno.resultado.model_dump_json()
        analise.extracoes_json = json.dumps(
            {arquivo_id: extracao.model_dump(mode="json") for arquivo_id, extracao in retorno.extracoes.items()},
            ensure_ascii=False,
        )
        analise.uso_json = retorno.uso.model_dump_json()
        analise.concluido_em = agora_utc()
        session.add(analise)
        session.commit()


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

@router.get("", response_model=list[AnaliseResumo])
def listar_analises(
    session: SessionDep,
    usuario_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[AnaliseResumo]:
    consulta = select(AnaliseDB).order_by(AnaliseDB.criado_em.desc()).limit(limit)
    if usuario_id:
        consulta = consulta.where(AnaliseDB.usuario_id == usuario_id)
    analises = session.exec(consulta).all()

    ids = [a.id for a in analises]
    contagem: dict[str, int] = dict(
        session.exec(
            select(ArquivoDB.analise_id, func.count()).where(ArquivoDB.analise_id.in_(ids)).group_by(ArquivoDB.analise_id)
        ).all()
    ) if ids else {}

    return [
        AnaliseResumo(
            id=a.id,
            processo=a.processo,
            usuario_id=a.usuario_id,
            status_processamento=a.status_processamento,
            status_resultado=resultado.status if (resultado := _ler_resultado(a)) else None,
            qtd_arquivos=contagem.get(a.id, 0),
            criado_em=_utc(a.criado_em),
        )
        for a in analises
    ]


@router.get("/{analise_id}", response_model=Analise)
def obter_analise(analise_id: str, session: SessionDep) -> Analise:
    analise = _buscar_analise(session, analise_id)
    return _para_analise(analise, _arquivos_da_analise(session, analise_id))


@router.get("/{analise_id}/arquivos/{arquivo_id}")
def baixar_arquivo(analise_id: str, arquivo_id: str, session: SessionDep) -> FileResponse:
    _buscar_analise(session, analise_id)
    arquivo = session.get(ArquivoDB, arquivo_id)
    if arquivo is None or arquivo.analise_id != analise_id:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    caminho = Path(arquivo.caminho)
    if not caminho.is_file():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado no armazenamento")
    disposicao = "inline" if arquivo.media_type in TIPOS_INLINE else "attachment"
    return FileResponse(caminho, media_type=arquivo.media_type, filename=arquivo.nome, content_disposition_type=disposicao)
