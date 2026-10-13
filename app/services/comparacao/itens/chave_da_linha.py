"""Chave que identifica cada linha de item."""

import os
from collections import Counter

from app.services.comparacao.constantes import TAMANHO_CABECA_DESCRICAO, TAMANHO_MAX_DESCRICAO
from app.services.comparacao.encurtar_texto import encurtar


def _curta_pelo_que_distingue(texto: str, parecidas: list[str]) -> str:
    """Encurta mantendo o começo e o trecho em que `texto` difere das `parecidas`."""
    comum = os.path.commonprefix(parecidas)
    inicio = comum.rfind(" ") + 1
    cabeca = texto[:TAMANHO_CABECA_DESCRICAO].rsplit(" ", 1)[0]
    if inicio <= len(cabeca):
        return encurtar(texto)
    resto = texto[inicio:]
    cabe = TAMANHO_MAX_DESCRICAO - len(cabeca) - 2
    return f"{cabeca}… {resto if len(resto) <= cabe else resto[: cabe - 1].rstrip() + '…'}"


def chaves_unicas(rotulos: list[tuple[str | None, str]]) -> list[str]:
    """Chave de cada linha a partir de (código, descrição). Identifica a linha na tela: não pode repetir."""
    chaves = [codigo or encurtar(descricao) for codigo, descricao in rotulos]
    for chave in {c for c in chaves if chaves.count(c) > 1}:
        indices = [i for i, c in enumerate(chaves) if c == chave and not rotulos[i][0]]
        descricoes = [" ".join(rotulos[i][1].split()) for i in indices]
        for i, descricao in zip(indices, descricoes):
            chaves[i] = _curta_pelo_que_distingue(descricao, descricoes)

    total, ordem = Counter(chaves), Counter()
    unicas = []
    for chave in chaves:
        if total[chave] > 1:
            ordem[chave] += 1
            chave = f"{chave} ({ordem[chave]})"
        unicas.append(chave)
    return unicas
