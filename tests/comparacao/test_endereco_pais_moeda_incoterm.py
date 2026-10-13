from tests.comparacao.apoio import campo, doc, mensagens, rodar
from tests.comparacao.cenarios import AURORA, END_COREIA, END_SHANGHAI, caso_4_v3


def test_pais_e_endereco_normalizados():
    r = rodar([
        doc("invoice", numero="1", exportador="X", pais_exportador="Republic of Korea", endereco_exportador="Rua A, 10 - Seoul"),
        doc("packing_list", numero="1", exportador="X", pais_exportador="KR", endereco_exportador="RUA A 10, SEOUL"),
    ])
    unica = r.comparacoes[0]
    assert campo(unica, "pais_exportador").status == "OK"
    assert campo(unica, "endereco_exportador").status == "OK"


def test_caso_1_endereco_com_cidades_diferentes_diverge():
    # textos quase iguais (similaridade alta), mas Shanghai × Gyeonggi-do
    invoice = doc("invoice", numero="1", exportador=AURORA, endereco_exportador=END_SHANGHAI, cidade_exportador="Shanghai")
    pl = doc("packing_list", numero="1", exportador=AURORA, endereco_exportador=END_COREIA, cidade_exportador="GYEONGGI-DO")
    r = rodar([invoice, pl])
    assert campo(r.comparacoes[0], "endereco_exportador").status == "DIVERGENTE"
    assert any(m.startswith("Endereço do exportador: ") for m in mensagens(r, "comparacao"))


def test_endereco_sem_cidade_dos_dois_lados_usa_similaridade():
    invoice = doc("invoice", numero="1", exportador=AURORA, endereco_exportador=END_SHANGHAI, cidade_exportador="SHANGHAI")
    pl = doc("packing_list", numero="1", exportador=AURORA, endereco_exportador=END_COREIA)
    assert campo(rodar([invoice, pl]).comparacoes[0], "endereco_exportador").status == "OK"


def test_endereco_cidade_e_provincia_do_mesmo_lugar_nao_diverge():
    a = "123 Jungang-ro, Hwaseong-si, Gyeonggi-do, Korea"
    invoice = doc("invoice", numero="1", exportador="X", endereco_exportador=a, cidade_exportador="HWASEONG-SI")
    pl = doc("packing_list", numero="1", exportador="X", endereco_exportador=a.upper(), cidade_exportador="Gyeonggi-do")
    assert campo(rodar([invoice, pl]).comparacoes[0], "endereco_exportador").status == "OK"


def test_caso_4_incoterms_diferentes_entre_invoices():
    r = caso_4_v3()
    consolidado = r.comparacoes[2]
    assert campo(consolidado, "incoterm").status == "DIVERGENTE"
    assert ("Consolidado — Incoterm: Invoice L30514262 FOB BEIJIN × Invoice L30518777 EXW BEIJIN"
            in mensagens(r, "comparacao"))
    assert campo(r.comparacoes[0], "incoterm").status == "INSUFICIENTE"  # só a invoice tem
