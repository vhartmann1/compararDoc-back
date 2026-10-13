from pathlib import Path

from app.schemas import (
    ArquivoEntrada,
    CodigoNcm,
    Contagem,
    DocumentoExtraido,
    ExtracaoArquivo,
    Incoterm,
    InconsistenciaInterna,
    ItemExtraido,
    Medida,
    Parte,
    Texto,
)
from app.services.comparador import comparar


def arquivo(id_):
    return ArquivoEntrada(id=id_, nome=f"{id_}.pdf", caminho=Path(f"/tmp/{id_}.pdf"), media_type="application/pdf")


def doc(tipo, liquido=None, bruto=None, ncms=(), versao="original", unidade="KG", pagina=1, numero=None,
        subtipo=None, refs=(), po=None, exportador=None, consignatario=None, origem=None, destino=None,
        volumes=None, quantidade=None, incoterm=None, frete=None, moeda=None, pais_origem=None,
        endereco_exportador=None, pais_exportador=None, assinatura=None, itens=(), internas=(),
        cidade_exportador=None):
    def m(v):
        return None if v is None else Medida(valor=v, unidade=unidade, texto_original=f"{v} {unidade}", pagina=pagina)

    def parte(p, endereco=None, pais=None, cidade=None):
        if p is None:
            return None
        nome, cnpj = p if isinstance(p, tuple) else (p, None)
        return Parte(nome=nome, cnpj=cnpj, endereco=endereco, cidade=cidade, pais=pais, pagina=pagina)

    def contagem(c):
        return None if c is None else Contagem(valor=c[0], unidade=c[1], texto_original=f"{c[0]} {c[1]}", pagina=pagina)

    def texto(t):
        return Texto(valor=t, pagina=pagina) if t else None

    def inc(i):
        if i is None:
            return None
        codigo, local = i if isinstance(i, tuple) else (i, None)
        return Incoterm(codigo=codigo, local=local, texto_original=f"{codigo} {local or ''}".strip(), pagina=pagina)

    return DocumentoExtraido(
        tipo=tipo, subtipo=subtipo, paginas=[pagina] if pagina else [], numero=numero, invoices_referenciadas=list(refs), po=po,
        versao=versao, exportador=parte(exportador, endereco_exportador, pais_exportador, cidade_exportador),
        consignatario=parte(consignatario),
        porto_origem=texto(origem), porto_destino=texto(destino),
        peso_liquido_total=m(liquido), peso_bruto_total=m(bruto),
        volumes_total=contagem(volumes), quantidade_total=contagem(quantidade),
        ncms=[CodigoNcm(codigo=c, pagina=pagina) for c in ncms],
        incoterm=inc(incoterm), frete=texto(frete), moeda=texto(moeda), pais_origem=texto(pais_origem),
        emitente_assinatura=assinatura, itens=list(itens),
        inconsistencias_internas=[InconsistenciaInterna(descricao=d, evidencia=e, pagina=pagina) for d, e in internas],
    )


def item(codigo, descricao, quantidade=None, unidade=None, lotes=(), validades=(), foc=False, valor=None, pagina=None,
         referencia=None):
    return ItemExtraido(codigo=codigo, descricao=descricao, referencia=referencia, lotes=list(lotes),
                        validades=list(validades), quantidade=quantidade, unidade=unidade, sem_valor_comercial=foc,
                        valor_total=valor, pagina=pagina)


def rodar(*docs_por_arquivo, modalidade=None):
    entradas = [(arquivo(f"a{i}"), ExtracaoArquivo(documentos=list(docs))) for i, docs in enumerate(docs_por_arquivo)]
    return comparar(entradas, modalidade)


def campo(comparacao, nome):
    return next((c for c in comparacao.campos if c.campo == nome), None)


def tres_ok(**bl):
    return rodar(
        [doc("invoice", 20000, 21200, ["3901.10.10"], numero="INV1"),
         doc("packing_list", 20000, 21200, ["39011010"], numero="INV1")],
        [doc("conhecimento", subtipo="BL", **({"liquido": 20000, "bruto": 21200, "ncms": ["3901.10.10"]} | bl))],
    )


# ---------------------------------------------------------------------------
# Caso simples
# ---------------------------------------------------------------------------

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


def test_tolerancia_peso():
    assert tres_ok(bruto=21200.5).status == "OK"
    r = tres_ok(bruto=21200.6)
    assert r.status == "DIVERGENTE"
    assert campo(r.comparacoes[0], "peso_bruto").status == "DIVERGENTE"


def test_mensagem_divergencia_formatada_sem_prefixo():
    r = tres_ok(bruto=21250)
    assert [d.mensagem for d in r.divergencias] == ["Peso bruto: BL 21.250,00 kg × Invoice/Packing List 21.200,00 kg"]
    assert r.divergencias[0].comparacao_id == "unica"


def test_bl_em_libras_convertido():
    r = rodar(
        [doc("invoice", 20000, 21200, numero="1"), doc("packing_list", 20000, 21200, numero="1")],
        [doc("conhecimento", 44092.452, 46737.0, unidade="LB", subtipo="BL")],
    )
    unica = r.comparacoes[0]
    assert campo(unica, "peso_liquido").status == "OK"
    assert campo(unica, "peso_bruto").valores["conhecimento"].exibicao == "21.199,55 kg"
    assert campo(unica, "peso_bruto").valores["conhecimento"].texto_original == "46737.0 LB"


def test_ncm_hs_compara_6_digitos():
    r = tres_ok(ncms=["HS 390110"])
    assert campo(r.comparacoes[0], "ncm").status == "OK"
    assert any("6 primeiros dígitos" in a for a in r.avisos)


def test_ncm_divergente():
    r = tres_ok(ncms=["3901.20.10"])
    assert r.divergencias[0].mensagem == "NCM: BL 3901.20.10 × Invoice/Packing List 3901.10.10"


def test_insuficiente_gera_aviso():
    r = tres_ok(liquido=None, ncms=[])
    assert campo(r.comparacoes[0], "peso_liquido").status == "OK"  # invoice e PL
    r = rodar([doc("invoice", 1, 2, ["39011010"], numero="1")], [doc("conhecimento", subtipo="BL")])
    assert campo(r.comparacoes[0], "ncm").status == "INSUFICIENTE"
    assert any("NCM informado só em Invoice" in a for a in r.avisos)


def test_documento_faltando_incompleto():
    r = rodar([doc("invoice", 1, 2, ["39011010"], numero="1"), doc("packing_list", 1, 2, ["39011010"], numero="1")])
    assert r.status == "INCOMPLETO"
    assert any("Conhecimento" in a for a in r.avisos)


def test_prioridade_de_versao_mesmo_numero():
    r = rodar(
        [doc("invoice", 1, 2, numero="1"), doc("packing_list", 1, 2, numero="1")],
        [doc("conhecimento", 1, 2, subtipo="BL", numero="BL9", versao="original")],
        [doc("conhecimento", 1, 3, subtipo="BL", numero="BL9", versao="draft")],
    )
    conhecimentos = [d for d in r.documentos if d.tipo == "conhecimento"]
    assert len(conhecimentos) == 1 and conhecimentos[0].versao == "original"
    assert campo(r.comparacoes[0], "peso_bruto").status == "OK"
    assert any("Mais de um documento BL BL9" in a for a in r.avisos)


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


def test_quantidade_unidades_equivalentes_e_diferentes():
    ok = rodar([doc("invoice", numero="1", quantidade=(24, "TON")), doc("packing_list", numero="1", quantidade=(24000, "KG"))])
    assert campo(ok.comparacoes[0], "quantidade").status == "OK"
    r = rodar([doc("invoice", numero="1", quantidade=(24, "TON")), doc("packing_list", numero="1", quantidade=(960, "BAGS"))])
    assert campo(r.comparacoes[0], "quantidade").status == "INSUFICIENTE"
    assert any("Quantidade em unidades" in a for a in r.avisos)


def test_parte_por_cnpj_quando_os_dois_tem():
    r = rodar([
        doc("invoice", numero="1", consignatario=("AtlasFit Ltda", "12.345.678/0005-80")),
        doc("packing_list", numero="1", consignatario=("ATLASFIT BRASIL LTDA", "12345678000190")),
    ])
    c = campo(r.comparacoes[0], "consignatario")
    assert c.status == "DIVERGENTE"
    assert c.valores["invoice"].exibicao == "AtlasFit Ltda (12.345.678/0005-80)"


CAPITAL = ("CAPITAL TRADE IMPORTACAO E EXPORTACAO LTDA.", "07.872.326/0001-58")


def consignado_a_capital(modalidade):
    return rodar(
        [doc("invoice", numero="1", consignatario=("AtlasFit Ltda", "12.345.678/0005-80")),
         doc("packing_list", numero="1", consignatario=("ATLASFIT LTDA", "12345678000580"))],
        [doc("conhecimento", subtipo="BL", consignatario=CAPITAL)],
        modalidade=modalidade,
    )


def test_capital_no_conhecimento_aceita_em_conta_e_ordem_e_encomenda():
    for modalidade in ("conta_e_ordem", "encomenda"):
        r = consignado_a_capital(modalidade)
        assert campo(r.comparacoes[0], "consignatario").status == "OK"
        assert not [d for d in r.divergencias if d.campo == "consignatario"]
        assert any("Capital Trade" in a and "aceito" in a for a in r.avisos)


def test_capital_no_conhecimento_diverge_em_propria_ou_sem_modalidade():
    for modalidade in ("propria", None):
        r = consignado_a_capital(modalidade)
        assert campo(r.comparacoes[0], "consignatario").status == "DIVERGENTE"


def test_conta_e_ordem_nao_esconde_divergencia_entre_invoice_e_pl():
    r = rodar(
        [doc("invoice", numero="1", consignatario=("AtlasFit Ltda", "12.345.678/0005-80")),
         doc("packing_list", numero="1", consignatario=("Outra Empresa Ltda", "99.999.999/0001-99"))],
        [doc("conhecimento", subtipo="BL", consignatario=CAPITAL)],
        modalidade="conta_e_ordem",
    )
    assert campo(r.comparacoes[0], "consignatario").status == "DIVERGENTE"


# ---------------------------------------------------------------------------
# Caso 4 (CASOS_TESTE.md): 2 invoices + 2 PLs + 1 AWB
# ---------------------------------------------------------------------------

ATLASFIT = "AtlasFit Brasil Importação e Comércio de Artigos Esportivos Ltda."
FAST_RUN = "Delta Fast-Run Footwear Ltd."


def caso_4():
    def par(numero, exp_inv, cnpj, nw_inv, nw_pl, gw, q_inv, q_pl, ctn):
        comum = dict(numero=numero, ncms=["6402.19.00"], bruto=gw, volumes=(ctn, "CNTR"), pagina=None,
                     consignatario=(ATLASFIT, cnpj), origem="BEIJIN , CHINA", destino="NAVEGANTES - SC BRASIL")
        return [
            doc("invoice", nw_inv, exportador=exp_inv, quantidade=(q_inv, "PAIRS"), versao="desconhecida", **comum),
            doc("packing_list", nw_pl, exportador=FAST_RUN, quantidade=(q_pl, "pair"), versao="desconhecida", **comum),
        ]

    return rodar(
        par("L30514262", "Orion Pacific Trading Co., Ltd.", "12.345.678/0001-90", 216.5, 216.5, 216.95, 320, 320, 32),
        par("L30518777", FAST_RUN, "12.345.678/0005-80", 113.2, 130.2, 132.0, 200, 210, 21),
        [doc("conhecimento", None, 349.0, ["NCM NO6402.19.00"], subtipo="AWB", numero="123-4567 8901",
             exportador="DELTA FAST-RUN FOOTWEAR LTD.", volumes=(4, "DRUMS"), origem="BEIJIN", destino="NAVEGANTES",
             consignatario=("CAPITAL TRADE IMPORTACAO E EXPORTACAO LTDA.", "07.872.326/0001-58"), pagina=None)],
    )


def test_caso_4_estrutura():
    r = caso_4()
    assert [c.id for c in r.comparacoes] == ["par-1", "par-2", "consolidado"]
    consolidado = r.comparacoes[2]
    assert [c.chave for c in consolidado.colunas] == ["soma_invoices", "soma_packing_lists", "conhecimento"]
    assert [c.rotulo for c in consolidado.colunas] == ["Soma das 2 invoices", "Soma dos 2 packing lists", "AWB 123-4567 8901"]
    assert consolidado.titulo == "Soma das 2 invoices × Soma dos 2 packing lists × AWB 123-4567 8901"
    assert r.status == "DIVERGENTE"


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
    assert "Par 2 (L30518777) — Peso líquido: Invoice 113,20 kg × Packing List 130,20 kg" in mensagens
    assert ("Par 1 (L30514262) — Exportador: Invoice Orion Pacific Trading Co., Ltd. × "
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


# ---------------------------------------------------------------------------
# Caso 6 (CASOS_TESTE.md): Invoice + PL + BL (+ CO ignorado)
# ---------------------------------------------------------------------------

SERRANA = "SERRANA POLÍMEROS S.A.S."


def caso_6():
    return rodar(
        [doc("invoice", 24000, 24592, ["3904.10.10"], numero="0077032707", po="246731-01", exportador=SERRANA,
             consignatario="CAPITAL TRADE IMPORTACAO EEXPORTACAO LTDA", origem="CARTAGENA", destino="ITAPOA",
             volumes=(16, "PALLETS"), quantidade=(24, "TO"), versao="desconhecida", pagina=None)],
        [doc("packing_list", 24000, 24592, ["39.04.10.20"], numero="48273916", refs=["70023077", "0070023077"],
             po="243918-01", exportador=SERRANA, consignatario="CAPITAL TRADE IMPORTACAO EEXPORTACAO LTDA",
             quantidade=(960, "BAGS"), versao="desconhecida", pagina=None)],
        [doc("conhecimento", 24000, 24000, ["39.04.10.10"], subtipo="BL", numero="614092377", exportador=SERRANA,
             consignatario=("CAPITAL TRADE IMPORTACAO E EXPORTACAO LTDA.", "07.872.326/0001-58"),
             origem="CARTAGENA", destino="NAVEGANTES", volumes=(16, "PALLETS"), pagina=None)],
        [doc("outro", subtipo="CO", pagina=None)],
    )


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
        "NCM: Packing List 3904.10.20 × Invoice/BL 3904.10.10",
        "Nº da invoice: Invoice 0077032707 × Packing List 70023077",
        "PO: Invoice 246731-01 × Packing List 243918-01",
        "Porto de destino: Invoice ITAPOA × BL NAVEGANTES",
    ]
    assert any("não cita o número da invoice" in a for a in r.avisos)
    assert len(r.documentos) == 3  # CO fica de fora


def test_ncm_posicao_redundante_no_mesmo_documento_e_ignorada():
    r = tres_ok(ncms=["3901", "3901.10.10"])
    ncm = campo(r.comparacoes[0], "ncm")
    assert ncm.status == "OK"
    assert ncm.valores["conhecimento"].exibicao == "3901.10.10"
    assert not any("primeiros dígitos" in a for a in r.avisos)


# ---------------------------------------------------------------------------
# v3 — gabaritos completos (CASOS_TESTE.md, "setas do analista")
# ---------------------------------------------------------------------------

AURORA = "Aurora Silk Co."
END_SHANGHAI = ("Unit 310, Building C, East Industrial Park, No. 27 Huaxin Road, Pudong New District, "
                "Shanghai, 200120, China")
END_COREIA = ("Unit 310, Building C, East Industrial Park, No. 27 Huaxin Road, Pudong New District, "
              "Gyeonggi-do, South Korea")
CAPITAL_DOC = ("Capital Trade Importação e Exportação Ltda.", "07.872.326/0001-58")


def caso_1(itens_bl=()):
    comum = dict(consignatario=CAPITAL_DOC, origem="SHEKOU", destino="NAVEGANTES", liquido=2827, bruto=3178,
                 volumes=(351, "CTNS"), quantidade=(2100, "PCS"), versao="desconhecida", pagina=None,
                 incoterm=("Fob", "Navegantes"), pais_origem="KR", exportador=AURORA)
    invoice = doc(
        "invoice", numero="KTR27393803", po="HBPX41357", moeda="USD", endereco_exportador=END_SHANGHAI,
        pais_exportador="CHINA", **comum,
        itens=[
            item("QB-SR-102", "Fresh Balance Toner – 150ml", 500, "PCS", ["#LT20310327A"], ["Exp 03/29"], valor=2730),
            item("QB-TN-505", "Soothing Eye Patch – 60pcs", 500, "PCS", ["#LT2031C14-E"], ["Exp 09/28"], valor=3750),
            item("OA-UV-088", "Sun Guard Sunscreen SPF 50+ – 50g", 500, "PCS", ["#SH2601-SUN"], ["Exp 01/2029"], valor=4800),
            item("QB-MS-312", "Deep Repair Sleeping Mask – 80ml", 500, "PCS", ["#LT2031-M03"], ["Exp 11/2025"], valor=3600),
            item("QB-MS-312", "Deep Repair Sleeping Mask – 80ml", 100, "PCS", ["#LT2031-M06"], ["Exp 11/2028"],
                 foc=True, valor=720),
        ],
        internas=[("Coluna de preços em USD, mas o total está em euros", '"USD" × "€ 15.600,00" / "euros"')],
    )
    pl = doc(
        "packing_list", numero="KTR27393806", po="HBPX41458", endereco_exportador=END_COREIA,
        pais_exportador="SOUTH KOREA", **comum,
        itens=[
            item("QB-SR-102", "Fresh Balance Toner – 150ml", 500, "PCS", ["#LT20310327A"], ["Exp 03/29"]),
            item("QB-TN-505", "Soothing Eye Patch – 60pcs", 500, "PCS", ["#LT2031C20-E"], ["Exp 09/28"]),
            item("OA-UV-088", "Sun Guard Sunscreen SPF 50+ – 50g", 500, "PCS", ["#SH2601-SUN"], ["Exp 01/2029"]),
            item("QB-MS-312", "Deep Repair Sleeping Mask – 80ml", 600, "PCS", ["#LT2031-M03", "#LT2031-M06"],
                 ["Exp 11/2025"]),
        ],
        internas=[("Pesos líquido e bruto trocados entre o total da tabela e o rodapé",
                   "Total: 2.827,00 | 3.178,00 × rodapé N.W 3.178,00 / G.W 2.827,00")],
    )
    bl = doc(
        "conhecimento", subtipo="BL", numero="TRX4838205", exportador="AURORA SILK CO.", consignatario=CAPITAL_DOC,
        endereco_exportador=END_SHANGHAI.upper(), pais_exportador="CHINA", origem="SHEKOU", destino="NAVEGANTES",
        bruto=3178, volumes=(351, "CARTONS"), ncms=["3304"], frete="COLLECT", versao="desconhecida", pagina=None,
        itens=itens_bl,
        internas=[("Volumes: 351 no campo de volumes × 531 na linha do container",
                   '"351 CARTONS" × "40 NOR/531CARTONS/3.178,00KGS"')],
    )
    return rodar([invoice], [pl], [bl])


def mensagens(r, categoria):
    return [d.mensagem for d in r.divergencias if d.categoria == categoria]


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


def test_caso_1_coerencia_fob_com_porto_de_destino():
    r = caso_1()
    assert mensagens(r, "coerencia") == [
        "Incoterm FOB NAVEGANTES (Invoice KTR27393803): FOB indica local de embarque/origem, mas NAVEGANTES é o destino"
    ]
    # BL COLLECT com FOB: frete coerente, sem divergência de frete


def test_caso_1_itens():
    r = caso_1()
    assert len(r.itens) == 1
    linhas = {l.chave: l for l in r.itens[0].linhas}
    assert list(linhas) == ["QB-SR-102", "QB-TN-505", "OA-UV-088", "QB-MS-312"]
    assert linhas["QB-SR-102"].status == "OK"
    assert linhas["QB-TN-505"].diferencas == ["lote"]
    # invoice 500 + 100 agrupados = 600 do PL; os lotes batem, a validade não
    assert linhas["QB-MS-312"].diferencas == ["validade"]
    assert linhas["QB-MS-312"].valores["invoice"].quantidade == "600 PCS"
    assert mensagens(r, "item") == [
        "Item QB-TN-505: lote Invoice #LT2031C14-E × Packing List #LT2031C20-E",
        "Item QB-MS-312: validade Invoice 11/2025, 11/2028 × Packing List 11/2025",
    ]
    assert [d.item_chave for d in r.divergencias if d.categoria == "item"] == ["QB-TN-505", "QB-MS-312"]
    assert all(d.item_chave is None for d in r.divergencias if d.categoria != "item")


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


def caso_4_v3(itens_par=((), ()), itens_awb=()):
    def par(numero, exp_inv, assinatura, incoterm, cnpj, nw_inv, nw_pl, gw, q_inv, q_pl, ctn, itens=()):
        comum = dict(numero=numero, ncms=["6402.19.00"], bruto=gw, volumes=(ctn, "CNTR"), pagina=None,
                     consignatario=(ATLASFIT, cnpj), origem="BEIJIN , CHINA", destino="NAVEGANTES - SC BRASIL",
                     versao="desconhecida")
        internas = [(f"Assinatura de {assinatura}, mas o cabeçalho é de {exp_inv}",
                     f'"{exp_inv}" × "{assinatura}"')] if assinatura != exp_inv else []
        return [
            doc("invoice", nw_inv, exportador=exp_inv, quantidade=(q_inv, "PAIRS"), incoterm=(incoterm, "BEIJIN"),
                moeda="USD", assinatura=assinatura, internas=internas, itens=itens, **comum),
            doc("packing_list", nw_pl, exportador=FAST_RUN, quantidade=(q_pl, "pair"), itens=itens, **comum),
        ]

    return rodar(
        par("L30514262", "Orion Pacific Trading Co., Ltd.", FAST_RUN, "FOB", "12.345.678/0001-90",
            216.5, 216.5, 216.95, 320, 320, 32, itens_par[0]),
        par("L30518777", FAST_RUN, FAST_RUN, "EXW", "12.345.678/0005-80", 113.2, 130.2, 132.0, 200, 210, 21, itens_par[1]),
        [doc("conhecimento", None, 349.0, ["NCM NO6402.19.00"], subtipo="AWB", numero="123-4567 8901",
             exportador="DELTA FAST-RUN FOOTWEAR LTD.", volumes=(4, "DRUMS"), origem="BEIJIN", destino="NAVEGANTES",
             consignatario=CAPITAL, frete="PP", pagina=None, itens=itens_awb)],
    )


def test_caso_4_incoterms_diferentes_entre_invoices():
    r = caso_4_v3()
    consolidado = r.comparacoes[2]
    assert campo(consolidado, "incoterm").status == "DIVERGENTE"
    assert ("Consolidado — Incoterm: Invoice L30514262 FOB BEIJIN × Invoice L30518777 EXW BEIJIN"
            in mensagens(r, "comparacao"))
    assert campo(r.comparacoes[0], "incoterm").status == "INSUFICIENTE"  # só a invoice tem


def test_caso_4_awb_prepaid_com_incoterm_ef():
    r = caso_4_v3()
    coerencia = [d for d in r.divergencias if d.categoria == "coerencia"]
    assert [d.mensagem for d in coerencia] == [
        "AWB 123-4567 8901 com frete PREPAID, mas o incoterm da Invoice L30514262 é FOB "
        "(frete por conta do comprador; esperado COLLECT)",
        "AWB 123-4567 8901 com frete PREPAID, mas o incoterm da Invoice L30518777 é EXW "
        "(frete por conta do comprador; esperado COLLECT)",
    ]
    assert {d.comparacao_id for d in coerencia} == {"consolidado"}


def test_caso_4_assinatura_de_outra_empresa():
    r = caso_4_v3()
    assert mensagens(r, "interna") == [
        "Invoice L30514262: Assinatura de Delta Fast-Run Footwear Ltd., mas o cabeçalho é de "
        "Orion Pacific Trading Co., Ltd."
    ]


def caso_6_v3(itens_bl=()):
    return rodar(
        [doc("invoice", 24000, 24592, ["3904.10.10"], numero="0077032707", po="246731-01", exportador=SERRANA,
             consignatario="CAPITAL TRADE IMPORTACAO EEXPORTACAO LTDA", origem="CARTAGENA", destino="ITAPOA",
             volumes=(16, "PALLETS"), quantidade=(24, "TO"), versao="desconhecida", pagina=None,
             incoterm=("CFR", "ITAPOA"), moeda="USD", pais_origem="COLOMBIA",
             itens=[item(None, "POLIRMX HD 475 / 25 kg SA RESINA DE PVC", 24, "TO", ["7713904"], ["20/02/2026"],
                         valor=28726.3)])],
        [doc("packing_list", 24000, 24592, ["39.04.10.20"], numero="48273916", refs=["70023077", "0070023077"],
             po="243918-01", exportador=SERRANA, consignatario="CAPITAL TRADE IMPORTACAO EEXPORTACAO LTDA",
             quantidade=(24000, "TONS"), versao="desconhecida", pagina=None,
             itens=[item("52871046", "POLIREX YK 455", 24000, "TONS", ["4K0518206"])],
             internas=[("Quantidade em toneladas incompatível com as bolsas", '"QUANTITY IN TONS 24000" × "960 X 25 KG"')])],
        [doc("conhecimento", 24000, 24000, ["39.04.10.10"], subtipo="BL", numero="614092377", exportador=SERRANA,
             consignatario=CAPITAL, origem="CARTAGENA", destino="NAVEGANTES", volumes=(16, "PALLETS"),
             frete="FREIGHT PREPAID", pagina=None, itens=itens_bl)],
        [doc("outro", subtipo="CO", pagina=None)],
    )


def test_caso_6_incoterm_cfr_com_porto_diferente_do_bl():
    r = caso_6_v3()
    assert mensagens(r, "coerencia") == [
        "Incoterm CFR ITAPOA (Invoice 0077032707) × porto de descarga do BL 614092377 NAVEGANTES"
    ]


def test_caso_6_itens_e_quantidade():
    r = caso_6_v3()
    unica = r.comparacoes[0]
    assert campo(unica, "quantidade").status == "DIVERGENTE"  # 24 TO × 24.000 TONS
    [linha] = r.itens[0].linhas
    assert linha.chave == "52871046"
    assert linha.diferencas == ["descricao", "quantidade", "lote"]
    [msg] = mensagens(r, "item")
    assert msg.startswith("Item 52871046: descrição Invoice POLIRMX HD 475")
    assert ("quantidade Invoice 24 TO × Packing List 24.000 TONS — provável unidade errada: "
            "24.000 TONS equivale a 24 t se for kg") in msg
    assert "lote Invoice 7713904 × Packing List 4K0518206" in msg
    assert any("provável unidade errada" in m for m in mensagens(r, "comparacao") if m.startswith("Quantidade"))
    assert mensagens(r, "interna") == ["Packing List 48273916: Quantidade em toneladas incompatível com as bolsas"]


def test_status_divergente_so_por_interna():
    r = rodar(
        [doc("invoice", 20000, 21200, ["3901.10.10"], numero="INV1",
             internas=[("Total por extenso diferente do numérico", '"2300" × "Four thousand six hundred"')]),
         doc("packing_list", 20000, 21200, ["39011010"], numero="INV1")],
        [doc("conhecimento", subtipo="BL", liquido=20000, bruto=21200, ncms=["3901.10.10"])],
    )
    assert all(c.status == "OK" for c in r.comparacoes[0].campos)
    assert r.status == "DIVERGENTE"


def test_frete_coerente_nao_gera_divergencia():
    r = rodar(
        [doc("invoice", 1, 2, ["39011010"], numero="1", incoterm=("CIF", "NAVEGANTES")),
         doc("packing_list", 1, 2, ["39011010"], numero="1")],
        [doc("conhecimento", 1, 2, ["39011010"], subtipo="BL", frete="PREPAID", destino="Navegantes, SC")],
    )
    assert mensagens(r, "coerencia") == []
    r = rodar(
        [doc("invoice", 1, 2, ["39011010"], numero="1", incoterm=("CIF", "NAVEGANTES")),
         doc("packing_list", 1, 2, ["39011010"], numero="1")],
        [doc("conhecimento", 1, 2, ["39011010"], subtipo="BL", frete="FREIGHT COLLECT", destino="NAVEGANTES")],
    )
    assert mensagens(r, "coerencia") == [
        "BL com frete COLLECT, mas o incoterm da Invoice 1 é CIF (frete por conta do vendedor; esperado PREPAID)"
    ]


def test_item_so_de_um_lado_e_casamento_por_descricao():
    r = rodar([
        doc("invoice", numero="1", itens=[item(None, "Synthetic Trail Running Shoes Model: Ridge-Path 2.", 150, "PAIRS"),
                                          item(None, "Synthetic Indoor Soccer Shoes Model: Indoor-Ace X.", 50, "PAIRS"),
                                          item(None, "Cycling socks", 10, "PCS")]),
        doc("packing_list", numero="1", itens=[item(None, "Synthetic Indoor Soccer Shoes Model: Indoor-Ace X", 50, "pair"),
                                               item(None, "Synthetic Trail Running Shoes Model: Ridge-Path 2", 150, "PRS")]),
    ])
    linhas = r.itens[0].linhas
    assert [l.status for l in linhas] == ["OK", "OK", "DIVERGENTE"]
    assert linhas[2].diferencas == ["ausente"]
    assert mensagens(r, "item") == ["Item Cycling socks: só na Invoice"]


def test_chave_do_item_nao_repete_quando_a_descricao_so_difere_no_fim():
    parafuso = "PARAFUSO SEXTAVADO (HEX BOLT) MARCA:ACME ACABAMENTO: ZINCADO CLASSE: 8.8 MEDIDA:{} PASSO: {}"
    itens = [item(None, parafuso.format("M8X40", 1), 500, "BOXES"), item(None, parafuso.format("M10X60", 2), 500, "BOXES")]
    r = rodar([doc("invoice", numero="1", itens=itens), doc("packing_list", numero="1", itens=itens)])
    chaves = [l.chave for l in r.itens[0].linhas]
    assert chaves == [
        "PARAFUSO SEXTAVADO (HEX… MEDIDA:M8X40 PASSO: 1",
        "PARAFUSO SEXTAVADO (HEX… MEDIDA:M10X60 PASSO: 2",
    ]


def test_chave_do_item_ganha_numero_de_ordem_quando_a_descricao_e_identica():
    itens = [item(None, "Parafuso", 10, "PCS", lotes=["L1"]), item(None, "Parafuso", 20, "PCS", lotes=["L2"]),
             item(None, "Porca", 5, "PCS")]
    r = rodar([doc("invoice", numero="1", itens=itens), doc("packing_list", numero="1", itens=itens)])
    assert [l.chave for l in r.itens[0].linhas] == ["Parafuso (1)", "Parafuso (2)", "Porca"]


def test_pais_e_endereco_normalizados():
    r = rodar([
        doc("invoice", numero="1", exportador="X", pais_exportador="Republic of Korea", endereco_exportador="Rua A, 10 - Seoul"),
        doc("packing_list", numero="1", exportador="X", pais_exportador="KR", endereco_exportador="RUA A 10, SEOUL"),
    ])
    unica = r.comparacoes[0]
    assert campo(unica, "pais_exportador").status == "OK"
    assert campo(unica, "endereco_exportador").status == "OK"


# ---------------------------------------------------------------------------
# v3.1 — conhecimento nos itens
# ---------------------------------------------------------------------------

def test_caso_1_bl_generico_so_aviso():
    r = caso_1(itens_bl=[item(None, "SKINCARE ESSENTIALS")])
    [comparacao] = r.itens
    assert [c.chave for c in comparacao.colunas] == ["invoice", "packing_list", "conhecimento"]
    assert all(l.valores["conhecimento"] is None for l in comparacao.linhas)
    assert comparacao.linhas[0].status == "OK"  # célula vazia do BL não é divergência
    assert all("ausente" not in l.diferencas for l in comparacao.linhas)
    assert mensagens(r, "item") == [  # as mesmas de antes, sem nada do BL
        "Item QB-TN-505: lote Invoice #LT2031C14-E × Packing List #LT2031C20-E",
        "Item QB-MS-312: validade Invoice 11/2025, 11/2028 × Packing List 11/2025",
    ]
    assert "BL descreve 'SKINCARE ESSENTIALS'; não foi possível relacionar aos itens." in r.avisos


def test_caso_4_awb_generico_no_consolidado_so_aviso():
    itens_par = (
        [item(None, "Synthetic Trail Running Shoes Model: Ridge-Path 2", 150, "PAIRS"),
         item(None, "Synthetic Indoor Soccer Shoes Model: Indoor-Ace X", 170, "PAIRS")],
        [item(None, "Synthetic Basketball Shoes Model: Jump-Shot 5", 120, "PAIRS"),
         item(None, "Synthetic Running Sandals Model: Summer-Lite", 80, "PAIRS")],
    )
    r = caso_4_v3(itens_par=itens_par, itens_awb=[item(None, "SYNTHETIC SHOES")])
    assert [c.comparacao_id for c in r.itens] == ["par-1", "par-2", "consolidado"]
    consolidado = r.itens[2]
    assert [c.chave for c in consolidado.colunas] == ["soma_invoices", "soma_packing_lists", "conhecimento"]
    assert len(consolidado.linhas) == 4
    assert all(l.status == "OK" and l.valores["conhecimento"] is None for l in consolidado.linhas)
    assert mensagens(r, "item") == []
    assert "Consolidado — AWB descreve 'SYNTHETIC SHOES'; não foi possível relacionar aos itens." in r.avisos


def test_caso_4_sem_itens_no_awb_nao_gera_consolidado_de_itens():
    itens_par = ([item("A", "Shoe A", 1, "PAIRS")], [item("B", "Shoe B", 1, "PAIRS")])
    r = caso_4_v3(itens_par=itens_par)
    assert [c.comparacao_id for c in r.itens] == ["par-1", "par-2"]


def test_caso_6_descricao_do_bl_diverge():
    r = caso_6_v3(itens_bl=[item(None, "POLIREX ZK 455")])
    [linha] = r.itens[0].linhas
    assert linha.valores["conhecimento"].descricao == "POLIREX ZK 455"
    assert linha.diferencas == ["descricao", "quantidade", "lote"]
    [divergencia] = [d for d in r.divergencias if d.categoria == "item"]
    assert divergencia.item_chave == "52871046"
    assert divergencia.mensagem.startswith(
        "Item 52871046: descrição Invoice POLIRMX HD 475 / 25 kg SA RESINA DE PVC × "
        "Packing List POLIREX YK 455 × BL POLIREX ZK 455;"
    )
    assert not any("descreve" in a for a in r.avisos)


def test_conhecimento_casa_por_codigo_e_compara_so_o_que_informa():
    r = rodar(
        [doc("invoice", numero="1", itens=[item("A1", "Widget", 10, "PCS", ["L1"]), item("B2", "Gadget", 5, "PCS")]),
         doc("packing_list", numero="1", itens=[item("A1", "Widget", 10, "PCS", ["L1"]), item("B2", "Gadget", 5, "PCS")])],
        [doc("conhecimento", subtipo="BL", itens=[item("A1", "Widget", 12, "PCS")])],
    )
    linhas = {l.chave: l for l in r.itens[0].linhas}
    assert linhas["A1"].diferencas == ["quantidade"]  # lote não informado no BL: não compara
    assert linhas["B2"].status == "OK" and linhas["B2"].valores["conhecimento"] is None
    assert mensagens(r, "item") == ["Item A1: quantidade BL 12 PCS × Invoice/Packing List 10 PCS"]


def test_conhecimento_com_descricao_que_serve_para_varios_itens_so_aviso():
    r = rodar(
        [doc("invoice", numero="1", itens=[item(None, "Synthetic Shoes Model: Trail-Max 10", 200, "PAIRS"),
                                           item(None, "Synthetic Shoes Model: Wind-Ride 500", 120, "PAIRS")]),
         doc("packing_list", numero="1", itens=[item(None, "Synthetic Shoes Model: Trail-Max 10", 200, "PAIRS"),
                                                item(None, "Synthetic Shoes Model: Wind-Ride 500", 120, "PAIRS")])],
        [doc("conhecimento", subtipo="AWB", itens=[item(None, "SYNTHETIC SHOES")])],
    )
    assert all(l.valores["conhecimento"] is None and l.status == "OK" for l in r.itens[0].linhas)
    assert "AWB descreve 'SYNTHETIC SHOES'; não foi possível relacionar aos itens." in r.avisos


# ---------------------------------------------------------------------------
# v3.2 — cidade do exportador, referência dos itens, unidade trocada (fator 1000)
# ---------------------------------------------------------------------------

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


def test_referencia_diferente_por_uma_letra_diverge():
    # Invoice = BL (XC); só o PL diz WC — similaridade das descrições é alta, mas a referência difere
    desc = "POLYVINYL CHLORIDE RESIN POLIREX {} 455 / 25 kg SA"
    r = rodar(
        [doc("invoice", numero="1", itens=[item("52871046", desc.format("ZK"), 24, "TON", referencia="POLIREX ZK 455")]),
         doc("packing_list", numero="1", itens=[item("52871046", desc.format("YK"), 24, "TON", referencia="POLIREX YK 455")])],
        [doc("conhecimento", subtipo="BL", itens=[item(None, "POLIREX ZK 455 - PVC RESIN", referencia="POLIREX ZK 455")])],
    )
    [linha] = r.itens[0].linhas
    assert linha.valores["conhecimento"] is not None
    assert linha.diferencas == ["descricao"]
    [msg] = mensagens(r, "item")
    assert "Packing List" in msg and "YK 455" in msg and "ZK 455" in msg


def test_referencia_igual_ou_sem_marca_nao_diverge_e_sem_referencia_usa_similaridade():
    r = rodar(
        [doc("invoice", numero="1", itens=[item("A", "PVC resin Polirex ZK-455", 1, "TON", referencia="Polirex ZK-455"),
                                           item("B", "Synthetic Shoes Model: Trail-Max 10", 5, "PAIRS")]),
         doc("packing_list", numero="1", itens=[item("A", "PVC RESIN ZK 455", 1, "TON", referencia="ZK 455"),
                                                item("B", "Synthetic Shoes Model Trail-Max 10", 5, "PAIRS",
                                                     referencia="Trail-Max 10")])],
    )
    assert [l.status for l in r.itens[0].linhas] == ["OK", "OK"]


def test_referencias_com_numero_diferente_divergem():
    r = rodar(
        [doc("invoice", numero="1", itens=[item("B", "Shoes Trail-Max 10", 5, "PAIRS", referencia="Trail-Max 10")]),
         doc("packing_list", numero="1", itens=[item("B", "Shoes Trail-Max 100", 5, "PAIRS", referencia="Trail-Max 100")])],
    )
    assert r.itens[0].linhas[0].diferencas == ["descricao"]


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
