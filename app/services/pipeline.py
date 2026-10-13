"""Orquestra extração -> comparação. Interface consumida pela API (não mudar a assinatura)."""

from collections.abc import Callable

from app.config import settings
from app.schemas import ArquivoEntrada, Etapa, Modalidade, ResultadoPipeline
from app.services.comparacao import comparar
from app.services.leitura import ler_pela_api, ler_pelo_claude_code, ler_simulado

EXTRATORES = {"claude": ler_pela_api, "mock": ler_simulado, "claude_code": ler_pelo_claude_code}


def processar(
    arquivos: list[ArquivoEntrada],
    ao_mudar_etapa: Callable[[Etapa], None] | None = None,
    modalidade: Modalidade | None = None,
) -> ResultadoPipeline:
    """Síncrona. Levanta exceção com mensagem em português se algo falhar."""
    if not arquivos:
        raise ValueError("Nenhum arquivo enviado para análise.")
    avisar = ao_mudar_etapa or (lambda _etapa: None)

    avisar("LENDO_DOCUMENTOS")
    extracoes, uso = EXTRATORES[settings.modo_extrator_efetivo].extrair_arquivos(arquivos)

    avisar("COMPARANDO")
    resultado = comparar([(a, extracoes[a.id]) for a in arquivos], modalidade)
    return ResultadoPipeline(resultado=resultado, extracoes=extracoes, uso=uso)
