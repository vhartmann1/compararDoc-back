"""Escolha dos documentos: entre duplicatas do mesmo número, fica a melhor versão."""

from app.schemas import ArquivoEntrada, ExtracaoArquivo, TipoDocumento
from app.services.comparacao.constantes import NOME_TIPO, PRIORIDADE_VERSAO, TIPOS
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

    escolhidos: dict[TipoDocumento, list[Fonte]] = {}
    for tipo, fontes in por_tipo.items():
        if not fontes:
            avisos.append(f"Documento não encontrado nos arquivos enviados: {NOME_TIPO[tipo]}.")
        # mesmo tipo e mesmo número => fica 1: original > copia > draft > desconhecida; empate => último enviado
        por_numero: dict[str, list[Fonte]] = {}
        for f in fontes:
            por_numero.setdefault(numero_normalizado(f.doc.numero), []).append(f)
        escolhidos[tipo] = []
        for mesmas in por_numero.values():
            melhor = max(mesmas, key=lambda f: (PRIORIDADE_VERSAO[f.doc.versao], f.ordem))
            escolhidos[tipo].append(melhor)
            ignorados = [f for f in mesmas if f is not melhor]
            if ignorados:
                avisos.append(
                    f"Mais de um documento {nome_doc(melhor)}; usado {_descrever(melhor)}. "
                    f"Ignorado(s): {'; '.join(_descrever(f) for f in ignorados)}."
                )
        escolhidos[tipo].sort(key=lambda f: f.ordem)
    return escolhidos


def _descrever(f: Fonte) -> str:
    paginas = ", ".join(str(p) for p in f.doc.paginas)
    onde = f"{f.arquivo.nome}, pág. {paginas}" if paginas else f.arquivo.nome
    return f"{f.doc.versao} ({onde})"
