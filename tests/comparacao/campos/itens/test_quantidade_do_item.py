"""Quantidade de um item em dois documentos: se dá para comparar e se é a mesma."""

from app.services.comparacao.campos.itens.quantidade_do_item import mesma_quantidade, unidades_de_familias_diferentes
from app.services.comparacao.campos.itens.tipos import ItemAgrupado


def _item(quantidade=None, unidade="UN"):
    total = None if quantidade is None else (unidade, float(quantidade))
    return ItemAgrupado(None, "Peça", None, total, None, unidade, [], [], "a0", 1)


def test_mesmo_total_na_mesma_familia_ou_com_unidade_em_branco():
    assert mesma_quantidade(_item(10), _item(10))
    assert mesma_quantidade(_item(10, ""), _item(10, "DZ"))


def test_total_diferente_familias_diferentes_ou_sem_quantidade_nao_e_a_mesma():
    assert not mesma_quantidade(_item(10), _item(11))
    assert not mesma_quantidade(_item(10, "CX"), _item(10, "DZ"))
    assert not mesma_quantidade(_item(), _item(1))


def test_familias_diferentes_so_com_unidade_dos_dois_lados():
    assert unidades_de_familias_diferentes(_item(10, "CX"), _item(10, "DZ"))
    assert not unidades_de_familias_diferentes(_item(10, ""), _item(10, "DZ"))
    assert not unidades_de_familias_diferentes(_item(), _item(1))
