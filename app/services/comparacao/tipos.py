"""Tipos internos da comparação."""

from dataclasses import dataclass, field
from typing import Any

from app.schemas import ArquivoEntrada, Divergencia, DocumentoExtraido, Modalidade


@dataclass(eq=False)
class Fonte:
    """Um documento enviado: dois com o mesmo conteúdo continuam sendo dois (igualdade por identidade)."""

    arquivo: ArquivoEntrada
    doc: DocumentoExtraido
    ordem: tuple[int, int]  # (posição do arquivo no envio, posição do documento no arquivo)
    invoice_par: DocumentoExtraido | None = None  # para packing list: a invoice com quem foi pareado
    duplicatas: list["Fonte"] = field(default_factory=list)  # o mesmo documento em outros arquivos, do melhor ao pior
    escaneado: bool | None = None  # imagem ou scan; None quando não se sabe


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

    def so_conhecimento(self) -> bool:
        return all(f.doc.tipo == "conhecimento" for f in self.fontes)


@dataclass
class Contexto:
    comparacao_id: str
    prefixo: str  # "Invoice L30518777 — " ou ""
    modalidade: Modalidade | None = None


@dataclass
class Apontamentos:
    """Avisos e divergências de uma conferência, cada lista na ordem em que surgem."""

    avisos: list[str] = field(default_factory=list)
    divergencias: list[Divergencia] = field(default_factory=list)

    def __add__(self, outros: "Apontamentos") -> "Apontamentos":
        return Apontamentos(self.avisos + outros.avisos, self.divergencias + outros.divergencias)
