"""Diferenças entre os atributos de um item nos documentos."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.services.comparacao.encurtar_texto import encurtar
from app.services.comparacao.itens.tipos import ColItens, ItemAgrupado, Linha
from app.services.comparacao.normalizacao import (
    descricoes_equivalentes,
    normalizar_descricao,
    normalizar_lote,
    normalizar_referencia,
    normalizar_validade,
    referencias_iguais,
)
from app.services.comparacao.regras_por_campo.pesos_volumes_quantidade import nota_fator_mil


@dataclass
class Atributo:
    nome: str  # vai em LinhaItem.diferencas
    rotulo: str  # usado na mensagem
    informado: Callable[[ItemAgrupado], bool]
    iguais: Callable[[ItemAgrupado, ItemAgrupado], bool]
    chave_exibicao: Callable[[ItemAgrupado], Any]  # agrupa valores iguais na mensagem
    exibicao: Callable[[ItemAgrupado], str]


def _validades(item: ItemAgrupado) -> list[str]:
    return list(dict.fromkeys(normalizar_validade(v) for v in item.validades))


def _quantidades_comparaveis_diferentes(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    return a.quantidade[0] == b.quantidade[0] and abs(a.quantidade[1] - b.quantidade[1]) > 1e-6


def _descricoes_iguais(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    """Com referência/modelo dos dois lados, compara as referências (uma letra muda o produto:
    'POLIREX YK 455' × 'POLIREX ZK 455'); senão, a similaridade das descrições."""
    if a.referencia and b.referencia:
        return referencias_iguais(a.referencia, b.referencia)
    return descricoes_equivalentes(a.descricao, b.descricao)


def _exibir_descricao(x: ItemAgrupado) -> str:
    """Descrição curta; com a referência entre parênteses se ela não estiver na descrição."""
    if x.referencia and normalizar_referencia(x.referencia) not in normalizar_referencia(x.descricao):
        return f"{encurtar(x.descricao)} (ref. {x.referencia})"
    return encurtar(x.descricao)


ATRIBUTOS_ITEM = [
    Atributo(
        "descricao", "descrição", lambda x: bool(x.descricao),
        _descricoes_iguais,
        lambda x: (normalizar_referencia(x.referencia or ""), normalizar_descricao(x.descricao)), _exibir_descricao,
    ),
    Atributo(
        "quantidade", "quantidade", lambda x: x.quantidade is not None,
        lambda a, b: not _quantidades_comparaveis_diferentes(a, b),  # unidades diferentes: não dá para comparar
        lambda x: x.quantidade, lambda x: x.quantidade_exibicao or "",
    ),
    Atributo(
        "lote", "lote", lambda x: bool(x.lotes),
        lambda a, b: {normalizar_lote(l) for l in a.lotes} == {normalizar_lote(l) for l in b.lotes},
        lambda x: frozenset(normalizar_lote(l) for l in x.lotes), lambda x: ", ".join(x.lotes),
    ),
    Atributo(
        "validade", "validade", lambda x: bool(x.validades),
        lambda a, b: set(_validades(a)) == set(_validades(b)),
        lambda x: frozenset(_validades(x)), lambda x: ", ".join(_validades(x)),
    ),
]


def diferencas_item(linha: Linha, colunas: list[ColItens], so_conhecimento: bool) -> list[tuple[str, str]]:
    """Lista de (nome da diferença, texto da mensagem). Com `so_conhecimento`, só contam as diferenças
    entre o conhecimento e outra coluna (invoice × PL já foram comparados em cada par)."""
    difs: list[tuple[str, str]] = []
    for atributo in ATRIBUTOS_ITEM:
        informados = [(c, linha[c.col.chave]) for c in colunas if c.col.chave in linha]
        informados = [(c, x) for c, x in informados if atributo.informado(x)]
        diferentes = any(
            not atributo.iguais(x, y)
            for n, (c1, x) in enumerate(informados)
            for c2, y in informados[n + 1:]
            if not so_conhecimento or c1.conhecimento or c2.conhecimento
        )
        if diferentes:
            nota = ""
            if atributo.nome == "quantidade":
                nota = nota_fator_mil([(x.quantidade[1], x.quantidade_exibicao or "", x.unidade) for _, x in informados])
            difs.append((atributo.nome, f"{atributo.rotulo} {_texto_grupos(atributo, informados)}{nota}"))
    return difs


def _texto_grupos(atributo: Atributo, informados: list[tuple[ColItens, ItemAgrupado]]) -> str:
    """'Invoice POLIRMX HD 475 × Packing List/BL POLIREX YK 455' — minoria primeiro."""
    grupos: dict[Any, tuple[list[str], ItemAgrupado]] = {}
    for c, x in informados:
        grupos.setdefault(atributo.chave_exibicao(x), ([], x))[0].append(c.col.nome_curto)
    ordenados = sorted(grupos.values(), key=lambda g: len(g[0]))
    return " × ".join(f"{'/'.join(nomes)} {atributo.exibicao(x)}" for nomes, x in ordenados)
