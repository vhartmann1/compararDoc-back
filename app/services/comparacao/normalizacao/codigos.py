"""NCM, CNPJ e incoterm só com o que identifica o código."""

import re

from app.services.comparacao.normalizacao.texto import sem_acento, so_digitos


def normalizar_ncm(codigo: str) -> str:
    """Só dígitos, no máximo 8 (códigos nacionais de 10 dígitos, ex. Colômbia, viram NCM de 8)."""
    return so_digitos(codigo)[:8]


def normalizar_cnpj(cnpj: str | None) -> str | None:
    digitos = so_digitos(cnpj or "")
    return digitos or None


def normalizar_incoterm(codigo: str) -> str:
    """'fob' / 'FOB 2020' / 'CFR-ITAPOA' -> 'FOB' / 'CFR' (as 3 primeiras letras)."""
    letras = re.sub(r"[^A-Z]", "", sem_acento(codigo).upper())
    return letras[:3]
