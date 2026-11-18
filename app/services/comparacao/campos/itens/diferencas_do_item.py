"""Diferenças entre os atributos de um item nos documentos."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.services.comparacao.campos.itens.descricoes_do_item import IGUAL, GRAVIDADE, Veredito, comparar_descricoes
from app.services.comparacao.campos.itens.quantidade_do_item import unidades_de_familias_diferentes
from app.services.comparacao.campos.itens.tipos import ColItens, ItemAgrupado, Linha
from app.services.comparacao.campos.regras_por_campo.pesos_volumes_quantidade import nota_fator_mil
from app.services.comparacao.normalizacao.encurtar_texto import encurtar
from app.services.comparacao.normalizacao.item import (
    normalizar_descricao,
    normalizar_lote,
    normalizar_referencia,
    normalizar_validade,
)

Informado = tuple[ColItens, ItemAgrupado]
ConferirPar = Callable[[ColItens, ColItens], bool]


@dataclass
class Atributo:
    nome: str  # vai em LinhaItem.diferencas
    rotulo: str  # usado na mensagem
    informado: Callable[[ItemAgrupado], bool]
    iguais: Callable[[ItemAgrupado, ItemAgrupado], bool]
    chave_exibicao: Callable[[ItemAgrupado], Any]  # agrupa valores iguais na mensagem
    exibicao: Callable[[ItemAgrupado], str]


@dataclass
class DiferencasDoItem:
    """As diferenças que são erro e, à parte, o par de descrições só escritas de outro jeito."""

    erros: list[tuple[str, str]] = field(default_factory=list)  # (nome da diferença, mensagem)
    escrita_diferente: tuple[str, str] | None = None


def _validades(item: ItemAgrupado) -> list[str]:
    return list(dict.fromkeys(normalizar_validade(v) for v in item.validades))


def _quantidades_comparaveis_diferentes(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    return not unidades_de_familias_diferentes(a, b) and abs(a.quantidade[1] - b.quantidade[1]) > 1e-6


def _descricao_generica(x: ItemAgrupado) -> bool:
    """'SYNTHETIC YARN', 'BOTTLED WINE': categoria, não o produto (sem referência nem número)."""
    return not x.referencia and not any(ch.isdigit() for ch in x.descricao)


def _exibir_descricao(x: ItemAgrupado) -> str:
    """Descrição curta; com a referência entre parênteses se ela não estiver na descrição."""
    if x.referencia and normalizar_referencia(x.referencia) not in normalizar_referencia(x.descricao):
        return f"{encurtar(x.descricao)} (ref. {x.referencia})"
    return encurtar(x.descricao)


def _chave_da_descricao(x: ItemAgrupado) -> tuple[str, str]:
    return normalizar_referencia(x.referencia or ""), normalizar_descricao(x.descricao)


OUTROS_ATRIBUTOS = [
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


def diferencas_item(linha: Linha, colunas: list[ColItens]) -> DiferencasDoItem:
    """As diferenças entre quaisquer duas colunas."""
    return _diferencas(linha, colunas, lambda c1, c2: True)


def diferencas_com_o_conhecimento(linha: Linha, colunas: list[ColItens]) -> DiferencasDoItem:
    """As diferenças só entre pares de colunas em que uma é o conhecimento."""
    return _diferencas(linha, colunas, lambda c1, c2: c1.conhecimento or c2.conhecimento)


def _diferencas(linha: Linha, colunas: list[ColItens], conferir_par: ConferirPar) -> DiferencasDoItem:
    presentes = [(c, linha[c.col.chave]) for c in colunas if c.col.chave in linha]
    resultado = _diferenca_de_descricao(presentes, conferir_par)
    for atributo in OUTROS_ATRIBUTOS:
        informados = [(c, x) for c, x in presentes if atributo.informado(x)]
        if any(not atributo.iguais(x, y) for (c1, x), (c2, y) in _pares(informados, conferir_par)):
            nota = ""
            if atributo.nome == "quantidade":
                nota = nota_fator_mil([(x.quantidade[1], x.quantidade_exibicao or "", x.unidade) for _, x in informados])
            grupos = _texto_grupos(informados, atributo.chave_exibicao, atributo.exibicao)
            resultado.erros.append((atributo.nome, f"{atributo.rotulo} {grupos}{nota}"))
    return resultado


def _pares(informados: list[Informado], conferir_par: ConferirPar) -> list[tuple[Informado, Informado]]:
    return [(a, b) for n, a in enumerate(informados) for b in informados[n + 1:] if conferir_par(a[0], b[0])]


def _diferenca_de_descricao(presentes: list[Informado], conferir_par: ConferirPar) -> DiferencasDoItem:
    """Erro na contradição ou em outra mercadoria; a escrita diferente fica à parte, para o aviso."""
    informados = [(c, x) for c, x in presentes if x.descricao and not (c.conhecimento and _descricao_generica(x))]
    vereditos = [(_veredito_do_par(a[1], b[1], informados), a, b) for a, b in _pares(informados, conferir_par)]
    if not vereditos:
        return DiferencasDoItem()
    pior, a, b = max(vereditos, key=lambda v: GRAVIDADE[v[0].classe])
    if pior.diverge:
        grupos = _texto_grupos(informados, _chave_da_descricao, _exibir_descricao)
        return DiferencasDoItem([("descricao", f"descrição {grupos}{_nota_da_contradicao(pior, a, b)}")])
    if pior.classe == "escrita_diferente":
        return DiferencasDoItem(escrita_diferente=(encurtar(a[1].descricao), encurtar(b[1].descricao)))
    return DiferencasDoItem()


def _veredito_do_par(x: ItemAgrupado, y: ItemAgrupado, informados: list[Informado]) -> Veredito:
    """Se um terceiro documento diz o mesmo que um dos dois, o par vale pelo melhor dos dois caminhos."""
    veredito = comparar_descricoes(x, y)
    if veredito.classe in ("igual", "contradicao"):
        return veredito
    outros = [z for _, z in informados if z is not x and z is not y]
    pelo_terceiro = [comparar_descricoes(z, y) for z in outros if comparar_descricoes(x, z) == IGUAL]
    pelo_terceiro += [comparar_descricoes(x, z) for z in outros if comparar_descricoes(z, y) == IGUAL]
    return min([veredito, *pelo_terceiro], key=lambda v: GRAVIDADE[v.classe])


def _nota_da_contradicao(veredito: Veredito, a: Informado, b: Informado) -> str:
    """' — Invoice 150 W × Packing List 120 W' e, num caractere de diferença com scan, que pode ser leitura."""
    c = veredito.contradicao
    if c is None:
        return ""
    nota = f" — {a[0].col.nome_curto} {c.de_a} × {b[0].col.nome_curto} {c.de_b}"
    escaneados = [col.col.nome_curto for col, _ in (a, b) if any(f.escaneado is True for f in col.col.fontes)]
    if c.um_caractere and escaneados:
        plural = "escaneado" if len(escaneados) == 1 else "escaneados"
        nota += f"; {' e '.join(escaneados)} {plural}, pode ser leitura — conferir na imagem"
    return nota


def _texto_grupos(
    informados: list[Informado], chave: Callable[[ItemAgrupado], Any], exibir: Callable[[ItemAgrupado], str]
) -> str:
    """'Invoice POLIRMX HD 475 × Packing List/BL POLIREX YK 455' — minoria primeiro."""
    grupos: dict[Any, tuple[list[str], ItemAgrupado]] = {}
    for c, x in informados:
        grupos.setdefault(chave(x), ([], x))[0].append(c.col.nome_curto)
    ordenados = sorted(grupos.values(), key=lambda g: len(g[0]))
    return " × ".join(f"{'/'.join(nomes)} {exibir(x)}" for nomes, x in ordenados)
