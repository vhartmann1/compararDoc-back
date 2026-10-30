"""PL consolidado que cita as invoices por outra numeração (uma por invoice): vai contra a soma."""

from app.services.comparacao.normalizacao.numeros_de_documento import numeros_quase_iguais
from tests.comparacao.apoio import campo, doc, rodar


def _processo(refs_principal, refs_complementar=("NF A 907101", "NF A 907102")):
    return rodar(
        [doc("invoice", None, 10, numero="907101", quantidade=(1, "EA")),
         doc("invoice", None, 20, numero="907102", quantidade=(2, "EA")),
         doc("invoice", None, 30, numero="907103", quantidade=(3, "EA"))],
        [doc("packing_list", None, 60, refs=refs_principal, quantidade=(6, "EA"))],
        [doc("packing_list", None, None, refs=refs_complementar)],
        [doc("conhecimento", None, 60, subtipo="CRT", numero="C1", refs=["A907101", "A907102", "A907103"])],
    )


def test_pl_consolidado_em_outra_numeracao_nao_forma_par_com_a_invoice_que_sobrou():
    r = _processo(["ERP-0901", "ERP-0902", "ERP-0903"])
    assert not [d.mensagem for d in r.divergencias if d.mensagem.startswith("Par ")]
    assert campo(r.comparacoes[-1], "numero_invoice").status == "OK"
    assert not any("sem packing list" in a or "não cita o número" in a for a in r.avisos)
    assert any("ERP-0901" in a and "outra numeração" in a for a in r.avisos)


def test_a_ordem_dos_arquivos_nao_muda_o_resultado():
    a = _processo(["ERP-0903", "ERP-0901", "ERP-0902"], ("NF A 907102", "NF A 907101"))
    b = _processo(["ERP-0901", "ERP-0902", "ERP-0903"])
    assert [d.mensagem for d in a.divergencias] == [d.mensagem for d in b.divergencias]


def test_numeros_a_mais_que_as_invoices_continuam_divergindo():
    r = _processo(["ERP-0901", "ERP-0902", "ERP-0903", "ERP-0904"])
    assert campo(r.comparacoes[-1], "numero_invoice").status == "DIVERGENTE"


def test_numero_que_parece_erro_de_digitacao_nao_e_outra_numeracao():
    r = _processo(["907104", "ERP-0902", "ERP-0903"])
    assert campo(r.comparacoes[-1], "numero_invoice").status == "DIVERGENTE"


def test_pl_que_cita_um_numero_errado_de_uma_invoice_so_continua_divergindo():
    r = rodar([doc("invoice", 50, 55, numero="907311"), doc("packing_list", 50, 55, refs=["ERP-0001"])])
    assert campo(r.comparacoes[0], "numero_invoice").status == "DIVERGENTE"


def test_numero_com_digito_a_menos_ou_a_mais_nao_e_outra_numeracao():
    for errado in ("90711", "9071030"):
        r = _processo([errado, "ERP-0902", "ERP-0903"])
        assert campo(r.comparacoes[-1], "numero_invoice").status == "DIVERGENTE", errado


def test_numeros_quase_iguais_aceita_caractere_a_mais_ou_a_menos():
    assert numeros_quase_iguais("A012345", "A0012345")
    assert numeros_quase_iguais("90711", "907101")
    assert not numeros_quase_iguais("90711", "ERP0902")


def test_pls_de_outro_processo_com_um_numero_cada_continuam_divergindo():
    r = rodar(
        [doc("invoice", None, 10, numero="907101"), doc("invoice", None, 20, numero="907102")],
        [doc("packing_list", None, 7, refs=["X-5501"]), doc("packing_list", None, 9, refs=["X-5502"])],
        [doc("conhecimento", None, 30, subtipo="CRT", numero="C1", refs=["907101", "907102"])],
    )
    assert campo(r.comparacoes[-1], "numero_invoice").status == "DIVERGENTE"
    assert any("sem packing list" in a for a in r.avisos)


def test_pl_certo_e_outro_com_numeros_estranhos_continua_divergindo():
    r = rodar(
        [doc("invoice", None, 10, numero="907101"), doc("invoice", None, 20, numero="907102")],
        [doc("packing_list", None, 10, refs=["NF A 907101"]), doc("packing_list", None, 50, refs=["Z-1", "Z-2"])],
        [doc("conhecimento", None, 30, subtipo="CRT", numero="C1", refs=["907101", "907102"])],
    )
    assert campo(r.comparacoes[-1], "numero_invoice").status == "DIVERGENTE"


def test_pl_em_outra_numeracao_nao_ganha_numero_que_nao_cita():
    r = _processo(["ERP-0901", "ERP-0902", "ERP-0903"])
    assert campo(r.comparacoes[-1], "numero_invoice").valores["soma_packing_lists"] is None
