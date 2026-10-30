"""Texto encurtado para caber em mensagem e em chave."""

from app.services.comparacao.constantes import TAMANHO_MAX_DESCRICAO


def encurtar(texto: str) -> str:
    texto = " ".join(texto.split())
    return texto if len(texto) <= TAMANHO_MAX_DESCRICAO else texto[: TAMANHO_MAX_DESCRICAO - 1].rstrip() + "…"
