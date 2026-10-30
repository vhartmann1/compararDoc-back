"""Linha 'Adquirente': adquirente/notify do conhecimento × adquirente da invoice (CNPJ e endereço)."""

import re

from app.schemas import CampoComparado, Divergencia, Parte, StatusCampo, ValorCampo
from app.services.comparacao.campos.regras_por_campo.exportador_consignatario import parte_da_capital
from app.services.comparacao.constantes import ROTULOS
from app.services.comparacao.normalizacao.codigos import normalizar_cnpj
from app.services.comparacao.normalizacao.enderecos import normalizar_cidade, normalizar_endereco
from app.services.comparacao.normalizacao.texto import sem_acento
from app.services.comparacao.partes.mesma_empresa import relacao_entre_partes
from app.services.comparacao.partes.parte_preenchida import parte_preenchida
from app.services.comparacao.tipos import Col, Contexto, Fonte

# Tipo de logradouro e marca de número: não distinguem uma rua da outra.
TIPOS_DE_LOGRADOURO = {"R", "RUA", "AV", "AVENIDA", "ROD", "RODOVIA", "ESTRADA", "ESTR", "AL", "ALAMEDA", "TRAVESSA",
                       "TV", "N", "NO", "NR", "NUMERO", "DE", "DA", "DO", "DAS", "DOS", "E"}
CONECTIVOS = {"N", "NO", "NR", "NUMERO", "DE", "DA", "DO", "DAS", "DOS", "E"}
# Partes do prédio que podem vir entre a rua e o número ('R X Sala 901 902 Andar 9 333').
PARTES_DO_PREDIO = {"SALA", "SALAS", "SL", "ANDAR", "AN", "CONJ", "CONJUNTO", "LOJA", "BLOCO", "BOX", "APTO", "AP",
                    "ED", "EDIFICIO"}
# Título na frente do nome da rua, que um documento escreve e outro não ('R. Doutor X' = 'R. X').
TITULOS = {"DOUTOR", "DR", "CORONEL", "CEL", "PROFESSOR", "PROF", "ENGENHEIRO", "ENG", "GOVERNADOR", "GOV",
           "PRESIDENTE", "PRES", "GENERAL", "GAL", "MAJOR", "CAPITAO", "MARECHAL", "SENADOR", "DEPUTADO", "PREFEITO"}
UNIDADES = ("", "UM", "DOIS", "TRES", "QUATRO", "CINCO", "SEIS", "SETE", "OITO", "NOVE", "DEZ", "ONZE", "DOZE",
            "TREZE", "QUATORZE", "QUINZE", "DEZESSEIS", "DEZESSETE", "DEZOITO", "DEZENOVE")
DEZENAS = {20: "VINTE", 30: "TRINTA"}
# a cidade antes da UF no fim do texto: 'Bairro X, Cidade Alta - SC 88000-100 BR' -> 'Cidade Alta'
CEP = re.compile(r"\b\d{2}\.?\d{3}-?\d{3}\b")
PEDACO = re.compile(r"[A-Z0-9]+|[,;.\-–/]")  # palavras e a pontuação que separa os trechos do endereço
MARCAS_DE_NUMERO = {"N", "NO", "NR", "NUMERO"}
CIDADE_ANTES_DA_UF = re.compile(r"([A-Za-z .]+?)\s*[-,/]?\s*\b[A-Z]{2}\b[\s,\-0-9.]*(?i:BRASIL|BRAZIL|BR)?[\s.,]*$")


def campo_do_adquirente(ctx: Contexto, colunas: list[Col]) -> CampoComparado | None:
    """None sem conhecimento na comparação ou sem adquirente em nenhum documento."""
    partes = {col.chave: _partes_da_coluna(col) for col in colunas}
    conhecimentos = [col for col in colunas if col.so_conhecimento()]
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
    iguais = [(c, x) for c, x in mesmos if mesma_empresa_registrada(p, x) and x.endereco and x.endereco.strip()]
    if not p.endereco or not p.endereco.strip() or not iguais:
        return bool(mesmos), []
    if any(mesmo_endereco(p, x) for _, x in iguais):
        return True, []
    c, x = iguais[0]
    return True, [f"Endereço do {papel}: {col.nome_curto} {p.endereco.strip()} × adquirente da {c.nome_curto} "
                  f"{x.endereco.strip()}"]


def mesma_empresa_registrada(a: Parte, b: Parte) -> bool:
    """Mesmo CNPJ; sem CNPJ num dos lados, o nome decide."""
    ca, cb = normalizar_cnpj(a.cnpj), normalizar_cnpj(b.cnpj)
    return ca == cb if ca and cb else relacao_entre_partes(a, b) == "mesma"


def mesmo_endereco(a: Parte, b: Parte) -> bool:
    """Mesma cidade e texto igual ou mesma rua e número; sem rua ou número reconhecível, não acusa."""
    if not _mesma_cidade(a, b):
        return False
    if normalizar_endereco(a.endereco or "") == normalizar_endereco(b.endereco or ""):
        return True
    la, lb = _logradouro(a.endereco or ""), _logradouro(b.endereco or "")
    if la is None or lb is None or la == lb:
        return True
    return _traz_logradouro(a.endereco or "", lb) or _traz_logradouro(b.endereco or "", la)


def _traz_logradouro(endereco: str, logradouro: tuple[str, str]) -> bool:
    """O endereço tem a rua e, logo depois ou depois da sala/andar, o número ('Sala 9 Rua X 77', 'R X Sala 9 77')."""
    palavras = [p for p, _ in _palavras_e_pausas(endereco)]
    rua, numero = logradouro
    for inicio in (i for i in range(len(palavras)) if _comeco_de_rua(palavras, i)):
        fim = _fim_da_rua(palavras, inicio, rua)
        resto = [p.lstrip("0") for p in palavras[fim:]] if fim is not None else []
        if resto and (resto[0] == numero or (palavras[fim] in PARTES_DO_PREDIO and numero in resto)):
            return True
    return False


def _comeco_de_rua(palavras: list[str], i: int) -> bool:
    """Palavra que abre o nome da rua: no começo ou logo depois do tipo ('Rua', 'Av.') ou do título."""
    if palavras[i] in TIPOS_DE_LOGRADOURO or palavras[i] in TITULOS:
        return False
    anterior = next((p for p in reversed(palavras[:i]) if p not in CONECTIVOS), None)
    return anterior is None or anterior in TITULOS or anterior in TIPOS_DE_LOGRADOURO


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


def _logradouro(endereco: str) -> tuple[str, str] | None:
    """'R. 7 de Setembro, 644 - Sala 5' -> ('SETESETEMBRO', '644'); None sem rua ou número."""
    palavras = _palavras_e_pausas(endereco)
    n = next((i for i in range(len(palavras)) if _numero_da_casa(palavras, i)), None)
    if n is None:
        return None
    rua = [w for p, _ in palavras[:n] for w in _por_extenso(p).split() if w not in TIPOS_DE_LOGRADOURO]
    while len(rua) > 1 and rua[0] in TITULOS:
        rua.pop(0)
    return ("".join(rua), palavras[n][0].lstrip("0")) if rua else None  # junto: 'PEDROFERREIRA' é a mesma rua


def _fim_da_rua(palavras: list[str], inicio: int, rua: str) -> int | None:
    """Posição logo depois da rua, se as palavras a partir de `inicio` formam exatamente `rua`."""
    juntas = ""
    for j in range(inicio, len(palavras)):
        juntas += "".join(w for w in _por_extenso(palavras[j]).split() if w not in TIPOS_DE_LOGRADOURO)
        if juntas == rua:
            return j + 1
        if not rua.startswith(juntas):
            return None
    return None


def _palavras_e_pausas(endereco: str) -> list[tuple[str, bool]]:
    """Cada palavra e se vem uma pontuação logo depois dela ('333, 9 ANDAR': 333 fecha o trecho)."""
    pedacos = PEDACO.findall(sem_acento(CEP.sub(" ", endereco)).upper())
    return [(p, i + 1 < len(pedacos) and not pedacos[i + 1].isalnum()) for i, p in enumerate(pedacos) if p.isalnum()]


def _depois_de_pausa(palavras: list[tuple[str, bool]], i: int) -> bool:
    """Número depois de vírgula ou de 'Nº': é o da casa, mesmo seguido de outro ('333, 9 andar')."""
    return i > 0 and (palavras[i - 1][1] or palavras[i - 1][0] in MARCAS_DE_NUMERO)


def _numero_da_casa(palavras: list[tuple[str, bool]], i: int) -> bool:
    """Número depois do nome da rua que não é parte dele ('7 de Setembro', 'BR 101 950'); pontuação fecha o trecho."""
    palavra, pausa = palavras[i]
    if not palavra.isdigit() or not any(p not in TIPOS_DE_LOGRADOURO for p, _ in palavras[:i]):
        return False
    seguinte = palavras[i + 1][0] if i + 1 < len(palavras) else ""
    return pausa or _depois_de_pausa(palavras, i) or not (seguinte.isdigit() or seguinte in {"DE", "DO", "DA"})


def _por_extenso(palavra: str) -> str:
    """'7' -> 'SETE', '25' -> 'VINTE E CINCO' (até 31); o resto fica como está."""
    if not palavra.isdigit() or not 0 < int(palavra) < 32:
        return palavra
    n = int(palavra)
    if n < 20:
        return UNIDADES[n]
    return " E ".join(filter(None, (DEZENAS[n // 10 * 10], UNIDADES[n % 10])))
