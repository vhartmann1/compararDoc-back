"""Regras de NCM, nº da invoice, PO e portos."""

from app.schemas import NomeCampo
from app.services.comparacao.normalizacao import (
    SIGLAS_PAISES,
    normalizar_pais,
    formatar_ncm,
    normalizar_ncm,
    normalizar_numero_documento,
    normalizar_po,
    nome_do_porto,
    normalizar_porto,
    numero_sem_serie,
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
        # PL que não cita invoice: o próprio número só vale se for o da invoice pareada ou quase (erro de digitação)
        par = f.invoice_par
        if doc.tipo == "packing_list" and doc.numero and not numeros and par and par.numero:
            proprio, da_invoice = numero_sem_serie(doc.numero), numero_sem_serie(par.numero)
            if proprio == da_invoice:
                numeros.append(par.numero)
            elif _quase_iguais(proprio, da_invoice):
                numeros.append(doc.numero)
    return valor_conjunto(numeros, normalizar_numero_documento, f, primeira_pagina(f))


def _quase_iguais(a: str, b: str) -> bool:
    """Mesmo tamanho e no máximo 2 caracteres diferentes: 'KTR27393806' × 'KTR27393803'."""
    return len(a) == len(b) >= 6 and sum(x != y for x, y in zip(a, b)) <= 2


def obter_po(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    return valor_conjunto([f.doc.po] if f.doc.po else [], normalizar_po, f, primeira_pagina(f))


def pos_iguais(a: frozenset, b: frozenset) -> bool:
    """Cada PO tem par do outro lado: igual ou com letras a mais na frente ('ACME11426' × '11426')."""
    return all(any(_mesmo_po(x, y) for y in b) for x in a) and all(any(_mesmo_po(y, x) for x in a) for y in b)


def _mesmo_po(x: str, y: str) -> bool:
    maior, menor = (x, y) if len(x) >= len(y) else (y, x)
    return x == y or (len(menor) >= 3 and maior.endswith(menor) and maior[: -len(menor)].isalpha())


def obter_porto(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    porto = f.doc.porto_origem if campo == "porto_origem" else f.doc.porto_destino
    entrega = f.doc.local_entrega if campo == "porto_destino" and f.doc.tipo == "conhecimento" else None
    porto = porto or entrega
    if porto is None or normalizar_pais(porto.valor) in SIGLAS_PAISES:  # "To: Brazil" é país, não porto
        return None
    nomes = [porto.valor] + ([entrega.valor] if entrega and entrega is not porto else [])
    valor = valor_conjunto(nomes, normalizar_porto, f, porto.pagina)
    if valor:
        valor.texto_original = porto.valor
        valor.exibicao = nome_do_porto(porto.valor)
        if len(valor.chave) > 1:  # conhecimento: descarga e entrega diferentes
            valor.exibicao += f" (entrega: {nome_do_porto(entrega.valor)})"
    return valor


def destinos_iguais(a: frozenset, b: frozenset) -> bool:
    """Destino confere com a descarga ou com o local de entrega do conhecimento."""
    return a <= b or b <= a


def juntar_porto(valores: list[Valor], campo: NomeCampo, ctx: Contexto, col: Col) -> Valor:
    chave = frozenset().union(*(v.chave for v in valores))
    return Valor(chave, " / ".join(sorted({v.exibicao for v in valores})), texto_soma(valores), None, None)
