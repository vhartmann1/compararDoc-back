"""Endpoints de /api/analises."""

import asyncio
import inspect
import logging
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, get_args

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError
from pymongo.errors import PyMongoError
from pypdf import PdfReader
from sqlalchemy import ColumnElement
from sqlmodel import Session, col, func, select

from app import mongo
from app.config import settings
from app.db import engine, get_session
from app.models import AnaliseDB, ArquivoDB, agora_utc
from app.schemas import (
    Analise,
    AnaliseResumo,
    Arquivo,
    ArquivoEntrada,
    ExtracaoArquivo,
    FiltroLista,
    ListaAnalises,
    Modalidade,
    ResultadoComparacao,
    Uso,
)
from app.tipos_de_arquivo import MEDIA_DOCX, MEDIA_PDF, MEDIA_XLS, MEDIA_XLSX, TIPOS_IMAGEM

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analises", tags=["analises"])

# media_type -> extensões aceitas
TIPOS_ACEITOS: dict[str, tuple[str, ...]] = {
    MEDIA_PDF: (".pdf",),
    "image/jpeg": (".jpg", ".jpeg"),
    "image/png": (".png",),
    MEDIA_DOCX: (".docx",),
    MEDIA_XLSX: (".xlsx",),
    MEDIA_XLS: (".xls",),
}
# Word/Excel: browsers às vezes mandam content-type genérico; aceitamos pela extensão + assinatura do arquivo.
OFFICE_POR_EXTENSAO = {".docx": MEDIA_DOCX, ".xlsx": MEDIA_XLSX, ".xls": MEDIA_XLS}
CONTENT_TYPES_GENERICOS = {"", "application/octet-stream", "application/zip", "application/x-zip-compressed"}
ASSINATURA_ZIP = b"PK\x03\x04"
ASSINATURA_OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # Office antigo (.xls)
ASSINATURA_POR_EXTENSAO = {".docx": ASSINATURA_ZIP, ".xlsx": ASSINATURA_ZIP, ".xls": ASSINATURA_OLE}
EXTENSOES_ANTIGAS = {".doc"}
TIPOS_INLINE = {MEDIA_PDF, *TIPOS_IMAGEM}
TAMANHO_BLOCO = 1024 * 1024

ERRO_RESULTADO_ANTIGO = "Análise feita em versão anterior; envie novamente"
ERRO_SEM_RESULTADO = "Resultado não encontrado; envie novamente"
MENSAGEM_ERRO_GENERICA = "Não foi possível processar os documentos. Tente novamente."

# A sessão fecha quando a rota termina: a leitura em segundo plano não segura conexão do banco
SessionDep = Annotated[Session, Depends(get_session, scope="function")]


# ---------------------------------------------------------------------------
# Conversão banco -> resposta
# ---------------------------------------------------------------------------

def _utc(dt: datetime | None) -> datetime | None:
    # Tudo é gravado em UTC; garante o fuso na resposta mesmo se o banco devolver sem.
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _ler_resultado(gravado: dict | None) -> ResultadoComparacao | None:
    """Resultado gravado no MongoDB; None se não houver ou se estiver em formato antigo (v1) que não valida mais."""
    if not gravado:
        return None
    try:
        return ResultadoComparacao.model_validate(gravado)
    except ValidationError:
        return None


def _para_analise(analise: AnaliseDB, arquivos: list[ArquivoDB], gravado: dict | None = None) -> Analise:
    """`gravado` é o resultado que está no MongoDB para a análise."""
    resultado = _ler_resultado(gravado)
    erro = analise.erro
    if analise.status_processamento == "CONCLUIDA" and resultado is None:
        erro = ERRO_RESULTADO_ANTIGO if gravado else ERRO_SEM_RESULTADO
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
        conferido_em=_utc(gravado.get("gravado_em")) if resultado and gravado else None,
        arquivos=[
            Arquivo(id=a.id, nome=a.nome, media_type=a.media_type, tamanho_bytes=a.tamanho_bytes, paginas=a.paginas)
            for a in arquivos
        ],
        resultado=resultado,
        uso=_ler_uso(analise),
    )


def _ler_uso(analise: AnaliseDB) -> Uso | None:
    if analise.modelo is None:
        return None
    return Uso(
        input_tokens=analise.tokens_entrada or 0,
        output_tokens=analise.tokens_saida or 0,
        custo_usd_estimado=float(analise.custo_usd or 0),
        modelo=analise.modelo,
    )


def _arquivos_da_analise(session: Session, analise_id: str) -> list[ArquivoDB]:
    return list(session.exec(select(ArquivoDB).where(ArquivoDB.analise_id == analise_id).order_by(ArquivoDB.ordem)).all())


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
            detail=f"Formato antigo não suportado: salve como .docx ('{nome}').",
        )

    if ext in OFFICE_POR_EXTENSAO:
        canonico = OFFICE_POR_EXTENSAO[ext]
        if media_type != canonico and media_type not in CONTENT_TYPES_GENERICOS:
            raise HTTPException(status_code=400, detail=f"Tipo de arquivo não aceito: '{nome}'.")
        # Confere a assinatura (ZIP no .docx/.xlsx, OLE no .xls) para não aceitar arquivo renomeado.
        assinatura = ASSINATURA_POR_EXTENSAO[ext]
        inicio = arquivo.file.read(len(assinatura))
        arquivo.file.seek(0)
        if inicio != assinatura:
            raise HTTPException(
                status_code=400,
                detail=f"Arquivo '{nome}' não é um {ext} válido (salve novamente no Word/Excel).",
            )
        return canonico, ext

    if media_type not in TIPOS_ACEITOS or ext not in TIPOS_ACEITOS[media_type]:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de arquivo não aceito: '{nome}'. Envie PDF, JPG, PNG, Word (.docx) ou Excel (.xlsx/.xls).",
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
    if media_type in (MEDIA_DOCX, MEDIA_XLSX, MEDIA_XLS):
        return None  # Word/Excel não têm páginas fixas
    if media_type != MEDIA_PDF:
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
        for ordem, (arquivo, (media_type, ext)) in enumerate(zip(arquivos, tipos, strict=True)):
            arquivo_id = str(uuid.uuid4())
            caminho = pasta / f"{arquivo_id}{ext}"
            tamanho = _salvar(arquivo, caminho)
            registros.append(
                ArquivoDB(
                    id=arquivo_id,
                    analise_id=analise.id,
                    ordem=ordem,
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

    background_tasks.add_task(agendar_processamento, analise.id)
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


def _marcar_erro(analise_id: str, mensagem: str) -> None:
    with Session(engine) as session:
        analise = session.get(AnaliseDB, analise_id)
        if analise is not None:
            analise.status_processamento = "ERRO"
            analise.erro = mensagem
            analise.concluido_em = agora_utc()
            session.add(analise)
            session.commit()


# Threads só da leitura: fora das que atendem as requisições, para a tela não travar com muitas análises
_leituras = ThreadPoolExecutor(max_workers=settings.leituras_simultaneas, thread_name_prefix="leitura")


async def agendar_processamento(analise_id: str) -> None:
    """Põe a análise na vez das leituras; passando do limite, ela espera ainda como PROCESSANDO."""
    await asyncio.get_running_loop().run_in_executor(_leituras, processar_analise, analise_id)


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
        from app.services.leitura.formato_da_resposta import ErroExtracao

        # ErroExtracao já traz mensagem pronta para o usuário; o resto fica genérico.
        _marcar_erro(analise_id, str(e) if isinstance(e, ErroExtracao) else MENSAGEM_ERRO_GENERICA)
        return

    # Primeiro o MongoDB, depois o Postgres: nada fica CONCLUIDA sem o resultado gravado.
    try:
        mongo.salvar(
            analise_id,
            resultado=retorno.resultado.model_dump(mode="json"),
            por_arquivo={arquivo_id: extracao.model_dump(mode="json") for arquivo_id, extracao in retorno.extracoes.items()},
        )
    except Exception:
        logger.exception("Falha ao gravar o resultado da análise %s no MongoDB", analise_id)
        _marcar_erro(analise_id, MENSAGEM_ERRO_GENERICA)
        return

    with Session(engine) as session:
        analise = session.get(AnaliseDB, analise_id)
        if analise is None:
            return
        analise.status_processamento = "CONCLUIDA"
        analise.etapa = "FINALIZADO"
        analise.erro = None
        analise.status_resultado = retorno.resultado.status
        analise.total_divergencias = len(retorno.resultado.divergencias)
        analise.modelo = retorno.uso.modelo
        analise.tokens_entrada = retorno.uso.input_tokens
        analise.tokens_saida = retorno.uso.output_tokens
        # str() primeiro: Decimal(float) carregaria o erro binário do ponto flutuante
        analise.custo_usd = Decimal(str(retorno.uso.custo_usd_estimado))
        analise.concluido_em = agora_utc()
        session.add(analise)
        session.commit()


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

def _condicoes_busca(usuario_id: str | None, q: str | None) -> list[ColumnElement[bool]]:
    condicoes: list[ColumnElement[bool]] = []
    if usuario_id:
        condicoes.append(col(AnaliseDB.usuario_id) == usuario_id)
    termo = (q or "").strip()
    if termo:
        # % e _ digitados pelo usuário são texto, não curinga
        literal = termo.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        condicoes.append(col(AnaliseDB.processo).ilike(f"%{literal}%", escape="\\"))
    return condicoes


def _condicao_filtro(status: FiltroLista) -> ColumnElement[bool]:
    if status in ("PROCESSANDO", "ERRO"):
        return col(AnaliseDB.status_processamento) == status
    return (col(AnaliseDB.status_processamento) == "CONCLUIDA") & (col(AnaliseDB.status_resultado) == status)


def _contar_por_filtro(session: Session, condicoes: list[ColumnElement[bool]]) -> dict[FiltroLista, int]:
    grupos = session.exec(
        select(AnaliseDB.status_processamento, AnaliseDB.status_resultado, func.count())
        .where(*condicoes)
        .group_by(AnaliseDB.status_processamento, AnaliseDB.status_resultado)
    ).all()
    contagem: dict[FiltroLista, int] = dict.fromkeys(get_args(FiltroLista), 0)
    for processamento, resultado, quantidade in grupos:
        contagem["TODAS"] += quantidade
        # concluída sem resultado (versão anterior) só entra em TODAS
        filtro = resultado if processamento == "CONCLUIDA" else processamento
        if filtro in contagem:
            contagem[filtro] += quantidade
    return contagem


@router.get("", response_model=ListaAnalises)
def listar_analises(
    session: SessionDep,
    usuario_id: str | None = None,
    status: FiltroLista = "TODAS",
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ListaAnalises:
    condicoes = _condicoes_busca(usuario_id, q)
    contagem = _contar_por_filtro(session, condicoes)

    consulta = select(AnaliseDB).where(*condicoes)
    if status != "TODAS":
        consulta = consulta.where(_condicao_filtro(status))
    # id desempata análises criadas no mesmo instante, para a paginação não repetir linha
    consulta = consulta.order_by(col(AnaliseDB.criado_em).desc(), col(AnaliseDB.id).desc()).limit(limit).offset(offset)
    analises = session.exec(consulta).all()

    ids = [a.id for a in analises]
    arquivos: dict[str, int] = dict(
        session.exec(
            select(ArquivoDB.analise_id, func.count()).where(col(ArquivoDB.analise_id).in_(ids)).group_by(ArquivoDB.analise_id)
        ).all()
    ) if ids else {}

    itens = [
        AnaliseResumo(
            id=a.id,
            processo=a.processo,
            usuario_id=a.usuario_id,
            status_processamento=a.status_processamento,
            status_resultado=a.status_resultado,
            modalidade=a.modalidade,
            total_divergencias=a.total_divergencias,
            erro=a.erro,
            qtd_arquivos=arquivos.get(a.id, 0),
            criado_em=_utc(a.criado_em),
        )
        for a in analises
    ]
    return ListaAnalises(itens=itens, contagem=contagem)


@router.get("/{analise_id}", response_model=Analise)
def obter_analise(analise_id: str, session: SessionDep) -> Analise:
    analise = _buscar_analise(session, analise_id)
    gravado = None
    if analise.status_processamento == "CONCLUIDA":
        try:
            gravado = mongo.ler_resultado(analise_id)
        except PyMongoError:
            logger.exception("MongoDB indisponível ao ler a análise %s", analise_id)
            raise HTTPException(status_code=503, detail="Não foi possível ler o resultado agora. Tente novamente em instantes.") from None
    return _para_analise(analise, _arquivos_da_analise(session, analise_id), gravado)


@router.post("/{analise_id}/refazer-conferencia", response_model=Analise)
def refazer_conferencia(analise_id: str, session: SessionDep) -> Analise:
    """Refaz a conferência com as leituras gravadas, sem ler os documentos de novo."""
    from app.services.comparacao import comparar

    analise = _buscar_analise(session, analise_id)
    if analise.status_processamento != "CONCLUIDA":
        raise HTTPException(status_code=409, detail="Só dá para refazer a conferência de uma análise concluída.")
    arquivos = _arquivos_da_analise(session, analise_id)
    try:
        gravadas = mongo.ler_extracoes([a.id for a in arquivos])
    except PyMongoError:
        logger.exception("MongoDB indisponível ao ler as extrações da análise %s", analise_id)
        raise HTTPException(status_code=503, detail="Não foi possível refazer a conferência agora. Tente novamente em instantes.") from None
    try:
        entradas = [
            (
                ArquivoEntrada(id=a.id, nome=a.nome, caminho=Path(a.caminho), media_type=a.media_type),
                ExtracaoArquivo.model_validate(gravadas[a.id]),
            )
            for a in arquivos
        ]
    except (KeyError, ValidationError):
        raise HTTPException(status_code=409, detail="A leitura desta análise não está disponível; envie novamente.") from None

    resultado = comparar(entradas, analise.modalidade).model_dump(mode="json")
    # Primeiro o MongoDB, depois o Postgres, como no processamento
    try:
        conferido_em = mongo.salvar_resultado(analise_id, resultado)
    except PyMongoError:
        logger.exception("Falha ao gravar a conferência refeita da análise %s", analise_id)
        raise HTTPException(status_code=503, detail="Não foi possível refazer a conferência agora. Tente novamente em instantes.") from None
    analise.status_resultado = resultado["status"]
    analise.total_divergencias = len(resultado["divergencias"])
    session.add(analise)
    session.commit()
    session.refresh(analise)
    return _para_analise(analise, arquivos, {**resultado, "gravado_em": conferido_em})


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
