"""Quantidade de um item em dois documentos: se dá para comparar e se é a mesma."""

from app.services.comparacao.campos.itens.tipos import ItemAgrupado


def unidades_de_familias_diferentes(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    """Caixas × dúzias: sem conversão, a quantidade não se compara; unidade em branco num lado não impede."""
    unidades = [x.quantidade[0] for x in (a, b) if x.quantidade and x.quantidade[0]]
    return len(unidades) == 2 and unidades[0] != unidades[1]


def mesma_quantidade(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    """Mesmo total, em unidades da mesma família ou com a unidade em branco num dos lados."""
    if not (a.quantidade and b.quantidade) or unidades_de_familias_diferentes(a, b):
        return False
    return abs(a.quantidade[1] - b.quantidade[1]) <= 1e-6
