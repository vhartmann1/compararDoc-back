"""Orquestra extração -> comparação. Interface consumida pela API (não mudar a assinatura)."""

from collections.abc import Callable

from app.config import settings
from app.schemas import ArquivoEntrada, Etapa, Modalidade, ResultadoPipeline
from app.services import comparador, extrator, extrator_mock


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
    modulo = extrator if settings.modo_extrator_efetivo == "claude" else extrator_mock
    extracoes, uso = modulo.extrair_arquivos(arquivos)

    avisar("COMPARANDO")
    resultado = comparador.comparar([(a, extracoes[a.id]) for a in arquivos], modalidade)
    return ResultadoPipeline(resultado=resultado, extracoes=extracoes, uso=uso)
