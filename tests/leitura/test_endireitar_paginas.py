"""Página escaneada de lado: endireita e relê só o arquivo apontado (sem chamar a Claude)."""

from pypdf import PdfReader, PdfWriter

from app.schemas import ArquivoEntrada, ExtracaoArquivo, PaginaGirada, Uso
from app.services.leitura.endireitar_paginas import endireitado, reler_paginas_giradas


def _pdf(caminho, giros=(0, 0)):
    escritor = PdfWriter()
    for giro in giros:
        escritor.add_blank_page(width=595, height=842).rotation = giro
    with caminho.open("wb") as f:
        escritor.write(f)
    return ArquivoEntrada(id=caminho.stem, nome=f"{caminho.stem}.pdf", caminho=caminho, media_type="application/pdf")


def _uso(custo):
    return Uso(input_tokens=10, output_tokens=5, custo_usd_estimado=custo, modelo="m")


def _girada(pagina, graus):
    return PaginaGirada(pagina=pagina, graus=graus)


def test_endireita_so_a_pagina_apontada_numa_copia_sem_mexer_no_original(tmp_path):
    original = _pdf(tmp_path / "a1.pdf")
    (tmp_path / "copias").mkdir()
    copia = endireitado(original, [_girada(2, 270)], tmp_path / "copias")
    assert copia.id == "a1" and copia.nome == "a1.pdf" and copia.caminho != original.caminho
    assert [p.rotation for p in PdfReader(copia.caminho).pages] == [0, 270]
    assert [p.rotation for p in PdfReader(original.caminho).pages] == [0, 0]


def test_soma_ao_giro_que_o_pdf_ja_tem_sem_passar_de_360_e_sem_girar_duas_vezes(tmp_path):
    original = _pdf(tmp_path / "a1.pdf", giros=(270, 0))
    copia = endireitado(original, [_girada(1, 180), _girada(1, 180)], tmp_path)
    assert [p.rotation for p in PdfReader(copia.caminho).pages] == [90, 0]


def test_pagina_fora_do_pdf_ou_pdf_corrompido_nao_gera_copia(tmp_path):
    assert endireitado(_pdf(tmp_path / "a1.pdf"), [_girada(9, 90)], tmp_path) is None
    corrompido = tmp_path / "a2.pdf"
    corrompido.write_bytes(b"%PDF-1.4 isto nao e um pdf")
    arquivo = ArquivoEntrada(id="a2", nome="a2.pdf", caminho=corrompido, media_type="application/pdf")
    assert endireitado(arquivo, [_girada(1, 90)], tmp_path) is None


def test_rele_uma_vez_so_o_arquivo_com_pagina_girada_e_soma_o_uso(tmp_path):
    girado, normal = _pdf(tmp_path / "a1.pdf"), _pdf(tmp_path / "a2.pdf")
    primeira = {
        "a1": ExtracaoArquivo(documentos=[], paginas_giradas=[_girada(1, 180)]),
        "a2": ExtracaoArquivo(documentos=[]),
    }
    relidos = []

    def extrair(arquivos):
        relidos.extend(a.id for a in arquivos)
        return {a.id: ExtracaoArquivo(documentos=[], paginas_giradas=[_girada(1, 90)]) for a in arquivos}, _uso(0.5)

    extracoes, uso = reler_paginas_giradas([girado, normal], primeira, _uso(1.0), extrair)
    assert relidos == ["a1"]
    assert extracoes["a2"] is primeira["a2"] and extracoes["a1"] is not primeira["a1"]
    assert uso.custo_usd_estimado == 1.5 and uso.input_tokens == 20


def test_sem_pagina_girada_que_exista_nao_rele(tmp_path):
    arquivo = _pdf(tmp_path / "a1.pdf")
    extracoes = {"a1": ExtracaoArquivo(documentos=[], paginas_giradas=[_girada(9, 90)])}

    def extrair(_arquivos):
        raise AssertionError("não devia reler")

    assert reler_paginas_giradas([arquivo], extracoes, _uso(1.0), extrair)[0] is extracoes
