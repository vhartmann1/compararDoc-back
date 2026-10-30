"""Moeda normalizada e valores iguais no centavo."""

from app.services.comparacao.normalizacao.texto import sem_acento, so_letras_numeros

MEIO_CENTAVO = 0.005


def iguais_no_centavo(x: float, y: float) -> bool:
    """Iguais em duas casas: 15532.6884 (Excel, sem arredondar) e 15532.69 (PDF impresso) são o mesmo total."""
    return abs(x - y) <= MEIO_CENTAVO + 1e-9


def fecham_no_centavo(x: float, y: float) -> bool:
    """Conta que fecha: a diferença fica abaixo de meio centavo, sem a folga do arredondamento."""
    return abs(x - y) < MEIO_CENTAVO


MOEDAS: dict[str, str] = {
    **dict.fromkeys(["USD", "US$", "U$", "$", "US DOLLAR", "US DOLLARS", "DOLLAR", "DOLLARS", "DOLAR", "DOLARES"], "USD"),
    **dict.fromkeys(["EUR", "€", "EURO", "EUROS"], "EUR"),
    **dict.fromkeys(["CNY", "RMB", "YUAN"], "CNY"),
    **dict.fromkeys(["BRL", "R$", "REAL", "REAIS"], "BRL"),
}


def normalizar_moeda(moeda: str) -> str:
    texto = sem_acento(moeda).upper().strip()
    return MOEDAS.get(texto, MOEDAS.get(so_letras_numeros(texto), so_letras_numeros(texto)))
