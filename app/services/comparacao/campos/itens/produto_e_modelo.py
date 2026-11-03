"""Linha sem código ('Guide Wheel RX550') × linha com código: mesmo nome de produto antes do modelo e mesmo modelo."""

import re

from app.services.comparacao.campos.itens.nome_do_modelo import unidades_de_familias_diferentes
from app.services.comparacao.campos.itens.tipos import ItemAgrupado
from app.services.comparacao.normalizacao.texto import sem_acento

ROTULOS_DO_MODELO = {"MODEL", "MODELO", "MOD", "TYPE", "TIPO"}


def _palavras(texto: str) -> list[str]:
    return re.findall(r"[A-Z0-9]+", sem_acento(texto).upper())


def _modelo(item: ItemAgrupado) -> list[str]:
    return _palavras(item.referencia or "")


def modelos_iguais(a: list[str], b: list[str]) -> bool:
    """Iguais, ou só a sigla da série na frente de um deles: '320' × 'E320'; nunca 'D6' × 'D60'."""
    if not a or not b:
        return False
    curto, longo = sorted(("".join(a), "".join(b)), key=len)
    serie = longo[: len(longo) - len(curto)]
    return curto == longo or (longo.endswith(curto) and curto[0].isdigit() and serie.isalpha())


def _nome_e_resto(item: ItemAgrupado) -> tuple[list[str], list[str]] | None:
    """Palavras da descrição antes do modelo (sem o rótulo 'Model') e depois dele."""
    modelo, palavras = _modelo(item), _palavras(item.descricao)
    inicio = next((i for i in range(len(palavras)) if palavras[i: i + len(modelo)] == modelo), None)
    if not modelo or inicio is None:
        return None
    nome = palavras[:inicio]
    while nome and nome[-1] in ROTULOS_DO_MODELO:
        nome.pop()
    return (nome, palavras[inicio + len(modelo):]) if any(p.isalpha() for p in nome) else None


def _resto_citado(resto: list[str], outra: list[str]) -> bool:
    """Cada palavra do fim que não é medida nem sigla curta ('38', 'L', 'SF') está na outra descrição."""
    return all(p in outra for p in resto if p.isalpha() and len(p) >= 3)


def mesmo_produto_e_modelo(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    """A linha sem código tem o mesmo nome antes do modelo, o mesmo modelo e nada a mais depois dele."""
    for sem_codigo, outro in ((a, b), (b, a)):
        if sem_codigo.codigo or not modelos_iguais(_modelo(sem_codigo), _modelo(outro)):
            continue
        curto, longo = _nome_e_resto(sem_codigo), _nome_e_resto(outro)
        if curto and longo and curto[0] == longo[0] and _resto_citado(curto[1], _palavras(outro.descricao)):
            return True
    return False


def mesma_quantidade(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    """Mesmo total, em unidades da mesma família ou com a unidade em branco num dos lados."""
    if not (a.quantidade and b.quantidade) or unidades_de_familias_diferentes(a, b):
        return False
    return abs(a.quantidade[1] - b.quantidade[1]) <= 1e-6


def mesma_linha_sem_codigo(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    """Mesmo produto, mesmo modelo e mesma quantidade: basta para casar a linha sem código."""
    return mesmo_produto_e_modelo(a, b) and mesma_quantidade(a, b)
