"""Parte (exportador, consignatário, notify...) que o documento traz com nome."""

from typing import TypeGuard

from app.schemas import Parte


def parte_preenchida(p: Parte | None) -> TypeGuard[Parte]:
    return p is not None and bool(p.nome.strip())
