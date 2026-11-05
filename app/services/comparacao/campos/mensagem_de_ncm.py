"""Divergência de NCM dita pelo código que sobra ou falta em cada lado, não pelas duas listas inteiras."""

from app.services.comparacao.mensagens import Diferenca, maiuscula, nos_documentos, pedido, sujeito
from app.services.comparacao.normalizacao.formatacao import formatar_ncm
from app.services.comparacao.tipos import Col, Valor


def _fora(codigos: tuple, outros: tuple, digitos: int) -> list[str]:
    return [c for c in codigos if not any(c[:digitos] == o[:digitos] for o in outros)]


def _ncms(codigos: list[str]) -> str:
    lista = ", ".join(formatar_ncm(c) for c in codigos)
    return f"o NCM {lista}" if len(codigos) == 1 else f"os NCMs {lista}"


def _consta(codigos: list[str]) -> str:
    return "consta" if len(codigos) == 1 else "constam"


def _diferenca(nomes: list[str], sobra: list[str], falta: list[str], nomes_ref: list[str]) -> str:
    """'o BL cita o NCM 8451, que não consta na invoice' / 'as invoices não citam…' / '… no lugar do…'."""
    quem, plural = sujeito(nomes)
    cita, onde = ("citam" if plural else "cita"), nos_documentos(nomes_ref)
    if sobra and falta:
        return f"{quem} {cita} {_ncms(sobra)} no lugar d{_ncms(falta)}, que {_consta(falta)} {onde}"
    if sobra:
        return f"{quem} {cita} {_ncms(sobra)}, que não {_consta(sobra)} {onde}"
    return f"{quem} não {cita} {_ncms(falta)}, que {_consta(falta)} {onde}"


def texto_ncm(grupos: list[tuple[list[Col], Valor]], digitos: int) -> Diferenca:
    """Cada grupo contra o da maioria (o último da lista), terminando com o que pedir."""
    *outros, (cols_ref, ref) = grupos
    nomes_ref = [c.nome_curto for c in cols_ref]
    partes = [
        _diferenca([c.nome_curto for c in cols], sobra, falta, nomes_ref)
        for cols, valor in outros
        if (sobra := _fora(valor.chave, ref.chave, digitos)) + (falta := _fora(ref.chave, valor.chave, digitos))
    ]
    return pedido(maiuscula("; ".join(partes)), "correção")
