"""Regras de exportador e consignatário."""

from app.schemas import NomeCampo, Parte
from app.services.comparacao.campos.regras_por_campo.regra import com_alternativas_iguais, texto_soma
from app.services.comparacao.normalizacao.codigos import normalizar_cnpj
from app.services.comparacao.normalizacao.formatacao import formatar_cnpj
from app.services.comparacao.partes.mesma_empresa import relacao_entre_nomes, relacao_entre_partes
from app.services.comparacao.partes.parte_preenchida import parte_preenchida
from app.services.comparacao.tipos import Col, Contexto, Fonte, Valor


def obter_parte(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    parte: Parte | None = f.doc.exportador if campo == "exportador" else f.doc.consignatario
    if not parte_preenchida(parte):
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
    return fab if f.doc.tipo != "conhecimento" and parte_preenchida(fab) else None


def fabricantes_iguais(fontes: list[Fonte]) -> bool:
    """Os fabricantes declarados nos documentos são todos a mesma empresa (ou só um declara)."""
    fabs = [fab for f in fontes if (fab := fabricante_alternativo(f))]
    return all(relacao_entre_partes(fabs[0], fab) == "mesma" for fab in fabs[1:])


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
    """Os dois com CNPJ/Tax ID => compara os dígitos; senão, se o nome é da mesma empresa."""
    if a[1] and b[1]:
        return a[1] == b[1]
    return relacao_entre_nomes(a[0], b[0]) == "mesma"


def listas_de_partes_iguais(a: tuple, b: tuple) -> bool:
    return com_alternativas_iguais(a, b, _partes_iguais)
