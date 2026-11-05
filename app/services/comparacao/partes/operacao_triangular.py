"""Operação triangular: shipper do conhecimento de outra empresa que o exportador da invoice/PL."""

from dataclasses import dataclass

from app.schemas import NomeCampo, Parte
from app.services.comparacao.campos.regras_por_campo.exportador_consignatario import fabricante_alternativo
from app.services.comparacao.documentos.identificacao_do_documento import nome_doc
from app.services.comparacao.mensagens import Diferenca, pedido, trecho
from app.services.comparacao.normalizacao.enderecos import enderecos_de_texto_parecido
from app.services.comparacao.partes.mesma_empresa import relacao_entre_partes
from app.services.comparacao.partes.parte_preenchida import parte_preenchida
from app.services.comparacao.partes.razao_social import palavras_distintivas
from app.services.comparacao.tipos import Col, Fonte, Valor

CAMPOS_DO_EXPORTADOR: set[NomeCampo] = {"exportador", "endereco_exportador", "pais_exportador"}

DE_QUEM = {"invoice": ("da invoice", "das invoices"), "packing_list": ("do packing list", "dos packing lists")}


@dataclass
class Triangulacao:
    conhecimento: Col
    shipper: Parte
    outras: list[Fonte]  # invoice/PL de outra empresa: só aviso
    proprias: list[Fonte]  # invoice/PL da mesma empresa (ou incerta): comparadas com o conhecimento


def triangulacoes(colunas: list[Col]) -> list[Triangulacao]:
    """Conhecimentos cujo shipper é outra empresa que o exportador de alguma invoice/PL da comparação."""
    referencias = [f for col in colunas if not col.so_conhecimento() for f in col.fontes]
    resultado = []
    for col in colunas:
        shipper = col.fontes[0].doc.exportador if col.so_conhecimento() else None
        if not parte_preenchida(shipper):
            continue
        proprias, outras = separar_por_empresa(shipper, referencias)
        if outras:
            resultado.append(Triangulacao(col, shipper, outras, proprias))
    return resultado


def separar_por_empresa(shipper: Parte, fontes: list[Fonte]) -> tuple[list[Fonte], list[Fonte]]:
    """(da mesma empresa do shipper ou incertas, de outra empresa)."""
    proprias: list[Fonte] = []
    outras: list[Fonte] = []
    for f in fontes:
        (outras if _de_outra_empresa(shipper, f) else proprias).append(f)
    return proprias, outras


def _partes_do_exportador(f: Fonte) -> list[Parte]:
    return [p for p in (f.doc.exportador, fabricante_alternativo(f)) if parte_preenchida(p)]


def _de_outra_empresa(shipper: Parte, f: Fonte) -> bool:
    """Outra empresa só com o endereço do shipper no conhecimento, diferente do exportador e do fabricante."""
    partes = _partes_do_exportador(f)
    if not partes or not _tem_endereco(shipper):
        return False
    return all(relacao_entre_partes(shipper, p) == "outra" and not _endereco_de_texto_parecido(shipper, p) for p in partes)


def _tem_endereco(parte: Parte) -> bool:
    return bool(parte.endereco and parte.endereco.strip())


def _endereco_de_texto_parecido(a: Parte, b: Parte) -> bool:
    if not (_tem_endereco(a) and _tem_endereco(b)):
        return False
    return enderecos_de_texto_parecido((a.endereco.strip(), a.cidade), (b.endereco.strip(), b.cidade))


def aviso_triangular(prefixo: str, t: Triangulacao) -> str:
    exportadores = " / ".join(dict.fromkeys(_nome_do_exportador(f) for f in t.outras))
    return (f"{prefixo}Shipper do {t.conhecimento.nome_curto} ({t.shipper.nome.strip()}) é outra empresa que o "
            f"exportador {_de_quem(t.outras)} ({exportadores}): operação triangular, não é divergência.")


def _nome_do_exportador(f: Fonte) -> str:
    """O exportador; sem nome, o fabricante; sem nenhum dos dois, o próprio documento."""
    partes = _partes_do_exportador(f)
    return partes[0].nome.strip() if partes else nome_doc(f)


def _de_quem(fontes: list[Fonte]) -> str:
    tipos = dict.fromkeys(f.doc.tipo for f in fontes)
    return " e ".join(DE_QUEM[t][sum(f.doc.tipo == t for f in fontes) > 1] for t in tipos)


def coluna_das_proprias(t: Triangulacao) -> Col:
    """As invoices/PLs da mesma empresa do shipper, como coluna (só dado: rótulo e fontes)."""
    curto = "/".join(dict.fromkeys(nome_doc(f) for f in t.proprias))
    return Col(f"proprias_{t.conhecimento.chave}", curto, curto, t.proprias, soma=len(t.proprias) > 1)


def da_mesma_empresa(t: Triangulacao) -> list[Fonte]:
    """Das próprias, as que são com certeza da empresa do shipper (as incertas ficam de fora)."""
    return [f for f in t.proprias
            if any(relacao_entre_partes(t.shipper, p) == "mesma" for p in _partes_do_exportador(f))]


def empresa_do_shipper(t: Triangulacao) -> str:
    """O nome do shipper pelas palavras que o distinguem, para pôr ao lado do rótulo."""
    return " ".join(palavras_distintivas(t.shipper.nome)) or t.shipper.nome.strip()


def texto_contra_as_proprias(
    t: Triangulacao, conhecimento: Valor, lados: list[tuple[Fonte, Valor]], cortar: bool
) -> Diferenca:
    """BL 'X…' × Invoice 1 'Y…', pedindo correção. Só o endereço é cortado."""
    def mostrar(v: Valor, outro: Valor) -> str:
        return trecho(v.exibicao, outro.exibicao) if cortar else v.exibicao

    partes = [f"{t.conhecimento.nome_curto} '{mostrar(conhecimento, lados[0][1])}'"]
    partes += [f"{nome_doc(f)} '{mostrar(v, conhecimento)}'" for f, v in lados]
    return pedido(" × ".join(partes), "correção")
