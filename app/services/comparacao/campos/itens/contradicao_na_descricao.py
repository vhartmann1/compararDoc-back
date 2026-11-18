"""Contradição entre duas descrições: as duas dizem a mesma coisa com valor diferente."""

import re
from dataclasses import dataclass

from app.services.comparacao.campos.itens.fichas_da_descricao import (
    colar,
    em_comum,
    fichas,
    polegadas,
    quase_iguais,
    tem_numero,
)
from app.services.comparacao.normalizacao.formatacao import formatar_contagem
from app.services.comparacao.normalizacao.texto import sem_acento

UNIDADES = "KW|W|V|MA|A|MM|CM|ML|CL|KG|G|L|HZ|K"
MEDIDA = re.compile(rf"(?<![A-Z0-9.,])(\d+(?:[.,]\d+)?) ?({UNIDADES})(?![A-Z0-9])")
ATRIBUTO = re.compile(rf"\b([A-Z]{{3,}}) (\d+)\b(?![.,]\d)(?! ?(?:{UNIDADES})(?![A-Z0-9]))")  # '24 V' é medida
NEGACOES = {"NOT", "NON", "WITHOUT", "SEM", "NAO", "SIN", "SANS", "OHNE"}


@dataclass(frozen=True)
class Contradicao:
    """O que cada descrição diz; `um_caractere` quando a diferença pode ser só de digitação ou de leitura."""

    de_a: str
    de_b: str
    um_caractere: bool = False


def contradicao(a: str, b: str) -> Contradicao | None:
    """Medida, atributo, polegadas, negação ou identificador com um caractere de diferença."""
    return (_medidas_diferentes(a, b) or _polegadas_diferentes(a, b) or _atributos_diferentes(a, b)
            or _negacao_so_de_um_lado(a, b) or _identificadores_quase_iguais(a, b))


def _medidas(descricao: str) -> dict[str, set[float]]:
    """'FONTE 24V 200W' -> {'V': {24}, 'W': {200}}."""
    por_unidade: dict[str, set[float]] = {}
    for valor, unidade in MEDIDA.findall(sem_acento(descricao).upper()):
        por_unidade.setdefault(unidade, set()).add(float(valor.replace(",", ".")))
    return por_unidade


def _medidas_diferentes(a: str, b: str) -> Contradicao | None:
    """A mesma unidade nas duas descrições com valores diferentes; a que só uma traz não conta."""
    ma, mb = _medidas(a), _medidas(b)
    unidade = next((u for u in sorted(ma.keys() & mb.keys()) if ma[u] != mb[u]), None)
    return Contradicao(_valores(ma[unidade], unidade), _valores(mb[unidade], unidade)) if unidade else None


def _valores(valores: set[float], unidade: str) -> str:
    return " e ".join(formatar_contagem(v, unidade) for v in sorted(valores))


def _atributos(descricao: str) -> dict[str, set[str]]:
    por_palavra: dict[str, set[str]] = {}
    for palavra, numero in ATRIBUTO.findall(sem_acento(descricao).upper()):
        por_palavra.setdefault(palavra, set()).add(numero)
    return por_palavra


def _atributos_diferentes(a: str, b: str) -> Contradicao | None:
    """'GRADE 430' × 'GRADE 304': a mesma palavra seguida de números diferentes."""
    na, nb = _atributos(a), _atributos(b)
    palavra = next((p for p in sorted(na.keys() & nb.keys()) if na[p] != nb[p]), None)
    if not palavra:
        return None
    return Contradicao(f"{palavra} {' e '.join(sorted(na[palavra]))}", f"{palavra} {' e '.join(sorted(nb[palavra]))}")


def _polegadas_diferentes(a: str, b: str) -> Contradicao | None:
    pa, pb = polegadas(a), polegadas(b)
    if not (pa and pb) or pa == pb:
        return None
    return Contradicao(*(" e ".join(f'{formatar_contagem(v, "")}"' for v in sorted(p)) for p in (pa, pb)))


def _negacao_so_de_um_lado(a: str, b: str) -> Contradicao | None:
    """'NOT ANODIZED' × 'ANODIZED': a negação só de um lado, seguida de uma palavra que o outro também diz."""
    comum = em_comum(a, b)
    for texto, so_meu, inverter in ((a, comum.so_a, False), (b, comum.so_b, True)):
        ps = fichas(texto)
        pares = zip(ps, ps[1:])
        negada = next((f"{n} {p}" for n, p in pares if n in NEGACOES and n in so_meu and p in comum.comum), None)
        if negada:
            lados = (negada, negada.split(" ", 1)[1])
            return Contradicao(*(reversed(lados) if inverter else lados))
    return None


def _identificadores_quase_iguais(a: str, b: str) -> Contradicao | None:
    """Um número ou código que só difere por um caractere: 'QR52F3' × 'QR52F4', '615' × '6158'."""
    fa, fb = fichas(a), fichas(b)
    so_a, so_b = colar(fa, set(fb)) - colar(fb, set(fa)), colar(fb, set(fa)) - colar(fa, set(fb))
    candidatas_a, candidatas_b = _com_vizinhas(fa, so_a), _com_vizinhas(fb, so_b)
    medidas_a, medidas_b = _numeros_com_unidade(a), _numeros_com_unidade(b)
    par = next(((x, y) for x in candidatas_a for y in candidatas_b
                if (x in so_a or y in so_b) and quase_iguais(x, y)
                and not (x in medidas_a and y in medidas_b)), None)  # '750 ML' × '75 CL': quem compara é a medida
    return Contradicao(*par, um_caractere=True) if par else None


def _numeros_com_unidade(descricao: str) -> set[str]:
    """Os números seguidos de unidade de medida, na notação das fichas: quem os compara é a regra da medida."""
    return {f"{float(valor.replace(',', '.')):g}" for valor, _ in MEDIDA.findall(sem_acento(descricao).upper())}


def _com_vizinhas(todas: list[str], so_minhas: set[str]) -> list[str]:
    """As fichas que só este lado traz e elas coladas à vizinha ('QZ' + 'QR52F4'), só as que têm número."""
    coladas = {"".join(todas[i: i + 2]) for i in range(len(todas) - 1) if so_minhas & set(todas[i: i + 2])}
    return sorted(f for f in so_minhas | coladas if tem_numero(f))
