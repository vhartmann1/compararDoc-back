"""Número de invoice, packing list e PO: série, marca do tipo e erro de digitação."""

import re

from app.services.comparacao.normalizacao.texto import distancia_de_edicao, sem_acento


def normalizar_numero_documento(numero: str) -> str:
    """'0077032707' -> '77032707'; 'inv-2026/01' -> 'INV202601'. Só letras e dígitos, sem zeros à esquerda."""
    limpo = re.sub(r"[^A-Z0-9]", "", sem_acento(numero).upper())
    return limpo.lstrip("0") or limpo


# Marcas do tipo de documento no meio do número: 'XYZ/PL/2526/LOC0123' é o PL da invoice 'XYZ2526/LOC0123'
MARCAS_DE_TIPO = {"PL", "PKL", "PK", "PACKING", "LIST", "CI", "INV", "INVOICE"}


# 'FT FA.2026/' de 'FT FA.2026/0123': série com o ano, separada do número por barra
SERIE_DO_ANO = re.compile(r"^(?:[A-Z]{1,4}\.?\s+)?[A-Z]+\.?\s*(?:19|20)\d{2}\s*/\s*(?=\w)")


def numero_da_invoice_para_conferir(numero: str) -> str:
    """'FT FA.2026/260781' -> '260781': a série com o ano sai só na conferência, não no pareamento."""
    return normalizar_numero_documento(SERIE_DO_ANO.sub("", sem_acento(numero).upper()))


def numero_sem_serie(numero: str) -> str:
    """'FT A26/000123' e 'GR A26/000123' -> 'A26000123'; 'XYZ/PL/25/0123' -> 'XYZ250123': série e marca do tipo saem."""
    texto = sem_acento(numero).upper()
    partes = texto.split(None, 1)
    if len(partes) == 2 and re.fullmatch(r"[A-Z]{1,4}\.?", partes[0]) and re.search(r"\d", partes[1]):
        texto = partes[1]
    pedacos = [p for p in re.split(r"[\s/._-]+", texto) if p not in MARCAS_DE_TIPO]
    return normalizar_numero_documento("".join(pedacos) or texto)  # só a marca ('INVOICE'): não é número, fica como está


def mesmo_numero(x: str, y: str) -> bool:
    """Já normalizados: iguais, ou um é o outro com letras na frente ('NFB907311' × '907311', série ou rótulo)."""
    maior, menor = (x, y) if len(x) >= len(y) else (y, x)
    return x == y or (len(menor) >= 3 and maior.endswith(menor) and maior[: -len(menor)].isalpha())


def numeros_quase_iguais(a: str, b: str) -> bool:
    """Erro de digitação: até 2 caracteres trocados, a mais ou a menos (1 se o menor tem 5): '90711' × '907101'."""
    menor = min(len(a), len(b))
    limite = 2 if menor >= 6 else 1 if menor == 5 else 0
    return limite > 0 and distancia_de_edicao(a, b) <= limite


PREFIXO_PO = re.compile(r"^\s*(P\.?\s?O\.?|PURCHASE ORDER|PEDIDO)(?=[\s:#.\-0-9])\s*(N[O°º]\.?|NR\.?|NUMBER|#|:)?\s*")


SEPARADORES_DE_PO = re.compile(r"[&,，;]|\s+/\s+")  # 'PO#1&PO#2', 'PO#1, PO#2', '1 / 2'; '114/26' é um número só


def pos_do_texto(texto: str) -> list[str]:
    """'PO# 5501&PO# 5502' -> ['PO# 5501', 'PO# 5502']: cada pedido de uma lista, como escrito."""
    return [p.strip() for p in SEPARADORES_DE_PO.split(texto) if p.strip()]


def normalizar_po(po: str) -> str:
    """'PO 15 March' e '15 March' -> '15MARCH': o rótulo na frente não faz parte do número."""
    return re.sub(r"[^A-Z0-9]", "", PREFIXO_PO.sub("", sem_acento(po).upper()))
