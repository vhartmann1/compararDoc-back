"""Onde a Capital tem de aparecer: no PL quando a invoice a traz; em algum documento na conta e ordem."""

from app.schemas import Divergencia, Modalidade, Parte
from app.services.comparacao.colunas_da_comparacao import listar_pares
from app.services.comparacao.identificacao_do_documento import nome_doc, ref_documento
from app.services.comparacao.consignatario_pela_modalidade import sem_sinal_da_capital
from app.services.comparacao.regras_por_campo.exportador_consignatario import parte_da_capital, valor_da_capital
from app.services.comparacao.tipos import Col, Fonte, Valor


def divergencias_da_capital(
    grupos: list[tuple[Fonte | None, Fonte | None]], conhecimentos: list[Fonte], modalidade: Modalidade | None
) -> list[Divergencia]:
    divergencias = [d for comparacao_id, prefixo, inv, pl in listar_pares(grupos)
                    if inv and pl and (d := _pl_sem_a_capital(comparacao_id, prefixo, inv, pl))]
    fontes = [f for par in grupos for f in par if f] + conhecimentos
    if modalidade == "conta_e_ordem" and (d := _conta_e_ordem_sem_a_capital(fontes)):
        divergencias.append(d)
    return divergencias


def _pl_sem_a_capital(comparacao_id: str, prefixo: str, inv: Fonte, pl: Fonte) -> Divergencia | None:
    """Invoice com a Capital consignatária e PL sem consignatário, só com o cliente (adquirente/notify)."""
    partes = [p for p in (pl.doc.adquirente, pl.doc.notify) if _preenchida(p)]
    if not _preenchida(inv.doc.consignatario) or not parte_da_capital(inv.doc.consignatario):
        return None
    if _preenchida(pl.doc.consignatario) or not partes or any(parte_da_capital(p) for p in partes):
        return None
    clientes = " / ".join(dict.fromkeys(p.nome.strip() for p in partes))
    return Divergencia(
        categoria="comparacao", comparacao_id=comparacao_id, campo="consignatario", documento=ref_documento(pl),
        mensagem=f"{prefixo}Consignatário: {falta_a_capital(nome_doc(pl), f'só {clientes}', nome_doc(inv))}",
    )


def falta_a_capital(sem: str, traz: str, com: str) -> str:
    return f"falta a Capital Trade em {sem}, que traz {traz}; ela consta em {com}; pedir inclusão."


def texto_sem_a_capital(grupos: list[tuple[list[Col], Valor]]) -> str | None:
    """Um lado com a Capital consignatária e o outro só com o cliente: o que pedir, em vez dos dois nomes."""
    com = [(cols, v) for cols, v in grupos if valor_da_capital(v)]
    sem = [(cols, v) for cols, v in grupos if sem_sinal_da_capital(v)]
    if len(grupos) != 2 or len(com) != 1 or len(sem) != 1:
        return None
    (cols_sem, valor), (cols_com, _) = sem[0], com[0]
    return falta_a_capital(_nomes(cols_sem), valor.exibicao, _nomes(cols_com))


def _nomes(cols: list[Col]) -> str:
    return "/".join(c.nome_curto for c in cols)


def _conta_e_ordem_sem_a_capital(fontes: list[Fonte]) -> Divergencia | None:
    consignatarios = [f.doc.consignatario for f in fontes if _preenchida(f.doc.consignatario)]
    if not consignatarios or any(parte_da_capital(p) for p in consignatarios):
        return None
    nomes = " / ".join(dict.fromkeys(p.nome.strip() for p in consignatarios))
    return Divergencia(
        categoria="coerencia", comparacao_id=None, campo="consignatario",
        mensagem=(f"Conta e ordem sem a Capital Trade como consignatária/importadora em nenhum documento ({nomes}); "
                  "a Capital deve ser consignee ou importer e o cliente, o notify"),
    )


def _preenchida(p: Parte | None) -> bool:
    return p is not None and bool(p.nome.strip())
