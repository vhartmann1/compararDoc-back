"""Pareamento invoice × packing list pelo número citado."""

from tests.comparacao.apoio import campo, doc, rodar


def test_pl_que_cita_a_invoice_com_a_serie_fiscal_na_frente_forma_par():
    r = rodar([doc("invoice", 50, 55, numero="907311"), doc("packing_list", 50, 55, refs=["NF B 907311"])])
    assert not any("sem packing list" in a or "sem invoice" in a for a in r.avisos)
    assert campo(r.comparacoes[0], "numero_invoice").status == "OK"


def test_numero_de_invoice_diferente_no_fim_continua_divergindo():
    r = rodar([doc("invoice", 50, 55, numero="907311"), doc("packing_list", 50, 55, refs=["907312"])])
    assert any("não cita o número da invoice" in a for a in r.avisos)


def test_um_pl_para_varias_invoices_entra_so_na_soma():
    r = rodar(
        [doc("invoice", 10, 11, numero="5001"), doc("invoice", 20, 22, numero="5002")],
        [doc("packing_list", 30, 33, refs=["NF A 5001", "NF A 5002"])],
        [doc("conhecimento", None, 33, subtipo="BL", numero="B1", refs=["5001", "5002"])],
    )
    assert "Packing List cobre as invoices 5001, 5002: comparado só na soma." in r.avisos
    assert not any("sem packing list" in a or "sem invoice" in a for a in r.avisos)
    assert campo(r.comparacoes[-1], "peso_bruto").status == "OK"
