"""Conversão de Word/Excel em blocos de conteúdo (sem chamar a API)."""

import base64
import io
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from app.schemas import ArquivoEntrada
from app.services.leitura.arquivo_para_conteudo import (
    MEDIA_DOCX,
    MEDIA_XLS,
    MEDIA_XLSX,
    ROTULO_FUNDO,
    ErroConversao,
    converter,
)


def entrada(caminho: Path, media_type: str | None = None) -> ArquivoEntrada:
    media_type = media_type or (MEDIA_DOCX if caminho.suffix == ".docx" else MEDIA_XLSX)
    return ArquivoEntrada(id="x", nome=caminho.name, caminho=caminho, media_type=media_type)


def textos(blocos):
    return "\n".join(b["text"] for b in blocos if b["type"] == "text")


def imagens(blocos):
    return [b for b in blocos if b["type"] == "image"]


def test_imagem_grande_e_reduzida(tmp_path):
    caminho = tmp_path / "grande.png"
    Image.new("RGB", (5000, 3000), "white").save(caminho)
    (bloco,) = converter(entrada(caminho, "image/png"))
    with Image.open(io.BytesIO(base64.b64decode(bloco["source"]["data"]))) as img:
        assert img.size == (2576, 1546)


def test_tipo_nao_suportado(tmp_path):
    caminho = tmp_path / "a.doc"
    caminho.write_bytes(b"x")
    with pytest.raises(ErroConversao, match="não suportado"):
        converter(entrada(caminho, "application/msword"))


def _docx_com_imagem(tmp_path, texto: str, ancora: str) -> Path:
    """Word mínimo com uma imagem 600×800 ancorada como indicado e outra sobrando em word/media."""
    from docx import Document

    caminho = tmp_path / "a.docx"
    doc = Document()
    doc.add_paragraph(texto)
    png = io.BytesIO()
    Image.new("RGB", (600, 800), "gray").save(png, format="PNG")
    png.seek(0)
    doc.add_picture(png)
    doc.save(caminho)
    with zipfile.ZipFile(caminho) as z:
        partes = {n: z.read(n) for n in z.namelist()}
    xml = partes["word/document.xml"].decode()
    if ancora == "fundo":  # inline -> anchor atrás do texto, página quase inteira
        inicio, fim = xml.index("<wp:inline"), xml.index("</wp:inline>") + len("</wp:inline>")
        miolo = xml[inicio:fim].replace("<wp:inline", '<wp:anchor behindDoc="1"', 1).replace("</wp:inline>", "</wp:anchor>")
        miolo = __import__("re").sub(r'<wp:extent cx="\d+" cy="\d+"/>', '<wp:extent cx="6800000" cy="9600000"/>', miolo)
        xml = xml[:inicio] + miolo + xml[fim:]
    partes["word/document.xml"] = xml.encode()
    sobra = io.BytesIO()
    Image.new("RGB", (500, 500), "red").save(sobra, format="PNG")
    partes["word/media/sobra.png"] = sobra.getvalue()
    with zipfile.ZipFile(caminho, "w") as z:
        for n, dados in partes.items():
            z.writestr(n, dados)
    return caminho


def test_docx_imagem_nao_referenciada_fica_de_fora(tmp_path):
    caminho = _docx_com_imagem(tmp_path, "curto", "normal")
    assert len(imagens(converter(entrada(caminho)))) == 1


def test_docx_fundo_vai_rotulado(tmp_path):
    caminho = _docx_com_imagem(tmp_path, "BILL OF LADING " * 30, "fundo")
    blocos = converter(entrada(caminho))
    assert len(imagens(blocos)) == 1 and ROTULO_FUNDO.format(nome="a.docx") in textos(blocos)


def test_docx_imagem_normal_sem_rotulo_de_fundo(tmp_path):
    caminho = _docx_com_imagem(tmp_path, "curto", "normal")
    blocos = converter(entrada(caminho))
    assert "FUNDO" not in textos(blocos)


def test_xlsx_so_imagens_dos_desenhos(tmp_path):
    import openpyxl
    from openpyxl.drawing.image import Image as ImagemXlsx

    caminho = tmp_path / "a.xlsx"
    livro = openpyxl.Workbook()
    livro.active["A1"] = "INVOICE"
    png = tmp_path / "logo.png"
    Image.new("RGB", (300, 200), "blue").save(png)
    livro.active.add_image(ImagemXlsx(str(png)), "B2")
    livro.save(caminho)
    sobra = io.BytesIO()
    Image.new("RGB", (500, 500), "red").save(sobra, format="PNG")
    with zipfile.ZipFile(caminho, "a") as z:
        z.writestr("xl/media/sobra.png", sobra.getvalue())

    (imagem,) = imagens(converter(entrada(caminho)))
    with Image.open(io.BytesIO(base64.b64decode(imagem["source"]["data"]))) as img:
        assert img.size == (300, 200)


def test_docx_celula_mesclada_entra_uma_vez(tmp_path):
    """Célula mesclada na vertical não pode repetir o texto (repetição gerava falso positivo de consignatário)."""
    from docx import Document

    caminho = tmp_path / "mesclada.docx"
    doc = Document()
    tabela = doc.add_table(rows=3, cols=2)
    mesclada = tabela.cell(0, 0).merge(tabela.cell(2, 0))
    mesclada.text = "SHIPPER SERRANA POLIMEROS"
    tabela.cell(0, 1).text = "linha 1"
    tabela.cell(1, 1).text = "linha 2"
    tabela.cell(2, 1).text = "linha 3"
    doc.save(caminho)
    texto = textos(converter(entrada(caminho)))
    assert texto.count("SERRANA") == 1
    assert all(f"linha {n}" in texto for n in (1, 2, 3))


def _wmf() -> bytes:
    """Cabeçalho WMF válido: o Pillow abre (lê o tamanho), mas não decodifica fora do Windows."""
    import struct

    cabecalho = b"\xd7\xcd\xc6\x9a" + struct.pack("<hhhhhHI", 0, 0, 0, 2000, 1000, 1440, 0)
    soma = 0
    for (palavra,) in struct.iter_unpack("<H", cabecalho):
        soma ^= palavra
    return cabecalho + struct.pack("<H", soma) + b"\x01\x00\x09\x00\x00\x03" + b"\x00" * 12


def test_xlsx_com_imagem_que_nao_decodifica_segue_com_o_texto(tmp_path):
    import openpyxl
    from openpyxl.drawing.image import Image as ImagemXlsx

    caminho = tmp_path / "a.xlsx"
    livro = openpyxl.Workbook()
    livro.active["A1"] = "PACKING LIST"
    png = tmp_path / "logo.png"
    Image.new("RGB", (300, 200), "blue").save(png)
    livro.active.add_image(ImagemXlsx(str(png)), "B2")
    livro.save(caminho)
    with zipfile.ZipFile(caminho) as z:
        partes = {n: z.read(n) for n in z.namelist()}
    [midia] = [n for n in partes if n.startswith("xl/media/")]
    partes[midia] = _wmf()
    with zipfile.ZipFile(caminho, "w") as z:
        for n, dados in partes.items():
            z.writestr(n, dados)
    blocos = converter(entrada(caminho))
    assert "PACKING LIST" in textos(blocos) and imagens(blocos) == []


def test_xls_vira_texto_das_planilhas(tmp_path):
    import datetime

    import xlwt

    caminho = tmp_path / "a.xls"
    livro = xlwt.Workbook()
    planilha = livro.add_sheet("Invoice")
    planilha.write(0, 0, "COMMERCIAL INVOICE")
    planilha.write(2, 0, "Qty")
    planilha.write(2, 1, 120.0)
    planilha.write(2, 2, 3.5)
    planilha.write(3, 0, datetime.datetime(2026, 3, 9), xlwt.easyxf(num_format_str="DD/MM/YYYY"))
    livro.add_sheet("Packing").write(0, 0, "PACKING LIST")
    livro.save(str(caminho))
    (bloco,) = converter(entrada(caminho, MEDIA_XLS))
    assert "=== Planilha: Invoice ===" in bloco["text"] and "=== Planilha: Packing ===\nPACKING LIST" in bloco["text"]
    assert "Qty | 120 | 3.5" in bloco["text"] and "2026-03-09" in bloco["text"]


def test_xls_invalido_da_erro_legivel(tmp_path):
    caminho = tmp_path / "a.xls"
    caminho.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 600)
    with pytest.raises(ErroConversao, match="Não consegui abrir"):
        converter(entrada(caminho, MEDIA_XLS))
