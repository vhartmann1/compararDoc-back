"""Divergência de NCM dita pelo código que sobra ou falta em cada lado, não pelas duas listas inteiras."""

from app.services.comparacao.mensagens import pedir
from app.services.comparacao.normalizacao.formatacao import formatar_ncm
from app.services.comparacao.tipos import Col, Valor


def _fora(codigos: tuple, outros: tuple, digitos: int) -> list[str]:
    return [c for c in codigos if not any(c[:digitos] == o[:digitos] for o in outros)]


def _ncms(codigos: list[str]) -> str:
    lista = ", ".join(formatar_ncm(c) for c in codigos)
    return f"o NCM {lista}" if len(codigos) == 1 else f"os NCMs {lista}"


def _diferenca(nome: str, sobra: list[str], falta: list[str], nome_ref: str) -> str:
    """'BL cita o NCM 8451, que não consta em Invoice' / 'BL não cita…' / 'BL cita… no lugar do…'."""
    if sobra and falta:
        return f"{nome} cita {_ncms(sobra)} no lugar d{_ncms(falta)}, que consta em {nome_ref}"
    if sobra:
        return f"{nome} cita {_ncms(sobra)}, que não consta em {nome_ref}"
    return f"{nome} não cita {_ncms(falta)}, que consta em {nome_ref}"


def texto_ncm(grupos: list[tuple[list[Col], Valor]], digitos: int) -> str:
    """Cada grupo contra o da maioria (o último da lista), terminando com o que pedir."""
    *outros, (cols_ref, ref) = grupos
    nome_ref = "/".join(c.nome_curto for c in cols_ref)
    partes = [
        _diferenca("/".join(c.nome_curto for c in cols), sobra, falta, nome_ref)
        for cols, valor in outros
        if (sobra := _fora(valor.chave, ref.chave, digitos)) + (falta := _fora(ref.chave, valor.chave, digitos))
    ]
    return pedir("; ".join(partes), "correção")
