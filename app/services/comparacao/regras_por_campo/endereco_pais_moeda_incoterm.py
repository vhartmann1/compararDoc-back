"""Regras de endereço, país, moeda e incoterm."""

import re

from app.schemas import NomeCampo
from app.services.comparacao.normalizacao import (
    enderecos_compativeis,
    normalizar_incoterm,
    normalizar_moeda,
    normalizar_pais,
    nome_do_porto,
)
from app.services.comparacao.regras_por_campo.regra import texto_soma, valor_conjunto
from app.services.comparacao.tipos import Col, Contexto, Fonte, Valor


def obter_endereco(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    parte = f.doc.exportador
    if parte is None or not parte.endereco or not parte.endereco.strip():
        return None
    texto = parte.endereco.strip()
    cidade = parte.cidade.strip() if parte.cidade and parte.cidade.strip() else None
    return Valor(((texto, cidade),), texto, texto, f.arquivo.id, parte.pagina)


def juntar_enderecos(valores: list[Valor], campo: NomeCampo, ctx: Contexto, col: Col) -> Valor:
    enderecos: list[tuple[str, str | None]] = []
    for v in valores:
        for e in v.chave:
            if not any(enderecos_compativeis(e, existente) for existente in enderecos):
                enderecos.append(e)
    return Valor(tuple(enderecos), " / ".join(t for t, _ in enderecos), texto_soma(valores), None, None)


def listas_de_enderecos_iguais(a: tuple, b: tuple) -> bool:
    """Cada item é (endereço, cidade): cidades diferentes divergem mesmo com endereço parecido."""
    return all(any(enderecos_compativeis(x, y) for y in b) for x in a) and all(
        any(enderecos_compativeis(y, x) for x in a) for y in b
    )


def obter_pais(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    if campo == "pais_exportador":
        parte = f.doc.exportador
        texto, pagina = (parte.pais, parte.pagina) if parte else (None, None)
    else:
        texto, pagina = (f.doc.pais_origem.valor, f.doc.pais_origem.pagina) if f.doc.pais_origem else (None, None)
        if texto:  # 'JAPAN / MALAYSIA': cada país é um valor do conjunto, em qualquer ordem
            return valor_conjunto(re.split(r"\s*(?:/|,|;|&|\bAND\b)\s*", texto, flags=re.IGNORECASE), normalizar_pais, f, pagina)
    return valor_conjunto([texto] if texto else [], normalizar_pais, f, pagina)


def obter_moeda(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    moeda = f.doc.moeda
    if moeda is None:
        return None
    return valor_conjunto([moeda.valor], normalizar_moeda, f, moeda.pagina)


def _exibir_incoterm(f: Fonte) -> str:
    inc = f.doc.incoterm
    sigla = normalizar_incoterm(inc.codigo)
    local = nome_do_porto(inc.local) if inc.local else ""
    return f"{sigla} {local}".strip()


def obter_incoterm(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    inc = f.doc.incoterm
    if inc is None or not normalizar_incoterm(inc.codigo):
        return None
    sigla = normalizar_incoterm(inc.codigo)
    return Valor(frozenset({sigla}), _exibir_incoterm(f), inc.texto_original, f.arquivo.id, inc.pagina)
