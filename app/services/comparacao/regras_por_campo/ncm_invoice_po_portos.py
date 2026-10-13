"""Regras de NCM, nº da invoice, PO e portos."""

from app.schemas import NomeCampo
from app.services.comparacao.normalizacao import (
    formatar_ncm,
    normalizar_ncm,
    normalizar_numero_documento,
    normalizar_po,
    normalizar_porto,
)
from app.services.comparacao.regras_por_campo.regra import primeira_pagina, texto_soma, valor_conjunto
from app.services.comparacao.tipos import Col, Contexto, Fonte, Valor


def obter_ncm(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    todos = {c for c in (normalizar_ncm(n.codigo) for n in f.doc.ncms) if len(c) >= 4}
    # "3904" junto de "39041010" no mesmo documento é só a posição do mesmo código: fica o mais específico
    codigos = sorted(c for c in todos if not any(o != c and o.startswith(c) for o in todos))
    if not codigos:
        return None
    return Valor(
        tuple(codigos),
        ", ".join(formatar_ncm(c) for c in codigos),
        ", ".join(n.codigo for n in f.doc.ncms),
        f.arquivo.id,
        f.doc.ncms[0].pagina,
    )


def juntar_ncm(valores: list[Valor], campo: NomeCampo, ctx: Contexto, col: Col) -> Valor:
    codigos = sorted({c for v in valores for c in v.chave})
    textos = list(dict.fromkeys(v.texto_original for v in valores if v.texto_original))
    return Valor(tuple(codigos), ", ".join(formatar_ncm(c) for c in codigos), ", ".join(textos) or None, None, None)


def obter_numero_invoice(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    doc = f.doc
    if doc.tipo == "invoice":
        numeros = [doc.numero] if doc.numero else []
    else:
        numeros = list(doc.invoices_referenciadas)
        # PL que não cita invoice usa o próprio número como referência (costuma ser o mesmo da invoice)
        if doc.tipo == "packing_list" and doc.numero and not numeros:
            numeros.append(doc.numero)
    return valor_conjunto(numeros, normalizar_numero_documento, f, primeira_pagina(f))


def obter_po(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    return valor_conjunto([f.doc.po] if f.doc.po else [], normalizar_po, f, primeira_pagina(f))


def obter_porto(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    porto = f.doc.porto_origem if campo == "porto_origem" else f.doc.porto_destino
    if porto is None:
        return None
    valor = valor_conjunto([porto.valor], normalizar_porto, f, porto.pagina)
    if valor:
        valor.texto_original = porto.valor
        valor.exibicao = normalizar_porto(porto.valor)
    return valor


def juntar_porto(valores: list[Valor], campo: NomeCampo, ctx: Contexto, col: Col) -> Valor:
    chave = frozenset().union(*(v.chave for v in valores))
    return Valor(chave, " / ".join(sorted(chave)), texto_soma(valores), None, None)
