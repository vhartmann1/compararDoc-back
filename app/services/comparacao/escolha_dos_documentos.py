"""Escolha dos documentos: tira proformas e resumos da soma e, entre duplicatas, fica a melhor versão."""

import re
from dataclasses import dataclass

from app.schemas import ArquivoEntrada, ExtracaoArquivo, ItemExtraido, TipoDocumento
from app.services.comparacao.constantes import NOME_TIPO, PRIORIDADE_FORMATO, PRIORIDADE_VERSAO, TIPOS
from app.services.comparacao.identificacao_do_documento import PROFORMA, e_proforma, nome_doc, numero_normalizado
from app.services.comparacao.normalizacao import (
    descricoes_equivalentes,
    normalizar_codigo_item,
    numero_sem_serie,
    sem_acento,
)
from app.services.comparacao.tipos import Fonte


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
                por_tipo[doc.tipo].append(Fonte(arquivo, doc, (i, j)))
        if extracao.documentos and all(d.tipo not in por_tipo for d in extracao.documentos):
            lidos = ", ".join(dict.fromkeys(d.subtipo or "documento de outro tipo" for d in extracao.documentos))
            avisos.append(f"{arquivo.nome} não entrou na comparação: não é invoice, packing list nem conhecimento ({lidos}).")
    comerciais, proformas = _separar_proformas(por_tipo["invoice"], avisos)
    por_tipo["invoice"], resumos = _separar_resumos(comerciais, avisos)
    fora_da_soma = [max(g, key=_preferencia) for g in _grupos_de_duplicatas(proformas + resumos)]
    return DocumentosEscolhidos(_melhores_versoes(por_tipo, avisos), fora_da_soma)


def _melhores_versoes(
    por_tipo: dict[TipoDocumento, list[Fonte]], avisos: list[str]
) -> dict[TipoDocumento, list[Fonte]]:
    """Entre duplicatas do mesmo documento fica a melhor versão; as outras viram `duplicatas` dela."""
    escolhidos: dict[TipoDocumento, list[Fonte]] = {}
    for tipo, fontes in por_tipo.items():
        if not fontes:
            avisos.append(f"Documento não encontrado nos arquivos enviados: {NOME_TIPO[tipo]}.")
        escolhidos[tipo] = []
        for mesmas in _grupos_de_duplicatas(fontes):
            melhor, *ignorados = sorted(mesmas, key=_preferencia, reverse=True)
            melhor.duplicatas = ignorados
            escolhidos[tipo].append(melhor)
            if ignorados:
                avisos.append(
                    f"Mais de um documento {nome_doc(melhor)}; usado {_descrever(melhor)}. "
                    f"Ignorado(s): {'; '.join(_descrever(f) + _totais_diferentes(melhor, f) for f in ignorados)}."
                )
        escolhidos[tipo].sort(key=lambda f: f.ordem)
    return escolhidos


def _grupos_de_duplicatas(fontes: list[Fonte]) -> list[list[Fonte]]:
    grupos: list[list[Fonte]] = []
    for f in fontes:
        grupo = next((g for g in grupos if _mesmo_documento(g[0], f)), None)
        if grupo:
            grupo.append(f)
        else:
            grupos.append([f])
    return grupos


def _separar_proformas(invoices: list[Fonte], avisos: list[str]) -> tuple[list[Fonte], list[Fonte]]:
    """Proforma (lida como tal, ex. uma aba do Excel) sai quando há invoice comercial: é o pedido, não o embarque."""
    proformas = [f for f in invoices if e_proforma(f.doc)]
    comerciais = [f for f in invoices if f not in proformas]
    if not comerciais:
        return invoices, []
    for f in proformas:
        avisos.append(f"{nome_doc(f)} ({_onde(f)}) não entrou na comparação: há invoice comercial.")
    return comerciais, proformas


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
    """Mesmo documento => fica 1: não proforma, versão lida, nome (rascunho/original, revisão), PDF, último."""
    return (
        not PROFORMA.search(f.arquivo.nome),  # proforma com o número da invoice nunca vale mais que ela
        PRIORIDADE_VERSAO[f.doc.versao],
        versao_pelo_nome(f.arquivo.nome),
        revisao_pelo_nome(f.arquivo.nome),
        PRIORIDADE_FORMATO.get(f.arquivo.media_type, 0),
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


def _mesmo_documento(a: Fonte, b: Fonte) -> bool:
    """Mesmo número; sem número, os mesmos totais ou, em arquivos diferentes, a mesma invoice e os mesmos itens."""
    na, nb = numero_normalizado(a.doc.numero), numero_normalizado(b.doc.numero)
    if na and nb:
        return na == nb
    ra = {numero_normalizado(n) for n in a.doc.invoices_referenciadas}
    rb = {numero_normalizado(n) for n in b.doc.invoices_referenciadas}
    if ra and rb and ra != rb:
        return False
    if ra and ra == rb and a.ordem[0] != b.ordem[0] and _mesmos_itens(a, b):
        return True  # rascunho em Word e versão final em PDF: os totais podem ter mudado
    return _mesmos_totais(a, b)


def _mesmos_totais(a: Fonte, b: Fonte) -> bool:
    pares = [(x.valor, y.valor) for x, y in zip(_totais(a), _totais(b)) if x and y]
    return len(pares) >= 2 and all(abs(x - y) < 1e-6 for x, y in pares)


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
    if x.quantidade != y.quantidade:
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


def _totais_diferentes(melhor: Fonte, outra: Fonte) -> str:
    """' com totais diferentes (peso bruto 326 KG × 330 KG)', se os totais não batem."""
    nomes = ("peso bruto", "peso líquido", "volumes")
    difs = [
        f"{nome} {x.valor:g} {x.unidade} × {y.valor:g} {y.unidade}"
        for nome, x, y in zip(nomes, _totais(melhor), _totais(outra))
        if x and y and abs(x.valor - y.valor) > 1e-6
    ]
    return f" com totais diferentes ({'; '.join(difs)})" if difs else ""


def _descrever(f: Fonte) -> str:
    return f"{f.doc.versao} ({_onde(f)})"


def _onde(f: Fonte) -> str:
    paginas = ", ".join(str(p) for p in f.doc.paginas)
    return f"{f.arquivo.nome}, pág. {paginas}" if paginas else f.arquivo.nome
