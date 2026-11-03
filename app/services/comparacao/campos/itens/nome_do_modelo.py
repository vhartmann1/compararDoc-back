"""Nome do modelo lido como código: 'ZX Storm' começa o 'ZX Storm-3pack' do outro documento."""

import re

from app.services.comparacao.campos.itens.tipos import ItemAgrupado
from app.services.comparacao.normalizacao.texto import sem_acento


def _palavras(texto: str) -> list[str]:
    return re.findall(r"[A-Z0-9]+", sem_acento(texto).upper())


def _nomes(item: ItemAgrupado) -> list[str]:
    return [n for n in (item.codigo, item.referencia) if n and n.strip()]


def resto_do_nome(curto: ItemAgrupado, longo: ItemAgrupado) -> list[str] | None:
    """Palavras que seguem o nome (código ou referência, ≥ 2 palavras) de `curto` num nome de `longo`."""
    for nome in _nomes(curto):
        inicio = _palavras(nome)
        if len(inicio) < 2:
            continue
        for outro in [*_nomes(longo), longo.descricao]:
            palavras = _palavras(outro)
            if len(palavras) > len(inicio) and palavras[: len(inicio)] == inicio:
                return palavras[len(inicio):]
    return None


def _variante_citada(curto: ItemAgrupado, resto: list[str]) -> bool:
    """Os números da variante ('3PACK') estão na descrição do outro lado ('com 3 petecas')."""
    numeros = set(re.findall(r"\d+", " ".join(resto)))
    return bool(numeros) and numeros <= set(re.findall(r"\d+", curto.descricao))


def unidades_de_familias_diferentes(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    """Caixas × dúzias: sem conversão, a quantidade não se compara; unidade em branco num lado não impede."""
    unidades = [x.quantidade[0] for x in (a, b) if x.quantidade and x.quantidade[0]]
    return len(unidades) == 2 and unidades[0] != unidades[1]


def nome_comeca_o_outro(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    """O código ou a referência de um começa um nome do outro, em palavras inteiras."""
    return resto_do_nome(a, b) is not None or resto_do_nome(b, a) is not None


def mesmo_modelo(a: ItemAgrupado, b: ItemAgrupado, com_variante: bool = False) -> bool:
    """Um nome começa o do outro, só com unidades de famílias diferentes; `com_variante` exige o desempate."""
    if not unidades_de_familias_diferentes(a, b):
        return False
    for curto, longo in ((a, b), (b, a)):
        resto = resto_do_nome(curto, longo)
        if resto is not None and (not com_variante or _variante_citada(curto, resto)):
            return True
    return False
