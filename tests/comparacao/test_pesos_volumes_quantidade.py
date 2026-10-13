from tests.comparacao.apoio import campo, doc, item, mensagens, rodar, tres_ok


def test_tolerancia_peso():
    assert tres_ok(bruto=21200.5).status == "OK"
    r = tres_ok(bruto=21200.6)
    assert r.status == "DIVERGENTE"
    assert campo(r.comparacoes[0], "peso_bruto").status == "DIVERGENTE"


def test_bl_em_libras_convertido():
    r = rodar(
        [doc("invoice", 20000, 21200, numero="1"), doc("packing_list", 20000, 21200, numero="1")],
        [doc("conhecimento", 44092.452, 46737.0, unidade="LB", subtipo="BL")],
    )
    unica = r.comparacoes[0]
    assert campo(unica, "peso_liquido").status == "OK"
    assert campo(unica, "peso_bruto").valores["conhecimento"].exibicao == "21.199,55 kg"
    assert campo(unica, "peso_bruto").valores["conhecimento"].texto_original == "46737.0 LB"


def test_quantidade_unidades_equivalentes_e_diferentes():
    ok = rodar([doc("invoice", numero="1", quantidade=(24, "TON")), doc("packing_list", numero="1", quantidade=(24000, "KG"))])
    assert campo(ok.comparacoes[0], "quantidade").status == "OK"
    r = rodar([doc("invoice", numero="1", quantidade=(24, "TON")), doc("packing_list", numero="1", quantidade=(960, "BAGS"))])
    assert campo(r.comparacoes[0], "quantidade").status == "INSUFICIENTE"
    assert any("Quantidade em unidades" in a for a in r.avisos)


def test_quantidade_na_mesma_unidade_em_outro_idioma_confere():
    r = rodar([doc("invoice", numero="1", quantidade=(1200, "BOTELLAS")),
               doc("packing_list", numero="1", quantidade=(1200, "BOTTLES"))])
    assert campo(r.comparacoes[0], "quantidade").status == "OK"


def volumes_em(*por_documento):
    invoice, packing, bl = por_documento
    return rodar([doc("invoice", numero="1", volumes=invoice), doc("packing_list", numero="1", volumes=packing)],
                 [doc("conhecimento", subtipo="BL", volumes=bl)])


def test_volumes_em_embalagens_de_niveis_diferentes_nao_divergem():
    r = volumes_em((80, "CARTONS"), (80, "CAJAS"), (2, "PALLETS"))
    assert campo(r.comparacoes[0], "volumes").status == "INSUFICIENTE"
    assert any("Volumes em embalagens diferentes" in a for a in r.avisos)
    assert mensagens(r, "comparacao") == []


def test_volumes_divergem_dentro_da_mesma_embalagem():
    r = volumes_em((80, "CARTONS"), (75, "CTNS"), (2, "PALLETS"))
    assert campo(r.comparacoes[0], "volumes").status == "DIVERGENTE"


def test_volumes_em_embalagem_generica_comparam_pelo_numero():
    assert campo(volumes_em((80, "BAGS"), (80, "BAGS"), (80, "PACKAGES")).comparacoes[0], "volumes").status == "OK"
    assert campo(volumes_em((80, "BAGS"), (80, "BAGS"), (75, "PACKAGES")).comparacoes[0], "volumes").status == "DIVERGENTE"


def test_quantidade_com_fator_mil_explica_unidade_trocada():
    r = rodar(
        [doc("invoice", numero="1", quantidade=(24, "TO"), itens=[item("A", "PVC", 24, "TO")]),
         doc("packing_list", numero="1", quantidade=(24000, "TONS"), itens=[item("A", "PVC", 24000, "TONS")])],
    )
    nota = "provável unidade errada: 24.000 TONS equivale a 24 t se for kg"
    assert campo(r.comparacoes[0], "quantidade").status == "DIVERGENTE"
    assert mensagens(r, "comparacao") == [f"Quantidade: Invoice 24 TO × Packing List 24.000 TONS — {nota}"]
    assert mensagens(r, "item") == [f"Item A: quantidade Invoice 24 TO × Packing List 24.000 TONS — {nota}"]


def test_quantidade_diferente_sem_fator_mil_nao_ganha_nota():
    r = rodar([doc("invoice", numero="1", quantidade=(24, "TON")), doc("packing_list", numero="1", quantidade=(25, "TON"))])
    assert mensagens(r, "comparacao") == ["Quantidade: Invoice 24 TON × Packing List 25 TON"]
