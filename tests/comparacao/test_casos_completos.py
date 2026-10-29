from tests.comparacao.apoio import campo, mensagens
from tests.comparacao.cenarios import caso_1, caso_4, caso_6


def test_caso_4_par_divergencias():
    r = caso_4()
    par1, par2 = r.comparacoes[0], r.comparacoes[1]
    assert par1.titulo == "Invoice L30514262 × Packing List L30514262"
    assert campo(par1, "exportador").status == "DIVERGENTE"
    assert campo(par1, "peso_liquido").status == "OK"
    assert campo(par2, "peso_liquido").status == "DIVERGENTE"
    assert campo(par2, "quantidade").status == "DIVERGENTE"  # 200 PAIRS × 210 pair
    assert campo(par2, "peso_bruto").status == "OK"
    mensagens = [d.mensagem for d in r.divergencias]
    assert "Invoice L30518777 — Peso líquido: Invoice 113,20 kg × Packing List 130,20 kg" in mensagens
    assert ("Invoice L30514262 — Exportador: Invoice Orion Pacific Trading Co., Ltd. × "
            "Packing List Delta Fast-Run Footwear Ltd.") in mensagens


def test_caso_4_consolidado():
    r = caso_4()
    consolidado = r.comparacoes[2]
    bruto = campo(consolidado, "peso_bruto")
    assert bruto.status == "OK"  # 348,95 × 349,0 dentro da tolerância
    assert bruto.valores["soma_invoices"].exibicao == "348,95 kg"
    assert bruto.valores["soma_invoices"].arquivo_id is None
    assert bruto.valores["conhecimento"].exibicao == "349,00 kg"
    volumes = campo(consolidado, "volumes")
    assert volumes.status == "DIVERGENTE"
    assert volumes.valores["soma_packing_lists"].exibicao == "53 CNTR"
    assert "Consolidado — Volumes: AWB 4 DRUMS × Invoices/Packing Lists 53 CNTR" in [d.mensagem for d in r.divergencias]
    assert campo(consolidado, "ncm").status == "OK"
    assert campo(consolidado, "porto_destino").status == "OK"
    assert campo(consolidado, "porto_destino").valores["soma_invoices"].exibicao == "NAVEGANTES"
    assert campo(consolidado, "quantidade").valores["soma_invoices"].exibicao == "520 PAIRS"
    # CNPJ do consignee difere entre as invoices
    assert any("Consignatário" in a and "Soma das 2 invoices" in a for a in r.avisos)


def test_caso_6():
    r = caso_6()
    assert r.status == "DIVERGENTE"
    assert [c.id for c in r.comparacoes] == ["unica"]
    unica = r.comparacoes[0]
    status = {c.campo: c.status for c in unica.campos}
    assert status == {
        "peso_liquido": "OK",
        "peso_bruto": "DIVERGENTE",
        "volumes": "OK",
        "quantidade": "INSUFICIENTE",
        "ncm": "DIVERGENTE",
        "numero_invoice": "DIVERGENTE",
        "po": "DIVERGENTE",
        "exportador": "OK",
        "consignatario": "OK",
        "porto_origem": "OK",
        "porto_destino": "DIVERGENTE",
    }
    assert campo(unica, "volumes").valores["packing_list"] is None
    assert campo(unica, "numero_invoice").valores["packing_list"].exibicao == "70023077"
    mensagens = [d.mensagem for d in r.divergencias]
    assert mensagens == [
        "Peso bruto: BL 24.000,00 kg × Invoice/Packing List 24.592,00 kg",
        "NCM: Packing List cita o NCM 3904.10.20 no lugar do NCM 3904.10.10, que consta em Invoice/BL; pedir correção.",
        "Nº da invoice: Invoice 0077032707 × Packing List 70023077",
        "PO: Invoice 246731-01 × Packing List 243918-01",
        "Porto de destino: Invoice ITAPOA × BL NAVEGANTES",
        "Invoice 0077032707: consignatário sem CNPJ (o checklist da fatura pede o importador com CNPJ)",
    ]
    assert any("não cita o número da invoice" in a for a in r.avisos)
    assert len(r.documentos) == 3  # CO fica de fora


def test_caso_1_comparacao_v3():
    r = caso_1()
    unica = r.comparacoes[0]
    assert r.status == "DIVERGENTE"
    assert campo(unica, "pais_exportador").status == "DIVERGENTE"
    assert campo(unica, "numero_invoice").status == "DIVERGENTE"
    assert campo(unica, "incoterm").status == "OK"
    assert campo(unica, "incoterm").valores["invoice"].exibicao == "FOB NAVEGANTES"
    assert campo(unica, "pais_origem").status == "OK"
    assert campo(unica, "moeda").status == "INSUFICIENTE"
    assert mensagens(r, "comparacao") == [
        "Nº da invoice: Invoice KTR27393803 × Packing List KTR27393806",
        "PO: Invoice HBPX41357 × Packing List HBPX41458",
        "País do exportador: Packing List SOUTH KOREA × Invoice/BL CHINA",
    ]
    assert any("país de origem da mercadoria (KR)" in a for a in r.avisos)
