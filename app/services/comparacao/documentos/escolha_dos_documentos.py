"""Escolha dos documentos: tira proformas e resumos da soma e, entre duplicatas, fica a melhor versão."""

from dataclasses import dataclass

from app.schemas import ArquivoEntrada, ExtracaoArquivo, TipoDocumento
from app.services.comparacao.constantes import NOME_TIPO, TIPOS
from app.services.comparacao.documentos.duplicatas import grupos_de_duplicatas, totais
from app.services.comparacao.documentos.fora_da_comparacao import (
    aviso_de_outro_tipo,
    sem_conhecimentos_de_saida,
    separar_proformas,
    separar_resumos,
)
from app.services.comparacao.documentos.identificacao_do_documento import nome_doc, numero_normalizado
from app.services.comparacao.documentos.paginas_juntadas import juntar_paginas
from app.services.comparacao.documentos.pl_da_versao_ignorada import sem_pls_das_versoes_ignoradas
from app.services.comparacao.documentos.preferencia_entre_versoes import motivo, preferencia
from app.services.comparacao.normalizacao.dinheiro import iguais_no_centavo
from app.services.comparacao.tipos import Fonte


@dataclass
class DocumentosEscolhidos:
    por_tipo: dict[TipoDocumento, list[Fonte]]
    fora_da_soma: list[Fonte]  # proformas e resumos: não entram na comparação, mas são conferidos por dentro
    avisos: list[str]


def escolher_documentos(extracoes: list[tuple[ArquivoEntrada, ExtracaoArquivo]]) -> DocumentosEscolhidos:
    por_tipo, de_outro_tipo = _separar_por_tipo(extracoes)
    saida = sem_conhecimentos_de_saida(por_tipo["conhecimento"])
    por_tipo["conhecimento"] = saida.ficam
    citados = _invoices_citadas(por_tipo)
    proformas = separar_proformas(por_tipo["invoice"])
    resumos = separar_resumos(proformas.ficam)
    por_tipo["invoice"] = resumos.ficam
    fora_da_soma = [max(g, key=preferencia) for g in grupos_de_duplicatas(proformas.saem + resumos.saem, citados)]
    escolhidos, das_versoes = _melhores_versoes(por_tipo, citados)
    pls = sem_pls_das_versoes_ignoradas(escolhidos["invoice"], escolhidos["packing_list"])
    escolhidos["packing_list"] = pls.ficam
    avisos = de_outro_tipo + saida.avisos + proformas.avisos + resumos.avisos + das_versoes + pls.avisos
    return DocumentosEscolhidos(escolhidos, fora_da_soma, avisos)


def _separar_por_tipo(
    extracoes: list[tuple[ArquivoEntrada, ExtracaoArquivo]],
) -> tuple[dict[TipoDocumento, list[Fonte]], list[str]]:
    """Os documentos de cada tipo, na ordem de envio, e o aviso de cada arquivo que não tem nenhum deles."""
    por_tipo: dict[TipoDocumento, list[Fonte]] = {tipo: [] for tipo in TIPOS}
    for i, (arquivo, extracao) in enumerate(extracoes):
        for j, doc in enumerate(extracao.documentos):
            if doc.tipo in por_tipo:
                por_tipo[doc.tipo].append(Fonte(arquivo, doc, (i, j), escaneado=extracao.escaneado))
    avisos = [a for arquivo, extracao in extracoes if (a := aviso_de_outro_tipo(arquivo, extracao))]
    return por_tipo, avisos


def _invoices_citadas(por_tipo: dict[TipoDocumento, list[Fonte]]) -> set[str]:
    return {numero_normalizado(n) for fontes in por_tipo.values() for f in fontes for n in f.doc.invoices_referenciadas}


def _melhores_versoes(
    por_tipo: dict[TipoDocumento, list[Fonte]], citados: set[str]
) -> tuple[dict[TipoDocumento, list[Fonte]], list[str]]:
    """Entre duplicatas do mesmo documento fica a melhor versão; as outras viram `duplicatas` dela."""
    escolhidos: dict[TipoDocumento, list[Fonte]] = {}
    avisos: list[str] = []
    for tipo, fontes in por_tipo.items():
        if not fontes:
            avisos.append(f"Documento não encontrado nos arquivos enviados: {NOME_TIPO[tipo]}.")
        escolhidos[tipo] = []
        for grupo in grupos_de_duplicatas(fontes, citados):
            mesmas, juntadas = juntar_paginas(grupo)
            melhor, aviso = _melhor_versao(mesmas)
            escolhidos[tipo].append(melhor)
            avisos.extend(juntadas + ([aviso] if aviso else []))
        escolhidos[tipo].sort(key=lambda f: f.ordem)
    return escolhidos, avisos


def _melhor_versao(mesmas: list[Fonte]) -> tuple[Fonte, str | None]:
    """A versão usada, com as outras em `duplicatas`, e o aviso que diz por que ela foi a escolhida."""
    melhor, *ignorados = sorted(mesmas, key=preferencia, reverse=True)
    melhor.duplicatas = ignorados
    if not ignorados:
        return melhor, None
    return melhor, (
        f"Mais de um documento {nome_doc(melhor)}; usado {_descrever(melhor)}, "
        f"{motivo(melhor, ignorados[0])}. "
        f"Ignorado(s): {'; '.join(_descrever(f) + _diferencas(melhor, f) for f in ignorados)}."
    )


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
        for nome, x, y in zip(nomes, totais(melhor), totais(outra))
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
