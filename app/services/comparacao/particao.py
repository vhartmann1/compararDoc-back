"""Partição de uma lista em duas por um critério, mantendo a ordem."""

from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def particionar(itens: list[T], criterio: Callable[[T], bool]) -> tuple[list[T], list[T]]:
    """(os que atendem ao critério, os que não atendem), cada um na ordem original."""
    sim: list[T] = []
    nao: list[T] = []
    for x in itens:
        (sim if criterio(x) else nao).append(x)
    return sim, nao
