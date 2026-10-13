"""Orquestra extração -> comparação. Interface consumida pela API (não mudar a assinatura)."""

from collections.abc import Callable

from app.config import settings
from app.schemas import ArquivoEntrada, Etapa, Modalidade, ResultadoPipeline
from app.services import comparador, extrator, extrator_claude_code, extrator_mock

EXTRATORES = {"claude": extrator, "mock": extrator_mock, "claude_code": extrator_claude_code}


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
    resultado = comparador.comparar([(a, extracoes[a.id]) for a in arquivos], modalidade)
    return ResultadoPipeline(resultado=resultado, extracoes=extracoes, uso=uso)
