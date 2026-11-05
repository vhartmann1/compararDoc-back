"""Base das regras por campo: como ler o valor de um documento, somar e comparar."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.schemas import NomeCampo
from app.services.comparacao.tipos import Col, Contexto, Fonte, Valor

Informados = list[tuple[Col, Valor]]
Grupos = list[tuple[list[Col], Valor]]
Iguais = Callable[[Any, Any], bool]
TextoDaDivergencia = Callable[[Grupos, Grupos], str]  # (minoria primeiro, na ordem das colunas) -> texto


@dataclass
class Comparador:
    """Como os valores informados se comparam e como a divergência entre eles é escrita."""

    iguais: Iguais
    texto: TextoDaDivergencia


def texto_dos_grupos(ordenados: Grupos, grupos: Grupos | None = None) -> str:
    """'Invoice/PL 10 KG × BL 12 KG': cada grupo com as colunas que trazem o valor."""
    return " × ".join(f"{'/'.join(c.nome_curto for c in cols)} {valor.exibicao}" for cols, valor in ordenados)


@dataclass
class Regra:
    obter: Callable[[Fonte, NomeCampo, Contexto], Valor | None]
    juntar: Callable[[list[Valor], NomeCampo, Contexto, Col], Valor | None]
    iguais: Iguais
    soma_alternativas: bool = False  # o grupo de documentos iguais leva as alternativas (fabricante) de todos
    conhecimento_e_referencia: bool = False  # invoice e PL conferem com o conhecimento, não entre si
    contido_no_outro: Callable[[Any, Any], bool] | None = None  # o conhecimento pode trazer só parte (PO, NCM)
    # ganchos dos campos com caso próprio; None é o comportamento comum
    vazio_em: Callable[[list[Col]], set[str]] | None = None  # chaves das colunas em que o campo não se confere
    separar_aceitos: Callable[[Contexto, Informados], tuple[Informados, str | None]] | None = None
    incomparavel: Callable[[Contexto, Informados], str | None] | None = None  # aviso que deixa INSUFICIENTE
    comparador: Callable[[Contexto, list[Valor]], Comparador] | None = None  # igualdade que depende dos valores
    incomparavel_nos_grupos: Callable[[Contexto, Grupos], str | None] | None = None
    texto_da_divergencia: TextoDaDivergencia | None = None
    avisos_da_comparacao: Callable[[list[Col]], list[str]] | None = None  # depois do status, sem o prefixo

    def comparador_para(self, ctx: Contexto, valores: list[Valor]) -> Comparador:
        if self.comparador:
            return self.comparador(ctx, valores)
        return Comparador(self.iguais, self.texto_da_divergencia or texto_dos_grupos)


def primeira_pagina(f: Fonte) -> int | None:
    return f.doc.paginas[0] if f.doc.paginas else None


def texto_soma(valores: list[Valor]) -> str | None:
    textos = [v.texto_original for v in valores if v.texto_original]
    return " + ".join(textos) or None


# Textos simples (nº invoice, PO, portos): conjunto de valores normalizados ----
def valor_conjunto(textos: list[str], normalizar, f: Fonte, pagina: int | None) -> Valor | None:
    exibicoes: dict[str, str] = {}
    for texto in textos:
        if texto and texto.strip():
            chave = normalizar(texto)
            if chave:
                exibicoes.setdefault(chave, texto.strip())
    if not exibicoes:
        return None
    return Valor(
        frozenset(exibicoes),
        " / ".join(exibicoes.values()),
        " / ".join(t.strip() for t in textos if t and t.strip()),
        f.arquivo.id,
        pagina,
    )


def juntar_conjunto(valores: list[Valor], campo: NomeCampo, ctx: Contexto, col: Col) -> Valor:
    chave = frozenset().union(*(v.chave for v in valores))
    exibicoes = list(dict.fromkeys(e for v in valores for e in v.exibicao.split(" / ")))
    return Valor(chave, " / ".join(exibicoes), texto_soma(valores), None, None)


def conjuntos_iguais(a: frozenset, b: frozenset) -> bool:
    return a == b


def com_alternativas_iguais(a: tuple, b: tuple, iguais: Callable[[Any, Any], bool]) -> bool:
    """Itens terminam em `alternativo` (ex.: fabricante); um lado pode bater com a alternativa do outro."""

    def cobre(x: tuple, y: tuple) -> bool:
        principais = [i for i in x if not i[-1]]
        return bool(principais) and all(any(iguais(p, j) for j in y) for p in principais)

    def tem_alternativa(x: tuple) -> bool:
        return any(i[-1] for i in x)

    mutuo = cobre(a, b) and cobre(b, a)
    pela_alternativa = (cobre(a, b) and tem_alternativa(b)) or (cobre(b, a) and tem_alternativa(a))
    return mutuo or pela_alternativa
