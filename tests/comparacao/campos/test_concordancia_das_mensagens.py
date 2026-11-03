"""Sujeito, artigo e verbo concordam nas mensagens que citam documentos no plural."""

from app.services.comparacao.mensagens import nos_documentos, sujeito
from tests.comparacao.apoio import doc, mensagens_de, rodar


def test_sujeito_com_artigo_e_numero():
    assert sujeito(["Invoices"]) == ("as invoices", True)
    assert sujeito(["Invoice"]) == ("a invoice", False)
    assert sujeito(["Invoice", "Packing List"]) == ("a invoice e o packing list", True)
    assert sujeito(["BL"]) == ("o BL", False)
    assert nos_documentos(["Invoices", "BL"]) == "nas invoices e no BL"


def test_ncm_que_falta_na_invoice_no_singular():
    r = rodar([doc("invoice", 100, 110, ["8402.10.00"], numero="A1"),
               doc("packing_list", 100, 110, ["8402.10.00", "8402.20.00"], refs=["A1"])],
              [doc("conhecimento", None, 110, ["8402.10.00", "8402.20.00"], subtipo="BL")])
    assert mensagens_de(r, "ncm") == [
        "NCM: A invoice não cita o NCM 8402.20.00, que consta no packing list e no BL; pedir correção."]


def test_ncms_que_faltam_nas_invoices_no_plural():
    r = rodar([doc("invoice", 100, 110, ["8402.10.00"], numero="A1"),
               doc("packing_list", 100, 110, refs=["A1"])],
              [doc("invoice", 50, 60, ["8402.10.00"], numero="B2"),
               doc("packing_list", 50, 60, refs=["B2"])],
              [doc("conhecimento", None, 170, ["8402.10", "3215", "8528"], subtipo="BL")])
    assert "Consolidado — NCM: As invoices não citam os NCMs 3215, 8528, que constam no BL; " \
           "pedir correção." in mensagens_de(r, "ncm")
