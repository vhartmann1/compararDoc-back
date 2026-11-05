"""Comparação campo a campo: o valor de cada coluna e o status de cada campo."""

from app.schemas import CampoComparado, Coluna, Comparacao, NomeCampo, ValorCampo
from app.services.comparacao.campos.campo_com_triangulacao import status_com_triangulacao
from app.services.comparacao.campos.regras_por_campo.regra import Regra
from app.services.comparacao.campos.regras_por_campo.regra_de_cada_campo import REGRAS
from app.services.comparacao.campos.status_do_campo import Status, status_do_campo
from app.services.comparacao.campos.valor_da_coluna import ValoresDoCampo, valores_das_colunas
from app.services.comparacao.constantes import CAMPOS_SEMPRE_VISIVEIS, ROTULOS
from app.services.comparacao.documentos.identificacao_do_documento import ref_documento
from app.services.comparacao.partes.conferencia_do_adquirente import campo_do_adquirente
from app.services.comparacao.partes.operacao_triangular import (
    CAMPOS_DO_EXPORTADOR,
    Triangulacao,
    aviso_triangular,
    triangulacoes,
)
from app.services.comparacao.tipos import Apontamentos, Col, Contexto, Valor


def comparar_colunas(ctx: Contexto, colunas: list[Col]) -> tuple[Comparacao, Apontamentos]:
    """A comparação dos campos e o que ela aponta."""
    triangulares = triangulacoes(colunas)
    apontamentos = Apontamentos([aviso_triangular(ctx.prefixo, t) for t in triangulares])
    campos: list[CampoComparado] = []
    for campo, regra in REGRAS.items():
        comparado, do_campo = _comparar_campo(ctx, campo, regra, colunas, triangulares)
        apontamentos += do_campo
        campos += [comparado] if comparado else []
    adquirente, do_adquirente = campo_do_adquirente(ctx, colunas)
    campos += [adquirente] if adquirente else []
    comparacao = Comparacao(
        id=ctx.comparacao_id,
        titulo=" × ".join(col.rotulo for col in colunas),
        colunas=[Coluna(chave=c.chave, rotulo=c.rotulo, documentos=[ref_documento(f) for f in c.fontes])
                 for c in colunas],
        campos=campos,
    )
    return comparacao, apontamentos + Apontamentos(divergencias=do_adquirente)


def _comparar_campo(
    ctx: Contexto, campo: NomeCampo, regra: Regra, colunas: list[Col], triangulares: list[Triangulacao]
) -> tuple[CampoComparado | None, Apontamentos]:
    """Campo None quando nenhuma coluna o traz e ele não é dos que sempre aparecem."""
    lidos = valores_das_colunas(ctx, campo, regra, colunas)
    valores = lidos.valores
    if campo not in CAMPOS_SEMPRE_VISIVEIS and all(v is None for v in valores.values()):
        return None, lidos.apontamentos
    status, do_status = _status(ctx, campo, regra, colunas, lidos, triangulares)
    depois = [f"{ctx.prefixo}{m}" for m in regra.avisos_da_comparacao(colunas)] if regra.avisos_da_comparacao else []
    comparado = CampoComparado(
        campo=campo,
        rotulo=ROTULOS[campo],
        status=status,
        valores={chave: _para_valor_campo(v) for chave, v in valores.items()},
    )
    return comparado, lidos.apontamentos + do_status + Apontamentos(depois)


def _status(
    ctx: Contexto, campo: NomeCampo, regra: Regra, colunas: list[Col], lidos: ValoresDoCampo,
    triangulares: list[Triangulacao],
) -> Status:
    na_soma = bool(lidos.apontamentos.divergencias)
    if campo in CAMPOS_DO_EXPORTADOR and triangulares:
        return status_com_triangulacao(ctx, campo, regra, colunas, lidos.valores, triangulares, na_soma)
    return status_do_campo(ctx, campo, regra, colunas, lidos.valores, na_soma)


def _para_valor_campo(v: Valor | None) -> ValorCampo | None:
    if v is None:
        return None
    return ValorCampo(exibicao=v.exibicao, texto_original=v.texto_original, arquivo_id=v.arquivo_id, pagina=v.pagina)
