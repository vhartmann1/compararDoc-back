"""Constantes das regras de comparação."""

from app.schemas import NomeCampo, TipoDocumento
from app.tipos_de_arquivo import MEDIA_DOCX, MEDIA_PDF, MEDIA_XLS, MEDIA_XLSX

# Até 0,5 kg (inclusive) de diferença não é divergência; mudou a regra, atualize o contrato e os testes.
TOLERANCIA_PESO_KG = 0.5

TIPOS: list[TipoDocumento] = ["invoice", "packing_list", "conhecimento"]

NOME_TIPO: dict[TipoDocumento, str] = {
    "invoice": "Invoice",
    "packing_list": "Packing List",
    "conhecimento": "Conhecimento (BL/AWB/CRT)",
}

PRIORIDADE_VERSAO = {"original": 3, "copia": 2, "draft": 1, "desconhecida": 0}

# Mesmo documento em dois formatos: vale o PDF emitido, que em tese não foi editado; Excel/Word só completam
PRIORIDADE_FORMATO = {MEDIA_PDF: 2, MEDIA_XLSX: 1, MEDIA_XLS: 1, MEDIA_DOCX: 1}
MEDIAS_DE_ESCRITORIO = (MEDIA_XLSX, MEDIA_XLS, MEDIA_DOCX)  # planilha ou Word: perde para o PDF do mesmo documento

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
    "adquirente": "Adquirente",
    "pais_origem": "País de origem",
    "porto_origem": "Porto de origem",
    "porto_destino": "Porto de destino",
}

CAMPOS_SEMPRE_VISIVEIS: set[NomeCampo] = {"peso_liquido", "peso_bruto", "ncm"}
# No conhecimento a moeda é a do frete, não a da mercadoria: não entra na comparação
CAMPOS_FORA_DO_CONHECIMENTO: set[NomeCampo] = {"moeda"}

CAMPOS_SOMADOS: set[NomeCampo] = {"peso_liquido", "peso_bruto", "volumes", "quantidade"}

# Em conta e ordem ou encomenda, a Capital Trade pode ser a consignatária no conhecimento.
MODALIDADES_CAPITAL_CONSIGNATARIA: set[str] = {"conta_e_ordem", "encomenda"}

CNPJ_RAIZ_CAPITAL = "07872326"  # Capital Trade Importação e Exportação Ltda. (qualquer filial)

# Campos em que invoices somadas com valores diferentes merecem aviso.
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

# Incoterms E/F: frete do comprador (COLLECT, origem); C/D: frete do vendedor (PREPAID, destino).
INCOTERMS_EF = {"EXW", "FCA", "FAS", "FOB"}

INCOTERMS_CD = {"CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP", "DAT"}

TAMANHO_MAX_DESCRICAO = 60

TAMANHO_CABECA_DESCRICAO = 24
