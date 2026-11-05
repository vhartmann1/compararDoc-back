"""Regras de NCM, nº da invoice, PO e portos."""

import re

from app.schemas import NomeCampo
from app.services.comparacao.campos.mensagem_de_ncm import texto_ncm
from app.services.comparacao.campos.regras_por_campo.regra import (
    Comparador,
    Iguais,
    primeira_pagina,
    texto_soma,
    valor_conjunto,
)
from app.services.comparacao.documentos.pareamento_invoice_packing_list import pls_em_outra_numeracao
from app.services.comparacao.normalizacao.codigos import normalizar_ncm
from app.services.comparacao.normalizacao.formatacao import formatar_ncm
from app.services.comparacao.normalizacao.numeros_de_documento import (
    mesmo_numero,
    normalizar_po,
    numero_da_invoice_para_conferir,
    numero_sem_serie,
    numeros_quase_iguais,
    pos_do_texto,
)
from app.services.comparacao.normalizacao.portos import (
    nome_do_porto,
    normalizar_porto,
    portos_do_estado,
    portos_separados_por_barra,
    so_o_pais,
)
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


def ncms_contidos(conhecimento: tuple, outro: tuple) -> bool:
    """Cada código do conhecimento é o começo de algum da invoice/PL ('8714.91' cobre '8714.91.20')."""
    return all(any(o.startswith(c) for o in outro) for c in conhecimento)


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


def numeros_contidos(conhecimento: frozenset, outro: frozenset) -> bool:
    """Cada número do conhecimento está na invoice/PL; faltar algum não importa."""
    return all(any(mesmo_numero(x, y) for y in outro) for x in conhecimento)


def obter_porto(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    """Chave = {alternativas}: conhecimento, embarque ou recebimento / descarga ou entrega; invoice, 'X OR Y'."""
    origem = campo == "porto_origem"
    porto = f.doc.porto_origem if origem else f.doc.porto_destino
    extra = (f.doc.local_recebimento if origem else f.doc.local_entrega) if f.doc.tipo == "conhecimento" else None
    porto = porto or extra
    if porto is None or so_o_pais(porto.valor):
        return None
    textos = [porto.valor] + ([extra.valor] if extra and extra is not porto else [])
    if f.doc.tipo != "conhecimento":
        trechos = ROTA.split(porto.valor)
        opcoes = [a for t in (trechos[:1] if origem else trechos) for a in ALTERNATIVAS.split(t)]
        textos = [p for a in opcoes for p in portos_separados_por_barra(a)]
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


def comparador_de_ncm(ctx: Contexto, valores: list[Valor]) -> Comparador:
    """NCM comparado e escrito pelos dígitos que todos os documentos trazem."""
    digitos = _digitos_ncm(ctx, valores)
    return Comparador(_iguais_nos_digitos(digitos), lambda ordenados, _: texto_ncm(ordenados, digitos))


def _iguais_nos_digitos(digitos: int) -> Iguais:
    return lambda a, b: {c[:digitos] for c in a} == {c[:digitos] for c in b}


def _digitos_ncm(ctx: Contexto, valores: list[Valor]) -> int:
    """Compara com 8 dígitos; se algum documento só traz HS (6) ou posição (4), compara por aí."""
    menor = min(len(c) for v in valores for c in v.chave)
    digitos = 8 if menor >= 8 else 6 if menor >= 6 else 4
    if digitos < 8:
        ctx.avisos.append(
            f"{ctx.prefixo}NCM comparado pelos {digitos} primeiros dígitos "
            "(algum documento traz só o HS Code ou a posição)."
        )
    return digitos


def colunas_com_pl_em_outra_numeracao(colunas: list[Col]) -> set[str]:
    """Colunas com PL que cita as invoices por outra numeração: não têm nº de invoice para conferir."""
    fontes = [f for col in colunas for f in col.fontes]
    invoices = [f for f in fontes if f.doc.tipo == "invoice"]
    sem_numero = pls_em_outra_numeracao(invoices, [f for f in fontes if f.doc.tipo == "packing_list"])
    return {col.chave for col in colunas if any(f in sem_numero for f in col.fontes)}
