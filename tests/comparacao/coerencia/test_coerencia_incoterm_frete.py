from tests.comparacao.apoio import doc, mensagens, rodar
from tests.comparacao.cenarios import caso_1, caso_4_v3, caso_6_v3


def test_caso_1_coerencia_fob_com_porto_de_destino():
    r = caso_1()
    assert mensagens(r, "coerencia") == [
        "Incoterm FOB NAVEGANTES (Invoice KTR27393803): FOB indica local de embarque/origem, mas NAVEGANTES é o destino"
    ]


def test_caso_4_awb_prepaid_com_incoterm_ef():
    r = caso_4_v3()
    coerencia = [d for d in r.divergencias if d.categoria == "coerencia"]
    assert [d.mensagem for d in coerencia] == [
        "AWB 123-4567 8901 com frete PREPAID, mas o incoterm da Invoice L30514262 é FOB "
        "(frete por conta do comprador; esperado COLLECT)",
        "AWB 123-4567 8901 com frete PREPAID, mas o incoterm da Invoice L30518777 é EXW "
        "(frete por conta do comprador; esperado COLLECT)",
    ]
    assert {d.comparacao_id for d in coerencia} == {"consolidado"}


def test_caso_6_incoterm_cfr_com_porto_diferente_do_bl():
    r = caso_6_v3()
    assert mensagens(r, "coerencia") == [
        "Incoterm CFR ITAPOA (Invoice 0077032707) × porto de descarga do BL 614092377 NAVEGANTES"
    ]


def test_frete_coerente_nao_gera_divergencia():
    r = rodar(
        [doc("invoice", 1, 2, ["39011010"], numero="1", incoterm=("CIF", "NAVEGANTES")),
         doc("packing_list", 1, 2, ["39011010"], numero="1")],
        [doc("conhecimento", 1, 2, ["39011010"], subtipo="BL", frete="PREPAID", destino="Navegantes, SC")],
    )
    assert mensagens(r, "coerencia") == []
    r = rodar(
        [doc("invoice", 1, 2, ["39011010"], numero="1", incoterm=("CIF", "NAVEGANTES")),
         doc("packing_list", 1, 2, ["39011010"], numero="1")],
        [doc("conhecimento", 1, 2, ["39011010"], subtipo="BL", frete="FREIGHT COLLECT", destino="NAVEGANTES")],
    )
    assert mensagens(r, "coerencia") == [
        "BL (a1.pdf) com frete COLLECT, mas o incoterm da Invoice 1 é CIF "
        "(frete por conta do vendedor; esperado PREPAID)"
    ]
