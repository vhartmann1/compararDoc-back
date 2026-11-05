"""Tipos compartilhados do backend. Espelha docs/CONTRATO_API.md — mudou aqui, muda lá e no front."""

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema

StatusProcessamento = Literal["PROCESSANDO", "CONCLUIDA", "ERRO"]
Etapa = Literal["RECEBIDO", "LENDO_DOCUMENTOS", "COMPARANDO", "FINALIZADO"]
StatusResultado = Literal["OK", "DIVERGENTE", "INCOMPLETO"]
# Filtro da listagem: resultado das concluídas, ou o andamento das que não concluíram.
FiltroLista = Literal["TODAS", "OK", "DIVERGENTE", "INCOMPLETO", "PROCESSANDO", "ERRO"]
StatusCampo = Literal["OK", "DIVERGENTE", "NAO_ENCONTRADO", "INSUFICIENTE"]
# conhecimento = BL (marítimo), AWB (aéreo) ou CRT (rodoviário)
TipoDocumento = Literal["invoice", "packing_list", "conhecimento"]
NomeCampo = Literal[
    "peso_liquido",
    "peso_bruto",
    "volumes",
    "quantidade",
    "ncm",
    "numero_invoice",
    "po",
    "exportador",
    "consignatario",
    "porto_origem",
    "porto_destino",
    "endereco_exportador",
    "pais_exportador",
    "pais_origem",
    "incoterm",
    "moeda",
    "adquirente",
]
# comparacao = campo cruzado entre documentos; coerencia = regra de negócio (ex.: incoterm × frete);
# interna = contradição dentro de um mesmo documento; item = linha de mercadoria
CategoriaDivergencia = Literal["comparacao", "coerencia", "interna", "item"]
Versao = Literal["original", "draft", "copia", "desconhecida"]
# Modalidade da importação: em conta e ordem / encomenda a Capital Trade pode ser a consignatária no conhecimento.
Modalidade = Literal["propria", "conta_e_ordem", "encomenda"]
UnidadePeso = Literal["KG", "LB", "MT", "TON", "G", "OUTRA"]


# ---------------------------------------------------------------------------
# Extração (o que o modelo devolve para cada arquivo enviado)
# ---------------------------------------------------------------------------

class Medida(BaseModel):
    valor: float = Field(description="Número já interpretado, ex. '18,452.500' -> 18452.5")
    unidade: UnidadePeso
    texto_original: str = Field(description="Texto exatamente como aparece no documento")
    pagina: int | None = Field(description="Página (1-based) onde aparece; null em Word/Excel")


class Contagem(BaseModel):
    valor: float
    unidade: str = Field(description="Como o documento chama: 'CTN', 'PALLETS', 'DRUMS', 'PAIRS', 'TON', 'BAGS'...")
    texto_original: str
    pagina: int | None


class Texto(BaseModel):
    valor: str
    pagina: int | None


class Parte(BaseModel):
    nome: str = Field(description="Razão social como aparece")
    cnpj: str | None = Field(description="CNPJ/Tax ID se aparecer junto ao nome")
    endereco: str | None = Field(description="Endereço como aparece junto ao nome (rua, cidade, região)")
    cidade: str | None = Field(
        default=None,
        description="Cidade/província/estado do endereço, ex. 'SHENZHEN', 'BAVARIA'"
    )
    pais: str | None = Field(description="País do endereço, em inglês maiúsculo, ex. 'CHINA', 'GERMANY', 'BRAZIL'")
    pagina: int | None


class ValorMonetario(BaseModel):
    valor: float = Field(description="Número já interpretado, ex. '26,130.00' -> 26130.0")
    moeda: str | None = Field(description="Código ISO da moeda desse valor, ex. 'USD'; null se não houver")
    texto_original: str = Field(description="Texto exatamente como aparece no documento")
    pagina: int | None


class Incoterm(BaseModel):
    codigo: str = Field(description="Sigla Incoterms: EXW, FCA, FAS, FOB, CFR, CIF, CPT, CIP, DAP, DPU, DDP")
    local: str | None = Field(description="Só o nome da cidade/porto que acompanha o incoterm, ex. 'SANTOS'")
    texto_original: str
    pagina: int | None


class ItemExtraido(BaseModel):
    codigo: str | None = Field(description="Código/ref do produto (product ref, item code, SKU, part number)")
    descricao: str = Field(description="Descrição do produto como aparece (inclua modelo/ref comercial)")
    referencia: str | None = Field(
        default=None,
        description="Modelo/referência comercial do produto, ex. 'LUMIPOL HD 450', 'Trail-Max 7', 'Nova-X 220'"
    )
    lotes: list[str] = Field(description="Lotes/batch numbers da linha, exatamente como aparecem")
    validades: list[str] = Field(description="Validades/expiry da linha como aparecem, ex. 'Exp 08/2027'")
    quantidade: float | None
    unidade: str | None = Field(description="Unidade da quantidade como aparece: 'PCS', 'PAIRS', 'TON', 'KG'...")
    sem_valor_comercial: bool = Field(description="Linha marcada como FOC / free of charge / no commercial value")
    valor_total: float | None = Field(description="Valor total da linha (preço × quantidade), se houver")
    peso_liquido: Medida | None = Field(default=None, description="Peso líquido da linha, se a tabela traz por linha")
    peso_bruto: Medida | None = Field(default=None, description="Peso bruto da linha, se a tabela traz por linha")
    volumes: Contagem | None = Field(default=None, description="Volumes/embalagens da linha, se a tabela traz por linha")
    pagina: int | None


class OutraDespesa(BaseModel):
    descricao: str = Field(description="Descrição da linha como aparece, ex. 'Pallets', 'Bank charges', 'Discount 3%'")
    valor: float = Field(description="Positivo para despesa, negativo para desconto, ex. 'Discount -150.00' -> -150.0")
    texto_original: str = Field(description="Texto do valor exatamente como aparece no documento")
    pagina: int | None


class InconsistenciaInterna(BaseModel):
    descricao: str = Field(
        description="Contradição objetiva DENTRO deste documento, em português, ex. "
        "'Peso líquido do rodapé (1.712,00) diferente do da linha de total (1.540,00)'"
    )
    evidencia: str = Field(description="Trechos do documento que se contradizem, citados literalmente")
    pagina: int | None


class CodigoNcm(BaseModel):
    codigo: str = Field(description="NCM ou HS Code como aparece, ex. '3901.10.10' ou 'HS 390110'")
    pagina: int | None


class DocumentoExtraido(BaseModel):
    tipo: Literal["invoice", "packing_list", "conhecimento", "outro"]
    subtipo: str | None = Field(description="Para conhecimento: 'BL', 'AWB' ou 'CRT'. Para outro: 'CO', 'DUIMP'...")
    paginas: list[int] = Field(description="Páginas (1-based) do arquivo deste documento; [] em Word/Excel")
    numero: str | None = Field(description="Número do próprio documento (nº invoice, nº PL, nº BL/AWB)")
    invoices_referenciadas: list[str] = Field(
        description="Números de invoice citados no documento (ex.: PL ou BL que mencionam 'Invoice No.')"
    )
    po: str | None = Field(description="Número do pedido do comprador (PO / Purchase Order / Your Order)")
    incoterm: Incoterm | None
    frete: Texto | None = Field(description="Pagamento do frete no documento: 'PREPAID' ou 'COLLECT' (normalize)")
    moeda: Texto | None = Field(description="Moeda dos valores, código ISO: 'USD', 'EUR', 'CNY'...")
    pais_origem: Texto | None = Field(description="País de origem da mercadoria, em inglês maiúsculo, ex. 'GERMANY'")
    emitente_assinatura: str | None = Field(
        description="Empresa que assina/carimba o documento (rodapé, assinatura), se aparecer"
    )
    empresa_cabecalho: str | None = Field(
        default=None, description="Empresa impressa no cabeçalho/papel timbrado do documento, como escrita, se houver"
    )
    versao: Versao
    exportador: Parte | None = Field(description="Shipper / exportador / vendedor")
    consignatario: Parte | None = Field(description="Consignee / importador / 'ship to' no Brasil")
    fabricante: Parte | None = Field(default=None, description="Manufacturer / Producer / Fabricante, quando o documento cita")
    adquirente: Parte | None = Field(
        default=None, description="Comprador/cliente quando é outro que não o consignatário (Buyer, Sold to, Adquirente)"
    )
    notify: Parte | None = Field(default=None, description="Notify party (no conhecimento e às vezes na invoice)")
    porto_origem: Texto | None = Field(description="Só o nome da cidade/porto/aeroporto de embarque, ex. 'NINGBO'")
    porto_destino: Texto | None = Field(
        description="Só o nome do porto/aeroporto de destino; no conhecimento, o de descarga, ex. 'PARANAGUA'"
    )
    local_entrega: Texto | None = Field(
        default=None, description="No conhecimento: Place of Delivery, só o nome da cidade/porto, ex. 'CURITIBA'"
    )
    local_recebimento: Texto | None = Field(
        default=None, description="No conhecimento: Place of Receipt, só o nome da cidade/porto, ex. 'CAMPINAS'"
    )
    pais_procedencia: Texto | None = Field(default=None, description="Country of provenance/shipment, em inglês maiúsculo")
    pais_aquisicao: Texto | None = Field(default=None, description="Country of acquisition, em inglês maiúsculo")
    modalidade_pagamento: Texto | None = Field(
        default=None, description="Condição de pagamento como escrita, ex. '30% T/T in advance, 70% against BL copy'"
    )
    valor_total: ValorMonetario | None = Field(default=None, description="Total final da invoice, na condição de venda (incoterm)")
    valor_frete: ValorMonetario | None = Field(default=None, description="Valor do frete informado no documento")
    valor_seguro: ValorMonetario | None = Field(default=None, description="Valor do seguro informado no documento")
    outras_despesas: list[OutraDespesa] = Field(
        default_factory=list,
        description="Na invoice: linhas que entram no valor_total sem ser mercadoria, frete nem seguro (embalagem, "
        "pallets, taxas, desconto); [] se não houver",
    )
    assinatura_manuscrita: bool | None = Field(
        default=None, description="Há assinatura feita à mão (não só carimbo ou nome digitado)? null se não der para ver"
    )
    embalagem_madeira: Texto | None = Field(
        default=None, description="Declaração sobre embalagem de madeira como escrita, ex. 'WOODEN PACKING: NOT APPLICABLE'"
    )
    free_time: Texto | None = Field(default=None, description="Free time informado, como escrito, ex. '14 DAYS AT DESTINATION'")
    to_order_of: bool | None = Field(
        default=None, description="No conhecimento: o consignee começa com 'TO ORDER OF' (ou 'TO THE ORDER OF')?"
    )
    peso_liquido_total: Medida | None
    peso_bruto_total: Medida | None
    volumes_total: Contagem | None = Field(description="Total de volumes/embalagens (cartons, pallets, drums...)")
    quantidade_total: Contagem | None = Field(description="Quantidade total de mercadoria (pares, peças, toneladas...)")
    ncms: list[CodigoNcm]
    itens: list[ItemExtraido] = Field(description="Linhas de mercadoria (invoice, packing list e mercadorias descritas no conhecimento); [] se não houver")
    inconsistencias_internas: list[InconsistenciaInterna] = Field(
        description="Só contradições objetivas dentro do documento; NÃO incluir dados faltando"
    )


class PaginaGirada(BaseModel):
    pagina: int = Field(description="Página (1-based) do PDF cujo texto está de lado ou de cabeça para baixo")
    graus: Literal[90, 180, 270] = Field(description="Quanto girar no sentido horário para o texto ficar na posição de leitura")


class ExtracaoArquivo(BaseModel):
    documentos: list[DocumentoExtraido]
    paginas_giradas: list[PaginaGirada] = Field(
        default_factory=list, description="Páginas escaneadas de lado ou invertidas; [] se todas estão na posição normal"
    )
    escaneado: SkipJsonSchema[bool | None] = None  # preenchido pelo código (documento_escaneado), fora do schema do modelo


# ---------------------------------------------------------------------------
# Resultado da comparação
# ---------------------------------------------------------------------------

class DocumentoRef(BaseModel):
    tipo: TipoDocumento
    subtipo: str | None
    arquivo_id: str
    arquivo_nome: str
    paginas: list[int]
    numero: str | None
    versao: Versao


class Coluna(BaseModel):
    chave: str  # ex. "invoice", "packing_list", "conhecimento", "soma_invoices"
    rotulo: str  # ex. "Invoice L30518777", "Soma das 2 invoices", "AWB 28340"
    documentos: list[DocumentoRef]  # 1 doc, ou vários quando a coluna é uma soma


class ValorCampo(BaseModel):
    exibicao: str  # pronto para a tela, ex. "21.200,00 kg", "53 CTN", "6402.19.00"
    texto_original: str | None
    arquivo_id: str | None  # None quando é soma de vários arquivos
    pagina: int | None


class CampoComparado(BaseModel):
    campo: NomeCampo
    rotulo: str  # ex. "Peso bruto"
    status: StatusCampo
    valores: dict[str, ValorCampo | None]  # chave = Coluna.chave


class Comparacao(BaseModel):
    id: str  # ex. "par-1", "consolidado"
    titulo: str  # ex. "Invoice L30518777 × Packing List L30518777"
    colunas: list[Coluna]
    campos: list[CampoComparado]


class ValorItem(BaseModel):
    descricao: str
    quantidade: str | None  # exibição, ex. "500 PCS"
    lotes: list[str]
    validades: list[str]
    arquivo_id: str
    pagina: int | None


class LinhaItem(BaseModel):
    chave: str  # código do produto ou descrição usada no casamento
    status: Literal["OK", "DIVERGENTE"]
    diferencas: list[str]  # ex. ["lote", "quantidade"] — campos que divergem
    valores: dict[str, ValorItem | None]  # chave = Coluna.chave ("invoice", "packing_list", "conhecimento", "soma_invoices"...)


class ComparacaoItens(BaseModel):
    comparacao_id: str  # mesma comparação (par/única) a que os itens pertencem
    titulo: str
    colunas: list[Coluna]
    linhas: list[LinhaItem]


class Divergencia(BaseModel):
    categoria: CategoriaDivergencia
    comparacao_id: str | None  # None para interna/coerência sem comparação específica
    campo: NomeCampo | None  # None para interna e item
    mensagem: str  # pronta para exibir
    documento: DocumentoRef | None = None  # interna: o documento com a contradição
    evidencia: str | None = None  # interna: trechos citados
    pagina: int | None = None
    item_chave: str | None = None  # item: LinhaItem.chave da linha divergente
    origem: str | None = None  # com comparacao_id, a comparação ("Invoice 1 — "); sem, o documento ("Invoice 1: ")
    rotulo: str | None = None  # o campo: "Endereço do exportador", "Item 7700100"
    detalhe: str | None = None  # o que difere: "BL 'ROOM 202…' × Invoice '2ND FLOOR…'"
    acao: str | None = None  # o que fazer: "pedir correção", "confira manualmente"


class ResultadoComparacao(BaseModel):
    status: StatusResultado
    documentos: list[DocumentoRef]  # todos os documentos usados
    comparacoes: list[Comparacao]
    itens: list[ComparacaoItens]
    divergencias: list[Divergencia]
    avisos: list[str]


class Uso(BaseModel):
    input_tokens: int
    output_tokens: int
    custo_usd_estimado: float
    modelo: str


# ---------------------------------------------------------------------------
# Interface pipeline <-> API
# ---------------------------------------------------------------------------

class ArquivoEntrada(BaseModel):
    id: str
    nome: str
    caminho: Path
    media_type: str


class ResultadoPipeline(BaseModel):
    resultado: ResultadoComparacao
    extracoes: dict[str, ExtracaoArquivo]  # arquivo_id -> extração bruta (auditoria)
    uso: Uso


# ---------------------------------------------------------------------------
# Respostas da API
# ---------------------------------------------------------------------------

class Arquivo(BaseModel):
    id: str
    nome: str
    media_type: str
    tamanho_bytes: int
    paginas: int | None


class Analise(BaseModel):
    id: str
    processo: str | None
    modalidade: Modalidade | None
    usuario_id: str | None
    status_processamento: StatusProcessamento
    etapa: Etapa
    erro: str | None
    criado_em: datetime
    concluido_em: datetime | None
    conferido_em: datetime | None  # quando o resultado foi gravado; muda ao refazer a conferência
    arquivos: list[Arquivo]
    resultado: ResultadoComparacao | None
    uso: Uso | None


class AnaliseResumo(BaseModel):
    id: str
    processo: str | None
    usuario_id: str | None
    status_processamento: StatusProcessamento
    status_resultado: StatusResultado | None
    modalidade: Modalidade | None
    total_divergencias: int | None
    erro: str | None
    qtd_arquivos: int
    criado_em: datetime


class ListaAnalises(BaseModel):
    """Uma página da listagem."""

    itens: list[AnaliseResumo]
    # Quantas análises batem com a busca em cada filtro (não depende do filtro nem da página).
    contagem: dict[FiltroLista, int]
