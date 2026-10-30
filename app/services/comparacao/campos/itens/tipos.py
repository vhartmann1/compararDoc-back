"""Tipos internos da comparação de itens."""

from dataclasses import dataclass

from app.services.comparacao.tipos import Col


@dataclass
class ItemAgrupado:
    """Linhas do mesmo código num documento, somadas (cobre o PL que junta 2 lotes numa linha)."""

    codigo: str | None
    descricao: str
    referencia: str | None
    quantidade: tuple[str, float] | None  # (unidade canônica, total)
    quantidade_exibicao: str | None
    unidade: str | None  # unidade do documento, se todas as linhas usam a mesma
    lotes: list[str]
    validades: list[str]
    arquivo_id: str
    pagina: int | None


@dataclass
class ColItens:
    col: Col
    itens: list[ItemAgrupado]
    conhecimento: bool = False


Linha = dict[str, ItemAgrupado]  # chave da coluna -> item daquela coluna (só as colunas que têm o item)
