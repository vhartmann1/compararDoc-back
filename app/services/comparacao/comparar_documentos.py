"""Compara Invoice × Packing List × Conhecimento: campos, itens, coerência e inconsistências internas."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass

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
from app.services.comparacao.campos.comparar_campos import comparar_colunas
from app.services.comparacao.campos.itens.comparar_itens import comparar_todos_os_itens
from app.services.comparacao.coerencia.coerencia_incoterm_frete import divergencias_de_coerencia
from app.services.comparacao.coerencia.frete_somado_ao_total import divergencias_de_frete_no_total
from app.services.comparacao.constantes import CAMPOS_SEMPRE_VISIVEIS
from app.services.comparacao.dentro_do_documento.cabecalho_e_assinatura import avisos_do_cabecalho
from app.services.comparacao.dentro_do_documento.inconsistencias_internas import (
    avisos_amostras,
    avisos_pais_origem,
    divergencias_internas,
)
from app.services.comparacao.dentro_do_documento.presenca_no_checklist import (
    avisos_do_checklist,
    divergencias_do_checklist,
)
from app.services.comparacao.dentro_do_documento.somas_do_documento import avisos_das_somas, divergencias_das_somas
from app.services.comparacao.documentos.colunas_da_comparacao import montar_comparacoes
from app.services.comparacao.documentos.escolha_dos_documentos import escolher_documentos
from app.services.comparacao.documentos.identificacao_do_documento import ref_documento
from app.services.comparacao.documentos.pareamento_invoice_packing_list import parear
from app.services.comparacao.documentos.versoes_com_valor_diferente import (
    avisos_entre_versoes,
    divergencias_entre_versoes,
)
from app.services.comparacao.partes.capital_nos_documentos import divergencias_da_capital
from app.services.comparacao.partes.conferencia_do_notify import avisos_do_notify, divergencias_do_notify
from app.services.comparacao.tipos import Contexto, Fonte


@dataclass
class _Processo:
    """Os documentos escolhidos e pareados, que cada conferência do processo lê."""

    por_tipo: dict[TipoDocumento, list[Fonte]]
    grupos: list[tuple[Fonte | None, Fonte | None]]
    usados: list[Fonte]
    fora_da_soma: list[Fonte]
    modalidade: Modalidade | None

    @property
    def invoices(self) -> list[Fonte]:
        return self.por_tipo["invoice"]

    @property
    def conhecimentos(self) -> list[Fonte]:
        return self.por_tipo["conhecimento"]

    @property
    def conferidos_por_dentro(self) -> list[Fonte]:
        return self.usados + self.fora_da_soma


_DIVERGENCIAS: list[Callable[[_Processo], Iterable[Divergencia]]] = [
    lambda p: divergencias_de_coerencia(p.grupos, p.conhecimentos),
    lambda p: (d for f in p.conferidos_por_dentro for d in divergencias_internas(f)),
    lambda p: (d for f in p.conferidos_por_dentro for d in divergencias_das_somas(f)),
    lambda p: divergencias_entre_versoes(p.usados),
    lambda p: divergencias_do_checklist(p.invoices),
    lambda p: divergencias_de_frete_no_total(p.invoices),
    lambda p: divergencias_da_capital(p.grupos, p.conhecimentos, p.modalidade),
    lambda p: divergencias_do_notify(p.invoices, p.conhecimentos),
]

_AVISOS: list[Callable[[_Processo], Iterable[str]]] = [
    lambda p: avisos_entre_versoes(p.usados),
    lambda p: avisos_do_cabecalho(p.conferidos_por_dentro),
    lambda p: avisos_das_somas(p.conferidos_por_dentro),
    lambda p: avisos_amostras(p.invoices),
    lambda p: avisos_pais_origem(p.invoices),
    lambda p: avisos_do_checklist(p.grupos, p.conhecimentos),
    lambda p: avisos_do_notify(p.invoices, p.invoices + p.por_tipo["packing_list"], p.conhecimentos),
]


def comparar(
    extracoes: list[tuple[ArquivoEntrada, ExtracaoArquivo]], modalidade: Modalidade | None = None
) -> ResultadoComparacao:
    """`extracoes` na ordem em que os arquivos foram enviados."""
    escolha = escolher_documentos(extracoes)
    avisos = escolha.avisos
    por_tipo = escolha.por_tipo
    conhecimentos = por_tipo["conhecimento"]
    grupos = parear(por_tipo["invoice"], por_tipo["packing_list"], avisos)

    comparacoes: list[Comparacao] = []
    divergencias: list[Divergencia] = []
    for comparacao_id, prefixo, colunas in montar_comparacoes(grupos, conhecimentos):
        ctx = Contexto(comparacao_id, prefixo, avisos, modalidade)
        comparacoes.append(comparar_colunas(ctx, colunas))
        divergencias.extend(ctx.divergencias)

    itens, divergencias_itens = comparar_todos_os_itens(grupos, conhecimentos, avisos)
    divergencias.extend(divergencias_itens)

    usados = sorted((f for fs in por_tipo.values() for f in fs), key=lambda f: f.ordem)
    processo = _Processo(por_tipo, grupos, usados, escolha.fora_da_soma, modalidade)
    divergencias.extend(d for conferir in _DIVERGENCIAS for d in conferir(processo))
    avisos.extend(a for conferir in _AVISOS for a in conferir(processo))
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
