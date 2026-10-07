"""Regras de comparação Invoice × Packing List × Conhecimento (docs/CONTRATO_API.md, "Regras de comparação").

Além da comparação campo a campo (categoria "comparacao"), gera divergências de coerência
(incoterm × frete/portos), de itens (Invoice × Packing List) e internas (contradições num mesmo documento).
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.schemas import (
    ArquivoEntrada,
    CampoComparado,
    Coluna,
    Comparacao,
    ComparacaoItens,
    Divergencia,
    DocumentoExtraido,
    DocumentoRef,
    ExtracaoArquivo,
    ItemExtraido,
    LinhaItem,
    Modalidade,
    NomeCampo,
    Parte,
    ResultadoComparacao,
    StatusCampo,
    StatusResultado,
    TipoDocumento,
    ValorCampo,
    ValorItem,
)
from app.services.normalizacao import (
    SIMILARIDADE_MINIMA_CASAMENTO,
    descricoes_equivalentes,
    enderecos_compativeis,
    formatar_cnpj,
    formatar_contagem,
    formatar_dinheiro,
    formatar_kg,
    formatar_ncm,
    nomes_equivalentes,
    normalizar_cnpj,
    normalizar_codigo_item,
    normalizar_descricao,
    normalizar_incoterm,
    normalizar_lote,
    normalizar_moeda,
    normalizar_ncm,
    normalizar_numero_documento,
    normalizar_pais,
    normalizar_po,
    normalizar_porto,
    normalizar_referencia,
    normalizar_validade,
    para_kg,
    referencias_iguais,
    similaridade,
    unidade_quantidade,
)

# Regra de negócio: diferença de até 0,5 kg (inclusive) entre documentos não é divergência.
# Cobre arredondamento de conversão (ex.: BL em LBS). Mudou a regra? Atualize o contrato e os testes.
TOLERANCIA_PESO_KG = 0.5

TIPOS: list[TipoDocumento] = ["invoice", "packing_list", "conhecimento"]
NOME_TIPO: dict[TipoDocumento, str] = {
    "invoice": "Invoice",
    "packing_list": "Packing List",
    "conhecimento": "Conhecimento (BL/AWB/CRT)",
}
PRIORIDADE_VERSAO = {"original": 3, "copia": 2, "draft": 1, "desconhecida": 0}
ROTULOS: dict[NomeCampo, str] = {
    "peso_liquido": "Peso líquido",
    "peso_bruto": "Peso bruto",
    "volumes": "Volumes",
    "quantidade": "Quantidade",
    "ncm": "NCM",
    "numero_invoice": "Nº da invoice",
    "po": "PO",
    "incoterm": "Incoterm",
    "moeda": "Moeda",
    "exportador": "Exportador",
    "endereco_exportador": "Endereço do exportador",
    "pais_exportador": "País do exportador",
    "consignatario": "Consignatário",
    "pais_origem": "País de origem",
    "porto_origem": "Porto de origem",
    "porto_destino": "Porto de destino",
}
CAMPOS_SEMPRE_VISIVEIS: set[NomeCampo] = {"peso_liquido", "peso_bruto", "ncm"}
CAMPOS_SOMADOS: set[NomeCampo] = {"peso_liquido", "peso_bruto", "volumes", "quantidade"}
# Campos de texto em que valores diferentes entre as invoices somadas merecem aviso.
# Em conta e ordem / encomenda, a Capital Trade pode ser a consignatária no conhecimento (BL/AWB/CRT).
MODALIDADES_CAPITAL_CONSIGNATARIA: set[str] = {"conta_e_ordem", "encomenda"}
CNPJ_RAIZ_CAPITAL = "07872326"  # Capital Trade Importação e Exportação Ltda. (qualquer filial)

CAMPOS_UNICOS_NA_SOMA: set[NomeCampo] = {
    "po", "exportador", "consignatario", "porto_origem", "porto_destino",
    "endereco_exportador", "pais_exportador", "pais_origem", "moeda",
}
# Invoices do mesmo processo com valores diferentes destes campos já são divergência no consolidado.
CAMPOS_DIVERGENTES_NA_SOMA: set[NomeCampo] = {"incoterm"}

# Campos que normalmente só a invoice traz: só 1 documento informar não merece aviso.
CAMPOS_SEM_AVISO_INSUFICIENTE: set[NomeCampo] = {
    "incoterm", "moeda", "pais_origem", "endereco_exportador", "pais_exportador",
}

# Incoterms: grupo E/F = frete por conta do comprador (COLLECT, local de origem);
# grupo C/D = frete por conta do vendedor (PREPAID, local de destino).
INCOTERMS_EF = {"EXW", "FCA", "FAS", "FOB"}
INCOTERMS_CD = {"CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP", "DAT"}
TAMANHO_MAX_DESCRICAO = 60


# ---------------------------------------------------------------------------
# Estruturas internas
# ---------------------------------------------------------------------------

@dataclass
class Fonte:
    """Um documento escolhido para a comparação."""

    arquivo: ArquivoEntrada
    doc: DocumentoExtraido
    ordem: tuple[int, int]  # (posição do arquivo no envio, posição do documento no arquivo)
    invoice_par: DocumentoExtraido | None = None  # para packing list: a invoice com quem foi pareado


@dataclass
class Valor:
    chave: Any  # valor normalizado usado na comparação
    exibicao: str
    texto_original: str | None
    arquivo_id: str | None
    pagina: int | None
    unidade: str | None = None  # unidade como no documento (volumes/quantidade)


@dataclass
class Col:
    chave: str
    rotulo: str
    nome_curto: str  # usado nas mensagens: "Invoice", "Invoices", "AWB"
    fontes: list[Fonte]
    soma: bool = False


@dataclass
class Contexto:
    comparacao_id: str
    prefixo: str  # "Par 1 (L30518777) — " ou ""
    avisos: list[str]
    modalidade: Modalidade | None = None
    divergencias: list[Divergencia] = field(default_factory=list)
    divergentes_na_soma: set[str] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------

def comparar(
    extracoes: list[tuple[ArquivoEntrada, ExtracaoArquivo]], modalidade: Modalidade | None = None
) -> ResultadoComparacao:
    """`extracoes` na ordem em que os arquivos foram enviados."""
    avisos: list[str] = []
    por_tipo = _escolher_documentos(extracoes, avisos)
    invoices, pls, conhecimentos = por_tipo["invoice"], por_tipo["packing_list"], por_tipo["conhecimento"]
    grupos = _parear(invoices, pls, avisos)

    comparacoes: list[Comparacao] = []
    divergencias: list[Divergencia] = []
    for comparacao_id, prefixo, colunas in _montar_comparacoes(grupos, conhecimentos):
        ctx = Contexto(comparacao_id, prefixo, avisos, modalidade)
        comparacoes.append(_comparar_colunas(ctx, colunas))
        divergencias.extend(ctx.divergencias)

    itens, divergencias_itens = _itens(grupos, conhecimentos, avisos)
    divergencias.extend(divergencias_itens)

    usados = sorted((f for fs in por_tipo.values() for f in fs), key=lambda f: f.ordem)
    divergencias.extend(_coerencia(grupos, conhecimentos))
    divergencias.extend(d for f in usados for d in _internas(f))
    avisos.extend(_avisos_pais_origem(por_tipo["invoice"]))
    return ResultadoComparacao(
        status=_status_geral(por_tipo, comparacoes, divergencias),
        documentos=[_ref(f) for f in usados],
        comparacoes=comparacoes,
        itens=itens,
        divergencias=divergencias,
        avisos=avisos,
    )


# ---------------------------------------------------------------------------
# Escolha dos documentos (duplicatas por versão)
# ---------------------------------------------------------------------------

def _escolher_documentos(
    extracoes: list[tuple[ArquivoEntrada, ExtracaoArquivo]], avisos: list[str]
) -> dict[TipoDocumento, list[Fonte]]:
    por_tipo: dict[TipoDocumento, list[Fonte]] = {tipo: [] for tipo in TIPOS}
    for i, (arquivo, extracao) in enumerate(extracoes):
        for j, doc in enumerate(extracao.documentos):
            if doc.tipo in por_tipo:
                por_tipo[doc.tipo].append(Fonte(arquivo, doc, (i, j)))

    escolhidos: dict[TipoDocumento, list[Fonte]] = {}
    for tipo, fontes in por_tipo.items():
        if not fontes:
            avisos.append(f"Documento não encontrado nos arquivos enviados: {NOME_TIPO[tipo]}.")
        # mesmo tipo e mesmo número => fica 1: original > copia > draft > desconhecida; empate => último enviado
        por_numero: dict[str, list[Fonte]] = {}
        for f in fontes:
            por_numero.setdefault(_numero_normalizado(f.doc.numero), []).append(f)
        escolhidos[tipo] = []
        for mesmas in por_numero.values():
            melhor = max(mesmas, key=lambda f: (PRIORIDADE_VERSAO[f.doc.versao], f.ordem))
            escolhidos[tipo].append(melhor)
            ignorados = [f for f in mesmas if f is not melhor]
            if ignorados:
                avisos.append(
                    f"Mais de um documento {_nome_doc(melhor)}; usado {_descrever(melhor)}. "
                    f"Ignorado(s): {'; '.join(_descrever(f) for f in ignorados)}."
                )
        escolhidos[tipo].sort(key=lambda f: f.ordem)
    return escolhidos


def _numero_normalizado(numero: str | None) -> str:
    return normalizar_numero_documento(numero) if numero else ""


def _nome_doc(f: Fonte) -> str:
    """'Invoice L30518777', 'AWB 123-4567 8901', 'Packing List'."""
    if f.doc.tipo == "conhecimento":
        nome = f.doc.subtipo or "Conhecimento"
    else:
        nome = NOME_TIPO[f.doc.tipo]
    return f"{nome} {f.doc.numero}" if f.doc.numero else nome


def _descrever(f: Fonte) -> str:
    paginas = ", ".join(str(p) for p in f.doc.paginas)
    onde = f"{f.arquivo.nome}, pág. {paginas}" if paginas else f.arquivo.nome
    return f"{f.doc.versao} ({onde})"


def _ref(f: Fonte) -> DocumentoRef:
    return DocumentoRef(
        tipo=f.doc.tipo,
        subtipo=f.doc.subtipo,
        arquivo_id=f.arquivo.id,
        arquivo_nome=f.arquivo.nome,
        paginas=f.doc.paginas,
        numero=f.doc.numero,
        versao=f.doc.versao,
    )


# ---------------------------------------------------------------------------
# Pareamento Invoice <-> Packing List
# ---------------------------------------------------------------------------

def _parear(
    invoices: list[Fonte], pls: list[Fonte], avisos: list[str]
) -> list[tuple[Fonte | None, Fonte | None]]:
    livres = list(pls)
    grupos: list[tuple[Fonte | None, Fonte | None]] = []
    for inv in invoices:
        pl = next((p for p in livres if _pl_da_invoice(p.doc, inv.doc)), None)
        if pl:
            livres.remove(pl)
        grupos.append((inv, pl))

    sem_pl = [i for i, (inv, pl) in enumerate(grupos) if pl is None]
    if len(sem_pl) == 1 and len(livres) == 1:
        i = sem_pl[0]
        inv, pl = grupos[i][0], livres.pop()
        grupos[i] = (inv, pl)
        avisos.append(
            f"{_nome_doc(inv)} e {_nome_doc(pl)} foram comparados juntos, mas o packing list "
            "não cita o número da invoice."
        )
    grupos.extend((None, pl) for pl in livres)

    for inv, pl in grupos:
        if inv and pl:
            pl.invoice_par = inv.doc
        elif inv and pls:
            avisos.append(f"{_nome_doc(inv)} sem packing list correspondente.")
        elif pl and invoices:
            avisos.append(f"{_nome_doc(pl)} sem invoice correspondente.")
    return grupos


def _pl_da_invoice(pl: DocumentoExtraido, inv: DocumentoExtraido) -> bool:
    numero = _numero_normalizado(inv.numero)
    if not numero:
        return False
    citados = {_numero_normalizado(n) for n in pl.invoices_referenciadas}
    return numero == _numero_normalizado(pl.numero) or numero in citados


# ---------------------------------------------------------------------------
# Montagem das comparações
# ---------------------------------------------------------------------------

def _montar_comparacoes(
    grupos: list[tuple[Fonte | None, Fonte | None]], conhecimentos: list[Fonte]
) -> list[tuple[str, str, list[Col]]]:
    """Lista de (id, prefixo das mensagens, colunas)."""
    cols_conhecimento = _colunas_conhecimento(conhecimentos)
    if len(grupos) <= 1:
        inv, pl = grupos[0] if grupos else (None, None)
        colunas = _colunas_par(inv, pl) + cols_conhecimento
        return [("unica", "", colunas)] if colunas else []

    resultado: list[tuple[str, str, list[Col]]] = [
        (comparacao_id, prefixo, _colunas_par(inv, pl)) for comparacao_id, prefixo, inv, pl in _pares(grupos)
    ]

    if conhecimentos:
        invoices = [inv for inv, _ in grupos if inv]
        pls = [pl for _, pl in grupos if pl]
        colunas = []
        if invoices:
            colunas.append(_coluna_soma("soma_invoices", invoices, "Invoices", "das", "invoice", "invoices"))
        if pls:
            colunas.append(
                _coluna_soma("soma_packing_lists", pls, "Packing Lists", "dos", "packing list", "packing lists")
            )
        resultado.append(("consolidado", "Consolidado — ", colunas + cols_conhecimento))
    return resultado


def _pares(grupos: list[tuple[Fonte | None, Fonte | None]]) -> list[tuple[str, str, Fonte | None, Fonte | None]]:
    """(id da comparação, prefixo das mensagens, invoice, packing list) de cada par."""
    if len(grupos) <= 1:
        return [("unica", "", inv, pl) for inv, pl in grupos]
    resultado = []
    for n, (inv, pl) in enumerate(grupos, start=1):
        numero = (inv or pl).doc.numero
        prefixo = f"Par {n} ({numero}) — " if numero else f"Par {n} — "
        resultado.append((f"par-{n}", prefixo, inv, pl))
    return resultado


def _colunas_par(inv: Fonte | None, pl: Fonte | None) -> list[Col]:
    colunas = []
    if inv:
        colunas.append(Col("invoice", _nome_doc(inv), "Invoice", [inv]))
    if pl:
        colunas.append(Col("packing_list", _nome_doc(pl), "Packing List", [pl]))
    return colunas


def _colunas_conhecimento(conhecimentos: list[Fonte]) -> list[Col]:
    colunas = []
    for i, f in enumerate(conhecimentos):
        chave = "conhecimento" if i == 0 else f"conhecimento_{i + 1}"
        curto = _nome_doc(f) if len(conhecimentos) > 1 else (f.doc.subtipo or "Conhecimento")
        colunas.append(Col(chave, _nome_doc(f), curto, [f]))
    return colunas


def _coluna_soma(chave: str, fontes: list[Fonte], curto: str, artigo: str, singular: str, plural: str) -> Col:
    if len(fontes) == 1:
        return Col(chave, _nome_doc(fontes[0]), curto, fontes, soma=True)
    return Col(chave, f"Soma {artigo} {len(fontes)} {plural}", curto, fontes, soma=True)


# ---------------------------------------------------------------------------
# Comparação campo a campo
# ---------------------------------------------------------------------------

def _comparar_colunas(ctx: Contexto, colunas: list[Col]) -> Comparacao:
    campos: list[CampoComparado] = []
    for campo, regra in REGRAS.items():
        valores = {col.chave: _valor_coluna(ctx, col, campo, regra) for col in colunas}
        if campo not in CAMPOS_SEMPRE_VISIVEIS and all(v is None for v in valores.values()):
            continue
        status = _status_campo(ctx, campo, regra, colunas, valores)
        campos.append(
            CampoComparado(
                campo=campo,
                rotulo=ROTULOS[campo],
                status=status,
                valores={chave: _para_valor_campo(v) for chave, v in valores.items()},
            )
        )
    return Comparacao(
        id=ctx.comparacao_id,
        titulo=" × ".join(col.rotulo for col in colunas),
        colunas=[Coluna(chave=c.chave, rotulo=c.rotulo, documentos=[_ref(f) for f in c.fontes]) for c in colunas],
        campos=campos,
    )


def _valor_coluna(ctx: Contexto, col: Col, campo: NomeCampo, regra: "Regra") -> Valor | None:
    valores = [regra.obter(f, campo, ctx) for f in col.fontes]
    if not col.soma or len(valores) == 1:
        return valores[0]
    presentes = [v for v in valores if v is not None]
    if not presentes:
        return None
    if campo in CAMPOS_SOMADOS and len(presentes) < len(valores):
        faltando = [_nome_doc(f) for f, v in zip(col.fontes, valores) if v is None]
        ctx.avisos.append(
            f"{ctx.prefixo}{ROTULOS[campo]}: soma incompleta em \"{col.rotulo}\" — "
            f"falta o valor em {', '.join(faltando)}."
        )
        return None
    soma = regra.juntar(presentes, campo, ctx, col)
    if soma is not None and campo in CAMPOS_DIVERGENTES_NA_SOMA and len(soma.chave) > 1:
        partes = [f"{_nome_doc(f)} {v.exibicao}" for f, v in zip(col.fontes, valores) if v is not None]
        ctx.divergentes_na_soma.add(campo)
        ctx.divergencias.append(
            Divergencia(
                categoria="comparacao",
                comparacao_id=ctx.comparacao_id,
                campo=campo,
                mensagem=f"{ctx.prefixo}{ROTULOS[campo]}: {' × '.join(partes)}",
            )
        )
    if soma is not None and campo in CAMPOS_UNICOS_NA_SOMA and len(soma.chave) > 1:
        ctx.avisos.append(
            f"{ctx.prefixo}{ROTULOS[campo]}: os documentos de \"{col.rotulo}\" "
            f"não trazem o mesmo valor ({soma.exibicao})."
        )
    return soma


def _status_campo(
    ctx: Contexto, campo: NomeCampo, regra: "Regra", colunas: list[Col], valores: dict[str, Valor | None]
) -> StatusCampo:
    if campo in ctx.divergentes_na_soma:
        return "DIVERGENTE"  # mensagem já registrada ao montar a soma
    informados = [(col, valores[col.chave]) for col in colunas if valores[col.chave] is not None]
    if not informados:
        return "NAO_ENCONTRADO"
    if campo == "consignatario" and ctx.modalidade in MODALIDADES_CAPITAL_CONSIGNATARIA:
        restantes = [(col, v) for col, v in informados if not _conhecimento_consignado_a_capital(col, v)]
        if len(restantes) < len(informados):
            aceitos = ", ".join(col.nome_curto for col, v in informados if (col, v) not in restantes)
            ctx.avisos.append(
                f"{ctx.prefixo}Consignatário: {aceitos} em nome da Capital Trade — aceito pela modalidade "
                f"{'conta e ordem' if ctx.modalidade == 'conta_e_ordem' else 'encomenda'}."
            )
            if len(restantes) <= 1:
                return "OK"
            informados = restantes
    if len(informados) == 1:
        if len(colunas) > 1 and campo not in CAMPOS_SEM_AVISO_INSUFICIENTE:
            ctx.avisos.append(
                f"{ctx.prefixo}{ROTULOS[campo]} informado só em {informados[0][0].nome_curto}; "
                "nada com o que comparar."
            )
        return "INSUFICIENTE"

    iguais = regra.iguais
    if campo == "quantidade":
        unidades = {v.chave[0] for _, v in informados}
        if len(unidades) > 1:
            textos = " × ".join(f"{col.nome_curto} {v.exibicao}" for col, v in informados)
            ctx.avisos.append(
                f"{ctx.prefixo}Quantidade em unidades que não dá para comparar ({textos}); confira manualmente."
            )
            return "INSUFICIENTE"
    if campo == "ncm":
        iguais = _iguais_ncm(ctx, [v for _, v in informados])

    grupos: list[tuple[list[Col], Valor]] = []
    for col, valor in informados:
        for cols, referencia in grupos:
            if iguais(referencia.chave, valor.chave):
                cols.append(col)
                break
        else:
            grupos.append(([col], valor))
    if len(grupos) == 1:
        return "OK"

    ordenados = sorted(grupos, key=lambda g: len(g[0]))  # minoria primeiro
    partes = [f"{'/'.join(c.nome_curto for c in cols)} {valor.exibicao}" for cols, valor in ordenados]
    nota = ""
    if campo == "quantidade":
        nota = _nota_fator_mil([(v.chave[1], v.exibicao, v.unidade) for _, v in grupos])
    ctx.divergencias.append(
        Divergencia(
            categoria="comparacao",
            comparacao_id=ctx.comparacao_id,
            campo=campo,
            mensagem=f"{ctx.prefixo}{ROTULOS[campo]}: {' × '.join(partes)}{nota}",
        )
    )
    return "DIVERGENTE"


def _iguais_ncm(ctx: Contexto, valores: list[Valor]) -> Callable[[Any, Any], bool]:
    """Compara com 8 dígitos; se algum documento só traz HS (6) ou posição (4), compara por aí."""
    menor = min(len(c) for v in valores for c in v.chave)
    digitos = 8 if menor >= 8 else 6 if menor >= 6 else 4
    if digitos < 8:
        ctx.avisos.append(
            f"{ctx.prefixo}NCM comparado pelos {digitos} primeiros dígitos "
            "(algum documento traz só o HS Code ou a posição)."
        )
    return lambda a, b: {c[:digitos] for c in a} == {c[:digitos] for c in b}


def _para_valor_campo(v: Valor | None) -> ValorCampo | None:
    if v is None:
        return None
    return ValorCampo(exibicao=v.exibicao, texto_original=v.texto_original, arquivo_id=v.arquivo_id, pagina=v.pagina)


# ---------------------------------------------------------------------------
# Regras por campo: como ler o valor de um documento, somar e comparar
# ---------------------------------------------------------------------------

@dataclass
class Regra:
    obter: Callable[[Fonte, NomeCampo, Contexto], Valor | None]
    juntar: Callable[[list[Valor], NomeCampo, Contexto, Col], Valor | None]
    iguais: Callable[[Any, Any], bool]


def _primeira_pagina(f: Fonte) -> int | None:
    return f.doc.paginas[0] if f.doc.paginas else None


def _texto_soma(valores: list[Valor]) -> str | None:
    textos = [v.texto_original for v in valores if v.texto_original]
    return " + ".join(textos) or None


# Pesos ----------------------------------------------------------------------

def _obter_peso(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    medida = f.doc.peso_liquido_total if campo == "peso_liquido" else f.doc.peso_bruto_total
    if medida is None:
        return None
    kg = para_kg(medida)
    if kg is None:
        ctx.avisos.append(
            f"{ctx.prefixo}{ROTULOS[campo]} ({_nome_doc(f)}) em unidade não reconhecida "
            f"(\"{medida.texto_original}\"); não comparado."
        )
        return None
    return Valor(kg, formatar_kg(kg), medida.texto_original, f.arquivo.id, medida.pagina)


def _somar_peso(valores: list[Valor], campo: NomeCampo, ctx: Contexto, col: Col) -> Valor:
    total = round(sum(v.chave for v in valores), 3)
    return Valor(total, formatar_kg(total), _texto_soma(valores), None, None)


def _pesos_iguais(a: float, b: float) -> bool:
    return abs(a - b) <= TOLERANCIA_PESO_KG + 1e-9


# Volumes --------------------------------------------------------------------

def _obter_volumes(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    c = f.doc.volumes_total
    if c is None:
        return None
    unidade = c.unidade.strip().upper()
    return Valor(c.valor, formatar_contagem(c.valor, unidade), c.texto_original, f.arquivo.id, c.pagina, unidade)


def _somar_volumes(valores: list[Valor], campo: NomeCampo, ctx: Contexto, col: Col) -> Valor:
    total = sum(v.chave for v in valores)
    unidades = list(dict.fromkeys(v.unidade for v in valores if v.unidade))
    unidade = "/".join(unidades)
    return Valor(total, formatar_contagem(total, unidade), _texto_soma(valores), None, None, unidade)


# Quantidade -----------------------------------------------------------------

def _obter_quantidade(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    c = f.doc.quantidade_total
    if c is None:
        return None
    canonica, fator = unidade_quantidade(c.unidade)
    unidade = c.unidade.strip().upper()
    chave = (canonica, round(c.valor * fator, 3))
    return Valor(chave, formatar_contagem(c.valor, unidade), c.texto_original, f.arquivo.id, c.pagina, unidade)


def _somar_quantidade(valores: list[Valor], campo: NomeCampo, ctx: Contexto, col: Col) -> Valor | None:
    canonicas = {v.chave[0] for v in valores}
    if len(canonicas) > 1:
        ctx.avisos.append(
            f"{ctx.prefixo}Quantidade: não dá para somar \"{col.rotulo}\" — unidades diferentes "
            f"({', '.join(v.exibicao for v in valores)})."
        )
        return None
    canonica = canonicas.pop()
    total = round(sum(v.chave[1] for v in valores), 3)
    unidades = {v.unidade for v in valores}
    if len(unidades) == 1:  # mesma unidade do documento: soma na unidade original
        unidade = unidades.pop()
        _, fator = unidade_quantidade(unidade)
        exibicao = formatar_contagem(round(total / fator, 3), unidade)
    else:
        unidade, exibicao = canonica, formatar_contagem(total, canonica)
    return Valor((canonica, total), exibicao, _texto_soma(valores), None, None, unidade)


def _quantidades_iguais(a: tuple[str, float], b: tuple[str, float]) -> bool:
    return a[0] == b[0] and abs(a[1] - b[1]) < 1e-6


def _nota_fator_mil(valores: list[tuple[float, str, str | None]]) -> str:
    """Valores (total na unidade canônica, exibição, unidade do documento) que diferem por exatamente
    1000× indicam unidade trocada — ex.: PL "24.000 TONS" (960 × 25 kg) × Invoice "24 TO"."""
    totais = sorted({round(total, 6): (total, exibicao, unidade) for total, exibicao, unidade in valores}.values())
    if len(totais) != 2 or totais[0][0] <= 0 or abs(totais[1][0] / totais[0][0] - 1000) > 1e-6:
        return ""
    total, exibicao, unidade = totais[1]
    _, fator = unidade_quantidade(unidade or "")
    if fator == 1000:  # rotulado como tonelada; se o número for kg, vale 1000× menos
        return f" — provável unidade errada: {exibicao} equivale a {formatar_contagem(total / fator / 1000, 't')} se for kg"
    return " — provável unidade errada (os valores diferem exatamente 1.000 vezes)"


# NCM ------------------------------------------------------------------------

def _obter_ncm(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    todos = {c for c in (normalizar_ncm(n.codigo) for n in f.doc.ncms) if len(c) >= 4}
    # "3904" junto de "39041010" no mesmo documento é só a posição do mesmo código: fica o mais específico
    codigos = sorted(c for c in todos if not any(o != c and o.startswith(c) for o in todos))
    if not codigos:
        return None
    return Valor(
        tuple(codigos),
        ", ".join(formatar_ncm(c) for c in codigos),
        ", ".join(n.codigo for n in f.doc.ncms),
        f.arquivo.id,
        f.doc.ncms[0].pagina,
    )


def _juntar_ncm(valores: list[Valor], campo: NomeCampo, ctx: Contexto, col: Col) -> Valor:
    codigos = sorted({c for v in valores for c in v.chave})
    textos = list(dict.fromkeys(v.texto_original for v in valores if v.texto_original))
    return Valor(tuple(codigos), ", ".join(formatar_ncm(c) for c in codigos), ", ".join(textos) or None, None, None)


# Textos simples (nº invoice, PO, portos): conjunto de valores normalizados ----

def _valor_conjunto(textos: list[str], normalizar, f: Fonte, pagina: int | None) -> Valor | None:
    exibicoes: dict[str, str] = {}
    for texto in textos:
        if texto and texto.strip():
            chave = normalizar(texto)
            if chave:
                exibicoes.setdefault(chave, texto.strip())
    if not exibicoes:
        return None
    return Valor(
        frozenset(exibicoes),
        " / ".join(exibicoes.values()),
        " / ".join(t.strip() for t in textos if t and t.strip()),
        f.arquivo.id,
        pagina,
    )


def _juntar_conjunto(valores: list[Valor], campo: NomeCampo, ctx: Contexto, col: Col) -> Valor:
    chave = frozenset().union(*(v.chave for v in valores))
    exibicoes = list(dict.fromkeys(e for v in valores for e in v.exibicao.split(" / ")))
    return Valor(chave, " / ".join(exibicoes), _texto_soma(valores), None, None)


def _obter_numero_invoice(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    doc = f.doc
    if doc.tipo == "invoice":
        numeros = [doc.numero] if doc.numero else []
    else:
        numeros = list(doc.invoices_referenciadas)
        # PL que não cita invoice usa o próprio número como referência (costuma ser o mesmo da invoice)
        if doc.tipo == "packing_list" and doc.numero and not numeros:
            numeros.append(doc.numero)
    return _valor_conjunto(numeros, normalizar_numero_documento, f, _primeira_pagina(f))


def _obter_po(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    return _valor_conjunto([f.doc.po] if f.doc.po else [], normalizar_po, f, _primeira_pagina(f))


def _obter_porto(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    porto = f.doc.porto_origem if campo == "porto_origem" else f.doc.porto_destino
    if porto is None:
        return None
    valor = _valor_conjunto([porto.valor], normalizar_porto, f, porto.pagina)
    if valor:
        valor.texto_original = porto.valor
        valor.exibicao = normalizar_porto(porto.valor)
    return valor


def _juntar_porto(valores: list[Valor], campo: NomeCampo, ctx: Contexto, col: Col) -> Valor:
    chave = frozenset().union(*(v.chave for v in valores))
    return Valor(chave, " / ".join(sorted(chave)), _texto_soma(valores), None, None)


def _conjuntos_iguais(a: frozenset, b: frozenset) -> bool:
    return a == b


# Partes (exportador / consignatário) -----------------------------------------

def _obter_parte(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    parte: Parte | None = f.doc.exportador if campo == "exportador" else f.doc.consignatario
    if parte is None or not parte.nome.strip():
        return None
    item = (parte.nome.strip(), normalizar_cnpj(parte.cnpj))
    texto = f"{parte.nome.strip()} — {parte.cnpj}" if parte.cnpj else parte.nome.strip()
    return Valor((item,), _exibir_partes([item]), texto, f.arquivo.id, parte.pagina)


def _juntar_partes(valores: list[Valor], campo: NomeCampo, ctx: Contexto, col: Col) -> Valor:
    itens: list[tuple[str, str | None]] = []
    for v in valores:
        for item in v.chave:
            if not any(_partes_iguais(item, existente) for existente in itens):
                itens.append(item)
    return Valor(tuple(itens), _exibir_partes(itens), _texto_soma(valores), None, None)


def _exibir_partes(itens: list[tuple[str, str | None]]) -> str:
    return " / ".join(f"{nome} ({formatar_cnpj(cnpj)})" if cnpj else nome for nome, cnpj in itens)


def _partes_iguais(a: tuple[str, str | None], b: tuple[str, str | None]) -> bool:
    """Os dois com CNPJ/Tax ID => compara os dígitos; senão, o nome normalizado."""
    if a[1] and b[1]:
        return a[1] == b[1]
    return nomes_equivalentes(a[0], b[0])


def _eh_capital(item: tuple[str, str | None]) -> bool:
    nome, cnpj = item
    if cnpj:
        return cnpj.startswith(CNPJ_RAIZ_CAPITAL)
    return "CAPITAL TRADE" in nome.upper()


def _conhecimento_consignado_a_capital(col: Col, valor: Valor) -> bool:
    return col.chave.startswith("conhecimento") and all(_eh_capital(item) for item in valor.chave)


def _listas_de_partes_iguais(a: tuple, b: tuple) -> bool:
    return all(any(_partes_iguais(x, y) for y in b) for x in a) and all(
        any(_partes_iguais(y, x) for x in a) for y in b
    )


# v3: endereço/país do exportador, país de origem, incoterm, moeda ----------------

def _obter_endereco(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    parte = f.doc.exportador
    if parte is None or not parte.endereco or not parte.endereco.strip():
        return None
    texto = parte.endereco.strip()
    cidade = parte.cidade.strip() if parte.cidade and parte.cidade.strip() else None
    return Valor(((texto, cidade),), texto, texto, f.arquivo.id, parte.pagina)


def _juntar_enderecos(valores: list[Valor], campo: NomeCampo, ctx: Contexto, col: Col) -> Valor:
    enderecos: list[tuple[str, str | None]] = []
    for v in valores:
        for e in v.chave:
            if not any(enderecos_compativeis(e, existente) for existente in enderecos):
                enderecos.append(e)
    return Valor(tuple(enderecos), " / ".join(t for t, _ in enderecos), _texto_soma(valores), None, None)


def _listas_de_enderecos_iguais(a: tuple, b: tuple) -> bool:
    """Cada item é (endereço, cidade): cidades diferentes divergem mesmo com endereço parecido."""
    return all(any(enderecos_compativeis(x, y) for y in b) for x in a) and all(
        any(enderecos_compativeis(y, x) for x in a) for y in b
    )


def _obter_pais(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    if campo == "pais_exportador":
        parte = f.doc.exportador
        texto, pagina = (parte.pais, parte.pagina) if parte else (None, None)
    else:
        texto, pagina = (f.doc.pais_origem.valor, f.doc.pais_origem.pagina) if f.doc.pais_origem else (None, None)
    return _valor_conjunto([texto] if texto else [], normalizar_pais, f, pagina)


def _obter_moeda(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    moeda = f.doc.moeda
    if moeda is None:
        return None
    return _valor_conjunto([moeda.valor], normalizar_moeda, f, moeda.pagina)


def _exibir_incoterm(f: Fonte) -> str:
    inc = f.doc.incoterm
    sigla = normalizar_incoterm(inc.codigo)
    local = normalizar_porto(inc.local) if inc.local else ""
    return f"{sigla} {local}".strip()


def _obter_incoterm(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    inc = f.doc.incoterm
    if inc is None or not normalizar_incoterm(inc.codigo):
        return None
    sigla = normalizar_incoterm(inc.codigo)
    return Valor(frozenset({sigla}), _exibir_incoterm(f), inc.texto_original, f.arquivo.id, inc.pagina)


REGRAS: dict[NomeCampo, Regra] = {
    "peso_liquido": Regra(_obter_peso, _somar_peso, _pesos_iguais),
    "peso_bruto": Regra(_obter_peso, _somar_peso, _pesos_iguais),
    "volumes": Regra(_obter_volumes, _somar_volumes, lambda a, b: abs(a - b) < 1e-6),
    "quantidade": Regra(_obter_quantidade, _somar_quantidade, _quantidades_iguais),
    "ncm": Regra(_obter_ncm, _juntar_ncm, lambda a, b: set(a) == set(b)),
    "numero_invoice": Regra(_obter_numero_invoice, _juntar_conjunto, _conjuntos_iguais),
    "po": Regra(_obter_po, _juntar_conjunto, _conjuntos_iguais),
    "incoterm": Regra(_obter_incoterm, _juntar_conjunto, _conjuntos_iguais),
    "moeda": Regra(_obter_moeda, _juntar_conjunto, _conjuntos_iguais),
    "exportador": Regra(_obter_parte, _juntar_partes, _listas_de_partes_iguais),
    "endereco_exportador": Regra(_obter_endereco, _juntar_enderecos, _listas_de_enderecos_iguais),
    "pais_exportador": Regra(_obter_pais, _juntar_conjunto, _conjuntos_iguais),
    "consignatario": Regra(_obter_parte, _juntar_partes, _listas_de_partes_iguais),
    "pais_origem": Regra(_obter_pais, _juntar_conjunto, _conjuntos_iguais),
    "porto_origem": Regra(_obter_porto, _juntar_porto, _conjuntos_iguais),
    "porto_destino": Regra(_obter_porto, _juntar_porto, _conjuntos_iguais),
}


# ---------------------------------------------------------------------------
# Status geral
# ---------------------------------------------------------------------------

def _status_geral(
    por_tipo: dict[TipoDocumento, list[Fonte]], comparacoes: list[Comparacao], divergencias: list[Divergencia]
) -> StatusResultado:
    campos = [c for comp in comparacoes for c in comp.campos]
    if divergencias or any(c.status == "DIVERGENTE" for c in campos):
        return "DIVERGENTE"
    if any(not fontes for fontes in por_tipo.values()) or any(
        c.status == "NAO_ENCONTRADO" and c.campo in CAMPOS_SEMPRE_VISIVEIS for c in campos
    ):
        return "INCOMPLETO"
    return "OK"


# ---------------------------------------------------------------------------
# Itens (Invoice × Packing List, + Conhecimento na única/consolidado)
# ---------------------------------------------------------------------------

@dataclass
class ItemAgrupado:
    """Linhas do mesmo código num documento, somadas (cobre o PL que junta 2 lotes numa linha)."""

    codigo: str | None
    descricao: str
    referencia: str | None
    quantidade: tuple[str, float] | None  # (unidade canônica, total)
    quantidade_exibicao: str | None
    unidade: str | None  # unidade do documento, se todas as linhas usam a mesma
    lotes: list[str]
    validades: list[str]
    arquivo_id: str
    pagina: int | None


@dataclass
class ColItens:
    col: Col
    itens: list[ItemAgrupado]
    conhecimento: bool = False


Linha = dict[str, ItemAgrupado]  # chave da coluna -> item daquela coluna (só as colunas que têm o item)


def _itens(
    grupos: list[tuple[Fonte | None, Fonte | None]], conhecimentos: list[Fonte], avisos: list[str]
) -> tuple[list[ComparacaoItens], list[Divergencia]]:
    cols_conhecimento = [
        ColItens(c, _agrupar_itens(c.fontes), conhecimento=True) for c in _colunas_conhecimento(conhecimentos)
    ]
    cols_conhecimento = [c for c in cols_conhecimento if c.itens]
    resultado: list[ComparacaoItens] = []
    divergencias: list[Divergencia] = []

    def gerar(comparacao_id: str, prefixo: str, base: list[ColItens], extras: list[ColItens], so_conhecimento: bool):
        if len(base) == 2 or (base and extras):
            comparacao, divs = _comparar_itens(comparacao_id, prefixo, base, extras, avisos, so_conhecimento)
            resultado.append(comparacao)
            divergencias.extend(divs)

    for comparacao_id, prefixo, inv, pl in _pares(grupos):
        base = [ColItens(c, _agrupar_itens(c.fontes)) for c in _colunas_par(inv, pl)]
        extras = cols_conhecimento if comparacao_id == "unica" else []
        gerar(comparacao_id, prefixo, [c for c in base if c.itens], extras, so_conhecimento=False)

    if len(grupos) > 1 and cols_conhecimento:
        invoices = [inv for inv, _ in grupos if inv]
        pls = [pl for _, pl in grupos if pl]
        somas = []
        if invoices:
            somas.append(_coluna_soma("soma_invoices", invoices, "Invoices", "das", "invoice", "invoices"))
        if pls:
            somas.append(_coluna_soma("soma_packing_lists", pls, "Packing Lists", "dos", "packing list", "packing lists"))
        base = [ColItens(c, _agrupar_itens(c.fontes)) for c in somas]
        # invoice × PL já foram comparados em cada par: aqui só interessa o que envolve o conhecimento
        gerar("consolidado", "Consolidado — ", [c for c in base if c.itens], cols_conhecimento, so_conhecimento=True)
    return resultado, divergencias


def _agrupar_itens(fontes: list[Fonte]) -> list[ItemAgrupado]:
    """Agrupa por código as linhas de todos os documentos da coluna (vários, quando é uma soma)."""
    grupos: dict[str, list[tuple[ItemExtraido, str]]] = {}
    linhas = [(item, f.arquivo.id) for f in fontes for item in f.doc.itens]
    for i, (item, arquivo_id) in enumerate(linhas):
        codigo = normalizar_codigo_item(item.codigo) if item.codigo else ""
        grupos.setdefault(codigo or f"#sem-codigo-{i}", []).append((item, arquivo_id))
    return [_juntar_linhas([l for l, _ in g], g[0][1]) for g in grupos.values()]


def _juntar_linhas(linhas: list[ItemExtraido], arquivo_id: str) -> ItemAgrupado:
    quantidade, exibicao = _somar_quantidades_itens(linhas)
    unidades = {(l.unidade or "").strip().upper() for l in linhas}
    return ItemAgrupado(
        codigo=next((l.codigo.strip() for l in linhas if l.codigo and l.codigo.strip()), None),
        descricao=linhas[0].descricao.strip(),
        referencia=next((l.referencia.strip() for l in linhas if l.referencia and l.referencia.strip()), None),
        quantidade=quantidade,
        quantidade_exibicao=exibicao,
        unidade=unidades.pop() if len(unidades) == 1 else None,
        lotes=list(dict.fromkeys(lote.strip() for l in linhas for lote in l.lotes if lote.strip())),
        validades=list(dict.fromkeys(v.strip() for l in linhas for v in l.validades if v.strip())),
        arquivo_id=arquivo_id,
        pagina=linhas[0].pagina,
    )


def _somar_quantidades_itens(linhas: list[ItemExtraido]) -> tuple[tuple[str, float] | None, str | None]:
    if any(l.quantidade is None for l in linhas):
        return None, None
    convertidas = [(*unidade_quantidade(l.unidade or ""), l) for l in linhas]
    canonicas = {canonica for canonica, _, _ in convertidas}
    if len(canonicas) > 1:
        return None, " + ".join(formatar_contagem(l.quantidade, (l.unidade or "").upper()) for l in linhas)
    canonica = canonicas.pop()
    total = round(sum(l.quantidade * fator for _, fator, l in convertidas), 6)
    unidades = {(l.unidade or "").strip().upper() for l in linhas}
    if len(unidades) == 1:  # mesma unidade do documento: exibe na unidade original
        exibicao = formatar_contagem(sum(l.quantidade for l in linhas), unidades.pop())
    else:
        exibicao = formatar_contagem(total, canonica)
    return (canonica, total), exibicao


def _mesmo_codigo(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    return bool(a.codigo and b.codigo and normalizar_codigo_item(a.codigo) == normalizar_codigo_item(b.codigo))


def _casar(
    linhas: list[list[ItemAgrupado]], itens: list[ItemAgrupado], generico_nao_casa: bool = False
) -> tuple[list[tuple[int, ItemAgrupado]], list[int], list[ItemAgrupado]]:
    """Casa `itens` com `linhas` (cada linha = itens já casados entre si): por código, pela descrição
    (≥ 0,80, melhor par primeiro) e, se sobrar exatamente 1 de cada lado, um com o outro.
    Com `generico_nao_casa` (conhecimento), item cuja descrição serve para mais de uma linha
    (ex.: "SYNTHETIC SHOES") não casa pela descrição.
    Devolve (casamentos (índice da linha, item), linhas que sobraram, itens que sobraram)."""
    casados: list[tuple[int, ItemAgrupado]] = []
    livres_l, livres_i = list(range(len(linhas))), list(itens)
    # 1) pelo código
    for item in itens:
        i = next((i for i in livres_l if any(_mesmo_codigo(item, x) for x in linhas[i])), None)
        if i is not None:
            casados.append((i, item))
            livres_l.remove(i)
            livres_i.remove(item)
    # 2) pela descrição
    candidatos = sorted(
        ((max(_semelhanca_descricao(item, x) for x in linhas[i]), -n, -i) for n, item in enumerate(livres_i) for i in livres_l),
        reverse=True,
    )
    usados_l, usados_i = set(), set()
    if generico_nao_casa:
        for n in range(len(livres_i)):
            if sum(1 for nota, m, _ in candidatos if -m == n and nota >= SIMILARIDADE_MINIMA_CASAMENTO) > 1:
                usados_i.add(n)
    genericos = set(usados_i)
    for nota, n, i in candidatos:
        n, i = -n, -i
        if nota < SIMILARIDADE_MINIMA_CASAMENTO or i in usados_l or n in usados_i:
            continue
        casados.append((i, livres_i[n]))
        usados_l.add(i)
        usados_i.add(n)
    livres_l = [i for i in livres_l if i not in usados_l]
    sobras = [item for n, item in enumerate(livres_i) if n in genericos]
    livres_i = [item for n, item in enumerate(livres_i) if n not in usados_i]
    # 3) sobrou exatamente 1 de cada lado: é o mesmo item com dados diferentes
    if len(livres_l) == 1 and len(livres_i) == 1 and not sobras:
        casados.append((livres_l.pop(), livres_i.pop()))
    return casados, livres_l, livres_i + sobras


def _casar_base(base: list[ColItens]) -> list[Linha]:
    """Linhas Invoice × Packing List (ou de uma coluna só), na ordem da primeira coluna."""
    primeira = base[0]
    linhas: list[Linha] = [{primeira.col.chave: item} for item in primeira.itens]
    if len(base) == 1:
        return linhas
    segunda = base[1]
    casados, _, sobras = _casar([[item] for item in primeira.itens], segunda.itens)
    for i, item in casados:
        linhas[i][segunda.col.chave] = item
    return linhas + [{segunda.col.chave: item} for item in sobras]


def _semelhanca_descricao(a: ItemAgrupado, b: ItemAgrupado) -> float:
    if descricoes_equivalentes(a.descricao, b.descricao):
        return 1.0
    return similaridade(normalizar_descricao(a.descricao), normalizar_descricao(b.descricao))


@dataclass
class Atributo:
    nome: str  # vai em LinhaItem.diferencas
    rotulo: str  # usado na mensagem
    informado: Callable[[ItemAgrupado], bool]
    iguais: Callable[[ItemAgrupado, ItemAgrupado], bool]
    chave_exibicao: Callable[[ItemAgrupado], Any]  # agrupa valores iguais na mensagem
    exibicao: Callable[[ItemAgrupado], str]


def _validades(item: ItemAgrupado) -> list[str]:
    return list(dict.fromkeys(normalizar_validade(v) for v in item.validades))


def _quantidades_comparaveis_diferentes(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    return a.quantidade[0] == b.quantidade[0] and abs(a.quantidade[1] - b.quantidade[1]) > 1e-6


def _descricoes_iguais(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    """Com referência/modelo dos dois lados, compara as referências (uma letra muda o produto:
    'POLIREX YK 455' × 'POLIREX ZK 455'); senão, a similaridade das descrições."""
    if a.referencia and b.referencia:
        return referencias_iguais(a.referencia, b.referencia)
    return descricoes_equivalentes(a.descricao, b.descricao)


def _exibir_descricao(x: ItemAgrupado) -> str:
    """Descrição curta; com a referência entre parênteses se ela não estiver na descrição."""
    if x.referencia and normalizar_referencia(x.referencia) not in normalizar_referencia(x.descricao):
        return f"{_curta(x.descricao)} (ref. {x.referencia})"
    return _curta(x.descricao)


ATRIBUTOS_ITEM = [
    Atributo(
        "descricao", "descrição", lambda x: bool(x.descricao),
        _descricoes_iguais,
        lambda x: (normalizar_referencia(x.referencia or ""), normalizar_descricao(x.descricao)), _exibir_descricao,
    ),
    Atributo(
        "quantidade", "quantidade", lambda x: x.quantidade is not None,
        lambda a, b: not _quantidades_comparaveis_diferentes(a, b),  # unidades diferentes: não dá para comparar
        lambda x: x.quantidade, lambda x: x.quantidade_exibicao or "",
    ),
    Atributo(
        "lote", "lote", lambda x: bool(x.lotes),
        lambda a, b: {normalizar_lote(l) for l in a.lotes} == {normalizar_lote(l) for l in b.lotes},
        lambda x: frozenset(normalizar_lote(l) for l in x.lotes), lambda x: ", ".join(x.lotes),
    ),
    Atributo(
        "validade", "validade", lambda x: bool(x.validades),
        lambda a, b: set(_validades(a)) == set(_validades(b)),
        lambda x: frozenset(_validades(x)), lambda x: ", ".join(_validades(x)),
    ),
]


def _diferencas_item(linha: Linha, colunas: list[ColItens], so_conhecimento: bool) -> list[tuple[str, str]]:
    """Lista de (nome da diferença, texto da mensagem). Com `so_conhecimento`, só contam as diferenças
    entre o conhecimento e outra coluna (invoice × PL já foram comparados em cada par)."""
    difs: list[tuple[str, str]] = []
    for atributo in ATRIBUTOS_ITEM:
        informados = [(c, linha[c.col.chave]) for c in colunas if c.col.chave in linha]
        informados = [(c, x) for c, x in informados if atributo.informado(x)]
        diferentes = any(
            not atributo.iguais(x, y)
            for n, (c1, x) in enumerate(informados)
            for c2, y in informados[n + 1:]
            if not so_conhecimento or c1.conhecimento or c2.conhecimento
        )
        if diferentes:
            nota = ""
            if atributo.nome == "quantidade":
                nota = _nota_fator_mil([(x.quantidade[1], x.quantidade_exibicao or "", x.unidade) for _, x in informados])
            difs.append((atributo.nome, f"{atributo.rotulo} {_texto_grupos(atributo, informados)}{nota}"))
    return difs


def _texto_grupos(atributo: Atributo, informados: list[tuple[ColItens, ItemAgrupado]]) -> str:
    """'Invoice POLIRMX HD 475 × Packing List/BL POLIREX YK 455' — minoria primeiro."""
    grupos: dict[Any, tuple[list[str], ItemAgrupado]] = {}
    for c, x in informados:
        grupos.setdefault(atributo.chave_exibicao(x), ([], x))[0].append(c.col.nome_curto)
    ordenados = sorted(grupos.values(), key=lambda g: len(g[0]))
    return " × ".join(f"{'/'.join(nomes)} {atributo.exibicao(x)}" for nomes, x in ordenados)


def _curta(texto: str) -> str:
    texto = " ".join(texto.split())
    return texto if len(texto) <= TAMANHO_MAX_DESCRICAO else texto[: TAMANHO_MAX_DESCRICAO - 1].rstrip() + "…"


def _valor_item(item: ItemAgrupado | None) -> ValorItem | None:
    if item is None:
        return None
    return ValorItem(
        descricao=item.descricao,
        quantidade=item.quantidade_exibicao,
        lotes=item.lotes,
        validades=item.validades,
        arquivo_id=item.arquivo_id,
        pagina=item.pagina,
    )


def _comparar_itens(
    comparacao_id: str,
    prefixo: str,
    base: list[ColItens],
    conhecimentos: list[ColItens],
    avisos: list[str],
    so_conhecimento: bool,
) -> tuple[ComparacaoItens, list[Divergencia]]:
    linhas = _casar_base(base)
    for c in conhecimentos:
        casados, _, sobras = _casar([list(l.values()) for l in linhas], c.itens, generico_nao_casa=True)
        for i, item in casados:
            linhas[i][c.col.chave] = item
        for item in sobras:  # BL costuma ter descrição genérica: não é divergência
            avisos.append(
                f"{prefixo}{c.col.nome_curto} descreve '{_curta(item.descricao)}'; "
                "não foi possível relacionar aos itens."
            )

    colunas = base + conhecimentos
    linhas_item: list[LinhaItem] = []
    divergencias: list[Divergencia] = []
    for linha in linhas:
        itens_base = [linha[c.col.chave] for c in base if c.col.chave in linha]
        primeiro = itens_base[0]
        codigo = next((x.codigo for x in [*itens_base, *linha.values()] if x.codigo), None)
        chave = codigo or _curta(primeiro.descricao)
        difs = _diferencas_item(linha, colunas, so_conhecimento)
        if len(base) == 2 and len(itens_base) == 1 and not so_conhecimento:
            difs.insert(0, ("ausente", "só na Invoice" if base[0].col.chave in linha else "só no Packing List"))
        linhas_item.append(
            LinhaItem(
                chave=chave,
                status="DIVERGENTE" if difs else "OK",
                diferencas=[nome for nome, _ in difs],
                valores={c.col.chave: _valor_item(linha.get(c.col.chave)) for c in colunas},
            )
        )
        if difs:
            divergencias.append(
                Divergencia(
                    categoria="item",
                    comparacao_id=comparacao_id,
                    campo=None,
                    mensagem=f"{prefixo}Item {chave}: {'; '.join(texto for _, texto in difs)}",
                    pagina=primeiro.pagina,
                    item_chave=chave,
                )
            )
    colunas_saida = [
        Coluna(chave=c.col.chave, rotulo=c.col.rotulo, documentos=[_ref(f) for f in c.col.fontes]) for c in colunas
    ]
    titulo = "Itens — " + " × ".join(c.col.rotulo for c in colunas)
    return (
        ComparacaoItens(comparacao_id=comparacao_id, titulo=titulo, colunas=colunas_saida, linhas=linhas_item),
        divergencias,
    )


# ---------------------------------------------------------------------------
# Coerência: incoterm × frete do conhecimento e × portos
# ---------------------------------------------------------------------------

def _frete_normalizado(texto: str) -> str | None:
    t = " ".join(texto.upper().replace(".", " ").split())
    if "PREPAID" in t or t in {"PP", "P P"}:
        return "PREPAID"
    if "COLLECT" in t or t in {"CC", "COLL", "C C"}:
        return "COLLECT"
    return None


def _coerencia(grupos: list[tuple[Fonte | None, Fonte | None]], conhecimentos: list[Fonte]) -> list[Divergencia]:
    divergencias: list[Divergencia] = []
    varios = len(grupos) > 1
    for comparacao_id, prefixo, inv, pl in _pares(grupos):
        fonte = next((f for f in (inv, pl) if f and f.doc.incoterm and normalizar_incoterm(f.doc.incoterm.codigo)), None)
        if fonte is None:
            continue
        id_conhecimento = "consolidado" if varios else comparacao_id
        for comp_id, mensagem in _coerencia_incoterm(fonte, [f for f in (inv, pl) if f], conhecimentos):
            divergencias.append(
                Divergencia(
                    categoria="coerencia",
                    comparacao_id=id_conhecimento if comp_id == "conhecimento" else comparacao_id,
                    campo="incoterm",
                    mensagem=(prefixo if comp_id == "par" else "") + mensagem,
                    documento=_ref(fonte),
                    evidencia=fonte.doc.incoterm.texto_original,
                    pagina=fonte.doc.incoterm.pagina,
                )
            )
    return divergencias


def _coerencia_incoterm(fonte: Fonte, par: list[Fonte], conhecimentos: list[Fonte]) -> list[tuple[str, str]]:
    """Lista de ('par' | 'conhecimento', mensagem)."""
    inc = fonte.doc.incoterm
    sigla = normalizar_incoterm(inc.codigo)
    local = normalizar_porto(inc.local) if inc.local else ""
    exibicao = f"{sigla} {local}".strip()
    nome = _nome_doc(fonte)
    resultado: list[tuple[str, str]] = []

    if sigla in INCOTERMS_EF or sigla in INCOTERMS_CD:
        esperado = "COLLECT" if sigla in INCOTERMS_EF else "PREPAID"
        quem = "comprador" if sigla in INCOTERMS_EF else "vendedor"
        for c in conhecimentos:
            frete = _frete_normalizado(c.doc.frete.valor) if c.doc.frete else None
            if frete and frete != esperado:
                resultado.append((
                    "conhecimento",
                    f"{_nome_doc(c)} com frete {frete}, mas o incoterm da {nome} é {sigla} "
                    f"(frete por conta do {quem}; esperado {esperado})",
                ))

    if local and sigla in INCOTERMS_EF:
        destinos = {
            normalizar_porto(f.doc.porto_destino.valor) for f in par + conhecimentos if f.doc.porto_destino
        }
        if local in destinos:
            resultado.append((
                "par",
                f"Incoterm {exibicao} ({nome}): {sigla} indica local de embarque/origem, mas {local} é o destino",
            ))
    if local and sigla in INCOTERMS_CD:
        for c in conhecimentos:
            destino = normalizar_porto(c.doc.porto_destino.valor) if c.doc.porto_destino else ""
            if destino and destino != local:
                resultado.append((
                    "conhecimento",
                    f"Incoterm {exibicao} ({nome}) × porto de descarga do {_nome_doc(c)} {destino}",
                ))
    return resultado


# ---------------------------------------------------------------------------
# Inconsistências internas (do modelo + determinísticas)
# ---------------------------------------------------------------------------

def _internas(f: Fonte) -> list[Divergencia]:
    nome = _nome_doc(f)
    divergencias = [
        Divergencia(
            categoria="interna",
            comparacao_id=None,
            campo=None,
            mensagem=f"{nome}: {i.descricao}",
            documento=_ref(f),
            evidencia=i.evidencia,
            pagina=i.pagina,
        )
        for i in f.doc.inconsistencias_internas
    ]
    moeda = normalizar_moeda(f.doc.moeda.valor) if f.doc.moeda else None
    for item in f.doc.itens:
        if item.sem_valor_comercial and (item.valor_total or 0) > 0:
            identificacao = item.codigo or _curta(item.descricao)
            valor = formatar_dinheiro(item.valor_total, moeda)
            divergencias.append(
                Divergencia(
                    categoria="interna",
                    comparacao_id=None,
                    campo=None,
                    mensagem=f"{nome}: item {identificacao} marcado como FOC (sem valor comercial), mas cobrado {valor}",
                    documento=_ref(f),
                    evidencia=f"{identificacao} — FOC — {valor}",
                    pagina=item.pagina,
                )
            )
    return divergencias


def _avisos_pais_origem(invoices: list[Fonte]) -> list[str]:
    avisos = []
    for f in invoices:
        origem, exportador = f.doc.pais_origem, f.doc.exportador
        if origem and exportador and exportador.pais:
            if normalizar_pais(origem.valor) != normalizar_pais(exportador.pais):
                avisos.append(
                    f"{_nome_doc(f)}: país de origem da mercadoria ({origem.valor}) diferente do país do "
                    f"exportador ({exportador.pais}) — confira se é esperado."
                )
    return avisos
