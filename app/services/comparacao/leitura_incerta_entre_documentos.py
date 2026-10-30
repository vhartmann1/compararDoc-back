"""Nº da invoice e PO quase iguais entre documentos, com um lado escaneado: pode ser leitura do scan, é aviso."""

from app.schemas import NomeCampo
from app.services.comparacao.constantes import ROTULOS
from app.services.comparacao.normalizacao import mesmo_numero, numeros_quase_iguais
from app.services.comparacao.tipos import Col, Contexto, Valor

# CNPJ e NCM ficam fora: nos processos reais há erros de verdade com 1 dígito trocado e um lado escaneado.
CAMPOS_COM_LEITURA_INCERTA: set[NomeCampo] = {"numero_invoice", "po"}


def aviso_de_leitura_incerta(ctx: Contexto, campo: NomeCampo, grupos: list[tuple[list[Col], Valor]]) -> str | None:
    """Dois grupos que diferem por um número com até 2 caracteres trocados e algum documento escaneado."""
    if campo not in CAMPOS_COM_LEITURA_INCERTA or len(grupos) != 2:
        return None
    (_, a), (_, b) = grupos
    escaneadas = [c for cols, _ in grupos for c in cols if any(f.escaneado is True for f in c.fontes)]
    if not escaneadas or not codigos_quase_iguais(a.chave, b.chave):
        return None
    lados = " × ".join(f"{'/'.join(c.nome_curto for c in cols)} {v.exibicao}"
                       for cols, v in sorted(grupos, key=lambda g: len(g[0])))
    nomes = " e ".join(c.nome_curto for c in escaneadas)
    escaneado = "escaneado" if len(escaneadas) == 1 else "escaneados"
    return f"{ctx.prefixo}{ROTULOS[campo]}: {lados}; {nomes} {escaneado}, pode ser leitura — conferir na imagem."


def codigos_quase_iguais(a: frozenset[str], b: frozenset[str]) -> bool:
    """Sobra exatamente um número de cada lado, e os dois diferem por até 2 caracteres."""
    sobra_a = [x for x in a if not any(mesmo_numero(x, y) for y in b)]
    sobra_b = [y for y in b if not any(mesmo_numero(y, x) for x in a)]
    return len(sobra_a) == len(sobra_b) == 1 and numeros_quase_iguais(sobra_a[0], sobra_b[0])
