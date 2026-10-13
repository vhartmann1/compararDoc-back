"""Instruções com o schema da resposta e a validação dela (structured outputs recusa o schema: grande demais)."""

import json
import re

from app.schemas import ExtracaoArquivo
from app.services.leitura.prompts import PROMPT_SISTEMA

ESFORCO = "high"  # leitura de scans: precisão importa; "medium" barateia se o acerto se mantiver
TENTATIVAS = 2  # JSON inválido => refaz uma vez

SISTEMA = (
    f"{PROMPT_SISTEMA}\n## Formato da resposta\n"
    "Responda só com um objeto JSON válido (sem texto antes ou depois, sem ```), que siga exatamente este "
    "JSON Schema — todos os campos presentes, null quando não houver valor:\n"
    f"{json.dumps(ExtracaoArquivo.model_json_schema(), ensure_ascii=False)}\n"
)


class ErroExtracao(Exception):
    pass


def json_da_resposta(texto: str) -> str:
    """Tira cercas ``` e qualquer texto fora do objeto JSON."""
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto.strip())
    inicio, fim = texto.find("{"), texto.rfind("}")
    return texto[inicio : fim + 1] if inicio >= 0 and fim > inicio else texto
