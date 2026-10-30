"""Números, pesos, NCM, CNPJ e dinheiro no formato brasileiro."""

import re

from app.services.comparacao.normalizacao.texto import so_digitos


def formatar_numero(valor: float, casas: int = 2) -> str:
    """21250 -> '21.250,00'."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_kg(valor: float) -> str:
    """21250.0 -> '21.250,00 kg'."""
    return f"{formatar_numero(valor)} kg"


def formatar_contagem(valor: float, unidade: str) -> str:
    """53, 'CTN' -> '53 CTN'; 24.5, 'TON' -> '24,5 TON'."""
    if float(valor).is_integer():
        numero = formatar_numero(valor, 0)
    else:
        numero = formatar_numero(valor, 3).rstrip("0").rstrip(",")
    return f"{numero} {unidade}".strip()


def formatar_ncm(codigo: str) -> str:
    """'39011010' -> '3901.10.10'; '390110' -> '3901.10'; '3304' -> '3304'."""
    partes = [codigo[:4], codigo[4:6], codigo[6:8]]
    return ".".join(p for p in partes if p)


def formatar_cnpj(cnpj: str) -> str:
    """14 dígitos -> '12.345.678/0001-90'; outros tamanhos e códigos com letras (registro chinês) ficam como vieram."""
    d = so_digitos(cnpj)
    if len(d) != 14 or re.search(r"[A-Za-z]", cnpj):
        return cnpj.strip()
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def formatar_dinheiro(valor: float, moeda: str | None) -> str:
    """720, 'USD' -> 'USD 720,00'."""
    return f"{moeda} {formatar_numero(valor)}" if moeda else formatar_numero(valor)
