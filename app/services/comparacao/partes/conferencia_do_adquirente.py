"""Linha 'Adquirente': adquirente/notify do conhecimento × adquirente da invoice (CNPJ e endereço)."""

from app.schemas import CampoComparado, Divergencia, Parte, StatusCampo, ValorCampo
from app.services.comparacao.constantes import ROTULOS
from app.services.comparacao.mensagens import Diferenca, divergencia
from app.services.comparacao.normalizacao.codigos import normalizar_cnpj
from app.services.comparacao.normalizacao.enderecos import mesma_rua_e_numero
from app.services.comparacao.partes.capital import parte_da_capital
from app.services.comparacao.partes.mesma_empresa import mesma_empresa_registrada, registro, relacao_entre_partes
from app.services.comparacao.partes.parte_preenchida import parte_preenchida
from app.services.comparacao.tipos import Col, Contexto, Fonte


def campo_do_adquirente(ctx: Contexto, colunas: list[Col]) -> tuple[CampoComparado | None, list[Divergencia]]:
    """A linha e suas divergências; None sem conhecimento na comparação ou sem adquirente em nenhum documento."""
    partes = {col.chave: _partes_da_coluna(col) for col in colunas}
    conhecimentos = [col for col in colunas if col.so_conhecimento()]
    if not conhecimentos or not any(partes.values()):
        return None, []
    clientes = _clientes(colunas, partes)
    conferidos = {col.chave: [(parte, *_conferir(col, parte[1], parte[2], clientes)) for parte in partes[col.chave]]
                  for col in conhecimentos}
    mensagens = list(dict.fromkeys(m for lista in conferidos.values() for _, _, ms in lista for m in ms))
    divergencias = [divergencia("comparacao", ctx.comparacao_id, "adquirente", ctx.origem, rotulo, Diferenca(detalhe))
                    for rotulo, detalhe in mensagens]
    comparou = any(c for lista in conferidos.values() for _, c, _ in lista)
    status: StatusCampo = "DIVERGENTE" if mensagens else "OK" if comparou else "INSUFICIENTE"
    valores = {col.chave: _valor(_a_mostrar(conferidos[col.chave]) if col.chave in conferidos else partes[col.chave])
               for col in colunas}
    campo = CampoComparado(campo="adquirente", rotulo=ROTULOS["adquirente"], status=status, valores=valores)
    return campo, divergencias


def _partes_da_coluna(col: Col) -> list[tuple[Fonte, str, Parte]]:
    """(documento, papel, parte): no conhecimento o adquirente e o notify; na invoice/PL só o adquirente."""
    papeis = ("adquirente", "notify") if col.so_conhecimento() else ("adquirente",)
    return [(f, papel, p) for f in col.fontes for papel in papeis if _do_cliente(p := getattr(f.doc, papel))]


def _clientes(colunas: list[Col], partes: dict[str, list]) -> list[tuple[Col, Parte]]:
    """Adquirente das colunas de invoice; sem ele, o das de packing list."""
    for tipo in ("invoice", "packing_list"):
        achados = [(col, p) for col in colunas if any(f.doc.tipo == tipo for f in col.fontes)
                   for f, _, p in partes[col.chave] if f.doc.tipo == tipo]
        if achados:
            return achados
    return []


def _do_cliente(p: Parte | None) -> bool:
    return parte_preenchida(p) and not parte_da_capital(p)


def _a_mostrar(
    conferidos: list[tuple[tuple[Fonte, str, Parte], bool, list[tuple[str, str]]]],
) -> list[tuple[Fonte, str, Parte]]:
    """A parte do conhecimento que deu erro; senão a que foi comparada; senão a primeira."""
    ordem = sorted(conferidos, key=lambda c: (not c[2], not c[1]))
    return [parte for parte, _, _ in ordem]


def _valor(partes: list[tuple[Fonte, str, Parte]]) -> ValorCampo | None:
    if not partes:
        return None
    f, _, p = partes[0]
    texto = " — ".join(t.strip() for t in (p.nome, p.cnpj, p.endereco) if t and t.strip())
    return ValorCampo(exibicao=texto, texto_original=texto, arquivo_id=f.arquivo.id, pagina=p.pagina)


def _conferir(
    col: Col, papel: str, p: Parte, clientes: list[tuple[Col, Parte]]
) -> tuple[bool, list[tuple[str, str]]]:
    """(comparou?, [(rótulo, detalhe)]); empresa de outro nome fica só com o aviso do notify."""
    mesmos = [(c, x) for c, x in clientes if relacao_entre_partes(p, x) != "outra"]
    cnpj = normalizar_cnpj(p.cnpj)
    com_cnpj = [(c, x) for c, x in mesmos if normalizar_cnpj(x.cnpj)]
    if cnpj and com_cnpj and all(normalizar_cnpj(x.cnpj) != cnpj for _, x in com_cnpj):
        c, x = com_cnpj[0]
        return True, [(f"CNPJ do {papel}", f"{col.nome_curto} {p.cnpj.strip()} × adquirente da {c.nome_curto} "
                                            f"{x.cnpj.strip()}")]
    iguais = [(c, x) for c, x in mesmos
              if mesma_empresa_registrada(registro(p), registro(x)) and x.endereco and x.endereco.strip()]
    if not p.endereco or not p.endereco.strip() or not iguais:
        return bool(mesmos), []
    if any(mesma_rua_e_numero(p, x) for _, x in iguais):
        return True, []
    c, x = iguais[0]
    return True, [(f"Endereço do {papel}", f"{col.nome_curto} {p.endereco.strip()} × adquirente da "
                                           f"{c.nome_curto} {x.endereco.strip()}")]
