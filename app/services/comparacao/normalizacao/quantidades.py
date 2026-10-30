"""Pesos em KG, unidades de quantidade equivalentes e espécies de volume."""

import re

from app.schemas import Medida
from app.services.comparacao.normalizacao.texto import sem_acento

KG_POR_UNIDADE: dict[str, float] = {
    "KG": 1.0,
    "LB": 0.45359237,
    "MT": 1000.0,
    "TON": 1000.0,
    "G": 0.001,
}


# Unidades de quantidade equivalentes: unidade -> (unidade canônica, fator)
UNIDADES_QUANTIDADE: dict[str, tuple[str, float]] = {
    **dict.fromkeys(["PAR", "PARES", "PAIR", "PAIRS", "PRS", "PR", "PRS."], ("PARES", 1.0)),
    **dict.fromkeys(["KG", "KGS", "KILO", "KILOS", "QUILO", "QUILOS"], ("KG", 1.0)),
    **dict.fromkeys(
        ["TON", "TONS", "TONELADA", "TONELADAS", "TONNE", "TONNES", "MT", "MTS", "TO", "TNE", "T", "TM"], ("KG", 1000.0)
    ),
    **dict.fromkeys(["LB", "LBS", "POUND", "POUNDS"], ("KG", 0.45359237)),
    **dict.fromkeys(
        ["PC", "PCS", "PIECE", "PIECES", "UN", "UND", "UNID", "UNIDADE", "UNIDADES", "UNIT", "UNITS",
         "PECA", "PECAS", "PZA", "PIEZAS", "EA", "EACH"],
        ("PECAS", 1.0),
    ),
    **dict.fromkeys(["BAG", "BAGS", "SACO", "SACOS", "BOLSA", "BOLSAS", "SACA", "SACAS"], ("SACOS", 1.0)),
    **dict.fromkeys(
        ["CARTON", "CARTONS", "CTN", "CTNS", "CAR", "CASE", "CASES", "CAJA", "CAJAS", "CAIXA", "CAIXAS", "CX", "CXS",
         "BOX", "BOXES", "CARTONE", "CARTONI"],
        ("CAIXAS", 1.0),
    ),
    **dict.fromkeys(["DRUM", "DRUMS", "TAMBOR", "TAMBORES"], ("TAMBORES", 1.0)),
    **dict.fromkeys(["PALLET", "PALLETS", "PALETE", "PALETES", "PALET", "PALETS", "PLT", "PLTS"], ("PALETES", 1.0)),
    **dict.fromkeys(
        ["BOTTLE", "BOTTLES", "BOTELLA", "BOTELLAS", "GARRAFA", "GARRAFAS", "BT", "BTL", "BTLS", "BOTTIGLIA", "BOTTIGLIE"],
        ("GARRAFAS", 1.0),
    ),
    **dict.fromkeys(["L", "LT", "LTS", "LITRO", "LITROS", "LITER", "LITERS", "LITRE", "LITRES"], ("L", 1.0)),
    **dict.fromkeys(["M", "MTR", "MTRS", "METRO", "METROS", "METER", "METERS"], ("M", 1.0)),
    **dict.fromkeys(["M2", "SQM", "METRO QUADRADO", "METROS QUADRADOS"], ("M2", 1.0)),
    **dict.fromkeys(["DZ", "DOZ", "DUZIA", "DUZIAS", "DOZEN", "DOZENS"], ("PECAS", 12.0)),
}


def para_kg(medida: Medida) -> float | None:
    """Converte a medida para KG. Unidade desconhecida ("OUTRA") => None."""
    fator = KG_POR_UNIDADE.get(medida.unidade)
    if fator is None:
        return None
    return round(medida.valor * fator, 3)


# Embalagens de níveis diferentes: 2 paletes e 160 caixas podem ser a mesma carga.
EMBALAGENS = {"SACOS", "CAIXAS", "PALETES", "TAMBORES", "PECAS"}  # espécies de volume; peça = bobina etc.


def embalagem(unidade: str) -> str | None:
    """'CTNS' -> 'CAIXAS'; 'PIECES' -> 'PECAS'; 'PACKAGES' (genérica) ou desconhecida -> None."""
    canonica, _ = unidade_quantidade(unidade)
    return canonica if canonica in EMBALAGENS else None


def unidade_quantidade(unidade: str) -> tuple[str, float]:
    """'PAIRS' -> ('PARES', 1.0); 'TON' -> ('KG', 1000.0). Desconhecida -> (unidade normalizada, 1.0)."""
    chave = " ".join(re.sub(r"[^A-Z0-9 ]", " ", sem_acento(unidade).upper()).split())
    if chave in UNIDADES_QUANTIDADE:
        return UNIDADES_QUANTIDADE[chave]
    sem_ponto = chave.replace(" ", "")
    if sem_ponto in UNIDADES_QUANTIDADE:
        return UNIDADES_QUANTIDADE[sem_ponto]
    return chave, 1.0
