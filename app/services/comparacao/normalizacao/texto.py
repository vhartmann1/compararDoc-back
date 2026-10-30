"""Texto sem acento, só dígitos ou só letras e números, e medidas de parecença entre textos."""

import difflib
import re
import unicodedata


def so_digitos(codigo: str) -> str:
    return re.sub(r"\D", "", codigo)


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def distancia_de_edicao(x: str, y: str) -> int:
    """Damerau-Levenshtein restrita: inserção, remoção, troca e vizinhas invertidas custam 1 cada."""
    duas_atras: list[int] = []
    anterior = list(range(len(y) + 1))
    for i, cx in enumerate(x, start=1):
        atual = [i]
        for j, cy in enumerate(y, start=1):
            custo = min(anterior[j] + 1, atual[j - 1] + 1, anterior[j - 1] + (cx != cy))
            if i > 1 and j > 1 and cx == y[j - 2] and x[i - 2] == cy:
                custo = min(custo, duas_atras[j - 2] + 1)
            atual.append(custo)
        duas_atras, anterior = anterior, atual
    return anterior[-1]


def so_letras_numeros(texto: str) -> str:
    return " ".join(re.sub(r"[^A-Z0-9 ]", " ", sem_acento(texto).upper()).split())


def similaridade(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()
