"""A mesma leitura de `ler_pela_api`, feita pela CLI do Claude Code (plano de quem está logado). Só teste local."""

import json
import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor

from pydantic import ValidationError

from app.config import settings
from app.schemas import ArquivoEntrada, ExtracaoArquivo, Uso
from app.services.leitura.arquivo_para_conteudo import converter
from app.services.leitura.formato_da_resposta import ESFORCO, SISTEMA, TENTATIVAS, ErroExtracao, json_da_resposta
from app.services.leitura.prompts import PROMPT_USUARIO

logger = logging.getLogger(__name__)

MAX_WORKERS = 3
TEMPO_LIMITE_S = 600
ROTULO_MODELO = "{modelo} (Claude Code)"


def extrair_arquivos(arquivos: list[ArquivoEntrada]) -> tuple[dict[str, ExtracaoArquivo], Uso]:
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        resultados = list(pool.map(_extrair, arquivos))

    extracoes = {a.id: extracao for a, (extracao, _, _) in zip(arquivos, resultados)}
    uso = Uso(
        input_tokens=sum(r[1] for r in resultados),
        output_tokens=sum(r[2] for r in resultados),
        custo_usd_estimado=0.0,  # não é cobrado da API
        modelo=ROTULO_MODELO.format(modelo=settings.modelo_claude),
    )
    return extracoes, uso


def _extrair(arquivo: ArquivoEntrada) -> tuple[ExtracaoArquivo, int, int]:
    conteudo = [*converter(arquivo), {"type": "text", "text": f"Arquivo: {arquivo.nome}\n\n{PROMPT_USUARIO}"}]
    entrada = saida = 0
    for tentativa in range(1, TENTATIVAS + 1):
        resultado = _chamar(arquivo, conteudo)
        e, s = _uso(resultado)
        entrada, saida = entrada + e, saida + s
        try:
            return ExtracaoArquivo.model_validate_json(json_da_resposta(resultado.get("result") or "")), entrada, saida
        except ValidationError as erro:
            if tentativa == TENTATIVAS:
                raise ErroExtracao(
                    f"A Claude devolveu dados em formato inválido para {arquivo.nome}: {erro.errors()[0]['msg']}"
                ) from erro
    raise AssertionError("inalcançável")


def _comando() -> list[str]:
    return [
        settings.claude_code_cli,
        "--print",
        # único formato de entrada que aceita o PDF em bloco, como na API
        "--input-format", "stream-json",
        "--output-format", "stream-json",
        "--verbose",  # exigido com stream-json
        "--model", settings.modelo_claude,
        "--effort", ESFORCO,
        "--system-prompt", SISTEMA,
        "--tools", "",
        "--strict-mcp-config",
        "--setting-sources", "",  # ignora configurações e CLAUDE.md da máquina
        "--no-session-persistence",
    ]  # fmt: skip


def _chamar(arquivo: ArquivoEntrada, conteudo: list[dict]) -> dict:
    mensagem = json.dumps({"type": "user", "message": {"role": "user", "content": conteudo}})
    try:
        processo = subprocess.run(
            _comando(),
            input=mensagem + "\n",
            capture_output=True,
            text=True,
            timeout=TEMPO_LIMITE_S,
            cwd=settings.storage_dir,  # fora do repositório
        )
    except FileNotFoundError as e:
        raise ErroExtracao(
            f"CLI do Claude Code não encontrada ({settings.claude_code_cli}). "
            "Instale e faça login, ou use EXTRATOR_MODO=claude ou mock."
        ) from e
    except subprocess.TimeoutExpired as e:
        raise ErroExtracao(f"O Claude Code demorou demais para ler {arquivo.nome}.") from e

    resultado = _evento_final(processo.stdout)
    if resultado is None:
        logger.error("Claude Code saiu com %s sem resultado: %s", processo.returncode, processo.stderr[-2000:])
        raise ErroExtracao(f"O Claude Code não devolveu resultado para {arquivo.nome} (está logado? `claude` no terminal).")
    if resultado.get("is_error"):
        raise ErroExtracao(f"O Claude Code não conseguiu ler {arquivo.nome}: {resultado.get('result') or resultado.get('subtype')}")
    if resultado.get("stop_reason") == "max_tokens":
        raise ErroExtracao(f"A resposta para {arquivo.nome} ficou grande demais e foi cortada.")
    return resultado


def _evento_final(saida: str) -> dict | None:
    """A CLI escreve um JSON por linha; o resultado é a de `type: result`."""
    for linha in reversed(saida.splitlines()):
        try:
            evento = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if isinstance(evento, dict) and evento.get("type") == "result":
            return evento
    return None


def _uso(resultado: dict) -> tuple[int, int]:
    u = resultado.get("usage") or {}
    entrada = sum(u.get(c) or 0 for c in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    return entrada, u.get("output_tokens") or 0
