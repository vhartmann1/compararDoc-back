"""Razão social sem forma jurídica e nomes de empresa equivalentes."""

import difflib
import re

from app.services.comparacao.normalizacao.texto import sem_acento

# Palavras ignoradas ao comparar razões sociais.
SUFIXOS_EMPRESA = {
    "LTD", "LTDA", "CO", "SAS", "SA", "INC", "LIMITED", "IMPORTACAO", "EXPORTACAO", "COMERCIO",
    "E", "DE", "DA", "DO", "AND", "THE", "EIRELI", "ME", "EPP", "CORP", "LLC", "GMBH", "SRL",
}


SIMILARIDADE_MINIMA_NOME = 0.85


def normalizar_nome_empresa(nome: str) -> str:
    """'Capital Trade Importação e Exportação Ltda.' -> 'CAPITAL TRADE'."""
    texto = re.sub(r"[^A-Z0-9 ]", " ", sem_acento(nome).upper().replace(".", ""))
    return " ".join(p for p in texto.split() if p not in SUFIXOS_EMPRESA)


def nomes_equivalentes(a: str, b: str) -> bool:
    """Similaridade ≥ 0,85 entre os nomes normalizados, ou um começa com o outro (sufixo colado por erro)."""
    na, nb = normalizar_nome_empresa(a), normalizar_nome_empresa(b)
    if not na or not nb:
        return na == nb
    if difflib.SequenceMatcher(None, na, nb).ratio() >= SIMILARIDADE_MINIMA_NOME:
        return True
    ca, cb = na.replace(" ", ""), nb.replace(" ", "")
    curto, longo = sorted((ca, cb), key=len)
    return len(curto) >= 6 and longo.startswith(curto)
