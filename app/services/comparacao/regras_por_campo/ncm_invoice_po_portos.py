"""Regras de NCM, nº da invoice, PO e portos."""

import re

from app.schemas import NomeCampo
from app.services.comparacao.normalizacao import (
    SIGLAS_PAISES,
    normalizar_pais,
    formatar_ncm,
    mesmo_numero,
    normalizar_ncm,
    numero_da_invoice_para_conferir,
    normalizar_po,
    pos_do_texto,
    nome_do_porto,
    normalizar_porto,
    portos_do_estado,
    numero_sem_serie,
    numeros_quase_iguais,
)
from app.services.comparacao.regras_por_campo.regra import primeira_pagina, texto_soma, valor_conjunto
from app.services.comparacao.tipos import Col, Contexto, Fonte, Valor

ALTERNATIVAS = re.compile(r"(?i)\s+(?:OR|OU)\s+")  # 'ITAPOA OR NAVEGANTES'
ROTA = re.compile(r"(?i)\s+TO\s+")  # 'Itapoa, Brazil to Navegantes': na origem vale o começo; no destino, os dois


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
        # PL que não cita invoice: o próprio número só vale se for o da invoice pareada ou quase (erro de digitação)
        par = f.invoice_par
        if doc.tipo == "packing_list" and doc.numero and not numeros and par and par.numero:
            proprio, da_invoice = numero_sem_serie(doc.numero), numero_sem_serie(par.numero)
            if proprio == da_invoice:
                numeros.append(par.numero)
            elif numeros_quase_iguais(proprio, da_invoice):
                numeros.append(doc.numero)
    return valor_conjunto(numeros, numero_da_invoice_para_conferir, f, primeira_pagina(f))


def obter_po(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    return valor_conjunto(pos_do_texto(f.doc.po or ""), normalizar_po, f, primeira_pagina(f))


def numeros_iguais(a: frozenset, b: frozenset) -> bool:
    """Cada número tem par do outro lado: igual ou com letras a mais na frente ('ACME11426' × '11426')."""
    return all(any(mesmo_numero(x, y) for y in b) for x in a) and all(any(mesmo_numero(y, x) for x in a) for y in b)


def obter_porto(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    """Chave = {alternativas}: conhecimento, embarque ou recebimento / descarga ou entrega; invoice, 'X OR Y'."""
    origem = campo == "porto_origem"
    porto = f.doc.porto_origem if origem else f.doc.porto_destino
    extra = (f.doc.local_recebimento if origem else f.doc.local_entrega) if f.doc.tipo == "conhecimento" else None
    porto = porto or extra
    if porto is None or normalizar_pais(porto.valor) in SIGLAS_PAISES:  # "To: Brazil" é país, não porto
        return None
    textos = [porto.valor] + ([extra.valor] if extra and extra is not porto else [])
    if f.doc.tipo != "conhecimento":
        trechos = ROTA.split(porto.valor)
        textos = [a for t in (trechos[:1] if origem else trechos) for a in ALTERNATIVAS.split(t)]
    alternativas = {normalizar_porto(t): t for t in textos if normalizar_porto(t)}
    if not alternativas:
        return None
    if f.doc.tipo != "conhecimento":
        exibicao = " ou ".join(dict.fromkeys(nome_do_porto(t) for t in alternativas.values()))
    else:
        exibicao = nome_do_porto(porto.valor)
        if len(alternativas) > 1:
            exibicao += f" ({'recebimento' if origem else 'entrega'}: {nome_do_porto(extra.valor)})"
    chaves = set(alternativas) | (set() if origem else {p for t in alternativas.values() for p in portos_do_estado(t)})
    return Valor(frozenset({frozenset(chaves)}), exibicao, porto.valor, f.arquivo.id, porto.pagina)


def portos_iguais(a: frozenset, b: frozenset) -> bool:
    """Cada documento de um lado tem uma alternativa em comum com algum documento do outro."""
    return all(any(x & y for y in b) for x in a) and all(any(y & x for x in a) for y in b)


def juntar_porto(valores: list[Valor], campo: NomeCampo, ctx: Contexto, col: Col) -> Valor:
    chave = frozenset().union(*(v.chave for v in valores))
    return Valor(chave, " / ".join(sorted({v.exibicao for v in valores})), texto_soma(valores), None, None)
