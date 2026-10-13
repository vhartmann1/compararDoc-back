"""Extração com a Claude API: uma requisição por arquivo, saída JSON validada contra ExtracaoArquivo.

Por que não structured outputs (`output_config.format`): a partir do schema v3 (itens, incoterm,
inconsistências...) a API recusa o schema com "The compiled grammar is too large". Por isso o schema
vai no prompt de sistema e a resposta é validada com Pydantic; se vier inválida, refaz uma vez.
"""

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor

import anthropic
from pydantic import ValidationError

from app.config import settings
from app.schemas import ArquivoEntrada, ExtracaoArquivo, Uso
from app.services.conversor import converter
from app.services.prompts import PROMPT_SISTEMA, PROMPT_USUARIO

logger = logging.getLogger(__name__)

MAX_WORKERS = 4
MAX_TOKENS = 16000
ESFORCO = "high"  # leitura de scans: precisão importa; "medium" barateia se o acerto se mantiver

# US$ por milhão de tokens: (entrada, saída, leitura do cache). Gravar no cache custa 1,25× a entrada (TTL 5 min).
PRECOS = {
    "claude-opus-5-5": (4.0, 20.0, 0.20),
    "claude-sonnet-5-5": (2.0, 10.0, 0.20),
}
PRECO_PADRAO = PRECOS["claude-opus-5-5"]
MULTIPLICADOR_GRAVACAO_CACHE = 1.25
TENTATIVAS = 2  # JSON inválido => refaz uma vez

SISTEMA = (
    f"{PROMPT_SISTEMA}\n## Formato da resposta\n"
    "Responda só com um objeto JSON válido (sem texto antes ou depois, sem ```), que siga exatamente este "
    "JSON Schema — todos os campos presentes, null quando não houver valor:\n"
    f"{json.dumps(ExtracaoArquivo.model_json_schema(), ensure_ascii=False)}\n"
)


# As instruções são iguais em toda chamada: ficam em cache e, repetidas em até 5 min, custam só a leitura.
SISTEMA_COM_CACHE = [{"type": "text", "text": SISTEMA, "cache_control": {"type": "ephemeral"}}]


class ErroExtracao(Exception):
    pass


def extrair_arquivos(arquivos: list[ArquivoEntrada]) -> tuple[dict[str, ExtracaoArquivo], Uso]:
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    # Com vários arquivos em paralelo, cada chamada gravaria o próprio cache; aquecer antes faz todas lerem.
    entrada, saida, custo = _aquecer_cache(client) if len(arquivos) > 1 else (0, 0, 0.0)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        resultados = list(pool.map(lambda a: _extrair(client, a), arquivos))

    extracoes = {a.id: extracao for a, (extracao, _, _, _) in zip(arquivos, resultados)}
    uso = Uso(
        input_tokens=entrada + sum(r[1] for r in resultados),
        output_tokens=saida + sum(r[2] for r in resultados),
        custo_usd_estimado=round(custo + sum(r[3] for r in resultados), 4),
        modelo=settings.modelo_claude,
    )
    return extracoes, uso


def _aquecer_cache(client: anthropic.Anthropic) -> tuple[int, int, float]:
    """Grava as instruções no cache (max_tokens=0: só processa a entrada, não gera resposta).
    Falhar aqui não impede a leitura: só perde a economia."""
    try:
        resposta = client.beta.messages.create(
            **_parametros([{"type": "text", "text": "."}]), max_tokens=0
        )
    except anthropic.APIError:
        logger.warning("Não foi possível aquecer o cache do prompt", exc_info=True)
        return 0, 0, 0.0
    return _uso(resposta)


def _extrair(client: anthropic.Anthropic, arquivo: ArquivoEntrada) -> tuple[ExtracaoArquivo, int, int, float]:
    """Devolve (extração, input_tokens, output_tokens, custo_usd), somando as tentativas."""
    conteudo = [*converter(arquivo), {"type": "text", "text": f"Arquivo: {arquivo.nome}\n\n{PROMPT_USUARIO}"}]
    entrada = saida = 0
    custo = 0.0
    for tentativa in range(1, TENTATIVAS + 1):
        resposta = _chamar(client, arquivo, conteudo)
        e, s, c = _uso(resposta)
        entrada, saida, custo = entrada + e, saida + s, custo + c
        _verificar_parada(resposta, arquivo)
        texto = "".join(b.text for b in resposta.content if b.type == "text")
        try:
            return ExtracaoArquivo.model_validate_json(json_da_resposta(texto)), entrada, saida, custo
        except ValidationError as erro:
            if tentativa == TENTATIVAS:
                raise ErroExtracao(
                    f"A Claude devolveu dados em formato inválido para {arquivo.nome}: {erro.errors()[0]['msg']}"
                ) from erro
    raise AssertionError("inalcançável")


def _chamar(client: anthropic.Anthropic, arquivo: ArquivoEntrada, conteudo: list[dict]):
    try:
        return client.beta.messages.create(**_parametros(conteudo), max_tokens=MAX_TOKENS)
    except anthropic.AuthenticationError as e:
        raise ErroExtracao("Chave da API Anthropic inválida ou ausente (ANTHROPIC_API_KEY).") from e
    except anthropic.PermissionDeniedError as e:
        raise ErroExtracao("A chave da API Anthropic não tem permissão para este modelo.") from e
    except anthropic.RateLimitError as e:
        raise ErroExtracao("Limite de uso da API Anthropic atingido. Tente de novo em alguns minutos.") from e
    except anthropic.BadRequestError as e:
        if "credit balance" in str(e):
            raise ErroExtracao(
                "Sem créditos na API Anthropic. Adicione créditos no Console (Faturamento) e envie novamente."
            ) from e
        raise ErroExtracao(f"A API Anthropic rejeitou o arquivo {arquivo.nome}: {e.message}") from e
    except anthropic.APIStatusError as e:
        raise ErroExtracao(f"Erro da API Anthropic ({e.status_code}) ao ler {arquivo.nome}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise ErroExtracao("Sem conexão com a API Anthropic. Verifique a internet/proxy.") from e


def _parametros(conteudo: list[dict]) -> dict:
    """Parâmetros comuns; aquecimento e leitura precisam ser idênticos até o fim das instruções."""
    return {
        "model": settings.modelo_claude,
        "system": SISTEMA_COM_CACHE,
        "messages": [{"role": "user", "content": conteudo}],
        "output_config": {"effort": ESFORCO},
        # Se o modelo recusar por falso positivo de segurança, a API refaz em outro modelo.
        "betas": ["server-side-fallback-2026-07-01"],
        "fallbacks": "default",
    }


def _verificar_parada(resposta, arquivo: ArquivoEntrada) -> None:
    if resposta.stop_reason == "refusal":
        motivo = resposta.stop_details.explanation if resposta.stop_details else None
        raise ErroExtracao(f"A Claude se recusou a ler {arquivo.nome}." + (f" Motivo: {motivo}" if motivo else ""))
    if resposta.stop_reason == "max_tokens":
        raise ErroExtracao(f"A resposta para {arquivo.nome} ficou grande demais e foi cortada.")


def json_da_resposta(texto: str) -> str:
    """Tira cercas ``` e qualquer texto fora do objeto JSON."""
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto.strip())
    inicio, fim = texto.find("{"), texto.rfind("}")
    return texto[inicio : fim + 1] if inicio >= 0 and fim > inicio else texto


def _uso(resposta) -> tuple[int, int, float]:
    u = resposta.usage
    gravados, lidos = u.cache_creation_input_tokens or 0, u.cache_read_input_tokens or 0
    preco_in, preco_out, preco_leitura = _preco(resposta.model)
    custo = (
        u.input_tokens * preco_in
        + gravados * preco_in * MULTIPLICADOR_GRAVACAO_CACHE
        + lidos * preco_leitura
        + u.output_tokens * preco_out
    ) / 1_000_000
    return u.input_tokens + gravados + lidos, u.output_tokens, custo


def _preco(modelo: str) -> tuple[float, float, float]:
    """Preço do modelo que respondeu (pode ter id com sufixo); senão o do modelo configurado."""
    for nome in (modelo, settings.modelo_claude):
        for chave, preco in PRECOS.items():
            if nome.startswith(chave):
                return preco
    return PRECO_PADRAO
