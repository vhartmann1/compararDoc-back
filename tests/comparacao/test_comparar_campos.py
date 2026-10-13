from tests.comparacao.apoio import campo, doc, rodar, tres_ok


def test_tudo_ok():
    r = tres_ok()
    assert r.status == "OK"
    assert [c.id for c in r.comparacoes] == ["unica"]
    unica = r.comparacoes[0]
    assert [c.chave for c in unica.colunas] == ["invoice", "packing_list", "conhecimento"]
    assert {c.status for c in unica.campos} == {"OK"}
    assert r.divergencias == []
    assert [d.tipo for d in r.documentos] == ["invoice", "packing_list", "conhecimento"]


def test_campos_sem_dado_nao_aparecem_exceto_pesos_e_ncm():
    r = rodar([doc("invoice", numero="1"), doc("packing_list", numero="1")], [doc("conhecimento", subtipo="BL")])
    nomes = [c.campo for c in r.comparacoes[0].campos]
    assert nomes == ["peso_liquido", "peso_bruto", "ncm", "numero_invoice"]
    assert campo(r.comparacoes[0], "peso_bruto").status == "NAO_ENCONTRADO"
    assert r.status == "INCOMPLETO"


def test_mensagem_divergencia_formatada_sem_prefixo():
    r = tres_ok(bruto=21250)
    assert [d.mensagem for d in r.divergencias] == ["Peso bruto: BL 21.250,00 kg × Invoice/Packing List 21.200,00 kg"]
    assert r.divergencias[0].comparacao_id == "unica"


def test_insuficiente_gera_aviso():
    r = tres_ok(liquido=None, ncms=[])
    assert campo(r.comparacoes[0], "peso_liquido").status == "OK"  # invoice e PL
    r = rodar([doc("invoice", 1, 2, ["39011010"], numero="1")], [doc("conhecimento", subtipo="BL")])
    assert campo(r.comparacoes[0], "ncm").status == "INSUFICIENTE"
    assert any("NCM informado só em Invoice" in a for a in r.avisos)
