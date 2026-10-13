"""Regras de exportador e consignatário."""

from app.schemas import NomeCampo, Parte
from app.services.comparacao.constantes import CNPJ_RAIZ_CAPITAL
from app.services.comparacao.normalizacao import formatar_cnpj, nomes_equivalentes, normalizar_cnpj
from app.services.comparacao.regras_por_campo.regra import texto_soma
from app.services.comparacao.tipos import Col, Contexto, Fonte, Valor


def obter_parte(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    parte: Parte | None = f.doc.exportador if campo == "exportador" else f.doc.consignatario
    if parte is None or not parte.nome.strip():
        return None
    item = (parte.nome.strip(), normalizar_cnpj(parte.cnpj))
    texto = f"{parte.nome.strip()} — {parte.cnpj}" if parte.cnpj else parte.nome.strip()
    return Valor((item,), _exibir_partes([item]), texto, f.arquivo.id, parte.pagina)


def juntar_partes(valores: list[Valor], campo: NomeCampo, ctx: Contexto, col: Col) -> Valor:
    itens: list[tuple[str, str | None]] = []
    for v in valores:
        for item in v.chave:
            if not any(_partes_iguais(item, existente) for existente in itens):
                itens.append(item)
    return Valor(tuple(itens), _exibir_partes(itens), texto_soma(valores), None, None)


def _exibir_partes(itens: list[tuple[str, str | None]]) -> str:
    return " / ".join(f"{nome} ({formatar_cnpj(cnpj)})" if cnpj else nome for nome, cnpj in itens)


def _partes_iguais(a: tuple[str, str | None], b: tuple[str, str | None]) -> bool:
    """Os dois com CNPJ/Tax ID => compara os dígitos; senão, o nome normalizado."""
    if a[1] and b[1]:
        return a[1] == b[1]
    return nomes_equivalentes(a[0], b[0])


def _eh_capital(item: tuple[str, str | None]) -> bool:
    nome, cnpj = item
    if cnpj:
        return cnpj.startswith(CNPJ_RAIZ_CAPITAL)
    return "CAPITAL TRADE" in nome.upper()


def conhecimento_consignado_a_capital(col: Col, valor: Valor) -> bool:
    return col.chave.startswith("conhecimento") and all(_eh_capital(item) for item in valor.chave)


def listas_de_partes_iguais(a: tuple, b: tuple) -> bool:
    return all(any(_partes_iguais(x, y) for y in b) for x in a) and all(
        any(_partes_iguais(y, x) for x in a) for y in b
    )
