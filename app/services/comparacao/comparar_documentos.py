"""Compara Invoice × Packing List × Conhecimento: campos, itens, coerência e inconsistências internas."""

from app.schemas import (
    ArquivoEntrada,
    Comparacao,
    Divergencia,
    ExtracaoArquivo,
    Modalidade,
    ResultadoComparacao,
    StatusResultado,
    TipoDocumento,
)
from app.services.comparacao.coerencia_incoterm_frete import divergencias_de_coerencia
from app.services.comparacao.colunas_da_comparacao import montar_comparacoes
from app.services.comparacao.comparar_campos import comparar_colunas
from app.services.comparacao.constantes import CAMPOS_SEMPRE_VISIVEIS
from app.services.comparacao.escolha_dos_documentos import escolher_documentos
from app.services.comparacao.identificacao_do_documento import ref_documento
from app.services.comparacao.inconsistencias_internas import avisos_amostras, avisos_pais_origem, divergencias_internas
from app.services.comparacao.itens.comparar_itens import comparar_todos_os_itens
from app.services.comparacao.pareamento_invoice_packing_list import parear
from app.services.comparacao.tipos import Contexto, Fonte


def comparar(
    extracoes: list[tuple[ArquivoEntrada, ExtracaoArquivo]], modalidade: Modalidade | None = None
) -> ResultadoComparacao:
    """`extracoes` na ordem em que os arquivos foram enviados."""
    avisos: list[str] = []
    escolha = escolher_documentos(extracoes, avisos)
    por_tipo = escolha.por_tipo
    invoices, pls, conhecimentos = por_tipo["invoice"], por_tipo["packing_list"], por_tipo["conhecimento"]
    grupos = parear(invoices, pls, avisos)

    comparacoes: list[Comparacao] = []
    divergencias: list[Divergencia] = []
    for comparacao_id, prefixo, colunas in montar_comparacoes(grupos, conhecimentos):
        ctx = Contexto(comparacao_id, prefixo, avisos, modalidade)
        comparacoes.append(comparar_colunas(ctx, colunas))
        divergencias.extend(ctx.divergencias)

    itens, divergencias_itens = comparar_todos_os_itens(grupos, conhecimentos, avisos)
    divergencias.extend(divergencias_itens)

    usados = sorted((f for fs in por_tipo.values() for f in fs), key=lambda f: f.ordem)
    divergencias.extend(divergencias_de_coerencia(grupos, conhecimentos))
    divergencias.extend(d for f in usados + escolha.fora_da_soma for d in divergencias_internas(f))
    avisos.extend(avisos_amostras(por_tipo["invoice"]))
    avisos.extend(avisos_pais_origem(por_tipo["invoice"]))
    return ResultadoComparacao(
        status=_status_geral(por_tipo, comparacoes, divergencias),
        documentos=[ref_documento(f) for f in usados],
        comparacoes=comparacoes,
        itens=itens,
        divergencias=divergencias,
        avisos=avisos,
    )


def _status_geral(
    por_tipo: dict[TipoDocumento, list[Fonte]], comparacoes: list[Comparacao], divergencias: list[Divergencia]
) -> StatusResultado:
    campos = [c for comp in comparacoes for c in comp.campos]
    if divergencias or any(c.status == "DIVERGENTE" for c in campos):
        return "DIVERGENTE"
    if any(not fontes for fontes in por_tipo.values()) or any(
        c.status == "NAO_ENCONTRADO" and c.campo in CAMPOS_SEMPRE_VISIVEIS for c in campos
    ):
        return "INCOMPLETO"
    return "OK"
