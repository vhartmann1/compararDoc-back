"""Descrições do mesmo item: iguais, escritas de outro jeito, de outra mercadoria ou em contradição."""

from app.services.comparacao.campos.itens.descricoes_do_item import comparar_descricoes, entre_textos
from app.services.comparacao.campos.itens.tipos import ItemAgrupado
from tests.comparacao.apoio import doc, item, mensagens, rodar


def _item(descricao, codigo=None, referencia=None, lotes=(), descricoes=()):
    return ItemAgrupado(codigo, descricao, referencia, None, None, None, list(lotes), [], "a0", 1, tuple(descricoes))


def _classe(a, b):
    return comparar_descricoes(a, b).classe


def test_classes_entre_textos():
    assert entre_textos("Roda guia K40 Talmex", "Roda guia K40").classe == "igual"
    assert entre_textos("Fita PE 0.05x1000", "Fita 0.05 MM x 1000 MM POLIESTER").classe == "escrita_diferente"
    assert entre_textos("Vinho tinto Montalva 2021", "Rosado Peninsula vino").classe == "outra_mercadoria"
    assert entre_textos("FONTE 12V 150W", "FONTE 12V 120W").classe == "contradicao"


def test_mesmo_codigo_so_diverge_na_contradicao():
    assert _classe(_item("Bomba azul X", "C1"), _item("Motor verde Y", "C1")) == "igual"
    assert _classe(_item("Bomba azul X"), _item("Motor verde Y")) == "outra_mercadoria"
    assert _classe(_item("Fonte 150W", "C1"), _item("Fonte 120W", "C1")) == "contradicao"


def test_mesmo_lote_so_diverge_na_contradicao():
    assert _classe(_item("Vinho tinto", lotes=["L-1"]), _item("Garrafa reserva", lotes=["L1"])) == "igual"


def test_modelo_com_um_caractere_de_diferenca_e_contradicao():
    for a, b in (("ZK 455", "YK 455"), ("Trail-Max 10", "Trail-Max 100"), ("Wind-Ride 500", "Wind-Ride 50O"),
                 ("BX-7", "BX-9")):
        veredito = comparar_descricoes(_item("Bomba", "C1", a), _item("Bomba", "C1", b))
        assert veredito.classe == "contradicao" and veredito.contradicao.um_caractere, (a, b)


def test_modelo_so_com_a_marca_a_mais_e_o_mesmo():
    assert _classe(_item("Resina", referencia="ZK 455"), _item("Resina", referencia="RESIMAX ZK-455")) == "igual"


def test_linhas_juntas_pelo_codigo_valem_pela_mais_parecida():
    a = _item("Fonte", "C1", descricoes=("Fonte 150W", "Fonte 200W"))
    assert _classe(a, _item("Fonte", "C1", descricoes=("Fonte 200W", "Fonte 150W"))) == "igual"
    assert _classe(a, _item("Fonte", "C1", descricoes=("Fonte 150W", "Fonte 120W"))) == "contradicao"


def _par(invoice, pl, escaneados=None):
    return rodar([doc("invoice", numero="1", itens=[item("S1", invoice, 4, "PCS")])],
                 [doc("packing_list", refs=["1"], itens=[item("S1", pl, 4, "PCS")])], escaneados=escaneados)


def test_nota_de_leitura_so_no_caractere_de_diferenca_com_scan():
    [com_scan] = mensagens(_par("Sensor de carga TS100", "Sensor de carga TS200", [False, True]), "item")
    assert com_scan.endswith("Invoice TS100 × Packing List TS200; Packing List escaneado, pode ser leitura — "
                             "conferir na imagem")
    [sem_scan] = mensagens(_par("Sensor de carga TS100", "Sensor de carga TS200", [False, False]), "item")
    assert sem_scan.endswith("Invoice TS100 × Packing List TS200")
    [medida] = mensagens(_par("Fonte 150W", "Fonte 120W", [True, True]), "item")
    assert medida.endswith("Invoice 150 W × Packing List 120 W")  # medida não é erro de leitura de um caractere


def test_palavra_diferente_sem_contradicao_e_um_aviso_unico():
    r = rodar([doc("invoice", numero="1", itens=[item(None, "TUBO ACO GALVANIZADO 50x3", 4, "PCS"),
                                                 item(None, "CHAPA ACO LAMINADA 2x1000", 2, "PCS")])],
              [doc("packing_list", refs=["1"], itens=[item(None, "TUBO ACO PINTADO 50 MM x 3 MM", 4, "PCS"),
                                                      item(None, "CHAPA ACO POLIDA 2 MM x 1000 MM", 2, "PCS")])])
    assert mensagens(r, "item") == []
    assert [a for a in r.avisos if "de forma diferente" in a] == [
        "Itens: 2 descrições escritas de forma diferente entre os documentos (ex.: 'TUBO ACO GALVANIZADO 50x3' × "
        "'TUBO ACO PINTADO 50 MM x 3 MM'); medidas e modelos não se contradizem — confira se é o mesmo produto."]
