from tests.comparacao.apoio import doc, mensagens, rodar
from tests.comparacao.cenarios import caso_1, caso_4_v3


def test_caso_1_internas():
    r = caso_1()
    internas = [d for d in r.divergencias if d.categoria == "interna"]
    assert [d.mensagem for d in internas] == [
        "Invoice KTR27393803: Coluna de preços em USD, mas o total está em euros",
        "Invoice KTR27393803: item QB-MS-312 marcado como FOC (sem valor comercial), mas cobrado USD 720,00",
        "Packing List KTR27393806: Pesos líquido e bruto trocados entre o total da tabela e o rodapé",
        "BL TRX4838205: Volumes: 351 no campo de volumes × 531 na linha do container",
    ]
    assert internas[0].documento.tipo == "invoice"
    assert internas[3].evidencia.startswith('"351 CARTONS"')
    assert all(d.comparacao_id is None and d.campo is None for d in internas)


def test_caso_4_assinatura_de_outra_empresa():
    r = caso_4_v3()
    assert mensagens(r, "interna") == [
        "Invoice L30514262: Assinatura de Delta Fast-Run Footwear Ltd., mas o cabeçalho é de "
        "Orion Pacific Trading Co., Ltd."
    ]


def test_status_divergente_so_por_interna():
    r = rodar(
        [doc("invoice", 20000, 21200, ["3901.10.10"], numero="INV1",
             internas=[("Total por extenso diferente do numérico", '"2300" × "Four thousand six hundred"')]),
         doc("packing_list", 20000, 21200, ["39011010"], numero="INV1")],
        [doc("conhecimento", subtipo="BL", liquido=20000, bruto=21200, ncms=["3901.10.10"])],
    )
    assert all(c.status == "OK" for c in r.comparacoes[0].campos)
    assert r.status == "DIVERGENTE"
