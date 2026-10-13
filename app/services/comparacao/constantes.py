"""Constantes das regras de comparação."""

from app.schemas import NomeCampo, TipoDocumento

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


TAMANHO_CABECA_DESCRICAO = 24
