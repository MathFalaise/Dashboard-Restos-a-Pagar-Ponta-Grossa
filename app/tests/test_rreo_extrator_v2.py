"""RREO Annex VII extractor v2 (correction request of 09/10/2026, item 6): never a partial, shifted or inconsistent
transcription.

v1 assigned each number to the NEAREST column label and accepted two equal numbers in one cell; in 31 real PDFs the
all-zero "INTRA" row lost its column (e) in silence. v2 transcribes a recognized row whole (12 numbers, each strictly
between the labels of the neighbouring columns) and checks the document's own arithmetic. SINTETICO = PDFs built
here with PyMuPDF.
"""
import pytest
from conftest import (CABECALHO_RREO, EXCETO_RREO, INTRA_RREO, TOTAL_RREO, linha_rreo, numero_pt, textos_da_linha)

from rp import normalizar

V = linha_rreo(a=455_000_00, b=1_275_241_67, c=1_266_236_53, d=12_976_00, f=1_283_420_45, g=4_907_516_05,
               h=4_061_528_40, i=3_993_615_21, j=752_649_51)
ZERO = linha_rreo()


def _pdf(textos):
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf
    doc = pymupdf.open()
    pg = doc.new_page(width=1000, height=600)
    for (x, y), t in textos:
        pg.insert_text((x, y), t, fontsize=7)
    return doc.tobytes()


class _Captura:
    def executemany(self, sql, linhas):
        self.linhas = list(linhas)

        class R:
            rowcount = len(self.linhas)
        return R()


def _transcrever(*linhas):
    cap = _Captura()
    n = normalizar._rreo(cap, 1, 1, {"rotulo": "4º Bimestre"}, _pdf(CABECALHO_RREO + [t for l in linhas for t in l]))
    return n, {(l[7], l[8]): l[9] for l in cap.linhas}, cap.linhas


def test_versao_do_extrator():
    assert normalizar.EXTRATOR_RREO == "rp-rreo-coordenadas/2"


def test_SINTETICO_linha_de_zeros_com_numero_alinhado_a_direita_sai_inteira():
    # the case of the 31 real PDFs: the "0,00" of (e) lies nearer to the label of (f) than to the label of (e)
    # (+30 pt: v1 put it in (f) and lost (e); more would overlap the "0,00" of (f) into one word)
    n, celulas, linhas = _transcrever(textos_da_linha(EXCETO_RREO, 200, V),
                                      textos_da_linha(INTRA_RREO, 210, ZERO, deslocar={"e": 30}),
                                      textos_da_linha(TOTAL_RREO, 300, V))
    assert n == 36 and celulas[("RESTOS A PAGAR (INTRA", "e")] == 0
    assert all(l[2] == "rp-rreo-coordenadas/2" for l in linhas)
    assert celulas[("TOTAL (III)", "L")] == V["L"]


def test_SINTETICO_linha_com_numero_faltando_e_recusada_inteira():
    falta = {c: v for c, v in V.items() if c != "h"}
    with pytest.raises(normalizar.LayoutDesconhecido, match="11 número.*transcrição parcial recusada"):
        _transcrever(textos_da_linha(EXCETO_RREO, 200, V), textos_da_linha(TOTAL_RREO, 300, falta))


def test_SINTETICO_numero_fora_da_faixa_da_coluna_e_recusado():
    with pytest.raises(normalizar.LayoutDesconhecido, match=r"fora da faixa da coluna \(c\)"):
        _transcrever(textos_da_linha(EXCETO_RREO, 200, V), textos_da_linha(TOTAL_RREO, 300, V, deslocar={"c": 60}))


@pytest.mark.parametrize("coluna, identidade", [("e", "e = a + b - c - d"), ("k", "k = f + g - i - j"),
                                                ("L", "L = e + k")])
def test_SINTETICO_identidade_do_documento_que_nao_fecha_e_recusada(coluna, identidade):
    errada = {**V, coluna: V[coluna] + 1}
    with pytest.raises(normalizar.LayoutDesconhecido, match=identidade.replace("+", r"\+")):
        _transcrever(textos_da_linha(EXCETO_RREO, 200, V), textos_da_linha(TOTAL_RREO, 300, errada))


def test_SINTETICO_total_diferente_da_soma_das_linhas_e_recusado():
    outro = linha_rreo(a=V["a"] + 100, b=V["b"], c=V["c"], d=V["d"], f=V["f"], g=V["g"], h=V["h"], i=V["i"], j=V["j"])
    with pytest.raises(normalizar.LayoutDesconhecido, match=r"TOTAL \(III\) diferente de \(I\) \+ \(II\)"):
        _transcrever(textos_da_linha(EXCETO_RREO, 200, V), textos_da_linha(TOTAL_RREO, 300, outro))


def test_SINTETICO_sem_total_ou_sem_linha_I_nao_vira_transcricao_vazia():
    with pytest.raises(normalizar.LayoutDesconhecido, match=r"'TOTAL \(III\)' não encontrada"):
        _transcrever(textos_da_linha(EXCETO_RREO, 200, V))
    with pytest.raises(normalizar.LayoutDesconhecido, match=r"'RESTOS A PAGAR \(EXCETO' não encontrada"):
        _transcrever(textos_da_linha(TOTAL_RREO, 300, V))


def test_SINTETICO_linha_repetida_com_outro_valor_continua_recusada():
    outro = {**V, "h": V["h"] + 1}
    with pytest.raises(normalizar.LayoutDesconhecido, match="repetida com outro valor na coluna"):
        _transcrever(textos_da_linha(EXCETO_RREO, 200, V), textos_da_linha(TOTAL_RREO, 300, V),
                     textos_da_linha(TOTAL_RREO, 400, outro))


def test_numero_pt():
    assert numero_pt(123456) == "1.234,56" and numero_pt(-5) == "-0,05" and normalizar._centavos_pt("-1.234,56") == -123456


# ------------------------------------------------------------------ coverage matrix (rp.rreo_cobertura)
def test_SINTETICO_matriz_de_cobertura(mundo):
    import json
    from conftest import COLETOR_SINTETICO
    from rp import homologar, rreo_cobertura
    from rp.snapshots import gravar_snapshot
    anexo = "Anexo VII - Demonstrativo dos Restos a Pagar por Poder e Órgão"
    lista = [{"list": [{"subGrupoRelatorio": {"valor": anexo}, "list": [
        {"idArquivo": 7, "valor": "6º Bimestre"}, {"idArquivo": 8, "valor": "6º Bimestre - Consolidado"},
        {"idArquivo": 9, "valor": "5º Bimestre"}]}]}]
    t = "2026-09-29T10:00:00-03:00"
    gravar_snapshot(mundo.con, mundo.armazem, tipo="publicacoes", endpoint="/api/publicacoes/1",
                    parametros={"entidade": 1, "exercicio": 2025}, coletada_em=t, origem_carimbo="relogio_coletor",
                    status="completa", coletor=COLETOR_SINTETICO, finalizada_em=t,
                    respostas=[{"url": "x", "http_status": 200, "corpo": json.dumps(lista).encode()}])
    pdf = _pdf(CABECALHO_RREO + textos_da_linha(EXCETO_RREO, 200, V) + textos_da_linha(TOTAL_RREO, 300, V))
    for arq, corpo in ((7, pdf), (8, _pdf([((50, 40), "OUTRO LAYOUT")]))):
        gravar_snapshot(mundo.con, mundo.armazem, tipo="rreo_pdf", endpoint=f"/api/files/arquivo/{arq}",
                        parametros={"id_arquivo": arq, "exercicio": 2025, "entidade": 1, "rotulo": "6º Bimestre"},
                        coletada_em=t, origem_carimbo="relogio_coletor", status="completa", coletor=COLETOR_SINTETICO,
                        finalizada_em=t, respostas=[{"url": "x", "http_status": 200, "corpo": corpo}])
    mundo.catalogos({1: [2025]})
    mundo.processar()
    m = rreo_cobertura.matriz(mundo.con)
    assert m["resumo"] == {"esperados": 3, "transcrito": 1, "recusado_layout": 1, "coletado_sem_extracao": 0,
                           "nao_coletado": 1}
    por_arq = {d["id_arquivo"]: d for d in m["documentos"]}
    assert por_arq[7]["situacao"] == "transcrito" and por_arq[7]["valores"] == 24 and por_arq[7]["bimestre"] == 6
    assert por_arq[8]["situacao"] == "recusado_layout" and por_arq[8]["escopo"] == "consolidado"
    assert por_arq[9]["situacao"] == "nao_coletado" and por_arq[9]["snapshot"] is None
    tipos = {p["tipo"] for p in homologar.pendencias_contabeis(mundo.con)}
    assert {"rreo_nao_transcrito", "rreo_nao_coletado"} <= tipos
