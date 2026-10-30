"""PDF com página escaneada de lado ou invertida: endireita as páginas que a leitura apontou e lê de novo."""

import logging
import tempfile
from collections.abc import Callable
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.errors import DependencyError, PyPdfError

from app.schemas import ArquivoEntrada, ExtracaoArquivo, PaginaGirada, Uso
from app.tipos_de_arquivo import MEDIA_PDF

logger = logging.getLogger(__name__)

Extrator = Callable[[list[ArquivoEntrada]], tuple[dict[str, ExtracaoArquivo], Uso]]


def reler_paginas_giradas(
    arquivos: list[ArquivoEntrada], extracoes: dict[str, ExtracaoArquivo], uso: Uso, extrair: Extrator
) -> tuple[dict[str, ExtracaoArquivo], Uso]:
    """Uma releitura só, dos arquivos com páginas giradas; o resultado dela vale mesmo que ainda aponte giro."""
    with tempfile.TemporaryDirectory() as pasta:
        copias = []
        for a in arquivos:
            if a.media_type == MEDIA_PDF and extracoes[a.id].paginas_giradas:
                copia = endireitado(a, extracoes[a.id].paginas_giradas, Path(pasta))
                if copia is not None:
                    copias.append(copia)
        if not copias:
            return extracoes, uso
        relidas, uso_releitura = extrair(copias)
    return {**extracoes, **relidas}, _somar(uso, uso_releitura)


def endireitado(arquivo: ArquivoEntrada, giradas: list[PaginaGirada], pasta: Path) -> ArquivoEntrada | None:
    """Cópia do PDF em `pasta` com as páginas na posição de leitura (mesmo id e nome); None se não há o que girar."""
    try:
        leitor = PdfReader(arquivo.caminho)
        escritor = PdfWriter()
        for pagina in leitor.pages:
            escritor.add_page(pagina)
        graus = {g.pagina: g.graus for g in giradas if 1 <= g.pagina <= len(escritor.pages)}
        for numero, giro in graus.items():
            pagina = escritor.pages[numero - 1]
            pagina.rotation = (pagina.rotation + giro) % 360  # o modelo viu a página já com o giro do PDF
        if not graus:
            return None
        destino = pasta / f"{arquivo.id}.pdf"
        with destino.open("wb") as f:
            escritor.write(f)
    except (PyPdfError, DependencyError):  # corrompido ou protegido: fica a primeira leitura
        logger.warning("Não foi possível endireitar %s", arquivo.nome, exc_info=True)
        return None
    return arquivo.model_copy(update={"caminho": destino})


def _somar(a: Uso, b: Uso) -> Uso:
    return Uso(
        input_tokens=a.input_tokens + b.input_tokens,
        output_tokens=a.output_tokens + b.output_tokens,
        custo_usd_estimado=round(a.custo_usd_estimado + b.custo_usd_estimado, 4),
        modelo=a.modelo,
    )
