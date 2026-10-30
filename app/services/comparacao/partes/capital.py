"""Se uma parte é a Capital Trade: pelo CNPJ quando há (identificar) ou por qualquer sinal (descartar)."""

from app.schemas import Parte
from app.services.comparacao.normalizacao.codigos import normalizar_cnpj
from app.services.comparacao.tipos import Valor

CNPJ_RAIZ_CAPITAL = "07872326"  # Capital Trade Importação e Exportação Ltda. (qualquer filial)
NOME_DA_CAPITAL = "CAPITAL TRADE"


def _identificada_como_capital(nome: str, cnpj: str | None) -> bool:
    """Com CNPJ, só a raiz decide; sem ele, o nome."""
    if cnpj:
        return cnpj.startswith(CNPJ_RAIZ_CAPITAL)
    return NOME_DA_CAPITAL in nome.upper()


def parte_da_capital(parte: Parte) -> bool:
    return _identificada_como_capital(parte.nome, normalizar_cnpj(parte.cnpj))


def valor_da_capital(valor: Valor) -> bool:
    """Todas as empresas do valor identificadas como a Capital."""
    return all(_identificada_como_capital(nome, cnpj) for nome, cnpj, _ in valor.chave)


def sem_sinal_da_capital(valor: Valor) -> bool:
    """Nem o nome nem a raiz do CNPJ em nenhuma empresa: um CNPJ lido errado não vira cliente."""
    return not any(NOME_DA_CAPITAL in nome.upper() or (cnpj or "").startswith(CNPJ_RAIZ_CAPITAL)
                   for nome, cnpj, _ in valor.chave)
