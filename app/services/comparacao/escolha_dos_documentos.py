"""Escolha dos documentos: entre duplicatas do mesmo número, fica a melhor versão."""

import re

from app.schemas import ArquivoEntrada, ExtracaoArquivo, TipoDocumento
from app.services.comparacao.constantes import NOME_TIPO, PRIORIDADE_FORMATO, PRIORIDADE_VERSAO, TIPOS
from app.services.comparacao.identificacao_do_documento import nome_doc, numero_normalizado
from app.services.comparacao.tipos import Fonte


def escolher_documentos(
    extracoes: list[tuple[ArquivoEntrada, ExtracaoArquivo]], avisos: list[str]
) -> dict[TipoDocumento, list[Fonte]]:
    por_tipo: dict[TipoDocumento, list[Fonte]] = {tipo: [] for tipo in TIPOS}
    for i, (arquivo, extracao) in enumerate(extracoes):
        for j, doc in enumerate(extracao.documentos):
            if doc.tipo in por_tipo:
                por_tipo[doc.tipo].append(Fonte(arquivo, doc, (i, j)))
        if extracao.documentos and all(d.tipo not in por_tipo for d in extracao.documentos):
            lidos = ", ".join(dict.fromkeys(d.subtipo or "documento de outro tipo" for d in extracao.documentos))
            avisos.append(f"{arquivo.nome} não entrou na comparação: não é invoice, packing list nem conhecimento ({lidos}).")

    escolhidos: dict[TipoDocumento, list[Fonte]] = {}
    for tipo, fontes in por_tipo.items():
        if not fontes:
            avisos.append(f"Documento não encontrado nos arquivos enviados: {NOME_TIPO[tipo]}.")
        grupos: list[list[Fonte]] = []
        for f in fontes:
            grupo = next((g for g in grupos if _mesmo_documento(g[0], f)), None)
            if grupo:
                grupo.append(f)
            else:
                grupos.append([f])
        escolhidos[tipo] = []
        for mesmas in grupos:
            melhor, *ignorados = sorted(mesmas, key=_preferencia, reverse=True)
            melhor.duplicatas = ignorados
            escolhidos[tipo].append(melhor)
            if ignorados:
                avisos.append(
                    f"Mais de um documento {nome_doc(melhor)}; usado {_descrever(melhor)}. "
                    f"Ignorado(s): {'; '.join(_descrever(f) for f in ignorados)}."
                )
        escolhidos[tipo].sort(key=lambda f: f.ordem)
    return escolhidos


def _preferencia(f: Fonte) -> tuple:
    """Mesmo documento => fica 1: não proforma, versão, revisão mais nova pelo nome, PDF antes de Excel/Word, último enviado."""
    return (
        not PROFORMA.search(f.arquivo.nome),  # proforma com o número da invoice nunca vale mais que ela
        PRIORIDADE_VERSAO[f.doc.versao],
        revisao_pelo_nome(f.arquivo.nome),
        PRIORIDADE_FORMATO.get(f.arquivo.media_type, 0),
        f.ordem,
    )


PROFORMA = re.compile(r"(?i)pro[\s_-]?forma")
REVISAO = re.compile(r"(?i)(?<![A-Z])(rev(?:is(?:ed|ad[oa]|ao|ão))?|ajustad[oa]|corrigid[oa]|final(?:is)?)(?![A-Z])[\s._-]*(\d+)?")


def revisao_pelo_nome(nome: str) -> tuple[int, int]:
    """'CI REV-1.pdf' > 'CI.pdf'; 'PL REV.2' > 'PL REV.1': o nome do arquivo é o que diz qual versão é a mais nova."""
    marcas = REVISAO.findall(nome)
    return (1, max(int(n or 0) for _, n in marcas)) if marcas else (0, 0)


def _mesmo_documento(a: Fonte, b: Fonte) -> bool:
    """Mesmo número; se um deles não tem número, os mesmos totais."""
    na, nb = numero_normalizado(a.doc.numero), numero_normalizado(b.doc.numero)
    if na and nb:
        return na == nb
    ra = {numero_normalizado(n) for n in a.doc.invoices_referenciadas}
    rb = {numero_normalizado(n) for n in b.doc.invoices_referenciadas}
    if ra and rb and ra != rb:
        return False
    pares = [(x.valor, y.valor) for x, y in zip(_totais(a), _totais(b)) if x and y]
    return len(pares) >= 2 and all(abs(x - y) < 1e-6 for x, y in pares)


def _totais(f: Fonte) -> tuple:
    return f.doc.peso_bruto_total, f.doc.peso_liquido_total, f.doc.volumes_total


def _descrever(f: Fonte) -> str:
    paginas = ", ".join(str(p) for p in f.doc.paginas)
    onde = f"{f.arquivo.nome}, pág. {paginas}" if paginas else f.arquivo.nome
    return f"{f.doc.versao} ({onde})"
