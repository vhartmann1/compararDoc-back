"""Medidas 'espessura x largura' na descrição: '.800 MM x 1250.000 MM' e '0.800x1250.000' são a mesma."""

import re

from app.services.comparacao.normalizacao.texto import sem_acento

NUMERO = r"(\d*\.\d+|\d+)"
SEPARADOR = r"\s*(?:MM)?\s*[X×*]\s*"
DIMENSOES = re.compile(rf"(?<![A-Z0-9.]){NUMERO}{SEPARADOR}{NUMERO}(?:{SEPARADOR}{NUMERO})?(?![0-9])")
TEXTO_SEM_MEDIDAS = re.compile(r"[^A-Z]+")
# a medida com o 'MM' final e o 'x' que a cola na palavra seguinte ('0.800x1250.000xCOIL')
MEDIDA_NA_FRASE = re.compile(DIMENSOES.pattern + r"(?:\s*MM\b)?(?:\s*[X×*](?=[A-Z]))?")


def medidas(descricao: str) -> tuple[tuple[float, ...], ...]:
    """'COIL .800 MM x 1250.000 MM' -> ((0.8, 1250.0),); sem 'número x número' -> ()."""
    texto = sem_acento(descricao).upper()
    return tuple(tuple(float(n) for n in grupo if n) for grupo in DIMENSOES.findall(texto))


def _inicio(descricao: str) -> list[str]:
    """As duas primeiras palavras sem números: o produto, antes das medidas."""
    return [p for p in TEXTO_SEM_MEDIDAS.split(sem_acento(descricao).upper()) if len(p) > 1][:2]


def mesmas_medidas(a: str, b: str) -> bool:
    """O mesmo produto (duas primeiras palavras) com as mesmas medidas, escritas de outro jeito."""
    ma, inicio = medidas(a), _inicio(a)
    return bool(ma) and ma == medidas(b) and len(inicio) == 2 and inicio == _inicio(b)


def _palavras(descricao: str) -> list[str]:
    """Palavras com a medida numa notação só: '.800 MM x 1250.000 MM' e '0.800x1250.000' viram '0.8X1250'."""
    texto = MEDIDA_NA_FRASE.sub(lambda m: " " + "X".join(f"{float(n):g}" for n in m.groups() if n) + " ",
                          sem_acento(descricao).upper())
    return re.findall(r"[A-Z0-9.]+", texto.replace(". ", " "))


def descricoes_iguais_pela_medida(a: str, b: str) -> bool:
    """As mesmas palavras, na mesma ordem, depois de escrever a medida numa notação só."""
    return mesmas_medidas(a, b) and _palavras(a) == _palavras(b)
