"""Pareamento invoice × packing list e as colunas de cada comparação."""

from tests.comparacao.apoio import campo, doc, rodar
from tests.comparacao.cenarios import caso_4


def test_documento_faltando_incompleto():
    r = rodar([doc("invoice", 1, 2, ["39011010"], numero="1"), doc("packing_list", 1, 2, ["39011010"], numero="1")])
    assert r.status == "INCOMPLETO"
    assert any("Conhecimento" in a for a in r.avisos)


def test_conhecimentos_com_numeros_diferentes_viram_colunas():
    r = rodar(
        [doc("invoice", 1, 2, numero="1"), doc("packing_list", 1, 2, numero="1")],
        [doc("conhecimento", 1, 2, subtipo="BL", numero="A"), doc("conhecimento", 1, 2, subtipo="BL", numero="B")],
    )
    assert [c.chave for c in r.comparacoes[0].colunas] == ["invoice", "packing_list", "conhecimento", "conhecimento_2"]


def test_pareamento_forcado_gera_aviso_e_pl_sem_referencia_usa_proprio_numero():
    r = rodar([doc("invoice", 1, 2, numero="KTR27393803"), doc("packing_list", 1, 2, numero="KTR27393806")])
    assert [c.chave for c in r.comparacoes[0].colunas] == ["invoice", "packing_list"]
    assert any("não cita o número da invoice" in a for a in r.avisos)
    # PL sem referência usa o próprio número (caso 1: KTR27393806 × KTR27393803)
    assert campo(r.comparacoes[0], "numero_invoice").status == "DIVERGENTE"
    assert "Nº da invoice: Invoice KTR27393803 × Packing List KTR27393806" in [d.mensagem for d in r.divergencias]


def test_caso_4_estrutura():
    r = caso_4()
    assert [c.id for c in r.comparacoes] == ["par-1", "par-2", "consolidado"]
    consolidado = r.comparacoes[2]
    assert [c.chave for c in consolidado.colunas] == ["soma_invoices", "soma_packing_lists", "conhecimento"]
    assert [c.rotulo for c in consolidado.colunas] == ["Soma das 2 invoices", "Soma dos 2 packing lists", "AWB 123-4567 8901"]
    assert consolidado.titulo == "Soma das 2 invoices × Soma dos 2 packing lists × AWB 123-4567 8901"
    assert r.status == "DIVERGENTE"


def test_invoice_e_packing_list_com_o_mesmo_numero_e_series_diferentes_formam_par():
    r = rodar([doc("invoice", 100, 110, numero="FT A26/000123"), doc("packing_list", 100, 110, numero="GR A26/000123")])
    assert not any("sem packing list" in a or "sem invoice" in a for a in r.avisos)
    assert campo(r.comparacoes[0], "numero_invoice").status != "DIVERGENTE"
    assert campo(r.comparacoes[0], "peso_bruto").status == "OK"


def test_numero_proprio_do_packing_list_nao_vira_divergencia_de_invoice():
    r = rodar([doc("invoice", 100, 110, numero="91234567"), doc("packing_list", 100, 110, numero="80765432")])
    assert campo(r.comparacoes[0], "numero_invoice").status != "DIVERGENTE"
