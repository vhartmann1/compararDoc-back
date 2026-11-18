"""Casa itens sem código pelo texto: quanto da descrição mais curta está na outra, pesando as palavras raras."""

import math
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from app.services.comparacao.campos.itens.descricoes_do_item import comparar_descricoes, textos_do_item
from app.services.comparacao.campos.itens.fichas_da_descricao import partes, partes_em_comum
from app.services.comparacao.campos.itens.quantidade_do_item import mesma_quantidade
from app.services.comparacao.campos.itens.tipos import ItemAgrupado

# Abaixo disso o que os dois têm em comum é pouco para dizer que são o mesmo item
EVIDENCIA_MINIMA = 0.3


@dataclass(frozen=True)
class Candidato:
    linha: int
    item: int  # posição na lista de itens
    evidencia: float
    mesma_quantidade: bool


@dataclass(frozen=True)
class CasadosPeloTexto:
    pares: list[tuple[int, int]]  # (linha, posição do item)
    genericos: set[int]  # itens que servem igualmente a várias linhas: categoria, não um produto


def casar_pelo_texto(
    linhas: list[list[ItemAgrupado]], itens: list[ItemAgrupado], livres_l: list[int], livres_i: list[int],
    pela_quantidade: bool,
) -> CasadosPeloTexto:
    """Rodada a rodada, casa o par em que cada lado é o melhor candidato do outro; `pela_quantidade` desempata."""
    candidatos = _candidatos(linhas, itens, livres_l, livres_i)
    pares: list[tuple[int, int]] = []
    while True:
        usadas, usados = {l for l, _ in pares}, {i for _, i in pares}
        vivos = [c for c in candidatos if c.linha not in usadas and c.item not in usados]
        aceitos = _melhores_dos_dois_lados(vivos, pela_quantidade)
        if not aceitos and pela_quantidade:
            aceitos = _intercambiaveis(vivos)[:1]
        if not aceitos:
            genericos = {c.item for c in vivos if len(_empatados([v for v in vivos if v.item == c.item], False)) > 1}
            return CasadosPeloTexto(pares, genericos)
        pares += [(c.linha, c.item) for c in aceitos]


def _candidatos(
    linhas: list[list[ItemAgrupado]], itens: list[ItemAgrupado], livres_l: list[int], livres_i: list[int]
) -> list[Candidato]:
    peso = _peso_pela_raridade([x for linha in linhas for x in linha] + itens)
    candidatos = []
    for l in livres_l:
        for i in livres_i:
            if any(comparar_descricoes(x, itens[i]).classe == "contradicao" for x in linhas[l]):
                continue  # medida ou modelo diferente: não é o mesmo item
            evidencia = max(_evidencia(x, itens[i], peso) for x in linhas[l])
            if evidencia >= EVIDENCIA_MINIMA:
                candidatos.append(Candidato(l, i, evidencia, any(mesma_quantidade(x, itens[i]) for x in linhas[l])))
    return candidatos


def _texto(x: ItemAgrupado) -> str:
    return " ; ".join(textos_do_item(x))


def _peso_pela_raridade(todos: list[ItemAgrupado]) -> Callable[[str], float]:
    """Palavra que está em toda linha não distingue nada (peso 0); a que está em uma só pesa mais."""
    frequencia = Counter(p for x in todos for p in set(partes(_texto(x))))
    return lambda parte: math.log((len(todos) + 1) / max(frequencia[parte], 1))


def _evidencia(a: ItemAgrupado, b: ItemAgrupado, peso: Callable[[str], float]) -> float:
    """De 0 a 1: o peso do que os dois têm em comum sobre o peso da descrição mais leve."""
    comum = partes_em_comum(_texto(a), _texto(b))
    em_comum_ = sum(map(peso, comum.comum))
    mais_leve = em_comum_ + min(sum(map(peso, comum.so_a)), sum(map(peso, comum.so_b)))
    return round(em_comum_ / mais_leve, 3) if mais_leve > 0 else 0.0


def _empatados(candidatos: list[Candidato], pela_quantidade: bool) -> list[Candidato]:
    """Os de maior evidência; entre eles, os de mesma quantidade vêm antes quando `pela_quantidade`."""
    if not candidatos:
        return []
    topo = max(c.evidencia for c in candidatos)
    empatados = [c for c in candidatos if c.evidencia == topo]
    com_quantidade = [c for c in empatados if c.mesma_quantidade]
    return com_quantidade if pela_quantidade and len(empatados) > 1 and com_quantidade else empatados


def _melhores_dos_dois_lados(vivos: list[Candidato], pela_quantidade: bool) -> list[Candidato]:
    """Os pares em que a linha tem um único melhor item e esse item tem a mesma linha como única melhor."""
    da_linha = _unico_melhor(vivos, lambda c: c.linha, pela_quantidade)
    do_item = _unico_melhor(vivos, lambda c: c.item, pela_quantidade)
    return [c for c in da_linha.values() if do_item.get(c.item) == c]


def _unico_melhor(
    vivos: list[Candidato], lado: Callable[[Candidato], int], pela_quantidade: bool
) -> dict[int, Candidato]:
    por_lado: dict[int, list[Candidato]] = {}
    for c in vivos:
        por_lado.setdefault(lado(c), []).append(c)
    melhores = {chave: _empatados(cs, pela_quantidade) for chave, cs in por_lado.items()}
    return {chave: cs[0] for chave, cs in melhores.items() if len(cs) == 1}


def _intercambiaveis(vivos: list[Candidato]) -> list[Candidato]:
    """Empate dos dois lados com a mesma quantidade: tanto faz o par, a comparação dá o mesmo resultado."""
    por_linha: dict[int, list[Candidato]] = {}
    por_item: dict[int, list[Candidato]] = {}
    for c in vivos:
        por_linha.setdefault(c.linha, []).append(c)
        por_item.setdefault(c.item, []).append(c)
    return sorted(
        (c for c in vivos if c.mesma_quantidade
         and c in _empatados(por_linha[c.linha], True) and c in _empatados(por_item[c.item], True)),
        key=lambda c: (c.linha, c.item),
    )
