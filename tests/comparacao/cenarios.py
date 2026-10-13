"""Cenários completos de docs/CASOS_TESTE.md, com dados inventados."""

from tests.comparacao.apoio import doc, item, rodar

CAPITAL = ("CAPITAL TRADE IMPORTACAO E EXPORTACAO LTDA.", "07.872.326/0001-58")
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
