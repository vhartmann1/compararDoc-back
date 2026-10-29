"""Diz, sem o modelo, se o arquivo é imagem ou scan (PDF sem texto visível na maioria das páginas)."""

import logging

from pypdf import PageObject, PdfReader
from pypdf.errors import DependencyError, PyPdfError

from app.schemas import ArquivoEntrada
from app.services.leitura.arquivo_para_conteudo import MEDIA_PDF, TIPOS_IMAGEM

logger = logging.getLogger(__name__)

# Página com menos caracteres visíveis que isso é praticamente imagem (carimbo, número de página).
MINIMO_CARACTERES_PAGINA = 30
# Modos de texto invisível (Tr 3 e 7): é a camada de OCR posta sobre a imagem do scan.
MODOS_INVISIVEIS = {3, 7}
OPERADORES_TEXTO = {b"Tj", b"TJ", b"'", b'"'}


def escaneado(arquivo: ArquivoEntrada) -> bool | None:
    """True para imagem ou PDF escaneado (com ou sem OCR); False para PDF digital, Word e Excel; None se o PDF não abre."""
    if arquivo.media_type in TIPOS_IMAGEM:
        return True
    if arquivo.media_type != MEDIA_PDF:
        return False
    try:
        paginas = PdfReader(arquivo.caminho).pages
        sem_texto = sum(1 for p in paginas if _caracteres_visiveis(p) < MINIMO_CARACTERES_PAGINA)
    except (PyPdfError, DependencyError):
        logger.warning("Não foi possível ver se %s é escaneado", arquivo.nome, exc_info=True)
        return None
    return bool(paginas) and sem_texto * 2 > len(paginas)


def _caracteres_visiveis(pagina: PageObject) -> int:
    """Bytes de texto desenhados em modo visível, seguindo o modo (Tr) salvo e restaurado por q/Q."""
    pilha, modo, total = [], 0, 0

    def operador(op: bytes, args: list, _cm, _tm) -> None:
        nonlocal modo, total
        if op == b"q":
            pilha.append(modo)
        elif op == b"Q" and pilha:
            modo = pilha.pop()
        elif op == b"Tr" and args:
            modo = int(args[0])
        elif op in OPERADORES_TEXTO and modo not in MODOS_INVISIVEIS:
            total += sum(len(s) for s in _textos(args))

    pagina.extract_text(visitor_operand_before=operador)
    return total


def _textos(args: list) -> list:
    """Strings de um operador de texto (TJ traz um array de strings e ajustes numéricos)."""
    itens = args[0] if args and isinstance(args[0], list) else args
    return [s for s in itens if isinstance(s, (str, bytes))]
