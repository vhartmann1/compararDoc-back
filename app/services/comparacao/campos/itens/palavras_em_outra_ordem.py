"""Mesmo item com as palavras em outra ordem: 'Gong 06" K-30 - Linha' × 'Linha - 6'' Gong'."""

import re

from app.services.comparacao.campos.itens.produto_e_modelo import mesma_quantidade
from app.services.comparacao.campos.itens.tipos import ItemAgrupado
from app.services.comparacao.normalizacao.texto import sem_acento

POLEGADAS = re.compile(r"(\d+(?:\.\d+)?)\s*(?:\"|''|’’|”|″|INCH(?:ES)?\b)")
PALAVRA = re.compile(r"[A-Z0-9]+(?:-[A-Z0-9]+)*")
GENERICAS = {"A", "AN", "THE", "OF", "AND", "DE", "DA", "DO", "DOS", "DAS", "E", "SERIES", "SERIE"}


def _texto(descricao: str) -> str:
    return sem_acento(descricao).upper()


def _medidas(descricao: str) -> tuple[float, ...]:
    """'Gong 06"' e "14'' Gong" -> (6.0,) e (14.0,): a medida em polegadas, sem o zero à esquerda."""
    return tuple(sorted(float(n) for n in POLEGADAS.findall(_texto(descricao))))


def _palavras(descricao: str) -> list[str]:
    """Palavras sem a medida, com o hífen interno tirado: 'K-30' -> 'K30'."""
    return [p.replace("-", "") for p in PALAVRA.findall(POLEGADAS.sub(" ", _texto(descricao)))]


def _colar(palavras: list[str], outras: set[str]) -> set[str]:
    """Duas palavras seguidas que o outro lado escreve juntas ('HI HAT' × 'HIHAT') viram uma, sem as genéricas."""
    coladas, i = [], 0
    while i < len(palavras):
        junta = "".join(palavras[i: i + 2])
        passo = 2 if i + 1 < len(palavras) and junta in outras and junta not in palavras else 1
        coladas.append(junta if passo == 2 else palavras[i])
        i += passo
    return set(coladas) - GENERICAS


def _codigo_curto(palavra: str) -> bool:
    return len(palavra) <= 6 and any(c.isalpha() for c in palavra) and any(c.isdigit() for c in palavra)


def mesmas_palavras(a: str, b: str) -> bool:
    """O mesmo conjunto de palavras; só um lado pode ter a mais, e só código curto de letra e número ('K30')."""
    pa, pb = _palavras(a), _palavras(b)
    ca, cb = _colar(pa, set(pb)), _colar(pb, set(pa))
    so_a, so_b = ca - cb, cb - ca
    sobra = so_a if not so_b else so_b if not so_a else None
    return sobra is not None and all(map(_codigo_curto, sobra)) and any(p.isalpha() for p in ca & cb)


def mesma_descricao_em_outra_ordem(a: str, b: str) -> bool:
    """Mesma medida em polegadas e mesmas palavras, em qualquer ordem."""
    medidas = _medidas(a)
    return bool(medidas) and medidas == _medidas(b) and mesmas_palavras(a, b)


def palavras_em_outra_ordem(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    """Mesma descrição em outra ordem e mesma quantidade: basta para casar a linha sem código."""
    return mesma_descricao_em_outra_ordem(a.descricao, b.descricao) and mesma_quantidade(a, b)
