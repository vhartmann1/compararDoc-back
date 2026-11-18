"""Código, lote, validade, referência e descrição de um item."""

import re

from app.services.comparacao.normalizacao.paises import SIGLAS_PAISES
from app.services.comparacao.normalizacao.texto import sem_acento, similaridade, so_letras_numeros

SIMILARIDADE_MINIMA_DESCRICAO = 0.85


def normalizar_codigo_item(codigo: str) -> str:
    """'4200000001004 TW' -> '4200000001004': a sigla do país de origem no fim não faz parte do código."""
    partes = sem_acento(codigo).upper().rsplit(None, 1)
    if len(partes) == 2 and partes[1] in SIGLAS_PAISES and re.search(r"\d", partes[0]):
        codigo = partes[0]
    return re.sub(r"[^A-Z0-9]", "", sem_acento(codigo).upper())


def normalizar_lote(lote: str) -> str:
    """'#LT2031C14-E' -> 'LT2031C14E'."""
    return re.sub(r"[\s#\-]", "", sem_acento(lote).upper())


def normalizar_validade(validade: str) -> str:
    """'Exp 11/2025' -> '11/2025'; 'Exp 03/29' -> '03/2029'; '20/02/2026' -> '02/2026'; '2026-02-20' -> '02/2026'."""
    texto = sem_acento(validade).upper()

    def ano(a: str) -> str:
        return a if len(a) == 4 else f"20{a.zfill(2)}"

    if m := re.search(r"\b(\d{4})[/.\-](\d{1,2})(?:[/.\-]\d{1,2})?\b", texto):
        return f"{int(m.group(2)):02d}/{m.group(1)}"
    if m := re.search(r"\b\d{1,2}[/.\-](\d{1,2})[/.\-](\d{2}|\d{4})\b", texto):
        return f"{int(m.group(1)):02d}/{ano(m.group(2))}"
    if m := re.search(r"\b(\d{1,2})[/.\-](\d{2}|\d{4})\b", texto):
        return f"{int(m.group(1)):02d}/{ano(m.group(2))}"
    return so_letras_numeros(texto)


def normalizar_descricao(descricao: str) -> str:
    return so_letras_numeros(descricao)


def normalizar_referencia(referencia: str) -> str:
    """'Polirex ZK-455' -> 'POLIREXZK455'."""
    return re.sub(r"[^A-Z0-9]", "", sem_acento(referencia).upper())


def descricoes_equivalentes(a: str, b: str) -> bool:
    """Similaridade >= 0,85 após normalizar, ou uma descrição contida na outra (PL costuma abreviar)."""
    na, nb = normalizar_descricao(a), normalizar_descricao(b)
    if not na or not nb:
        return na == nb
    curto, longo = sorted((na, nb), key=len)
    return similaridade(na, nb) >= SIMILARIDADE_MINIMA_DESCRICAO or (len(curto) >= 8 and curto in longo)
