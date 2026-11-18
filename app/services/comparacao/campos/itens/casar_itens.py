"""Casa os itens de um documento com os do outro."""

from collections.abc import Callable

from app.services.comparacao.campos.itens.casar_pelo_texto import casar_pelo_texto
from app.services.comparacao.campos.itens.tipos import ColItens, ItemAgrupado, Linha
from app.services.comparacao.normalizacao.item import normalizar_codigo_item, normalizar_descricao, normalizar_lote

Combina = Callable[[ItemAgrupado, ItemAgrupado], bool]
Pares = list[tuple[int, int]]  # (linha, posição do item)


def _mesma_descricao(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    return normalizar_descricao(a.descricao) == normalizar_descricao(b.descricao)


def _mesmo_lote(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    return bool({normalizar_lote(l) for l in a.lotes} & {normalizar_lote(l) for l in b.lotes})


def _mesmo_codigo(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    return bool(a.codigo and b.codigo and normalizar_codigo_item(a.codigo) == normalizar_codigo_item(b.codigo))


def _livres(total: int, pares: Pares, lado: int) -> list[int]:
    usados = {par[lado] for par in pares}
    return [n for n in range(total) if n not in usados]


def _pelo_codigo(linhas: list[list[ItemAgrupado]], itens: list[ItemAgrupado]) -> Pares:
    """Cada item com a primeira linha livre do mesmo código."""
    pares: Pares = []
    for i, item in enumerate(itens):
        livres = _livres(len(linhas), pares, 0)
        l = next((l for l in livres if any(_mesmo_codigo(item, x) for x in linhas[l])), None)
        if l is not None:
            pares.append((l, i))
    return pares


def _unicos(linhas: list[list[ItemAgrupado]], itens: list[ItemAgrupado], pares: Pares, combina: Combina) -> Pares:
    """Item e linha que combinam só um com o outro: lote trocado entre duas linhas continua erro de lote."""
    novos: Pares = []
    for i in _livres(len(itens), pares, 1):
        livres_l, livres_i = _livres(len(linhas), pares + novos, 0), _livres(len(itens), pares + novos, 1)
        da_linha = [l for l in livres_l if any(combina(itens[i], x) for x in linhas[l])]
        if len(da_linha) != 1:
            continue
        if sum(1 for outro in livres_i if any(combina(itens[outro], x) for x in linhas[da_linha[0]])) == 1:
            novos.append((da_linha[0], i))
    return novos


def casar(
    linhas: list[list[ItemAgrupado]], itens: list[ItemAgrupado], generico_nao_casa: bool = False
) -> tuple[list[tuple[int, ItemAgrupado]], list[int], list[ItemAgrupado]]:
    """Casa por código, descrição idêntica, lote, texto e o último par; devolve os casados e as sobras."""
    pares = _pelo_codigo(linhas, itens)
    pares += _unicos(linhas, itens, pares, _mesma_descricao)
    pares += _unicos(linhas, itens, pares, _mesmo_lote)
    pelo_texto = casar_pelo_texto(linhas, itens, _livres(len(linhas), pares, 0), _livres(len(itens), pares, 1),
                                  pela_quantidade=not generico_nao_casa)
    pares += pelo_texto.pares
    livres_l, livres_i = _livres(len(linhas), pares, 0), _livres(len(itens), pares, 1)
    genericos = pelo_texto.genericos if generico_nao_casa else set()
    if len(livres_l) == 1 and len(livres_i) == 1 and not genericos:
        pares.append((livres_l.pop(), livres_i.pop()))  # sobrou um de cada lado: o mesmo item com dados diferentes
    return [(l, itens[i]) for l, i in pares], livres_l, [itens[i] for i in livres_i]


def casar_base(base: list[ColItens]) -> list[Linha]:
    """Linhas Invoice × Packing List (ou de uma coluna só), na ordem da primeira coluna."""
    primeira = base[0]
    linhas: list[Linha] = [{primeira.col.chave: item} for item in primeira.itens]
    if len(base) == 1:
        return linhas
    segunda = base[1]
    casados, _, sobras = casar([[item] for item in primeira.itens], segunda.itens)
    for i, item in casados:
        linhas[i][segunda.col.chave] = item
    return linhas + [{segunda.col.chave: item} for item in sobras]
