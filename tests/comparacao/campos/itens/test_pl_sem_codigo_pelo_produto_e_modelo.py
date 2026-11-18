"""PL só com o nome do produto e o modelo casa com a linha da invoice que tem código, sem depender da ordem."""

from app.services.comparacao.campos.itens.descricoes_do_item import entre_textos
from app.services.comparacao.campos.itens.fichas_da_descricao import em_comum, quase_iguais
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


def test_negacao_depois_do_modelo_e_contradicao():
    invoice = "Chain Belt - Model: K41 - Brand: Talmex - With Grease"
    assert entre_textos(invoice, "Chain Belt K41 38 L (with Grease)").classe != "contradicao"
    assert entre_textos(invoice, "Chain Belt K41 38 L (without Grease)").classe == "contradicao"


def test_modelo_contido_so_com_a_sigla_da_serie_na_frente():
    assert em_comum("Guide Wheel - Model: 550", "Guide Wheel RX550").so_b == frozenset()
    assert quase_iguais("K4", "K40") and quase_iguais("550", "5500")  # um dígito a mais é outro modelo
    assert not quase_iguais("550", "E550")  # só a letra de série na frente


def test_palavra_a_mais_no_nome_do_produto_e_so_aviso():
    pl = [*PL[:3], item(None, "Guide Wheel Double RX550", 16, referencia="RX550"), *PL[4:]]
    r = rodar([doc("invoice", numero="1", itens=INVOICE), doc("packing_list", refs=["1"], itens=pl)])
    assert mensagens(r, "item") == []
    assert any("3 descrições escritas de forma diferente" in a for a in r.avisos)  # as duas da corrente e esta


def test_modelo_so_parecido_nao_conta_como_contido():
    pl = [*PL[:3], item(None, "Guide Wheel 5500", 16, referencia="5500"), *PL[4:]]
    assert _itens(INVOICE, pl)
