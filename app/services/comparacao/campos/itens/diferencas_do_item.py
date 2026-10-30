"""Diferenças entre os atributos de um item nos documentos."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.services.comparacao.campos.itens.medidas_do_item import descricoes_iguais_pela_medida
from app.services.comparacao.campos.itens.nome_do_modelo import nome_comeca_o_outro
from app.services.comparacao.campos.itens.tipos import ColItens, ItemAgrupado, Linha
from app.services.comparacao.campos.regras_por_campo.pesos_volumes_quantidade import nota_fator_mil
from app.services.comparacao.normalizacao.encurtar_texto import encurtar
from app.services.comparacao.normalizacao.item import (
    descricoes_equivalentes,
    normalizar_codigo_item,
    normalizar_descricao,
    normalizar_lote,
    normalizar_referencia,
    normalizar_validade,
    referencias_iguais,
)
from app.services.comparacao.normalizacao.texto import sem_acento


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
    """Idêntica é igual; medida diferente diverge; senão descrição contida, referências, código e semelhança."""
    if normalizar_descricao(a.descricao) == normalizar_descricao(b.descricao) and _referencias_na_descricao(a, b):
        return True  # descrição idêntica: a "referência" é só o trecho que cada leitura destacou
    mesmo_codigo = bool(a.codigo and b.codigo and normalizar_codigo_item(a.codigo) == normalizar_codigo_item(b.codigo))
    if _medidas_diferentes(a.descricao, b.descricao) or _atributos_diferentes(a.descricao, b.descricao):
        return False  # mesmo código não salva: a potência, a tensão ou o tamanho mudou
    if descricoes_iguais_pela_medida(a.descricao, b.descricao):
        return True  # só a notação da medida muda: '.800 MM x 1250 MM' e '0.800x1250'
    if _so_o_modelo(a, b) or _so_o_modelo(b, a) or nome_comeca_o_outro(a, b):
        return True
    ra, rb = _referencia_de_modelo(a), _referencia_de_modelo(b)
    sem_conflito = mesmo_codigo or not (ra and rb) or _referencia_da_curta(a, b)
    if _uma_comeca_a_outra(a.descricao, b.descricao) and sem_conflito:
        return True  # a "referência" lida difere (modelo × código do fabricante), mas o item é o mesmo
    if ra and rb:
        return referencias_iguais(ra, rb)
    if mesmo_codigo:
        return True
    return descricoes_equivalentes(a.descricao, b.descricao)


MEDIDA = re.compile(r"(?<![A-Z0-9.,])(\d+(?:[.,]\d+)?) ?(KW|W|V|MA|A|MM|CM|ML|KG|G|L|HZ|K)(?![A-Z0-9])")


def _medidas(descricao: str) -> dict[str, set[float]]:
    """'FONTE 24V 200W' -> {'V': {24}, 'W': {200}}."""
    por_unidade: dict[str, set[float]] = {}
    for valor, unidade in MEDIDA.findall(sem_acento(descricao).upper()):
        por_unidade.setdefault(unidade, set()).add(float(valor.replace(",", ".")))
    return por_unidade


def _medidas_diferentes(a: str, b: str) -> bool:
    """Uma unidade que aparece nas duas descrições com valores diferentes; a que só uma traz não conta."""
    ma, mb = _medidas(a), _medidas(b)
    return any(ma[u] != mb[u] for u in ma.keys() & mb.keys())


ATRIBUTO = re.compile(r"\b([A-Z]{3,}) (\d+)\b(?![.,]\d)")


def _atributos_diferentes(a: str, b: str) -> bool:
    """'GRADE 430' × 'GRADE 304': a mesma palavra seguida de números diferentes."""
    na, nb = (_atributos(x) for x in (a, b))
    return any(na[p] != nb[p] for p in na.keys() & nb.keys())


def _atributos(descricao: str) -> dict[str, set[str]]:
    por_palavra: dict[str, set[str]] = {}
    for palavra, numero in ATRIBUTO.findall(sem_acento(descricao).upper()):
        por_palavra.setdefault(palavra, set()).add(numero)
    return por_palavra


def _referencia_de_modelo(x: ItemAgrupado) -> str | None:
    """A referência lida, se não for a descrição inteira ('COBRE ANTIGO' como as duas coisas não é modelo)."""
    if x.referencia and normalizar_referencia(x.referencia) != normalizar_referencia(x.descricao):
        return x.referencia
    return None


def _referencias_na_descricao(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    """Cada referência lida está dentro da própria descrição (ou falta num dos lados): não há referência a mais."""
    return all(
        not x.referencia or normalizar_referencia(x.referencia) in normalizar_referencia(x.descricao) for x in (a, b)
    )


def _uma_comeca_a_outra(a: str, b: str) -> bool:
    """'CELULA DE CARGA MODELO XL-20' começa 'CELULA DE CARGA MODELO XL-20, CAPACIDADE 10 MN…': o documento só abreviou."""
    curta, longa = sorted((_palavras(a), _palavras(b)), key=len)
    return len(curta) >= 3 and longa[: len(curta)] == curta


def _so_o_modelo(curto: ItemAgrupado, outro: ItemAgrupado) -> bool:
    """'QX-77' × 'QX-77 - medidor': descrição = modelo lido; igual ao código do outro ou começo da descrição dele."""
    modelo = normalizar_referencia(curto.descricao)
    proprios = {normalizar_referencia(r) for r in (curto.referencia, curto.codigo) if r}
    if not any(ch.isdigit() for ch in modelo) or not proprios or not proprios <= {modelo}:
        return False
    do_outro = {normalizar_referencia(r) for r in (outro.referencia, outro.codigo) if r}
    palavras, longas = _palavras(curto.descricao), _palavras(outro.descricao)
    return modelo in do_outro or longas[: len(palavras)] == palavras


def _referencia_da_curta(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    """A referência da descrição mais curta é uma palavra inteira da mais longa (marca lida como modelo)."""
    curto, longo = sorted((a, b), key=lambda x: len(_palavras(x.descricao)))
    ref = _referencia_de_modelo(curto)
    palavras = {normalizar_referencia(p) for p in re.split(r"[\s,;:()]+", longo.descricao)}
    return bool(ref) and normalizar_referencia(ref) in palavras


def _palavras(descricao: str) -> list[str]:
    return re.findall(r"[A-Z0-9]+", sem_acento(descricao).upper())


def _descricao_generica(x: ItemAgrupado) -> bool:
    """'SYNTHETIC YARN', 'BOTTLED WINE': categoria, não o produto (sem referência nem número)."""
    return not x.referencia and not any(ch.isdigit() for ch in x.descricao)


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
    """(nome da diferença, mensagem); com `so_conhecimento`, só as diferenças que envolvem o conhecimento."""
    difs: list[tuple[str, str]] = []
    for atributo in ATRIBUTOS_ITEM:
        informados = [(c, linha[c.col.chave]) for c in colunas if c.col.chave in linha]
        informados = [(c, x) for c, x in informados if atributo.informado(x)]
        if atributo.nome == "descricao":
            informados = [(c, x) for c, x in informados if not (c.conhecimento and _descricao_generica(x))]
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
