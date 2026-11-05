"""Qual versão do mesmo documento vale: os critérios em ordem, cada um com o motivo que vai no aviso."""

import re
from collections.abc import Callable
from typing import Any

from app.services.comparacao.constantes import PRIORIDADE_FORMATO, PRIORIDADE_VERSAO
from app.services.comparacao.documentos.identificacao_do_documento import PROFORMA
from app.services.comparacao.tipos import Fonte

REVISAO = re.compile(r"(?i)(?<![A-Z])(rev(?:is(?:ed|ad[oa]|ao|ão))?|ajustad[oa]|corrigid[oa]|final(?:is)?)(?![A-Z])[\s._-]*(\d+)?")


PALAVRAS_DE_RASCUNHO = [
    "drafts?", "rascunhos?", "preliminar(?:y)?", "borrador", "c[oó]pias?", "copy", r"(?:n[aã]o|non)[\s_-]*original",
]
RASCUNHO = re.compile(rf"(?i)(?<![A-Z])({'|'.join(PALAVRAS_DE_RASCUNHO)})(?![A-Z])")
ORIGINAL = re.compile(r"(?i)(?<![A-Z])(orig(?:inal(?:es|s)?|inais)?)(?![A-Z])")


def versao_pelo_nome(nome: str) -> int:
    """'CI DRAFT.pdf' -1 < 'CI.pdf' 0 < 'CI ORIGINAL.pdf' 1: rascunho ou cópia no nome perde mesmo que diga original."""
    return -1 if RASCUNHO.search(nome) else 1 if ORIGINAL.search(nome) else 0


def revisao_pelo_nome(nome: str) -> tuple[int, int]:
    """'CI REV-1.pdf' > 'CI.pdf'; 'PL REV.2' > 'PL REV.1': o nome do arquivo é o que diz qual versão é a mais nova."""
    marcas = REVISAO.findall(nome)
    return (1, max(int(n or 0) for _, n in marcas)) if marcas else (0, 0)


CRITERIOS: list[tuple[Callable[[Fonte], Any], str]] = [
    # proforma com o número da invoice nunca vale mais que ela
    (lambda f: not PROFORMA.search(f.arquivo.nome), "porque o outro é proforma"),
    (lambda f: PRIORIDADE_VERSAO[f.doc.versao], "pela versão lida no documento"),
    (lambda f: versao_pelo_nome(f.arquivo.nome), "pelo nome do arquivo (original × rascunho ou cópia)"),
    (lambda f: revisao_pelo_nome(f.arquivo.nome), "por ser a revisão mais nova pelo nome do arquivo"),
    (lambda f: PRIORIDADE_FORMATO.get(f.arquivo.media_type, 0), "por ser o PDF (vale mais que Excel ou Word)"),
    # a lista por contêiner sem número é detalhe do PL
    (lambda f: bool(f.doc.numero or f.doc.invoices_referenciadas), "por trazer o número"),
    (lambda f: f.ordem, "por ser o último enviado"),
]
ULTIMO_ENVIADO = CRITERIOS[-1][1]


def preferencia(f: Fonte) -> tuple:
    """Mesmo documento => fica 1: não proforma, versão, nome (rascunho/original, revisão), PDF, identificado, último."""
    return tuple(criterio(f) for criterio, _ in CRITERIOS)


def motivo(melhor: Fonte, outra: Fonte) -> str:
    """O primeiro critério em que o usado vence o ignorado; nenhum (a mesma fonte): o último enviado."""
    return next((m for criterio, m in CRITERIOS if criterio(melhor) != criterio(outra)), ULTIMO_ENVIADO)
