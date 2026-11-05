"""Comparação campo a campo: o valor de cada coluna e o status de cada campo."""

from app.schemas import CampoComparado, Coluna, Comparacao, NomeCampo, StatusCampo, ValorCampo
from app.services.comparacao.campos.campo_com_triangulacao import status_com_triangulacao
from app.services.comparacao.campos.regras_por_campo.regra import Regra
from app.services.comparacao.campos.regras_por_campo.regra_de_cada_campo import REGRAS
from app.services.comparacao.campos.status_do_campo import status_do_campo
from app.services.comparacao.campos.valor_da_coluna import valores_das_colunas
from app.services.comparacao.constantes import CAMPOS_SEMPRE_VISIVEIS, ROTULOS
from app.services.comparacao.documentos.identificacao_do_documento import ref_documento
from app.services.comparacao.partes.conferencia_do_adquirente import campo_do_adquirente
from app.services.comparacao.partes.operacao_triangular import (
    CAMPOS_DO_EXPORTADOR,
    Triangulacao,
    aviso_triangular,
    triangulacoes,
)
from app.services.comparacao.tipos import Col, Contexto, Valor


def comparar_colunas(ctx: Contexto, colunas: list[Col]) -> Comparacao:
    triangulares = triangulacoes(colunas)
    ctx.avisos.extend(aviso_triangular(ctx.prefixo, t) for t in triangulares)
    campos = [c for campo, regra in REGRAS.items() if (c := _comparar_campo(ctx, campo, regra, colunas, triangulares))]
    if adquirente := campo_do_adquirente(ctx, colunas):
        campos.append(adquirente)
    return Comparacao(
        id=ctx.comparacao_id,
        titulo=" × ".join(col.rotulo for col in colunas),
        colunas=[Coluna(chave=c.chave, rotulo=c.rotulo, documentos=[ref_documento(f) for f in c.fontes])
                 for c in colunas],
        campos=campos,
    )


def _comparar_campo(
    ctx: Contexto, campo: NomeCampo, regra: Regra, colunas: list[Col], triangulares: list[Triangulacao]
) -> CampoComparado | None:
    """None quando nenhuma coluna traz o campo e ele não é dos que sempre aparecem."""
    valores = valores_das_colunas(ctx, campo, regra, colunas)
    if campo not in CAMPOS_SEMPRE_VISIVEIS and all(v is None for v in valores.values()):
        return None
    status = _status(ctx, campo, regra, colunas, valores, triangulares)
    if regra.avisos_da_comparacao:
        ctx.avisos.extend(f"{ctx.prefixo}{m}" for m in regra.avisos_da_comparacao(colunas))
    return CampoComparado(
        campo=campo,
        rotulo=ROTULOS[campo],
        status=status,
        valores={chave: _para_valor_campo(v) for chave, v in valores.items()},
    )


def _status(
    ctx: Contexto, campo: NomeCampo, regra: Regra, colunas: list[Col], valores: dict[str, Valor | None],
    triangulares: list[Triangulacao],
) -> StatusCampo:
    if campo in CAMPOS_DO_EXPORTADOR and triangulares:
        return status_com_triangulacao(ctx, campo, regra, colunas, valores, triangulares)
    return status_do_campo(ctx, campo, regra, colunas, valores)


def _para_valor_campo(v: Valor | None) -> ValorCampo | None:
    if v is None:
        return None
    return ValorCampo(exibicao=v.exibicao, texto_original=v.texto_original, arquivo_id=v.arquivo_id, pagina=v.pagina)
