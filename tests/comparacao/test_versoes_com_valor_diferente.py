"""Duas versões da mesma invoice com valores diferentes: divergência, não só aviso."""

from tests.comparacao.apoio import dinheiro, doc, item, mensagens, rodar


def _invoice(total, precos, versao="original", frete=None, seguro=None):
    itens = [item("A1", "Chave de boca", 10, valor=precos[0]), item("B2", "Alicate", 5, valor=precos[1])]
    return doc("invoice", numero="77", bruto=100, liquido=90, volumes=(4, "CTN"), itens=itens, versao=versao,
               valor_total=total, valor_frete=frete, valor_seguro=seguro)


def _pl():
    return doc("packing_list", numero="77", bruto=100, liquido=90, volumes=(4, "CTN"))


def _versoes(r):
    return [m for m in mensagens(r, "interna") if "versões" in m]


def test_mesma_invoice_com_valor_total_diferente_e_divergencia():
    r = rodar([_invoice(300.0, [100.0, 200.0]), _pl()], [_invoice(250.0, [80.0, 170.0])])
    assert _versoes(r) == ["Invoice 77: duas versões com valores diferentes — a0.pdf USD 300.00 × a1.pdf USD 250.00"]


def test_resultado_nao_depende_da_ordem_dos_arquivos():
    a = rodar([_invoice(300.0, [100.0, 200.0]), _pl()], [_invoice(250.0, [80.0, 170.0])])
    b = rodar([_invoice(250.0, [80.0, 170.0])], [_invoice(300.0, [100.0, 200.0]), _pl()])
    assert len(_versoes(a)) == len(_versoes(b)) == 1


def test_mesmo_total_com_precos_trocados_e_divergencia():
    r = rodar([_invoice(300.0, [100.0, 200.0]), _pl()], [_invoice(300.0, [120.0, 180.0])])
    assert len(_versoes(r)) == 1


def test_rascunho_e_original_com_o_mesmo_valor_nao_divergem():
    r = rodar([_invoice(300.0, [100.0, 200.0]), _pl()], [_invoice(300.0, [100.0, 200.0], versao="draft")])
    assert not _versoes(r)
    assert any(a.startswith("Mais de um documento") for a in r.avisos)


def test_total_do_excel_sem_arredondar_e_o_mesmo_valor():
    r = rodar([_invoice(300.004, [100.0, 200.004]), _pl()], [_invoice(300.0, [100.0, 200.0])])
    assert not _versoes(r)


def test_linha_que_nao_soma_o_total_e_leitura_duvidosa_e_nao_diverge():
    r = rodar([_invoice(300.0, [100.0, 200.0]), _pl()], [_invoice(300.0, [100.0, 230.0])])
    assert not _versoes(r)


def test_diferenca_igual_a_frete_e_seguro_declarados_nao_diverge_e_avisa():
    r = rodar([_invoice(330.0, [100.0, 200.0], frete=25.0, seguro=5.0), _pl()], [_invoice(300.0, [100.0, 200.0])])
    assert not _versoes(r)
    assert any("total FOB" in a for a in r.avisos)


def test_diferenca_igual_so_ao_frete_nao_diverge():
    r = rodar([_invoice(300.0, [100.0, 200.0]), _pl()], [_invoice(325.0, [100.0, 200.0], frete=25.0, seguro=5.0)])
    assert not _versoes(r)


def test_diferenca_que_nao_e_frete_continua_divergindo():
    r = rodar([_invoice(300.0, [100.0, 200.0], frete=25.0, seguro=5.0), _pl()], [_invoice(250.0, [80.0, 170.0])])
    assert len(_versoes(r)) == 1


def test_moedas_diferentes_nao_divergem():
    eur = _invoice(330.0, [110.0, 220.0])
    eur = eur.model_copy(update={"valor_total": dinheiro(330.0, "EUR")})
    r = rodar([_invoice(300.0, [100.0, 200.0]), _pl()], [eur])
    assert not _versoes(r)


def test_rascunho_com_valor_diferente_continua_divergindo():
    r = rodar([_invoice(300.0, [100.0, 200.0]), _pl()], [_invoice(250.0, [80.0, 170.0], versao="draft")])
    assert len(_versoes(r)) == 1
