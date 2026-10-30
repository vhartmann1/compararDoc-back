"""Aviso: a mesma empresa (CNPJ ou nome) como consignatário em endereços diferentes entre os documentos."""

from app.schemas import Parte
from app.services.comparacao.partes.conferencia_do_adquirente import mesmo_endereco
from app.services.comparacao.partes.mesma_empresa import mesma_empresa_registrada, registro
from app.services.comparacao.partes.parte_preenchida import parte_preenchida
from app.services.comparacao.tipos import Col

Lugar = tuple[list[Col], Parte]  # um endereço e as colunas que o trazem


def avisos_de_endereco(colunas: list[Col]) -> list[str]:
    """Uma mensagem por empresa que aparece em mais de um endereço."""
    return [_mensagem(lugares) for lugares in _lugares_por_empresa(colunas) if len(lugares) > 1]


def _lugares_por_empresa(colunas: list[Col]) -> list[list[Lugar]]:
    empresas: list[list[Lugar]] = []
    for col, parte in _consignatarios(colunas):
        lugares = next((e for e in empresas if mesma_empresa_registrada(registro(parte), registro(e[0][1]))), None)
        if lugares is None:
            empresas.append([([col], parte)])
            continue
        lugar = next((lg for lg in lugares if mesmo_endereco(parte, lg[1])), None)
        if lugar is None:
            lugares.append(([col], parte))
        elif col not in lugar[0]:
            lugar[0].append(col)
    return empresas


def _consignatarios(colunas: list[Col]) -> list[tuple[Col, Parte]]:
    return [(col, p) for col in colunas for f in col.fontes
            if parte_preenchida(p := f.doc.consignatario) and p.endereco and p.endereco.strip()]


def _mensagem(lugares: list[Lugar]) -> str:
    """Minoria primeiro, como nos outros campos."""
    ordenados = sorted(lugares, key=lambda lg: len(lg[0]))
    partes = [f"{'/'.join(dict.fromkeys(c.nome_curto for c in cols))} {p.endereco.strip()}" for cols, p in ordenados]
    return (f"Endereço do consignatário diferente entre os documentos: {' × '.join(partes)} "
            "(confira se é endereço antigo)")
