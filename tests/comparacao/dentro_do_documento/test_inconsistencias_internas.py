from tests.comparacao.apoio import doc, item, mensagens, rodar
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


def test_invoice_so_de_amostras_com_valor_para_a_alfandega_nao_acusa_foc_cobrado():
    r = rodar([doc("invoice", numero="S-1", itens=[
        item("A-1", "BONECO DE PELUCIA", 2, "PCS", foc=True, valor=12.5),
        item("A-2", "LUMINARIA INFANTIL", 1, "PCS", foc=True, valor=8.0),
    ])])
    assert not mensagens(r, "interna")
    assert "Invoice S-1: todos os itens sem valor comercial (amostras); os valores informados servem só para a alfândega." in r.avisos


def test_invoice_que_mistura_item_cobrado_e_foc_cobrado_continua_apontando():
    r = rodar([doc("invoice", numero="S-2", itens=[
        item("A-1", "BONECO DE PELUCIA", 20, "PCS", valor=250.0),
        item("A-2", "LUMINARIA INFANTIL", 1, "PCS", foc=True, valor=8.0),
    ])])
    assert mensagens(r, "interna") == ["Invoice S-2: item A-2 marcado como FOC (sem valor comercial), mas cobrado 8,00"]


def test_leitura_entre_parenteses_sai_da_mensagem():
    interna = ("Total escrito 5,00.00 (lido como 500,00) diferente da soma 5.000,00", "TOTAL 5,00.00")
    r = rodar([doc("invoice", numero="9", internas=[interna])])
    assert [d.mensagem for d in r.divergencias if d.categoria == "interna"] == [
        "Invoice 9: Total escrito 5,00.00 diferente da soma 5.000,00"
    ]
