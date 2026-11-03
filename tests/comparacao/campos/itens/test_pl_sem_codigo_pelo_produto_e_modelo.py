"""PL só com o nome do produto e o modelo casa com a linha da invoice que tem código, sem depender da ordem."""

from app.services.comparacao.campos.itens.produto_e_modelo import modelos_iguais, mesmo_produto_e_modelo
from app.services.comparacao.campos.itens.tipos import ItemAgrupado
from tests.comparacao.apoio import doc, item, mensagens, rodar

INVOICE = [
    item("AB-100-01", "Guide Wheel - Model: K40 - Loaders Brand: Talmex", 4, "PC", referencia="K40"),
    item("AB-100-02", "Guide Wheel - Model: K41 - Loaders Brand: Talmex", 4, "PC", referencia="K41"),
    item("AB-200-01", "Chain Belt - Model: K40 - Loaders Brand: Talmex - Without Grease", 8, "PC", referencia="K40"),
    item("AB-200-02", "Chain Belt - Model: K41 - Loaders Brand: Talmex - With Grease", 8, "PC", referencia="K41"),
    item("7Q1234", "Guide Wheel - Model: 550 - Loaders Brand: Rovix", 16, "PC", referencia="550"),
]
PL = [
    item(None, "Guide Wheel K41", 4, referencia="K41"),
    item(None, "Chain Belt K41 38 L (with Grease)", 8, referencia="K41"),
    item(None, "Guide Wheel K40", 4, referencia="K40"),
    item(None, "Guide Wheel RX550", 16, referencia="RX550"),
    item(None, "Chain Belt K40 37 L (without Grease)", 8, referencia="K40"),
]


def _itens(invoice, pl):
    return sorted(mensagens(rodar([doc("invoice", numero="1", itens=invoice),
                                   doc("packing_list", refs=["1"], itens=pl)]), "item"))


def test_pl_sem_codigo_casa_pelo_nome_do_produto_e_modelo():
    assert _itens(INVOICE, PL) == []


def test_ordem_das_linhas_nao_muda_o_resultado():
    assert _itens(INVOICE[::-1], PL) == _itens(INVOICE, PL[::-1]) == []


def test_quantidade_diferente_continua_apontada():
    pl = [*PL[:2], item(None, "Guide Wheel K40", 6, referencia="K40"), *PL[3:]]
    assert any("quantidade" in m for m in _itens(INVOICE, pl))


def test_modelo_diferente_continua_apontado():
    pl = [*PL[:2], item(None, "Guide Wheel K42", 4, referencia="K42"), *PL[3:]]
    assert _itens(INVOICE, pl)


def _agrupado(codigo, descricao, referencia):
    return ItemAgrupado(codigo, descricao, referencia, ("PCS", 8.0), "8", None, [], [], "a0", None)


def test_palavra_a_mais_depois_do_modelo_nao_casa():
    invoice = _agrupado("AB-200-02", "Chain Belt - Model: K41 - Brand: Talmex - With Grease", "K41")
    assert mesmo_produto_e_modelo(invoice, _agrupado(None, "Chain Belt K41 38 L (with Grease)", "K41"))
    assert not mesmo_produto_e_modelo(invoice, _agrupado(None, "Chain Belt K41 38 L (without Grease)", "K41"))
    assert not mesmo_produto_e_modelo(invoice, _agrupado(None, "Chain Belt K41 NOT GREASED", "K41"))


def test_modelo_contido_so_com_a_sigla_da_serie_na_frente():
    assert modelos_iguais(["550"], ["RX550"])
    assert not modelos_iguais(["K4"], ["K40"])
    assert not modelos_iguais(["550"], ["5500"])


def test_produto_com_outro_nome_continua_apontado():
    pl = [*PL[:3], item(None, "Guide Wheel Double RX550", 16, referencia="RX550"), *PL[4:]]
    assert _itens(INVOICE, pl)


def test_modelo_so_parecido_nao_conta_como_contido():
    pl = [*PL[:3], item(None, "Guide Wheel 5500", 16, referencia="5500"), *PL[4:]]
    assert _itens(INVOICE, pl)
