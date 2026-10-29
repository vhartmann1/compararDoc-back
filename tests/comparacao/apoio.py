"""Como montar documentos e rodar a comparação nos testes."""

from pathlib import Path

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
)
from app.services.comparacao import comparar


def arquivo(id_):
    return ArquivoEntrada(id=id_, nome=f"{id_}.pdf", caminho=Path(f"/tmp/{id_}.pdf"), media_type="application/pdf")


def doc(tipo, liquido=None, bruto=None, ncms=(), versao="original", unidade="KG", pagina=1, numero=None,
        subtipo=None, refs=(), po=None, exportador=None, consignatario=None, origem=None, destino=None,
        volumes=None, quantidade=None, incoterm=None, frete=None, moeda=None, pais_origem=None,
        endereco_exportador=None, pais_exportador=None, assinatura=None, itens=(), internas=(),
        cidade_exportador=None, entrega=None, fabricante=None, recebimento=None, notify=None, adquirente=None,
        cabecalho=None):
    def m(v):
        return None if v is None else Medida(valor=v, unidade=unidade, texto_original=f"{v} {unidade}", pagina=pagina)

    def parte(p, endereco=None, pais=None, cidade=None):
        if p is None:
            return None
        nome, cnpj, *resto = p if isinstance(p, tuple) else (p, None)
        endereco, cidade = (*resto, cidade)[:2] if resto else (endereco, cidade)  # (nome, cnpj, endereço[, cidade])
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
        consignatario=parte(consignatario), notify=parte(notify), adquirente=parte(adquirente),
        porto_origem=texto(origem), porto_destino=texto(destino), local_entrega=texto(entrega),
        local_recebimento=texto(recebimento),
        fabricante=parte(fabricante[0], *fabricante[1:]) if fabricante else None,
        peso_liquido_total=m(liquido), peso_bruto_total=m(bruto),
        volumes_total=contagem(volumes), quantidade_total=contagem(quantidade),
        ncms=[CodigoNcm(codigo=c, pagina=pagina) for c in ncms],
        incoterm=inc(incoterm), frete=texto(frete), moeda=texto(moeda), pais_origem=texto(pais_origem),
        emitente_assinatura=assinatura, empresa_cabecalho=cabecalho, itens=list(itens),
        inconsistencias_internas=[InconsistenciaInterna(descricao=d, evidencia=e, pagina=pagina) for d, e in internas],
    )


def item(codigo, descricao, quantidade=None, unidade=None, lotes=(), validades=(), foc=False, valor=None, pagina=None,
         referencia=None, liquido=None, bruto=None, volumes=None):
    def kg(v):
        return None if v is None else Medida(valor=v, unidade="KG", texto_original=f"{v} KG", pagina=pagina)

    return ItemExtraido(codigo=codigo, descricao=descricao, referencia=referencia, lotes=list(lotes),
                        validades=list(validades), quantidade=quantidade, unidade=unidade, sem_valor_comercial=foc,
                        valor_total=valor, pagina=pagina, peso_liquido=kg(liquido), peso_bruto=kg(bruto),
                        volumes=None if volumes is None else Contagem(valor=volumes[0], unidade=volumes[1],
                                                                       texto_original=f"{volumes[0]} {volumes[1]}",
                                                                       pagina=pagina))


def rodar(*docs_por_arquivo, modalidade=None, escaneado=None):
    entradas = [(arquivo(f"a{i}"), ExtracaoArquivo(documentos=list(docs), escaneado=escaneado))
                for i, docs in enumerate(docs_por_arquivo)]
    return comparar(entradas, modalidade)


def campo(comparacao, nome):
    return next((c for c in comparacao.campos if c.campo == nome), None)


def mensagens(r, categoria):
    return [d.mensagem for d in r.divergencias if d.categoria == categoria]


def tres_ok(**bl):
    return rodar(
        [doc("invoice", 20000, 21200, ["3901.10.10"], numero="INV1"),
         doc("packing_list", 20000, 21200, ["39011010"], numero="INV1")],
        [doc("conhecimento", subtipo="BL", **({"liquido": 20000, "bruto": 21200, "ncms": ["3901.10.10"]} | bl))],
    )
