"""Razão social limpa para comparar: o nome inteiro por semelhança ou palavra a palavra."""

import difflib
import re

from app.services.comparacao.normalizacao.texto import sem_acento

# Duas listas de propósito: o nome inteiro tolera conectivos e ramo; palavra a palavra, artigos e ramo distinguem.

# Nome inteiro (semelhança): tira forma jurídica, conectivos e IMPORTACAO/EXPORTACAO/COMERCIO.
SUFIXOS_EMPRESA = {
    "LTD", "LTDA", "CO", "SAS", "SA", "INC", "LIMITED", "IMPORTACAO", "EXPORTACAO", "COMERCIO",
    "E", "DE", "DA", "DO", "AND", "THE", "EIRELI", "ME", "EPP", "CORP", "LLC", "GMBH", "SRL",
}

# Palavra a palavra: só forma jurídica e termos que não distinguem; artigos e IMPORT/EXPORT distinguem.
TERMOS_GENERICOS = {
    "LTD", "LTDA", "CO", "SAS", "SA", "INC", "LIMITED", "EIRELI", "ME", "EPP", "CORP", "LLC", "GMBH", "SRL",
    "SPA", "SRLS", "SNC", "AG", "KG", "BV", "NV", "PTE", "PT", "TBK", "ULC", "PLC", "LLP", "LP", "OY", "AB", "AS",
    "APS", "SARL", "SL", "SLU", "CV", "SCCM", "COOP", "COOPERATIVA", "SDAD", "SOCIEDAD", "SOCIEDADE", "SOCIETA",
    "UNIPERSONALE", "LIMITADA", "CORPORATION", "INCORPORATED", "COMPANY", "COMPANHIA", "COMPANIA", "CIA", "KK",
    "AZIENDA", "AGRICOLA", "BRANCH",
}

# Formas jurídicas que aparecem coladas no nome; só as que não terminam palavras comuns (CIA, SAS, SPA ficam fora).
FORMAS_COLAVEIS = ("LIMITED", "LTDA", "GMBH", "SARL", "LTD", "LLC", "INC", "SRL")

SIMILARIDADE_MINIMA_NOME = 0.85


def _maiusculas_sem_pontuacao(nome: str) -> str:
    return re.sub(r"[^A-Z0-9 ]", " ", sem_acento(nome).upper().replace(".", ""))


def normalizar_nome_empresa(nome: str) -> str:
    """'Capital Trade Importação e Exportação Ltda.' -> 'CAPITAL TRADE'."""
    return " ".join(p for p in _maiusculas_sem_pontuacao(nome).split() if p not in SUFIXOS_EMPRESA)


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


def palavras_distintivas(nome: str) -> tuple[str, ...]:
    """Palavras do nome, na ordem, sem forma jurídica: 'LA SERRA VERDE S.r.l.' -> ('LA', 'SERRA', 'VERDE')."""
    palavras = (_sem_forma_juridica_colada(_digitos_como_letras(p)) for p in _maiusculas_sem_pontuacao(nome).split())
    return tuple(p for p in palavras if p not in TERMOS_GENERICOS)


def _digitos_como_letras(palavra: str) -> str:
    """'K0RN' -> 'KORN': 0 e 1 no meio de uma palavra quase só de letras são O e I lidos errado."""
    letras = sum(c.isalpha() for c in palavra)
    if letras < 2 or len(palavra) - letras > 1:
        return palavra
    return palavra.replace("0", "O").replace("1", "I")


def _sem_forma_juridica_colada(palavra: str) -> str:
    """'KRONGMBH' -> 'KRON': forma jurídica de 3+ letras colada no fim, sobrando 3+ letras."""
    for termo in FORMAS_COLAVEIS:
        if palavra.endswith(termo) and len(palavra) - len(termo) >= 3:
            return palavra[: -len(termo)]
    return palavra
