"""Normalização determinística: pesos -> KG, NCM/HS, números de documento, nomes, portos e formatação BR."""

import difflib
import re
import unicodedata

from app.schemas import Medida

KG_POR_UNIDADE: dict[str, float] = {
    "KG": 1.0,
    "LB": 0.45359237,
    "MT": 1000.0,
    "TON": 1000.0,
    "G": 0.001,
}

# Unidades de quantidade equivalentes: unidade -> (unidade canônica, fator)
UNIDADES_QUANTIDADE: dict[str, tuple[str, float]] = {
    **dict.fromkeys(["PAR", "PARES", "PAIR", "PAIRS", "PRS", "PR", "PRS."], ("PARES", 1.0)),
    **dict.fromkeys(["KG", "KGS", "KILO", "KILOS", "QUILO", "QUILOS"], ("KG", 1.0)),
    **dict.fromkeys(
        ["TON", "TONS", "TONELADA", "TONELADAS", "TONNE", "TONNES", "MT", "MTS", "TO", "TNE", "T", "TM"], ("KG", 1000.0)
    ),
    **dict.fromkeys(["LB", "LBS", "POUND", "POUNDS"], ("KG", 0.45359237)),
    **dict.fromkeys(
        ["PC", "PCS", "PIECE", "PIECES", "UN", "UND", "UNID", "UNIDADE", "UNIDADES", "UNIT", "UNITS",
         "PECA", "PECAS", "PZA", "PIEZAS", "EA", "EACH"],
        ("PECAS", 1.0),
    ),
    **dict.fromkeys(["BAG", "BAGS", "SACO", "SACOS", "BOLSA", "BOLSAS", "SACA", "SACAS"], ("SACOS", 1.0)),
    **dict.fromkeys(
        ["CARTON", "CARTONS", "CTN", "CTNS", "CAR", "CASE", "CASES", "CAJA", "CAJAS", "CAIXA", "CAIXAS", "CX", "CXS",
         "BOX", "BOXES", "CARTONE", "CARTONI"],
        ("CAIXAS", 1.0),
    ),
    **dict.fromkeys(["PALLET", "PALLETS", "PALETE", "PALETES", "PALET", "PALETS", "PLT", "PLTS"], ("PALETES", 1.0)),
    **dict.fromkeys(
        ["BOTTLE", "BOTTLES", "BOTELLA", "BOTELLAS", "GARRAFA", "GARRAFAS", "BT", "BTL", "BTLS", "BOTTIGLIA", "BOTTIGLIE"],
        ("GARRAFAS", 1.0),
    ),
    **dict.fromkeys(["L", "LT", "LTS", "LITRO", "LITROS", "LITER", "LITERS", "LITRE", "LITRES"], ("L", 1.0)),
    **dict.fromkeys(["M", "MTR", "MTRS", "METRO", "METROS", "METER", "METERS"], ("M", 1.0)),
    **dict.fromkeys(["M2", "SQM", "METRO QUADRADO", "METROS QUADRADOS"], ("M2", 1.0)),
    **dict.fromkeys(["DZ", "DOZ", "DUZIA", "DUZIAS", "DOZEN", "DOZENS"], ("PECAS", 12.0)),
}

# Palavras ignoradas ao comparar razões sociais.
SUFIXOS_EMPRESA = {
    "LTD", "LTDA", "CO", "SAS", "SA", "INC", "LIMITED", "IMPORTACAO", "EXPORTACAO", "COMERCIO",
    "E", "DE", "DA", "DO", "AND", "THE", "EIRELI", "ME", "EPP", "CORP", "LLC", "GMBH", "SRL",
}
SIMILARIDADE_MINIMA_NOME = 0.85

PALAVRAS_PORTO = {"PORT", "PORTO", "PUERTO", "AIRPORT", "AEROPORTO", "AEROPUERTO", "OF", "DE", "DO", "DA"}
# Sufixos de UF/país depois do nome da cidade, ex.: "NAVEGANTES SC BRASIL"
SUFIXOS_LOCAL = {
    "BRASIL", "BRAZIL", "BR", "CHINA", "CN", "PRC", "COLOMBIA", "CO", "USA", "US", "INDIA", "IN",
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR",
    "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}


# Pesos e números

def para_kg(medida: Medida) -> float | None:
    """Converte a medida para KG. Unidade desconhecida ("OUTRA") => None."""
    fator = KG_POR_UNIDADE.get(medida.unidade)
    if fator is None:
        return None
    return round(medida.valor * fator, 3)


def interpretar_numero(texto: str) -> float:
    """Lê '27,200.00', '27.200,00', '46737', '1.234': o último separador é o decimal, salvo se parecer milhar."""
    limpo = re.sub(r"[^\d.,]", "", texto)
    if not limpo or not re.search(r"\d", limpo):
        raise ValueError(f"Número inválido: {texto!r}")

    tem_ponto, tem_virgula = "." in limpo, "," in limpo
    if tem_ponto and tem_virgula:
        decimal = "." if limpo.rfind(".") > limpo.rfind(",") else ","
        milhar = "," if decimal == "." else "."
        return float(limpo.replace(milhar, "").replace(decimal, "."))

    separador = "." if tem_ponto else "," if tem_virgula else None
    if separador is None:
        return float(limpo)
    partes = limpo.split(separador)
    if len(partes) > 2 or len(partes[-1]) == 3:
        return float(limpo.replace(separador, ""))  # separador de milhar
    return float(limpo.replace(separador, "."))


# Embalagens de níveis diferentes: 2 paletes e 160 caixas podem ser a mesma carga.
EMBALAGENS = {"SACOS", "CAIXAS", "PALETES"}


def embalagem(unidade: str) -> str | None:
    """'CTNS' -> 'CAIXAS'; 'PACKAGES' (genérica) ou desconhecida -> None."""
    canonica, _ = unidade_quantidade(unidade)
    return canonica if canonica in EMBALAGENS else None


def unidade_quantidade(unidade: str) -> tuple[str, float]:
    """'PAIRS' -> ('PARES', 1.0); 'TON' -> ('KG', 1000.0). Desconhecida -> (unidade normalizada, 1.0)."""
    chave = " ".join(re.sub(r"[^A-Z0-9 ]", " ", sem_acento(unidade).upper()).split())
    if chave in UNIDADES_QUANTIDADE:
        return UNIDADES_QUANTIDADE[chave]
    sem_ponto = chave.replace(" ", "")
    if sem_ponto in UNIDADES_QUANTIDADE:
        return UNIDADES_QUANTIDADE[sem_ponto]
    return chave, 1.0


# NCM / HS

def so_digitos(codigo: str) -> str:
    return re.sub(r"\D", "", codigo)


def normalizar_ncm(codigo: str) -> str:
    """Só dígitos, no máximo 8 (códigos nacionais de 10 dígitos, ex. Colômbia, viram NCM de 8)."""
    return so_digitos(codigo)[:8]


# Textos

def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def normalizar_numero_documento(numero: str) -> str:
    """'0077032707' -> '77032707'; 'inv-2026/01' -> 'INV202601'. Só letras e dígitos, sem zeros à esquerda."""
    limpo = re.sub(r"[^A-Z0-9]", "", sem_acento(numero).upper())
    return limpo.lstrip("0") or limpo


# Marcas do tipo de documento no meio do número: 'XYZ/PL/2526/LOC0123' é o PL da invoice 'XYZ2526/LOC0123'
MARCAS_DE_TIPO = {"PL", "PKL", "PK", "PACKING", "LIST", "CI", "INV", "INVOICE"}


def numero_sem_serie(numero: str) -> str:
    """'FT A26/000123' e 'GR A26/000123' -> 'A26000123'; 'XYZ/PL/25/0123' -> 'XYZ250123': série e marca do tipo saem."""
    texto = sem_acento(numero).upper()
    partes = texto.split(None, 1)
    if len(partes) == 2 and re.fullmatch(r"[A-Z]{1,4}\.?", partes[0]) and re.search(r"\d", partes[1]):
        texto = partes[1]
    pedacos = [p for p in re.split(r"[\s/._-]+", texto) if p not in MARCAS_DE_TIPO]
    return normalizar_numero_documento("".join(pedacos) or texto)  # só a marca ('INVOICE'): não é número, fica como está


def mesmo_numero(x: str, y: str) -> bool:
    """Já normalizados: iguais, ou um é o outro com letras na frente ('NFB907311' × '907311', série ou rótulo)."""
    maior, menor = (x, y) if len(x) >= len(y) else (y, x)
    return x == y or (len(menor) >= 3 and maior.endswith(menor) and maior[: -len(menor)].isalpha())


PREFIXO_PO = re.compile(r"^\s*(P\.?\s?O\.?|PURCHASE ORDER|PEDIDO)(?=[\s:#.\-0-9])\s*(N[O°º]\.?|NR\.?|NUMBER|#|:)?\s*")


def normalizar_po(po: str) -> str:
    """'PO 15 March' e '15 March' -> '15MARCH': o rótulo na frente não faz parte do número."""
    return re.sub(r"[^A-Z0-9]", "", PREFIXO_PO.sub("", sem_acento(po).upper()))


def normalizar_nome_empresa(nome: str) -> str:
    """'Capital Trade Importação e Exportação Ltda.' -> 'CAPITAL TRADE'."""
    texto = re.sub(r"[^A-Z0-9 ]", " ", sem_acento(nome).upper().replace(".", ""))
    return " ".join(p for p in texto.split() if p not in SUFIXOS_EMPRESA)


def nomes_equivalentes(a: str, b: str) -> bool:
    """Similaridade ≥ 0,85 entre os nomes normalizados, ou um começa com o outro (sufixo colado por erro)."""
    na, nb = normalizar_nome_empresa(a), normalizar_nome_empresa(b)
    if not na or not nb:
        return na == nb
    if difflib.SequenceMatcher(None, na, nb).ratio() >= SIMILARIDADE_MINIMA_NOME:
        return True
    ca, cb = na.replace(" ", ""), nb.replace(" ", "")
    curto, longo = sorted((ca, cb), key=len)
    return len(curto) >= 6 and longo.startswith(curto)


# Terminal ou nome alternativo -> porto (o BL costuma citar o terminal; a invoice, a cidade)
PORTOS_EQUIVALENTES = {
    **dict.fromkeys(["XINGANG", "TIANJIN XINGANG", "XINGANG TIANJIN", "TIANJINXINGANG"], "TIANJIN"),
    **dict.fromkeys(["YANTIAN", "SHEKOU", "CHIWAN", "DA CHAN BAY"], "SHENZHEN"),
    **dict.fromkeys(["NANSHA", "HUANGPU"], "GUANGZHOU"),
    **dict.fromkeys(["YANGSHAN", "WAIGAOQIAO", "SHANGAI"], "SHANGHAI"),
    **dict.fromkeys(["BEILUN", "NINGBO ZHOUSHAN"], "NINGBO"),
    **dict.fromkeys(["TANJUNG PRIOK"], "JAKARTA"),
    **dict.fromkeys(["BARRA RIO"], "ITAJAI"),
}


def normalizar_porto(nome: str) -> str:
    """Nome do porto para comparar: 'XINGANG' e 'Tianjin, China' -> 'TIANJIN'."""
    porto = nome_do_porto(nome)
    return PORTOS_EQUIVALENTES.get(porto, porto)


def nome_do_porto(nome: str) -> str:
    """Nome do porto como o documento escreve, sem rótulo e sem país: 'Port of Navegantes - SC, Brazil' -> 'NAVEGANTES'."""
    texto = sem_acento(nome).upper()
    texto = re.sub(r"\(.*?\)", " ", texto)  # 'SHEKOU (CHINA)'
    texto = re.split(r",|/| - ", texto)[0]  # 'NAVEGANTES, SC' / 'NAVEGANTES - SC'
    palavras = [p for p in re.sub(r"[^A-Z0-9 ]", " ", texto).split() if p not in PALAVRAS_PORTO]
    while len(palavras) > 1 and palavras[-1] in SUFIXOS_LOCAL:
        palavras.pop()
    return " ".join(palavras)


def normalizar_cnpj(cnpj: str | None) -> str | None:
    digitos = so_digitos(cnpj or "")
    return digitos or None


# Formatação BR

def formatar_numero(valor: float, casas: int = 2) -> str:
    """21250 -> '21.250,00'."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_kg(valor: float) -> str:
    """21250.0 -> '21.250,00 kg'."""
    return f"{formatar_numero(valor)} kg"


def formatar_contagem(valor: float, unidade: str) -> str:
    """53, 'CTN' -> '53 CTN'; 24.5, 'TON' -> '24,5 TON'."""
    if float(valor).is_integer():
        numero = formatar_numero(valor, 0)
    else:
        numero = formatar_numero(valor, 3).rstrip("0").rstrip(",")
    return f"{numero} {unidade}".strip()


def formatar_ncm(codigo: str) -> str:
    """'39011010' -> '3901.10.10'; '390110' -> '3901.10'; '3304' -> '3304'."""
    partes = [codigo[:4], codigo[4:6], codigo[6:8]]
    return ".".join(p for p in partes if p)


def formatar_cnpj(cnpj: str) -> str:
    """14 dígitos -> '12.345.678/0001-90'; outros tamanhos e códigos com letras (registro chinês) ficam como vieram."""
    d = so_digitos(cnpj)
    if len(d) != 14 or re.search(r"[A-Za-z]", cnpj):
        return cnpj.strip()
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


# Endereço, país, moeda, incoterm e itens

SIMILARIDADE_MINIMA_ENDERECO = 0.80
SIMILARIDADE_MINIMA_DESCRICAO = 0.85
SIMILARIDADE_MINIMA_CASAMENTO = 0.80  # casar itens sem código pela descrição

# País normalizado -> código ISO de 2 letras (sinônimos comuns em documentos de comércio exterior)
PAISES: dict[str, str] = {
    **dict.fromkeys(["CHINA", "PRC", "CN", "CHN", "P R CHINA", "PR CHINA", "PEOPLES REPUBLIC OF CHINA",
                     "PEOPLE S REPUBLIC OF CHINA", "REPUBLICA POPULAR DA CHINA"], "CN"),
    **dict.fromkeys(["KOREA", "SOUTH KOREA", "REPUBLIC OF KOREA", "KOREA REPUBLIC OF", "KR", "KOR",
                     "COREIA", "COREIA DO SUL", "COREA", "COREA DEL SUR", "ROK"], "KR"),
    **dict.fromkeys(["BRAZIL", "BRASIL", "BR", "BRA"], "BR"),
    **dict.fromkeys(["COLOMBIA", "CO", "COL"], "CO"),
    **dict.fromkeys(["USA", "US", "UNITED STATES", "UNITED STATES OF AMERICA", "ESTADOS UNIDOS", "EUA"], "US"),
    **dict.fromkeys(["INDIA", "IN", "IND"], "IN"),
    **dict.fromkeys(["JAPAN", "JAPAO", "JAPON", "JP", "JPN"], "JP"),
    **dict.fromkeys(["TAIWAN", "TW", "TWN", "CHINESE TAIPEI"], "TW"),
    **dict.fromkeys(["HONG KONG", "HK", "HKG"], "HK"),
    **dict.fromkeys(["VIETNAM", "VIET NAM", "VN", "VNM"], "VN"),
    **dict.fromkeys(["GERMANY", "ALEMANHA", "ALEMANIA", "DE", "DEU"], "DE"),
    **dict.fromkeys(["ITALY", "ITALIA", "IT", "ITA"], "IT"),
    **dict.fromkeys(["SPAIN", "ESPANHA", "ESPANA", "ES", "ESP"], "ES"),
    **dict.fromkeys(["NETHERLANDS", "HOLLAND", "HOLANDA", "PAISES BAIXOS", "PAISES BAJOS", "NL", "NLD"], "NL"),
    **dict.fromkeys(["BELGIUM", "BELGICA", "BELGIQUE", "BE", "BEL"], "BE"),
    **dict.fromkeys(["FRANCE", "FRANCA", "FRANCIA", "FR", "FRA"], "FR"),
    **dict.fromkeys(["PORTUGAL", "PT", "PRT"], "PT"),
    **dict.fromkeys(["UNITED KINGDOM", "UK", "GREAT BRITAIN", "REINO UNIDO", "GB", "GBR"], "GB"),
    **dict.fromkeys(["ARGENTINA", "AR", "ARG"], "AR"),
    **dict.fromkeys(["CHILE", "CL", "CHL"], "CL"),
    **dict.fromkeys(["MEXICO", "MX", "MEX"], "MX"),
    **dict.fromkeys(["PERU", "PE", "PER"], "PE"),
    **dict.fromkeys(["THAILAND", "TAILANDIA", "TH", "THA"], "TH"),
    **dict.fromkeys(["INDONESIA", "ID", "IDN"], "ID"),
    **dict.fromkeys(["MALAYSIA", "MALASIA", "MY", "MYS"], "MY"),
    **dict.fromkeys(["TURKEY", "TURKIYE", "TURQUIA", "TR", "TUR"], "TR"),
}
SIGLAS_PAISES = set(PAISES.values())

MOEDAS: dict[str, str] = {
    **dict.fromkeys(["USD", "US$", "U$", "$", "US DOLLAR", "US DOLLARS", "DOLLAR", "DOLLARS", "DOLAR", "DOLARES"], "USD"),
    **dict.fromkeys(["EUR", "€", "EURO", "EUROS"], "EUR"),
    **dict.fromkeys(["CNY", "RMB", "YUAN"], "CNY"),
    **dict.fromkeys(["BRL", "R$", "REAL", "REAIS"], "BRL"),
}


def _so_letras_numeros(texto: str) -> str:
    return " ".join(re.sub(r"[^A-Z0-9 ]", " ", sem_acento(texto).upper()).split())


def normalizar_pais(pais: str) -> str:
    """'South Korea' / 'KR' / 'Republic of Korea' -> 'KR'; desconhecido -> texto normalizado."""
    chave = _so_letras_numeros(pais)
    if chave.startswith("THE "):
        chave = chave[4:]
    return PAISES.get(chave, chave)


def normalizar_moeda(moeda: str) -> str:
    texto = sem_acento(moeda).upper().strip()
    return MOEDAS.get(texto, MOEDAS.get(_so_letras_numeros(texto), _so_letras_numeros(texto)))


def normalizar_endereco(endereco: str) -> str:
    return _so_letras_numeros(endereco.replace(".", ""))


def palavras_do_endereco(endereco: str) -> set[str]:
    """Palavras do endereço, com o país pela sigla ('THE NETHERLANDS' e 'NL' viram 'NL')."""
    texto = f" {normalizar_endereco(endereco)} "
    for nome in sorted(PAISES, key=len, reverse=True):
        texto = texto.replace(f" {nome} ", f" {PAISES[nome]} ")
    return set(texto.split()) - {"THE"}


def enderecos_equivalentes(a: str, b: str) -> bool:
    """Texto parecido na mesma ordem, as mesmas palavras em outra ordem, ou um é o outro com mais detalhe."""
    na, nb = normalizar_endereco(a), normalizar_endereco(b)
    if difflib.SequenceMatcher(None, na, nb).ratio() >= SIMILARIDADE_MINIMA_ENDERECO:
        return True
    pa, pb = palavras_do_endereco(a), palavras_do_endereco(b)
    pa, pb = _sem_abreviacoes(pa, pb), _sem_abreviacoes(pb, pa)
    if pa | pb and len(pa & pb) / len(pa | pb) >= SIMILARIDADE_MINIMA_ENDERECO:
        return True
    return _contido_com_mais_detalhe(pa, pb) or _contido_com_mais_detalhe(pb, pa)


def _sem_abreviacoes(palavras: set[str], outras: set[str]) -> set[str]:
    """'ON' vira 'ONTARIO' se o outro endereço traz 'ONTARIO': sigla de estado/província é o começo do nome."""
    def completa(p: str) -> str:
        if p in outras or not p.isalpha() or len(p) < 2:
            return p
        return next((o for o in sorted(outras) if o.startswith(p) and o.isalpha()), p)
    return {completa(p) for p in palavras}


def _contido_com_mais_detalhe(curto: set[str], longo: set[str]) -> bool:
    """'NO 88 LIANHUA ROAD SHANGHAI 201100 CN' ⊂ '2F NO 88 LIANHUA ROAD MINHANG DISTRICT SHANGHAI', fora CEP e país."""
    essencial = {p for p in curto if p not in SIGLAS_PAISES and not re.fullmatch(r"\d{5,}", p)}
    return len(essencial) >= 3 and any(ch.isdigit() for p in essencial for ch in p) and essencial <= longo


def normalizar_cidade(cidade: str) -> str:
    """'Gyeonggi-do' -> 'GYEONGGIDO'; 'Bogotá, D.C.' -> 'BOGOTADC'."""
    return re.sub(r"[^A-Z0-9]", "", sem_acento(cidade).upper())


def cidades_compativeis(cidade_a: str, endereco_a: str, cidade_b: str, endereco_b: str) -> bool:
    """Mesma cidade, uma contida na outra, ou a cidade de um aparece no endereço do outro."""
    ca, cb = normalizar_cidade(cidade_a), normalizar_cidade(cidade_b)
    if not ca or not cb or ca in cb or cb in ca:
        return True
    return ca in normalizar_cidade(endereco_b) or cb in normalizar_cidade(endereco_a)


def enderecos_compativeis(a: tuple[str, str | None], b: tuple[str, str | None]) -> bool:
    """(endereço, cidade): cidades diferentes => divergem, mesmo com texto parecido; senão similaridade."""
    (texto_a, cidade_a), (texto_b, cidade_b) = a, b
    if cidade_a and cidade_b and not cidades_compativeis(cidade_a, texto_a, cidade_b, texto_b):
        return False
    return enderecos_equivalentes(texto_a, texto_b)


def normalizar_incoterm(codigo: str) -> str:
    """'fob' / 'FOB 2020' / 'CFR-ITAPOA' -> 'FOB' / 'CFR' (as 3 primeiras letras)."""
    letras = re.sub(r"[^A-Z]", "", sem_acento(codigo).upper())
    return letras[:3]


def normalizar_codigo_item(codigo: str) -> str:
    """'4200000001004 TW' -> '4200000001004': a sigla do país de origem no fim não faz parte do código."""
    partes = sem_acento(codigo).upper().rsplit(None, 1)
    if len(partes) == 2 and partes[1] in SIGLAS_PAISES and re.search(r"\d", partes[0]):
        codigo = partes[0]
    return re.sub(r"[^A-Z0-9]", "", sem_acento(codigo).upper())


def normalizar_lote(lote: str) -> str:
    """'#LT2031C14-E' -> 'LT2031C14E'."""
    return re.sub(r"[\s#\-]", "", sem_acento(lote).upper())


def normalizar_validade(validade: str) -> str:
    """'Exp 11/2025' -> '11/2025'; 'Exp 03/29' -> '03/2029'; '20/02/2026' -> '02/2026'; '2026-02-20' -> '02/2026'."""
    texto = sem_acento(validade).upper()

    def ano(a: str) -> str:
        return a if len(a) == 4 else f"20{a.zfill(2)}"

    if m := re.search(r"\b(\d{4})[/.\-](\d{1,2})(?:[/.\-]\d{1,2})?\b", texto):
        return f"{int(m.group(2)):02d}/{m.group(1)}"
    if m := re.search(r"\b\d{1,2}[/.\-](\d{1,2})[/.\-](\d{2}|\d{4})\b", texto):
        return f"{int(m.group(1)):02d}/{ano(m.group(2))}"
    if m := re.search(r"\b(\d{1,2})[/.\-](\d{2}|\d{4})\b", texto):
        return f"{int(m.group(1)):02d}/{ano(m.group(2))}"
    return _so_letras_numeros(texto)


def normalizar_descricao(descricao: str) -> str:
    return _so_letras_numeros(descricao)


def normalizar_referencia(referencia: str) -> str:
    """'Polirex ZK-455' -> 'POLIREXZK455'."""
    return re.sub(r"[^A-Z0-9]", "", sem_acento(referencia).upper())


def referencias_iguais(a: str, b: str) -> bool:
    """Iguais após normalizar; tolera só a omissão de palavras inteiras (a marca), nunca troca de letra."""
    if normalizar_referencia(a) == normalizar_referencia(b):
        return True
    pa, pb = set(_so_letras_numeros(a).split()), set(_so_letras_numeros(b).split())
    return bool(pa and pb) and (pa <= pb or pb <= pa)


def similaridade(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def descricoes_equivalentes(a: str, b: str) -> bool:
    """Similaridade >= 0,85 após normalizar, ou uma descrição contida na outra (PL costuma abreviar)."""
    na, nb = normalizar_descricao(a), normalizar_descricao(b)
    if not na or not nb:
        return na == nb
    curto, longo = sorted((na, nb), key=len)
    return similaridade(na, nb) >= SIMILARIDADE_MINIMA_DESCRICAO or (len(curto) >= 8 and curto in longo)


def formatar_dinheiro(valor: float, moeda: str | None) -> str:
    """720, 'USD' -> 'USD 720,00'."""
    return f"{moeda} {formatar_numero(valor)}" if moeda else formatar_numero(valor)
