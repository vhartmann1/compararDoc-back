"""Linha 'Adquirente': adquirente/notify do conhecimento × adquirente da invoice (CNPJ e endereço)."""

import re

from app.schemas import CampoComparado, Divergencia, Parte, StatusCampo, ValorCampo
from app.services.comparacao.constantes import ROTULOS
from app.services.comparacao.mesma_empresa import relacao_entre_partes
from app.services.comparacao.normalizacao import (
    normalizar_cidade,
    normalizar_cnpj,
    normalizar_endereco,
    sem_acento,
)
from app.services.comparacao.regras_por_campo.exportador_consignatario import parte_da_capital
from app.services.comparacao.tipos import Col, Contexto, Fonte

# Tipo de logradouro e marca de número: não distinguem uma rua da outra.
TIPOS_DE_LOGRADOURO = {"R", "RUA", "AV", "AVENIDA", "ROD", "RODOVIA", "ESTRADA", "ESTR", "AL", "ALAMEDA", "TRAVESSA",
                       "TV", "N", "NO", "NR", "NUMERO", "DE", "DA", "DO", "DAS", "DOS", "E"}
UNIDADES = ("", "UM", "DOIS", "TRES", "QUATRO", "CINCO", "SEIS", "SETE", "OITO", "NOVE", "DEZ", "ONZE", "DOZE",
            "TREZE", "QUATORZE", "QUINZE", "DEZESSEIS", "DEZESSETE", "DEZOITO", "DEZENOVE")
DEZENAS = {20: "VINTE", 30: "TRINTA"}
# a cidade antes da UF no fim do texto: 'Bairro X, Cidade Alta - SC 88000-100 BR' -> 'Cidade Alta'
CEP = re.compile(r"\b\d{2}\.?\d{3}-?\d{3}\b")
CIDADE_ANTES_DA_UF = re.compile(r"([A-Za-z .]+?)\s*[-,/]?\s*\b[A-Z]{2}\b[\s,\-0-9.]*(?i:BRASIL|BRAZIL|BR)?[\s.,]*$")


def campo_do_adquirente(ctx: Contexto, colunas: list[Col]) -> CampoComparado | None:
    """None sem conhecimento na comparação ou sem adquirente em nenhum documento."""
    partes = {col.chave: _partes_da_coluna(col) for col in colunas}
    conhecimentos = [col for col in colunas if _do_conhecimento(col)]
    if not conhecimentos or not any(partes.values()):
        return None
    clientes = _clientes(colunas, partes)
    conferidos = {col.chave: [(parte, *_conferir(col, parte[1], parte[2], clientes)) for parte in partes[col.chave]]
                  for col in conhecimentos}
    mensagens = list(dict.fromkeys(m for lista in conferidos.values() for _, _, ms in lista for m in ms))
    ctx.divergencias.extend(Divergencia(categoria="comparacao", comparacao_id=ctx.comparacao_id, campo="adquirente",
                                        mensagem=f"{ctx.prefixo}{m}") for m in mensagens)
    comparou = any(c for lista in conferidos.values() for _, c, _ in lista)
    status: StatusCampo = "DIVERGENTE" if mensagens else "OK" if comparou else "INSUFICIENTE"
    valores = {col.chave: _valor(_a_mostrar(conferidos[col.chave]) if col.chave in conferidos else partes[col.chave])
               for col in colunas}
    return CampoComparado(campo="adquirente", rotulo=ROTULOS["adquirente"], status=status, valores=valores)


def _do_conhecimento(col: Col) -> bool:
    return all(f.doc.tipo == "conhecimento" for f in col.fontes)


def _partes_da_coluna(col: Col) -> list[tuple[Fonte, str, Parte]]:
    """(documento, papel, parte): no conhecimento o adquirente e o notify; na invoice/PL só o adquirente."""
    papeis = ("adquirente", "notify") if _do_conhecimento(col) else ("adquirente",)
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
    return p is not None and bool(p.nome.strip()) and not parte_da_capital(p)


def _a_mostrar(conferidos: list[tuple[tuple[Fonte, str, Parte], bool, list[str]]]) -> list[tuple[Fonte, str, Parte]]:
    """A parte do conhecimento que deu erro; senão a que foi comparada; senão a primeira."""
    ordem = sorted(conferidos, key=lambda c: (not c[2], not c[1]))
    return [parte for parte, _, _ in ordem]


def _valor(partes: list[tuple[Fonte, str, Parte]]) -> ValorCampo | None:
    if not partes:
        return None
    f, _, p = partes[0]
    texto = " — ".join(t.strip() for t in (p.nome, p.cnpj, p.endereco) if t and t.strip())
    return ValorCampo(exibicao=texto, texto_original=texto, arquivo_id=f.arquivo.id, pagina=p.pagina)


def _conferir(col: Col, papel: str, p: Parte, clientes: list[tuple[Col, Parte]]) -> tuple[bool, list[str]]:
    """(comparou?, mensagens); empresa de outro nome fica só com o aviso do notify."""
    mesmos = [(c, x) for c, x in clientes if relacao_entre_partes(p, x) != "outra"]
    cnpj = normalizar_cnpj(p.cnpj)
    com_cnpj = [(c, x) for c, x in mesmos if normalizar_cnpj(x.cnpj)]
    if cnpj and com_cnpj and all(normalizar_cnpj(x.cnpj) != cnpj for _, x in com_cnpj):
        c, x = com_cnpj[0]
        return True, [f"CNPJ do {papel}: {col.nome_curto} {p.cnpj.strip()} × adquirente da {c.nome_curto} "
                      f"{x.cnpj.strip()}"]
    iguais = [(c, x) for c, x in mesmos if _mesma_empresa_registrada(p, x) and x.endereco and x.endereco.strip()]
    if not p.endereco or not p.endereco.strip() or not iguais:
        return bool(mesmos), []
    if any(_mesmo_endereco(p, x) for _, x in iguais):
        return True, []
    c, x = iguais[0]
    return True, [f"Endereço do {papel}: {col.nome_curto} {p.endereco.strip()} × adquirente da {c.nome_curto} "
                  f"{x.endereco.strip()}"]


def _mesma_empresa_registrada(a: Parte, b: Parte) -> bool:
    """Mesmo CNPJ; sem CNPJ num dos lados, o nome decide."""
    ca, cb = normalizar_cnpj(a.cnpj), normalizar_cnpj(b.cnpj)
    return ca == cb if ca and cb else relacao_entre_partes(a, b) == "mesma"


def _mesmo_endereco(a: Parte, b: Parte) -> bool:
    """Mesma cidade e texto igual ou mesma rua e número; sem rua ou número reconhecível, não acusa."""
    if not _mesma_cidade(a, b):
        return False
    if normalizar_endereco(a.endereco or "") == normalizar_endereco(b.endereco or ""):
        return True
    la, lb = _logradouro(a.endereco or ""), _logradouro(b.endereco or "")
    return la is None or lb is None or la == lb


def _mesma_cidade(a: Parte, b: Parte) -> bool:
    """Sem cidade num dos lados passa; com as duas, iguais ou a de um escrita no endereço do outro."""
    ca, cb = _cidade(a), _cidade(b)
    if not ca or not cb:
        return True
    return ca == cb or ca in normalizar_cidade(b.endereco or "") or cb in normalizar_cidade(a.endereco or "")


def _cidade(p: Parte) -> str | None:
    """A cidade do campo; sem ela, a que vem antes da UF no fim do texto do endereço."""
    if p.cidade and p.cidade.strip():
        return normalizar_cidade(p.cidade)
    achado = CIDADE_ANTES_DA_UF.search(sem_acento(p.endereco or ""))
    return normalizar_cidade(achado.group(1)) if achado and achado.group(1).strip() else None


def _logradouro(endereco: str) -> tuple[tuple[str, ...], str] | None:
    """'R. 7 de Setembro, 644 - Sala 5' -> (('SETE', 'SETEMBRO'), '644'); None sem rua ou número."""
    palavras = normalizar_endereco(CEP.sub(" ", endereco)).split()
    n = next((i for i, p in enumerate(palavras) if _numero_da_casa(palavras, i)), None)
    if n is None:
        return None
    rua = tuple(w for p in palavras[:n] for w in _por_extenso(p).split() if w not in TIPOS_DE_LOGRADOURO)
    return (rua, palavras[n].lstrip("0")) if rua else None


def _numero_da_casa(palavras: list[str], i: int) -> bool:
    """Número depois do nome da rua que não é parte dele ('7 de Setembro', 'BR 101 950')."""
    if not palavras[i].isdigit() or not any(p not in TIPOS_DE_LOGRADOURO for p in palavras[:i]):
        return False
    seguinte = palavras[i + 1] if i + 1 < len(palavras) else ""
    return not (seguinte.isdigit() or seguinte in {"DE", "DO", "DA"})


def _por_extenso(palavra: str) -> str:
    """'7' -> 'SETE', '25' -> 'VINTE E CINCO' (até 31); o resto fica como está."""
    if not palavra.isdigit() or not 0 < int(palavra) < 32:
        return palavra
    n = int(palavra)
    if n < 20:
        return UNIDADES[n]
    return " E ".join(filter(None, (DEZENAS[n // 10 * 10], UNIDADES[n % 10])))
