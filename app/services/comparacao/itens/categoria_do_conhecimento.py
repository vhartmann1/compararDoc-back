"""Descrição do conhecimento por categoria ('CABO USB'), contida em palavras inteiras na descrição dos itens."""

import re

from app.services.comparacao.itens.tipos import ItemAgrupado
from app.services.comparacao.normalizacao import normalizar_descricao


def _trechos(descricao: str) -> list[list[str]]:
    """O texto fora dos parênteses e o de cada parêntese ('POWER BANK (MOBILE POWER)'), já em palavras."""
    dentro = re.findall(r"\(([^()]*)\)", descricao)
    fora = re.sub(r"\([^()]*\)", " ", descricao)
    return [p for t in [fora, *dentro] if (p := normalizar_descricao(t).split())]


def _contem_palavras(palavras: list[str], descricao: str) -> bool:
    return f" {' '.join(palavras)} " in f" {normalizar_descricao(descricao)} "


def descreve_categoria(item: ItemAgrupado, itens: list[ItemAgrupado]) -> bool:
    """Algum trecho da descrição do conhecimento aparece, em palavras inteiras, na de algum item."""
    return any(_contem_palavras(t, outro.descricao) for t in _trechos(item.descricao) for outro in itens)
