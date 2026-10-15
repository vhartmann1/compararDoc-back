"""Converte cada arquivo enviado (PDF, imagem, Word, Excel) em blocos de conteúdo para o Claude."""

import base64
import hashlib
import io
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

import openpyxl
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from PIL import Image

from app.schemas import ArquivoEntrada

MEDIA_PDF = "application/pdf"
MEDIA_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MEDIA_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TIPOS_IMAGEM = {"image/jpeg", "image/png"}

# Limites da API: lado até 2576 px (2000 com mais de 20 imagens), 5 MB por imagem em base64, 100 por requisição.
LADO_MAXIMO = 2576
LADO_MAXIMO_MUITAS = 2000
LIMITE_MUITAS_IMAGENS = 20
MAX_IMAGENS = 100
MAX_BYTES_IMAGEM = 3_500_000  # binário; vira ~4,7 MB em base64
# Imagens embutidas muito pequenas são ícones, linhas e logos: não ajudam e gastam tokens.
LADO_MINIMO_EMBUTIDA = 40
# Imagem atrás do texto com ao menos meia A4 é fundo: vai rotulada e, em conflito, o texto prevalece.
AREA_A4_EMU = 21.0 * 29.7 * 360000**2  # 1 cm = 360.000 EMU
FRACAO_PAGINA_FUNDO = 0.5
ROTULO_FUNDO = (
    "Imagens de FUNDO do arquivo {nome} (atrás do texto): use só para dados que não estão no texto; "
    "se conflitarem com o texto, o texto prevalece."
)
# Proporção exibida / proporção real acima disso (ou abaixo do inverso): imagem espremida, ilegível.
DISTORCAO_MAXIMA = 3.0
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


class ErroConversao(Exception):
    pass


def converter(arquivo: ArquivoEntrada) -> list[dict]:
    """Blocos de conteúdo (formato da Messages API) que representam o arquivo."""
    media = arquivo.media_type
    if media == MEDIA_PDF:
        dados = arquivo.caminho.read_bytes()
        return [{"type": "document", "source": {"type": "base64", "media_type": MEDIA_PDF, "data": _b64(dados)}}]
    if media in TIPOS_IMAGEM:
        return [_bloco_imagem(arquivo.caminho.read_bytes(), LADO_MAXIMO, arquivo.nome)]
    if media == MEDIA_DOCX:
        return _blocos_office(_texto_docx(arquivo.caminho), arquivo.caminho, arquivo.nome)
    if media == MEDIA_XLSX:
        return _blocos_office(_texto_xlsx(arquivo.caminho), arquivo.caminho, arquivo.nome)
    raise ErroConversao(
        f"Tipo de arquivo não suportado: {arquivo.nome} ({media}). Use PDF, JPG, PNG, Word (.docx) ou Excel (.xlsx)."
    )


# Word / Excel

def _blocos_office(texto: str, caminho: Path, nome: str) -> list[dict]:
    todas = _imagens_embutidas(caminho)
    imagens = [dados for dados, fundo in todas if not fundo]
    fundos = [dados for dados, fundo in todas if fundo]
    if len(todas) > MAX_IMAGENS:
        raise ErroConversao(f"{nome} tem {len(todas)} imagens; o limite é {MAX_IMAGENS} por arquivo.")
    lado = LADO_MAXIMO if len(todas) <= LIMITE_MUITAS_IMAGENS else LADO_MAXIMO_MUITAS

    blocos: list[dict] = []
    if texto.strip():
        blocos.append({"type": "text", "text": f"Conteúdo em texto do arquivo {nome}:\n\n{texto}"})
    if imagens:
        blocos.append({"type": "text", "text": f"Imagens embutidas no arquivo {nome} ({len(imagens)}):"})
        blocos.extend(_bloco_imagem(dados, lado, nome) for dados in imagens)
    if fundos:
        blocos.append({"type": "text", "text": ROTULO_FUNDO.format(nome=nome)})
        blocos.extend(_bloco_imagem(dados, lado, nome) for dados in fundos)
    if not blocos:
        raise ErroConversao(f"{nome} está vazio (sem texto nem imagens).")
    return blocos


def _texto_docx(caminho: Path) -> str:
    documento = Document(str(caminho))
    linhas: list[str] = []
    for item in documento.iter_inner_content():
        if isinstance(item, Paragraph):
            if item.text.strip():
                linhas.append(item.text.strip())
        elif isinstance(item, Table):
            linhas.extend(_linhas_tabela(item))
    return "\n".join(linhas)


def _linhas_tabela(tabela: Table) -> list[str]:
    """Uma linha de texto por linha da tabela; célula mesclada entra uma vez só."""
    linhas: list[str] = []
    vistas: set = set()  # os próprios elementos <w:tc> (mantê-los vivos garante identidade estável)
    for linha in tabela.rows:
        celulas: list[str] = []
        for celula in linha.cells:
            if celula._tc in vistas:
                continue
            vistas.add(celula._tc)
            texto = " ".join(celula.text.split())
            if texto:
                celulas.append(texto)
        if celulas:
            linhas.append(" | ".join(celulas))
    return linhas


def _texto_xlsx(caminho: Path) -> str:
    livro = openpyxl.load_workbook(caminho, data_only=True, read_only=True)
    partes: list[str] = []
    try:
        for planilha in livro.worksheets:
            linhas = []
            for valores in planilha.iter_rows(values_only=True):
                celulas = [_texto_celula(v) for v in valores if v is not None and str(v).strip()]
                if celulas:
                    linhas.append(" | ".join(celulas))
            if linhas:
                partes.append(f"=== Planilha: {planilha.title} ===\n" + "\n".join(linhas))
    finally:
        livro.close()
    return "\n\n".join(partes)


def _texto_celula(valor) -> str:
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return " ".join(str(valor).split())


@dataclass
class ImagemReferenciada:
    caminho: str  # dentro do zip, ex. "word/media/image4.png"
    fundo: bool  # atrás do texto (behindDoc) e ocupando boa parte da página
    tamanho_exibido: tuple[int, int] | None  # (largura, altura) em EMU, como aparece no documento


def _imagens_embutidas(caminho: Path) -> list[tuple[bytes, bool]]:
    """Imagens referenciadas pelo documento, sem duplicatas, ícones e deformadas. Cada item: (dados, é_fundo)."""
    imagens: list[tuple[bytes, bool]] = []
    vistas: set[str] = set()
    with zipfile.ZipFile(caminho) as z:
        for ref in _imagens_referenciadas(z):
            if ref.caminho not in z.namelist():
                continue
            dados = z.read(ref.caminho)
            hash_ = hashlib.sha256(dados).hexdigest()
            if hash_ in vistas or not _legivel(dados, ref):
                continue
            vistas.add(hash_)
            imagens.append((dados, ref.fundo))
    return imagens


def _legivel(dados: bytes, ref: ImagemReferenciada) -> bool:
    """Nem ícone minúsculo, nem espremida no documento, nem formato que o Pillow não decodifica (ex.: WMF)."""
    try:
        with Image.open(io.BytesIO(dados)) as img:
            img.load()
            return min(img.size) >= LADO_MINIMO_EMBUTIDA and not _deformada(ref.tamanho_exibido, img.size)
    except OSError:
        return False


def _imagens_referenciadas(z: zipfile.ZipFile) -> list[ImagemReferenciada]:
    """Word: document.xml, cabeçalhos e rodapés. Excel: os desenhos (drawings) das planilhas."""
    nomes = z.namelist()
    if "word/document.xml" in nomes:
        partes = ["word/document.xml"] + sorted(
            n for n in nomes if re.fullmatch(r"word/(header|footer)\d*\.xml", n)
        )
    else:
        partes = [
            alvo
            for planilha in sorted((n for n in nomes if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)), key=_ordem_natural)
            for alvo in _relacoes(z, planilha).values()
            if re.fullmatch(r"xl/drawings/drawing\d+\.xml", alvo)
        ]
    refs: list[ImagemReferenciada] = []
    for parte in dict.fromkeys(partes):
        refs.extend(_imagens_da_parte(z, parte))
    return refs


def _imagens_da_parte(z: zipfile.ZipFile, parte: str) -> list[ImagemReferenciada]:
    relacoes = _relacoes(z, parte)
    raiz = ET.fromstring(z.read(parte))
    pais = {filho: pai for pai in raiz.iter() for filho in pai}
    refs: list[ImagemReferenciada] = []
    for el in raiz.iter():
        nome = _local(el.tag)
        rid = el.get(f"{{{NS_R}}}embed") if nome == "blip" else el.get(f"{{{NS_R}}}id") if nome == "imagedata" else None
        if not rid or rid not in relacoes or _dentro_de_fallback(el, pais):
            continue
        ancora = _ancestral(el, pais, {"anchor", "inline"})
        refs.append(
            ImagemReferenciada(
                caminho=relacoes[rid],
                fundo=ancora is not None and _eh_fundo(ancora),
                tamanho_exibido=_tamanho_exibido(el, pais),
            )
        )
    return refs


def _ordem_natural(nome: str) -> tuple:
    """'sheet10.xml' depois de 'sheet9.xml'."""
    digitos = "".join(c for c in Path(nome).stem if c.isdigit())
    return (int(digitos) if digitos else 0, nome)


def _relacoes(z: zipfile.ZipFile, parte: str) -> dict[str, str]:
    """Id da relação -> caminho no zip, a partir de <pasta>/_rels/<parte>.rels."""
    pasta, arquivo = posixpath.split(parte)
    rels = posixpath.join(pasta, "_rels", f"{arquivo}.rels")
    if rels not in z.namelist():
        return {}
    relacoes: dict[str, str] = {}
    for rel in ET.fromstring(z.read(rels)):
        alvo = rel.get("Target") or ""
        if rel.get("TargetMode") == "External" or not alvo:
            continue
        caminho = alvo.lstrip("/") if alvo.startswith("/") else posixpath.normpath(posixpath.join(pasta, alvo))
        relacoes[rel.get("Id")] = caminho
    return relacoes


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _ancestral(el: ET.Element, pais: dict, nomes: set[str]) -> ET.Element | None:
    while el in pais:
        el = pais[el]
        if _local(el.tag) in nomes:
            return el
    return None


def _dentro_de_fallback(el: ET.Element, pais: dict) -> bool:
    """mc:Fallback repete o desenho em VML para Word antigo (às vezes com outra cópia da imagem)."""
    return _ancestral(el, pais, {"Fallback"}) is not None


def _eh_fundo(ancora: ET.Element) -> bool:
    """Imagem atrás do texto ocupando pelo menos metade de uma página A4."""
    if _local(ancora.tag) != "anchor" or ancora.get("behindDoc") not in ("1", "true"):
        return False
    extensao = next((e for e in ancora if _local(e.tag) == "extent"), None)
    if extensao is None:
        return False
    area = int(extensao.get("cx", 0)) * int(extensao.get("cy", 0))
    return area >= FRACAO_PAGINA_FUNDO * AREA_A4_EMU


def _tamanho_exibido(el: ET.Element, pais: dict) -> tuple[int, int] | None:
    """Tamanho da figura no documento: <a:ext> do <pic:spPr> da imagem."""
    figura = _ancestral(el, pais, {"pic"})
    if figura is None:
        return None
    for ext in figura.iter():
        if _local(ext.tag) == "ext" and ext.get("cx") and ext.get("cy"):
            return int(ext.get("cx")), int(ext.get("cy"))
    return None


def _deformada(tamanho_exibido: tuple[int, int] | None, tamanho_real: tuple[int, int]) -> bool:
    """Exibida com proporção muito diferente da original: ilegível no documento, não conta como conteúdo."""
    if not tamanho_exibido or not all(tamanho_exibido) or not all(tamanho_real):
        return False
    proporcao = (tamanho_exibido[0] / tamanho_exibido[1]) / (tamanho_real[0] / tamanho_real[1])
    return proporcao > DISTORCAO_MAXIMA or proporcao < 1 / DISTORCAO_MAXIMA


# Imagens

def _bloco_imagem(dados: bytes, lado_maximo: int, nome: str) -> dict:
    media_type, dados = _preparar_imagem(dados, lado_maximo, nome)
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": _b64(dados)}}


def _preparar_imagem(dados: bytes, lado_maximo: int, nome: str) -> tuple[str, bytes]:
    """Reduz para caber nos limites da API e converte para PNG/JPEG."""
    try:
        img = Image.open(io.BytesIO(dados))
        img.load()
    except OSError as e:
        raise ErroConversao(f"Não consegui abrir a imagem de {nome}.") from e

    formato_original = img.format
    if max(img.size) > lado_maximo:
        img.thumbnail((lado_maximo, lado_maximo), Image.Resampling.LANCZOS)
    elif formato_original in ("PNG", "JPEG") and len(dados) <= MAX_BYTES_IMAGEM:
        return f"image/{formato_original.lower()}", dados

    if img.mode not in ("RGB", "L"):
        img = img.convert("RGBA") if "A" in img.getbands() else img.convert("RGB")
    saida = io.BytesIO()
    img.save(saida, format="PNG", optimize=True)
    if saida.tell() <= MAX_BYTES_IMAGEM:
        return "image/png", saida.getvalue()

    saida = io.BytesIO()
    img.convert("RGB").save(saida, format="JPEG", quality=85)
    return "image/jpeg", saida.getvalue()


def _b64(dados: bytes) -> str:
    return base64.standard_b64encode(dados).decode("utf-8")
