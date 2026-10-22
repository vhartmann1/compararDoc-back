"""Extrator falso, sem rede: um cenário para 1 arquivo e outro para 2 ou mais, com divergências conhecidas."""

from app.schemas import (
    ArquivoEntrada,
    CodigoNcm,
    Contagem,
    DocumentoExtraido,
    ExtracaoArquivo,
    InconsistenciaInterna,
    Incoterm,
    ItemExtraido,
    Medida,
    Parte,
    Texto,
    Uso,
)
from app.services.leitura.arquivo_para_conteudo import MEDIA_PDF, TIPOS_IMAGEM

ATLASFIT = "AtlasFit Brasil Importação e Comércio de Artigos Esportivos Ltda."
CAPITAL = "CAPITAL TRADE IMPORTACAO E EXPORTACAO LTDA."
FAST_RUN = "Delta Fast-Run Footwear Ltd."
ENDERECO_HANGZHOU = "Room 804, Riverside Tower, No. 12 Jiangnan Road, Hangzhou, Zhejiang, China"


def _doc(tipo: str, pagina: int | None, **campos) -> DocumentoExtraido:
    base = dict(
        subtipo=None, paginas=[pagina] if pagina else [], numero=None, invoices_referenciadas=[], po=None,
        versao="desconhecida", exportador=None, consignatario=None, porto_origem=None, porto_destino=None,
        peso_liquido_total=None, peso_bruto_total=None, volumes_total=None, quantidade_total=None, ncms=[],
        incoterm=None, frete=None, moeda=None, pais_origem=None, emitente_assinatura=None, itens=[],
        inconsistencias_internas=[],
    )
    return DocumentoExtraido(tipo=tipo, **(base | campos))


def _kg(valor: float, texto: str, pagina: int | None, unidade: str = "KG") -> Medida:
    return Medida(valor=valor, unidade=unidade, texto_original=texto, pagina=pagina)


def _contagem(valor: float, unidade: str, pagina: int | None) -> Contagem:
    return Contagem(valor=valor, unidade=unidade, texto_original=f"{valor:g} {unidade}", pagina=pagina)


def _parte(nome: str, cnpj: str | None, pagina: int | None, endereco: str | None = None, pais: str | None = None) -> Parte:
    return Parte(nome=nome, cnpj=cnpj, endereco=endereco, pais=pais, pagina=pagina)


def _item(codigo: str | None, descricao: str, quantidade: float, unidade: str, pagina: int | None,
          lotes: list[str] | None = None, validades: list[str] | None = None, valor: float | None = None) -> ItemExtraido:
    return ItemExtraido(
        codigo=codigo, descricao=descricao, lotes=lotes or [], validades=validades or [], quantidade=quantidade,
        unidade=unidade, sem_valor_comercial=False, valor_total=valor, pagina=pagina,
    )


# Cenário com 1 arquivo (comparação única)

def _simples(pagina) -> list[DocumentoExtraido]:
    comum = dict(
        po="PO-7781", versao="original",
        exportador=_parte("Serrana Polímeros S.A.S.", None, pagina(1), "Calle 10 #20-30, Bogotá D.C.", "COLOMBIA"),
        consignatario=_parte(CAPITAL, "07.872.326/0001-58", pagina(1)),
        pais_origem=Texto(valor="COLOMBIA", pagina=pagina(1)),
        porto_origem=Texto(valor="CARTAGENA", pagina=pagina(1)),
        porto_destino=Texto(valor="NAVEGANTES", pagina=pagina(1)),
        ncms=[CodigoNcm(codigo="3904.10.10", pagina=pagina(1))],
    )
    invoice = _doc(
        "invoice", pagina(1), numero="INV-2026-0042", **comum,
        incoterm=Incoterm(codigo="FOB", local="CARTAGENA", texto_original="FOB CARTAGENA", pagina=pagina(1)),
        moeda=Texto(valor="USD", pagina=pagina(1)),
        itens=[
            _item("PVC-SP660", "Resina de PVC SP 660", 12, "TON", pagina(1), ["L2026-01"], ["01/2028"], 14400.0),
            _item("PVC-SP700", "Resina de PVC SP 700", 8, "TON", pagina(1), ["L2026-02"], ["02/2028"], 9600.0),
        ],
        inconsistencias_internas=[InconsistenciaInterna(
            descricao="Coluna de preços em USD, mas o total por extenso está em euros",
            evidencia='"UNIT PRICE USD" × "SAY: TWENTY-FOUR THOUSAND EUROS"', pagina=pagina(1),
        )],
        peso_liquido_total=_kg(20000.0, "20,000.00 KGS", pagina(1)),
        peso_bruto_total=_kg(21200.0, "21,200.00 KGS", pagina(1)),
        volumes_total=_contagem(16, "PALLETS", pagina(1)),
        quantidade_total=_contagem(20, "TON", pagina(1)),
    )
    pl = _doc(
        "packing_list", pagina(2), numero="PL-2026-0042", invoices_referenciadas=["INV-2026-0042"],
        **(comum | {"ncms": [CodigoNcm(codigo="3904.10.10", pagina=pagina(2))]}),
        peso_liquido_total=_kg(20000.0, "20.000,000 KG", pagina(2)),
        peso_bruto_total=_kg(21200.0, "21.200,000 KG", pagina(2)),
        volumes_total=_contagem(16, "PALLETS", pagina(2)),
        quantidade_total=_contagem(20000, "KG", pagina(2)),
        itens=[
            _item("PVC-SP660", "Resina de PVC SP 660", 12000, "KG", pagina(2), ["L2026-01"], ["01/2028"]),
            _item("PVC-SP700", "Resina de PVC SP 700", 8000, "KG", pagina(2), ["L2026-03"], ["02/2028"]),
        ],
    )
    # 44,092.452 LBS = 20.000,00 kg; 46,848.231 LBS = 21.250,00 kg
    bl = _doc(
        "conhecimento", pagina(3), subtipo="BL", numero="MEDU1234567", versao="original",
        invoices_referenciadas=["INV-2026-0042"],
        exportador=comum["exportador"], consignatario=comum["consignatario"],
        frete=Texto(valor="PREPAID", pagina=pagina(3)),
        porto_origem=Texto(valor="CARTAGENA", pagina=pagina(3)),
        porto_destino=Texto(valor="NAVEGANTES", pagina=pagina(3)),
        peso_liquido_total=_kg(44092.452, "44,092.452 LBS", pagina(3), "LB"),
        peso_bruto_total=_kg(46848.231, "46,848.231 LBS", pagina(3), "LB"),
        volumes_total=_contagem(16, "PALLETS", pagina(3)),
        ncms=[CodigoNcm(codigo="HS CODE 390410", pagina=pagina(3))],
    )
    return [invoice, pl, bl]


# Cenário com 2+ arquivos (dois pares e consolidado)

def _par(numero: str, exportador_inv: str, cnpj_consignee: str, nw_inv: float, nw_pl: float, gw: float,
         qtd_inv: float, qtd_pl: float, ctn: int, pagina_inv: int | None, pagina_pl: int | None,
         incoterm: str = "EXW", modelo: str = "Trail-Max 10", assinatura: str | None = None):
    def comum(pagina):
        return dict(
            numero=numero, versao="desconhecida",
            consignatario=_parte(ATLASFIT, cnpj_consignee, pagina),
            porto_origem=Texto(valor="BEIJIN", pagina=pagina),
            porto_destino=Texto(valor="NAVEGANTES", pagina=pagina),
            ncms=[CodigoNcm(codigo="6402.19.00", pagina=pagina)],
            peso_bruto_total=_kg(gw, f"Gross Weight: {gw:.2f} kg".replace(".", ","), pagina),
            volumes_total=_contagem(ctn, "CTN", pagina),
        )

    invoice = _doc(
        "invoice", pagina_inv, **comum(pagina_inv),
        exportador=_parte(exportador_inv, None, pagina_inv, ENDERECO_HANGZHOU, "CHINA"),
        peso_liquido_total=_kg(nw_inv, f"Net Weight: {nw_inv:.2f} kg".replace(".", ","), pagina_inv),
        quantidade_total=_contagem(qtd_inv, "PAIRS", pagina_inv),
        incoterm=Incoterm(codigo=incoterm, local="BEIJIN", texto_original=f"{incoterm} BEIJIN, CHINA", pagina=pagina_inv),
        moeda=Texto(valor="USD", pagina=pagina_inv),
        pais_origem=Texto(valor="CHINA", pagina=pagina_inv),
        emitente_assinatura=assinatura or exportador_inv,
        empresa_cabecalho=exportador_inv,
        itens=[_item(None, f"Synthetic Shoes Model: {modelo}.", qtd_inv, "PAIRS", pagina_inv)],
    )
    pl = _doc(
        "packing_list", pagina_pl, **comum(pagina_pl),
        exportador=_parte(FAST_RUN, None, pagina_pl, ENDERECO_HANGZHOU, "CHINA"),
        peso_liquido_total=_kg(nw_pl, f"NW {nw_pl}", pagina_pl),
        quantidade_total=_contagem(qtd_pl, "PRS", pagina_pl),
        itens=[_item(None, f"Synthetic Shoes Model: {modelo}.", qtd_pl, "PRS", pagina_pl)],
    )
    return [invoice, pl]


def _par_1(pagina) -> list[DocumentoExtraido]:
    # Divergências: peso líquido 113,20 × 130,20 e quantidade 200 × 210 pares.
    return _par("L30518777", FAST_RUN, "12.345.678/0005-80", 113.2, 130.2, 132.0, 200, 210, 21, pagina(1), pagina(2))


def _par_2(pagina, deslocamento: int = 0) -> list[DocumentoExtraido]:
    # Divergência: exportador da invoice (Orion Pacific) × packing list (Delta Fast-Run).
    return _par(
        "L30514262", "Orion Pacific Trading Co., Ltd.", "12.345.678/0001-90", 216.5, 216.5, 216.95, 320, 320, 32,
        pagina(1 + deslocamento), pagina(2 + deslocamento), incoterm="FOB", modelo="Wind-Ride 500",
        assinatura=FAST_RUN,
    )


def _awb(pagina) -> DocumentoExtraido:
    # 769.4 LB = 348,99 kg (× soma 348,95 kg: dentro da tolerância)
    return _doc(
        "conhecimento", pagina(1), subtipo="AWB", numero="123-4567 8901", versao="original",
        exportador=_parte("DELTA FAST-RUN FOOTWEAR LTD.", None, pagina(1), ENDERECO_HANGZHOU.upper(), "CHINA"),
        consignatario=_parte(ATLASFIT, "12.345.678/0001-90", pagina(1)),
        frete=Texto(valor="PREPAID", pagina=pagina(1)),
        invoices_referenciadas=["L30518777", "L30514262"],
        porto_origem=Texto(valor="BEIJIN", pagina=pagina(1)),
        porto_destino=Texto(valor="NAVEGANTES", pagina=pagina(1)),
        peso_bruto_total=_kg(769.4, "769.4 LB", pagina(1), "LB"),
        volumes_total=_contagem(4, "DRUMS", pagina(1)),
        ncms=[CodigoNcm(codigo="NCM NO6402.19.00", pagina=pagina(1))],
        # descrição genérica: não casa com os itens das invoices => só aviso (v3.1)
        itens=[ItemExtraido(codigo=None, descricao="SYNTHETIC SHOES", lotes=[], validades=[], quantidade=None,
                            unidade=None, sem_valor_comercial=False, valor_total=None, pagina=pagina(1))],
    )


def _outro(pagina) -> DocumentoExtraido:
    return _doc("outro", pagina(1), subtipo="CO")


# ---------------------------------------------------------------------------

def extrair_arquivos(arquivos: list[ArquivoEntrada]) -> tuple[dict[str, ExtracaoArquivo], Uso]:
    extracoes: dict[str, ExtracaoArquivo] = {}
    for i, arquivo in enumerate(arquivos):
        tem_paginas = arquivo.media_type == MEDIA_PDF or arquivo.media_type in TIPOS_IMAGEM

        def pagina(n: int, tem_paginas=tem_paginas) -> int | None:
            return n if tem_paginas else None

        if len(arquivos) == 1:
            documentos = _simples(pagina)
        elif i == 0:
            documentos = _par_1(pagina) + (_par_2(pagina, 2) if len(arquivos) == 2 else [])
        elif i == 1 and len(arquivos) >= 3:
            documentos = _par_2(pagina)
        elif (i == 1 and len(arquivos) == 2) or i == 2:
            documentos = [_awb(pagina)]
        else:
            documentos = [_outro(pagina)]
        extracoes[arquivo.id] = ExtracaoArquivo(documentos=documentos)
    return extracoes, Uso(input_tokens=0, output_tokens=0, custo_usd_estimado=0.0, modelo="mock")
