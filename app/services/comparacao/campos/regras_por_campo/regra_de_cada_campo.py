"""Qual regra vale para cada campo."""

from app.schemas import NomeCampo
from app.services.comparacao.campos.chegada_por_dta import separar_chegada_por_dta
from app.services.comparacao.campos.regras_por_campo.endereco_pais_moeda_incoterm import (
    juntar_enderecos,
    listas_de_enderecos_iguais,
    obter_endereco,
    obter_incoterm,
    obter_moeda,
    obter_pais,
    paises_do_exportador_iguais,
)
from app.services.comparacao.campos.regras_por_campo.exportador_consignatario import (
    juntar_partes,
    listas_de_partes_iguais,
    obter_parte,
    texto_do_consignatario,
)
from app.services.comparacao.campos.regras_por_campo.ncm_invoice_po_portos import (
    colunas_com_pl_em_outra_numeracao,
    comparador_de_ncm,
    juntar_ncm,
    juntar_porto,
    ncms_contidos,
    numeros_contidos,
    numeros_iguais,
    obter_ncm,
    obter_numero_invoice,
    obter_po,
    obter_porto,
    portos_iguais,
)
from app.services.comparacao.campos.regras_por_campo.pesos_volumes_quantidade import (
    embalagens_incomparaveis,
    obter_peso,
    obter_quantidade,
    obter_volumes,
    pesos_iguais,
    quantidades_iguais,
    somar_peso,
    somar_quantidade,
    somar_volumes,
    texto_da_quantidade,
    unidades_incomparaveis,
)
from app.services.comparacao.campos.regras_por_campo.regra import Regra, conjuntos_iguais, juntar_conjunto
from app.services.comparacao.partes.consignatario_pela_modalidade import separar_conhecimentos_da_capital
from app.services.comparacao.partes.endereco_do_consignatario import avisos_de_endereco

REGRAS: dict[NomeCampo, Regra] = {
    "peso_liquido": Regra(obter_peso, somar_peso, pesos_iguais),
    "peso_bruto": Regra(obter_peso, somar_peso, pesos_iguais),
    "volumes": Regra(
        obter_volumes, somar_volumes, lambda a, b: abs(a - b) < 1e-6, incomparavel_nos_grupos=embalagens_incomparaveis
    ),
    "quantidade": Regra(
        obter_quantidade, somar_quantidade, quantidades_iguais,
        incomparavel=unidades_incomparaveis, texto_da_divergencia=texto_da_quantidade,
    ),
    "ncm": Regra(
        obter_ncm, juntar_ncm, lambda a, b: set(a) == set(b), contido_no_outro=ncms_contidos,
        comparador=comparador_de_ncm,
    ),
    "numero_invoice": Regra(
        obter_numero_invoice, juntar_conjunto, numeros_iguais, vazio_em=colunas_com_pl_em_outra_numeracao
    ),
    "po": Regra(obter_po, juntar_conjunto, numeros_iguais, contido_no_outro=numeros_contidos),
    "incoterm": Regra(obter_incoterm, juntar_conjunto, conjuntos_iguais),
    "moeda": Regra(obter_moeda, juntar_conjunto, conjuntos_iguais),
    "exportador": Regra(obter_parte, juntar_partes, listas_de_partes_iguais, soma_alternativas=True),
    "endereco_exportador": Regra(obter_endereco, juntar_enderecos, listas_de_enderecos_iguais, soma_alternativas=True),
    "pais_exportador": Regra(obter_pais, juntar_conjunto, paises_do_exportador_iguais, soma_alternativas=True),
    "consignatario": Regra(
        obter_parte, juntar_partes, listas_de_partes_iguais, separar_aceitos=separar_conhecimentos_da_capital,
        texto_da_divergencia=texto_do_consignatario, avisos_da_comparacao=avisos_de_endereco,
    ),
    "pais_origem": Regra(obter_pais, juntar_conjunto, conjuntos_iguais),
    "porto_origem": Regra(obter_porto, juntar_porto, portos_iguais, conhecimento_e_referencia=True),
    "porto_destino": Regra(
        obter_porto, juntar_porto, portos_iguais, conhecimento_e_referencia=True,
        separar_aceitos=separar_chegada_por_dta,
    ),
}
