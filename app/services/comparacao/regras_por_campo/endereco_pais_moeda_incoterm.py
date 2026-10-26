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
from app.services.comparacao.regras_por_campo.exportador_consignatario import fabricante_alternativo
from app.services.comparacao.regras_por_campo.regra import com_alternativas_iguais, texto_soma, valor_conjunto
from app.services.comparacao.tipos import Col, Contexto, Fonte, Valor

SEPARADORES_DE_PAISES = re.compile(r"\s*(?:/|,|;|&|\bAND\b)\s*|\s+-\s+", re.IGNORECASE)  # 'GUINEA-BISSAU' fica


def obter_endereco(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    parte = f.doc.exportador
    if parte is None or not parte.endereco or not parte.endereco.strip():
        return None
    texto = parte.endereco.strip()
    itens = [(texto, _cidade(parte), False)]
    fab = fabricante_alternativo(f)
    if fab and fab.endereco and fab.endereco.strip():
        itens.append((fab.endereco.strip(), _cidade(fab), True))
    exibicao = texto + (f" (fabricante: {itens[1][0]})" if len(itens) > 1 else "")
    return Valor(tuple(itens), exibicao, texto, f.arquivo.id, parte.pagina)


def _cidade(parte) -> str | None:
    return parte.cidade.strip() if parte.cidade and parte.cidade.strip() else None


def juntar_enderecos(valores: list[Valor], campo: NomeCampo, ctx: Contexto, col: Col) -> Valor:
    enderecos: list[tuple[str, str | None, bool]] = []
    for v in valores:
        for e in v.chave:
            if not any(_enderecos_iguais(e, existente) for existente in enderecos):
                enderecos.append(e)
    return Valor(tuple(enderecos), " / ".join(t for t, _, alt in enderecos if not alt), texto_soma(valores), None, None)


def _enderecos_iguais(a: tuple, b: tuple) -> bool:
    return enderecos_compativeis(a[:2], b[:2])


def listas_de_enderecos_iguais(a: tuple, b: tuple) -> bool:
    """Itens (endereço, cidade, alternativo): cidades diferentes divergem mesmo com endereço parecido."""
    return com_alternativas_iguais(a, b, _enderecos_iguais)


def obter_pais(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    if campo == "pais_exportador":
        return _pais_do_exportador(f)
    else:
        texto, pagina = (f.doc.pais_origem.valor, f.doc.pais_origem.pagina) if f.doc.pais_origem else (None, None)
        if texto:  # 'JAPAN / MALAYSIA' ou 'JAPAN - MALAYSIA': cada país é um valor do conjunto, em qualquer ordem
            return valor_conjunto(SEPARADORES_DE_PAISES.split(texto), normalizar_pais, f, pagina)
    return valor_conjunto([texto] if texto else [], normalizar_pais, f, pagina)


def _pais_do_exportador(f: Fonte) -> Valor | None:
    parte, fab = f.doc.exportador, fabricante_alternativo(f)
    if parte is None or not parte.pais or not normalizar_pais(parte.pais):
        return None
    itens = {(normalizar_pais(parte.pais), False)}
    if fab and fab.pais and normalizar_pais(fab.pais) and normalizar_pais(fab.pais) != normalizar_pais(parte.pais):
        itens.add((normalizar_pais(fab.pais), True))
    exibicao = parte.pais.strip() + (f" (fabricante: {fab.pais.strip()})" if len(itens) > 1 else "")
    return Valor(frozenset(itens), exibicao, parte.pais, f.arquivo.id, parte.pagina)


def paises_do_exportador_iguais(a: frozenset, b: frozenset) -> bool:
    return com_alternativas_iguais(tuple(a), tuple(b), lambda x, y: x[0] == y[0])


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
