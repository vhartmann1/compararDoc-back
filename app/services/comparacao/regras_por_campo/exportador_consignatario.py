"""Regras de exportador e consignatário."""

from app.schemas import NomeCampo, Parte
from app.services.comparacao.constantes import CNPJ_RAIZ_CAPITAL
from app.services.comparacao.normalizacao import formatar_cnpj, nomes_equivalentes, normalizar_cnpj
from app.services.comparacao.regras_por_campo.regra import com_alternativas_iguais, texto_soma
from app.services.comparacao.tipos import Col, Contexto, Fonte, Valor


def obter_parte(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    parte: Parte | None = f.doc.exportador if campo == "exportador" else f.doc.consignatario
    if parte is None or not parte.nome.strip():
        return None
    itens = [(parte.nome.strip(), normalizar_cnpj(parte.cnpj), False)]
    fabricante = fabricante_alternativo(f) if campo == "exportador" else None
    if fabricante and not _partes_iguais(itens[0], (fabricante.nome.strip(), normalizar_cnpj(fabricante.cnpj), True)):
        itens.append((fabricante.nome.strip(), normalizar_cnpj(fabricante.cnpj), True))
    texto = f"{parte.nome.strip()} — {parte.cnpj}" if parte.cnpj else parte.nome.strip()
    return Valor(tuple(itens), _exibir_partes(itens), texto, f.arquivo.id, parte.pagina)


def fabricante_alternativo(f: Fonte) -> Parte | None:
    """Fabricante da invoice/PL, que o checklist aceita como shipper do BL."""
    fab = f.doc.fabricante
    return fab if f.doc.tipo != "conhecimento" and fab and fab.nome.strip() else None


def juntar_partes(valores: list[Valor], campo: NomeCampo, ctx: Contexto, col: Col) -> Valor:
    itens: list[tuple[str, str | None, bool]] = []
    for v in valores:
        for item in v.chave:
            if not any(_partes_iguais(item, existente) for existente in itens):
                itens.append(item)
    return Valor(tuple(itens), _exibir_partes(itens), texto_soma(valores), None, None)


def _exibir_partes(itens: list[tuple[str, str | None, bool]]) -> str:
    principais = " / ".join(f"{n} ({formatar_cnpj(c)})" if c else n for n, c, alt in itens if not alt)
    fabricantes = ", ".join(n for n, _, alt in itens if alt)
    return f"{principais} (fabricante: {fabricantes})" if fabricantes else principais


def _partes_iguais(a: tuple, b: tuple) -> bool:
    """Os dois com CNPJ/Tax ID => compara os dígitos; senão, o nome normalizado."""
    if a[1] and b[1]:
        return a[1] == b[1]
    return nomes_equivalentes(a[0], b[0])


def _eh_capital(item: tuple) -> bool:
    nome, cnpj = item[0], item[1]
    if cnpj:
        return cnpj.startswith(CNPJ_RAIZ_CAPITAL)
    return "CAPITAL TRADE" in nome.upper()


def conhecimento_consignado_a_capital(col: Col, valor: Valor) -> bool:
    return col.chave.startswith("conhecimento") and all(_eh_capital(item) for item in valor.chave)


def listas_de_partes_iguais(a: tuple, b: tuple) -> bool:
    return com_alternativas_iguais(a, b, _partes_iguais)
