"""Escolha dos documentos: tira proformas e resumos da soma e, entre duplicatas, fica a melhor versão."""

import re
from dataclasses import dataclass

from app.schemas import ArquivoEntrada, DocumentoExtraido, ExtracaoArquivo, ItemExtraido, TipoDocumento
from app.services.comparacao.constantes import (
    MEDIAS_DE_ESCRITORIO,
    NOME_TIPO,
    PRIORIDADE_FORMATO,
    PRIORIDADE_VERSAO,
    TIPOS,
)
from app.services.comparacao.identificacao_do_documento import PROFORMA, e_proforma, nome_doc, numero_normalizado
from app.services.comparacao.normalizacao import (
    descricoes_equivalentes,
    iguais_no_centavo,
    normalizar_codigo_item,
    numero_sem_serie,
    porto_brasileiro,
    sem_acento,
    unidade_quantidade,
)
from app.services.comparacao.tipos import Fonte
from app.services.leitura.arquivo_para_conteudo import MEDIA_PDF, MEDIA_XLS, MEDIA_XLSX

MEDIAS_DE_PLANILHA = (MEDIA_XLS, MEDIA_XLSX)


@dataclass
class DocumentosEscolhidos:
    por_tipo: dict[TipoDocumento, list[Fonte]]
    fora_da_soma: list[Fonte]  # proformas e resumos: não entram na comparação, mas são conferidos por dentro


def escolher_documentos(
    extracoes: list[tuple[ArquivoEntrada, ExtracaoArquivo]], avisos: list[str]
) -> DocumentosEscolhidos:
    por_tipo: dict[TipoDocumento, list[Fonte]] = {tipo: [] for tipo in TIPOS}
    for i, (arquivo, extracao) in enumerate(extracoes):
        for j, doc in enumerate(extracao.documentos):
            if doc.tipo in por_tipo:
                por_tipo[doc.tipo].append(Fonte(arquivo, doc, (i, j), escaneado=extracao.escaneado))
        if extracao.documentos and all(d.tipo not in por_tipo for d in extracao.documentos):
            lidos = ", ".join(dict.fromkeys(d.subtipo or "documento de outro tipo" for d in extracao.documentos))
            avisos.append(f"{arquivo.nome} não entrou na comparação: não é invoice, packing list nem conhecimento ({lidos}).")
    por_tipo["conhecimento"] = _sem_conhecimentos_de_saida(por_tipo["conhecimento"], avisos)
    citados = _invoices_citadas(por_tipo)
    comerciais, proformas = _separar_proformas(por_tipo["invoice"], avisos)
    por_tipo["invoice"], resumos = _separar_resumos(comerciais, avisos)
    fora_da_soma = [max(g, key=_preferencia) for g in _grupos_de_duplicatas(proformas + resumos, citados)]
    return DocumentosEscolhidos(_melhores_versoes(por_tipo, avisos, citados), fora_da_soma)


def _invoices_citadas(por_tipo: dict[TipoDocumento, list[Fonte]]) -> set[str]:
    return {numero_normalizado(n) for fontes in por_tipo.values() for f in fontes for n in f.doc.invoices_referenciadas}


def _melhores_versoes(
    por_tipo: dict[TipoDocumento, list[Fonte]], avisos: list[str], citados: set[str]
) -> dict[TipoDocumento, list[Fonte]]:
    """Entre duplicatas do mesmo documento fica a melhor versão; as outras viram `duplicatas` dela."""
    escolhidos: dict[TipoDocumento, list[Fonte]] = {}
    for tipo, fontes in por_tipo.items():
        if not fontes:
            avisos.append(f"Documento não encontrado nos arquivos enviados: {NOME_TIPO[tipo]}.")
        escolhidos[tipo] = []
        for grupo in _grupos_de_duplicatas(fontes, citados):
            mesmas = _paginas_juntadas(grupo, avisos)
            melhor, *ignorados = sorted(mesmas, key=_preferencia, reverse=True)
            melhor.duplicatas = ignorados
            escolhidos[tipo].append(melhor)
            if ignorados:
                avisos.append(
                    f"Mais de um documento {nome_doc(melhor)}; usado {_descrever(melhor)}, "
                    f"{_motivo(melhor, ignorados[0])}. "
                    f"Ignorado(s): {'; '.join(_descrever(f) + _diferencas(melhor, f) for f in ignorados)}."
                )
        escolhidos[tipo].sort(key=lambda f: f.ordem)
    return escolhidos


def _grupos_de_duplicatas(fontes: list[Fonte], citados: set[str]) -> list[list[Fonte]]:
    """`citados`: números de invoice citados por PL/BL; um número citado nunca é tratado como versão descartável."""
    grupos: list[list[Fonte]] = []
    for f in fontes:
        grupo = next((g for g in grupos if any(_mesmo_documento(x, f, citados) for x in g)), None)
        if grupo:
            grupo.append(f)
        else:
            grupos.append([f])
    return grupos


def _paginas_juntadas(mesmas: list[Fonte], avisos: list[str]) -> list[Fonte]:
    """Mesmo número em arquivos com itens que não se repetem e totais só em um: são páginas, viram um documento."""
    if len(mesmas) < 2 or not _sao_paginas(mesmas):
        return mesmas
    paginas = sorted(mesmas, key=lambda f: (f.arquivo.nome, f.ordem))
    base = next(f for f in paginas if _tem_totais(f))
    doc = _documento_juntado(base.doc, [f.doc for f in paginas])
    juntada = Fonte(base.arquivo, doc, base.ordem, escaneado=base.escaneado)
    nomes = ", ".join(f.arquivo.nome for f in paginas)
    avisos.append(
        f"{nome_doc(juntada)} veio em {len(paginas)} arquivos ({nomes}): itens juntados, totais de {base.arquivo.nome}."
    )
    return [juntada]


def _sao_paginas(fontes: list[Fonte]) -> bool:
    """Todos com itens, nenhuma linha repetida entre arquivos e totais em um só (ou totais que batem com a soma)."""
    if not all(f.doc.itens for f in fontes):
        return False
    pares = [(a, b) for i, a in enumerate(fontes) for b in fontes[i + 1:]]
    if any(_mesma_linha(x, y, False) for a, b in pares for x in a.doc.itens for y in b.doc.itens):
        return False
    com_totais = [f for f in fontes if _tem_totais(f)]
    return len(com_totais) == 1 or bool(com_totais) and all(_total_e_a_soma(f, fontes) for f in com_totais)


def _tem_totais(f: Fonte) -> bool:
    return any(_totais(f)) or f.doc.valor_total is not None


def _total_e_a_soma(f: Fonte, fontes: list[Fonte]) -> bool:
    valores = [i.valor_total for g in fontes for i in g.doc.itens]
    total = f.doc.valor_total
    return total is not None and None not in valores and iguais_no_centavo(round(sum(valores), 2), total.valor)


def _documento_juntado(base: DocumentoExtraido, paginas: list[DocumentoExtraido]) -> DocumentoExtraido:
    """O documento com os totais, com os itens de todas as páginas e os campos que só outra página traz."""
    vazios = {
        nome: valor
        for nome in DocumentoExtraido.model_fields
        if not getattr(base, nome) and (valor := next((v for d in paginas if (v := getattr(d, nome))), None))
    }
    return base.model_copy(update=vazios | {"itens": [i for d in paginas for i in d.itens]})


def _separar_proformas(invoices: list[Fonte], avisos: list[str]) -> tuple[list[Fonte], list[Fonte]]:
    """Proforma (lida como tal, ex. uma aba do Excel) sai quando há invoice comercial: é o pedido, não o embarque."""
    proformas = [f for f in invoices if e_proforma(f.doc)]
    comerciais = [f for f in invoices if f not in proformas]
    if not comerciais:
        return invoices, []
    for f in proformas:
        avisos.append(f"{nome_doc(f)} ({_onde(f)}) não entrou na comparação: há invoice comercial.")
    return comerciais, proformas


def _sem_conhecimentos_de_saida(conhecimentos: list[Fonte], avisos: list[str]) -> list[Fonte]:
    """Sai do Brasil para o exterior e há outro que chega ao Brasil: é de exportação ou devolução, não o da importação."""
    if not any(_chega_ao_brasil(f.doc) for f in conhecimentos):
        return conhecimentos
    saida = [f for f in conhecimentos if _sai_do_brasil(f.doc)]
    for f in saida:
        avisos.append(
            f"{nome_doc(f)} ({_onde(f)}) não entrou na comparação: é de exportação ou devolução "
            f"({f.doc.porto_origem.valor} → {f.doc.porto_destino.valor})."
        )
    return [f for f in conhecimentos if not _sai_do_brasil(f.doc)]


def _chega_ao_brasil(doc: DocumentoExtraido) -> bool:
    origem, destino = doc.porto_origem, doc.porto_destino
    return bool(origem and destino) and porto_brasileiro(destino.valor) and not porto_brasileiro(origem.valor)


def _sai_do_brasil(doc: DocumentoExtraido) -> bool:
    origem, destino = doc.porto_origem, doc.porto_destino
    return bool(origem and destino) and porto_brasileiro(origem.valor) and not porto_brasileiro(destino.valor)


def _separar_resumos(invoices: list[Fonte], avisos: list[str]) -> tuple[list[Fonte], list[Fonte]]:
    """Invoice cujo número junta o de duas ou mais outras do processo ('A1, A2') é o resumo delas: sai da soma."""
    numeros = {numero_sem_serie(f.doc.numero) for f in invoices if f.doc.numero}
    resumos = [f for f in invoices if f.doc.numero and len(_partes(f.doc.numero) & numeros) >= 2]
    for f in resumos:
        avisos.append(f"Invoice {f.doc.numero} ({_onde(f)}) não entrou na comparação: é o resumo das outras invoices.")
    return [f for f in invoices if f not in resumos], resumos


SEPARADOR_DE_NUMEROS = re.compile(r"(?i)\s*[,;/&+]\s*|\s+E\s+|\s+AND\s+")


def _partes(numero: str) -> set[str]:
    return {numero_sem_serie(p) for p in SEPARADOR_DE_NUMEROS.split(numero) if p.strip()}


def _preferencia(f: Fonte) -> tuple:
    """Mesmo documento => fica 1: não proforma, versão, nome (rascunho/original, revisão), PDF, identificado, último."""
    return (
        not PROFORMA.search(f.arquivo.nome),  # proforma com o número da invoice nunca vale mais que ela
        PRIORIDADE_VERSAO[f.doc.versao],
        versao_pelo_nome(f.arquivo.nome),
        revisao_pelo_nome(f.arquivo.nome),
        PRIORIDADE_FORMATO.get(f.arquivo.media_type, 0),
        bool(f.doc.numero or f.doc.invoices_referenciadas),  # a lista por contêiner sem número é detalhe do PL
        f.ordem,
    )


REVISAO = re.compile(r"(?i)(?<![A-Z])(rev(?:is(?:ed|ad[oa]|ao|ão))?|ajustad[oa]|corrigid[oa]|final(?:is)?)(?![A-Z])[\s._-]*(\d+)?")


PALAVRAS_DE_RASCUNHO = [
    "drafts?", "rascunhos?", "preliminar(?:y)?", "borrador", "c[oó]pias?", "copy", r"(?:n[aã]o|non)[\s_-]*original",
]
RASCUNHO = re.compile(rf"(?i)(?<![A-Z])({'|'.join(PALAVRAS_DE_RASCUNHO)})(?![A-Z])")
ORIGINAL = re.compile(r"(?i)(?<![A-Z])(orig(?:inal(?:es|s)?|inais)?)(?![A-Z])")


def versao_pelo_nome(nome: str) -> int:
    """'CI DRAFT.pdf' -1 < 'CI.pdf' 0 < 'CI ORIGINAL.pdf' 1: rascunho ou cópia no nome perde mesmo que diga original."""
    return -1 if RASCUNHO.search(nome) else 1 if ORIGINAL.search(nome) else 0


def revisao_pelo_nome(nome: str) -> tuple[int, int]:
    """'CI REV-1.pdf' > 'CI.pdf'; 'PL REV.2' > 'PL REV.1': o nome do arquivo é o que diz qual versão é a mais nova."""
    marcas = REVISAO.findall(nome)
    return (1, max(int(n or 0) for _, n in marcas)) if marcas else (0, 0)


def _mesmo_documento(a: Fonte, b: Fonte, citados: set[str]) -> bool:
    """Mesmo número (ou carga renumerada em outro formato); sem número, os mesmos totais ou a mesma invoice e itens."""
    if _detalhe_em_planilha(a, b) or _detalhe_em_planilha(b, a):
        return True
    na, nb = numero_normalizado(a.doc.numero), numero_normalizado(b.doc.numero)
    if na and nb:
        return na == nb or _mesma_carga_em_outro_formato(a, b, citados)
    ra = {numero_normalizado(n) for n in a.doc.invoices_referenciadas}
    rb = {numero_normalizado(n) for n in b.doc.invoices_referenciadas}
    if ra and rb and ra != rb:
        return False
    if ra and ra == rb and a.ordem[0] != b.ordem[0] and _mesmos_itens(a, b):
        return True  # rascunho em Word e versão final em PDF: os totais podem ter mudado
    return _mesmos_totais(a, b)


def _mesma_carga_em_outro_formato(a: Fonte, b: Fonte, citados: set[str]) -> bool:
    """Excel/Word × PDF com outro número, mesmos totais e itens, e o número do Excel/Word não citado: renumerado."""
    pdf, office = (a, b) if a.arquivo.media_type == MEDIA_PDF else (b, a)
    if pdf.arquivo.media_type != MEDIA_PDF or office.arquivo.media_type not in MEDIAS_DE_ESCRITORIO:
        return False
    if numero_normalizado(office.doc.numero) in citados:
        return False  # outro documento cita esse número: é outra invoice, não uma versão antiga
    return _mesmos_totais(a, b) and _mesmos_itens(a, b)


def _detalhe_em_planilha(planilha: Fonte, pdf: Fonte) -> bool:
    """PL em planilha com os pesos (e a quantidade, se houver) do PL em PDF e sem citar outra invoice: é o detalhe."""
    if planilha.doc.tipo != "packing_list" or pdf.doc.tipo != "packing_list":
        return False
    if planilha.arquivo.media_type not in MEDIAS_DE_PLANILHA or pdf.arquivo.media_type != MEDIA_PDF:
        return False
    return _mesmos_pesos_e_quantidade(planilha.doc, pdf.doc) and not _citam_outras_invoices(planilha.doc, pdf.doc)


def _mesmos_pesos_e_quantidade(x: DocumentoExtraido, y: DocumentoExtraido) -> bool:
    pesos = [(x.peso_liquido_total, y.peso_liquido_total), (x.peso_bruto_total, y.peso_bruto_total)]
    qa, qb = x.quantidade_total, y.quantidade_total
    return all(p and q and iguais_no_centavo(p.valor, q.valor) for p, q in pesos) and (
        not (qa and qb) or iguais_no_centavo(qa.valor, qb.valor)
    )


def _citam_outras_invoices(x: DocumentoExtraido, y: DocumentoExtraido) -> bool:
    """Os dois citam invoices e nenhuma em comum: são PLs de outras invoices, não detalhe um do outro."""
    rx = {numero_normalizado(n) for n in x.invoices_referenciadas}
    ry = {numero_normalizado(n) for n in y.invoices_referenciadas}
    return bool(rx and ry) and not rx & ry


def _mesmos_totais(a: Fonte, b: Fonte) -> bool:
    """Ao menos 2 totais iguais; se um deles é a quantidade e só há 2, também o mesmo número de linhas."""
    iguais = [iguais_no_centavo(x.valor, y.valor) for x, y in zip(_totais(a), _totais(b)) if x and y]
    qa, qb = _quantidade(a), _quantidade(b)
    if qa and qb:
        iguais.append(qa[0] == qb[0] and iguais_no_centavo(qa[1], qb[1]))
    if len(iguais) < 2 or not all(iguais):
        return False
    return len(iguais) > 2 or not (qa and qb) or _mesmo_numero_de_linhas(a, b)


def _quantidade(f: Fonte) -> tuple[str, float] | None:
    """Quantidade total na unidade canônica: 2 TON -> ('KG', 2000)."""
    q = f.doc.quantidade_total
    if q is None:
        return None
    canonica, fator = unidade_quantidade(q.unidade)
    return canonica, q.valor * fator


def _mesmo_numero_de_linhas(a: Fonte, b: Fonte) -> bool:
    return bool(a.doc.itens) and len(a.doc.itens) == len(b.doc.itens)


def _mesmos_itens(a: Fonte, b: Fonte) -> bool:
    """Cada linha de um tem par no outro: primeiro todos os pares exatos, depois as sobras por descrição equivalente."""
    sobra_a, sobra_b = list(a.doc.itens), list(b.doc.itens)
    for exata in (True, False):
        for x in list(sobra_a):
            par = next((y for y in sobra_b if _mesma_linha(x, y, exata)), None)
            if par is not None:
                sobra_a.remove(x)
                sobra_b.remove(par)
    return bool(a.doc.itens) and not sobra_a and not sobra_b


def _mesma_linha(x: ItemExtraido, y: ItemExtraido, exata: bool) -> bool:
    """Mesma quantidade e mesmo código; sem código, as mesmas palavras (em qualquer ordem) ou descrição parecida."""
    if (x.quantidade is None) != (y.quantidade is None):
        return False
    if x.quantidade is not None and not iguais_no_centavo(x.quantidade, y.quantidade):
        return False
    if x.codigo and y.codigo:
        return normalizar_codigo_item(x.codigo) == normalizar_codigo_item(y.codigo)
    if _palavras(x.descricao) == _palavras(y.descricao):
        return True
    return not exata and descricoes_equivalentes(x.descricao, y.descricao)


def _palavras(descricao: str) -> list[str]:
    return sorted(re.findall(r"[A-Z0-9]+", sem_acento(descricao).upper()))


def _totais(f: Fonte) -> tuple:
    return f.doc.peso_bruto_total, f.doc.peso_liquido_total, f.doc.volumes_total


def _diferencas(melhor: Fonte, outra: Fonte) -> str:
    """' com outro número (A-9)' e/ou ' com totais diferentes (…)', para o usuário saber que as versões não batem."""
    numeros = melhor.doc.numero, outra.doc.numero
    mudou = all(numeros) and numero_normalizado(numeros[0]) != numero_normalizado(numeros[1])
    return (f" com outro número ({outra.doc.numero})" if mudou else "") + _totais_diferentes(melhor, outra)


def _totais_diferentes(melhor: Fonte, outra: Fonte) -> str:
    """' com totais diferentes (peso bruto 326 KG × 330 KG)', se os totais não batem."""
    nomes = ("peso bruto", "peso líquido", "volumes")
    difs = [
        f"{nome} {x.valor:g} {x.unidade} × {y.valor:g} {y.unidade}"
        for nome, x, y in zip(nomes, _totais(melhor), _totais(outra))
        if x and y and not iguais_no_centavo(x.valor, y.valor)
    ]
    return f" com totais diferentes ({'; '.join(difs)})" if difs else ""


def _descrever(f: Fonte) -> str:
    """'BL.pdf (original, pág. 1)': o arquivo, com a versão quando a leitura a identificou."""
    paginas = ", ".join(str(p) for p in f.doc.paginas)
    partes = [NOME_VERSAO.get(f.doc.versao, ""), f"pág. {paginas}" if paginas else ""]
    detalhe = ", ".join(p for p in partes if p)
    return f"{f.arquivo.nome} ({detalhe})" if detalhe else f.arquivo.nome


NOME_VERSAO = {"original": "original", "copia": "cópia", "draft": "rascunho"}
MOTIVOS = (
    "porque o outro é proforma",
    "pela versão lida no documento",
    "pelo nome do arquivo (original × rascunho ou cópia)",
    "por ser a revisão mais nova pelo nome do arquivo",
    "por ser o PDF (vale mais que Excel ou Word)",
    "por trazer o número",
    "por ser o último enviado",
)


def _motivo(melhor: Fonte, outra: Fonte) -> str:
    """O primeiro critério de `_preferencia` em que o usado vence o ignorado."""
    pares = zip(_preferencia(melhor), _preferencia(outra))
    return next((m for m, (a, b) in zip(MOTIVOS, pares) if a != b), MOTIVOS[-1])


def _onde(f: Fonte) -> str:
    paginas = ", ".join(str(p) for p in f.doc.paginas)
    return f"{f.arquivo.nome}, pág. {paginas}" if paginas else f.arquivo.nome
