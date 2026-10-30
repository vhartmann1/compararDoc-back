"""Conhecimento em nome da Capital e invoice/PL em nome do cliente: alerta conforme a modalidade, não divergência."""

from app.services.comparacao.campos.regras_por_campo.exportador_consignatario import valor_da_capital
from app.services.comparacao.constantes import CNPJ_RAIZ_CAPITAL, MODALIDADES_CAPITAL_CONSIGNATARIA
from app.services.comparacao.tipos import Col, Contexto, Valor

NOME_MODALIDADE = {"conta_e_ordem": "conta e ordem", "encomenda": "encomenda"}


def _da_capital_no_conhecimento(col: Col, valor: Valor) -> bool:
    return col.so_conhecimento() and valor_da_capital(valor)


def _do_cliente(col: Col, valor: Valor) -> bool:
    """Invoice/PL sem nenhum sinal da Capital: nem o nome nem a raiz do CNPJ."""
    return not col.so_conhecimento() and sem_sinal_da_capital(valor)


def sem_sinal_da_capital(valor: Valor) -> bool:
    """Nem o nome nem a raiz do CNPJ da Capital (não usa eh_capital: um CNPJ lido errado viraria cliente)."""
    return not any(
        "CAPITAL TRADE" in nome.upper() or (cnpj or "").startswith(CNPJ_RAIZ_CAPITAL) for nome, cnpj, _ in valor.chave
    )


def separar_conhecimentos_da_capital(
    ctx: Contexto, informados: list[tuple[Col, Valor]]
) -> tuple[list[tuple[Col, Valor]], str | None]:
    """(colunas que seguem na comparação, aviso); o conhecimento da Capital sai se a invoice/PL traz o cliente."""
    da_capital = [(col, v) for col, v in informados if _da_capital_no_conhecimento(col, v)]
    do_cliente = [(col, v) for col, v in informados if _do_cliente(col, v)]
    if not da_capital or not do_cliente:
        return informados, None
    restantes = [(col, v) for col, v in informados if not _da_capital_no_conhecimento(col, v)]
    return restantes, _aviso(ctx, da_capital, do_cliente)


def _aviso(ctx: Contexto, da_capital: list[tuple[Col, Valor]], do_cliente: list[tuple[Col, Valor]]) -> str:
    conhecimentos = "/".join(col.nome_curto for col, _ in da_capital)
    documentos = "/".join(col.nome_curto for col, _ in do_cliente)
    clientes = " / ".join(dict.fromkeys(v.exibicao for _, v in do_cliente))
    return (f"{ctx.prefixo}Consignatário: {conhecimentos} em nome da Capital Trade e {documentos} em nome de "
            f"{clientes} — {_o_que_a_modalidade_espera(ctx)}.")


def _o_que_a_modalidade_espera(ctx: Contexto) -> str:
    if ctx.modalidade in MODALIDADES_CAPITAL_CONSIGNATARIA:
        return (f"aceito pela modalidade {NOME_MODALIDADE[ctx.modalidade]}; na invoice o esperado é a Capital "
                "como importadora e o cliente como adquirente")
    if ctx.modalidade == "propria":
        return "em conta própria o consignatário esperado é o cliente; confira (varia por cliente)"
    return "modalidade não informada: aceito como conta e ordem/encomenda; em conta própria seria o cliente"
