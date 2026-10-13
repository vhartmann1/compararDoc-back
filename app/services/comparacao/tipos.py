"""Tipos internos da comparação."""

from dataclasses import dataclass, field
from typing import Any

from app.schemas import ArquivoEntrada, Divergencia, DocumentoExtraido, Modalidade


@dataclass
class Fonte:
    """Um documento escolhido para a comparação."""

    arquivo: ArquivoEntrada
    doc: DocumentoExtraido
    ordem: tuple[int, int]  # (posição do arquivo no envio, posição do documento no arquivo)
    invoice_par: DocumentoExtraido | None = None  # para packing list: a invoice com quem foi pareado


@dataclass
class Valor:
    chave: Any  # valor normalizado usado na comparação
    exibicao: str
    texto_original: str | None
    arquivo_id: str | None
    pagina: int | None
    unidade: str | None = None  # unidade como no documento (volumes/quantidade)


@dataclass
class Col:
    chave: str
    rotulo: str
    nome_curto: str  # usado nas mensagens: "Invoice", "Invoices", "AWB"
    fontes: list[Fonte]
    soma: bool = False


@dataclass
class Contexto:
    comparacao_id: str
    prefixo: str  # "Par 1 (L30518777) — " ou ""
    avisos: list[str]
    modalidade: Modalidade | None = None
    divergencias: list[Divergencia] = field(default_factory=list)
    divergentes_na_soma: set[str] = field(default_factory=set)
