"""Versioned layout rules of the RREO Annex VII (corrective audit of 13/10/2026, item 6.5): the portal's 2016 layout and
the print of the SICONFI declaration (2018-2020). SINTETICO = PDFs built here with PyMuPDF; the real documents were
validated cell by cell against a second engine (docs/audits/rreo/VALIDACAO_LAYOUTS.md)."""
import pytest
from conftest import EXCETO_RREO, TOTAL_RREO, linha_rreo, numero_pt

from rp import normalizar, rreo_layouts
from rp.normalizar import LayoutDesconhecido

XS = [300 + 50 * i for i in range(12)]
V = linha_rreo(a=455_000_00, b=1_275_241_67, c=1_266_236_53, d=0, f=1_283_420_45, g=4_907_516_05,
               h=4_061_528_40, i=3_993_615_21, j=752_649_51)
EXECUTIVO_2016 = [(20, "EXECUTIVO")]
EXECUTIVO_SICONFI = [(20, "PODER"), (50, "EXECUTIVO")]


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


def _linha(rotulo, y, valores, traco_no_zero=False):
    return [((x, y), w) for x, w in rotulo] + [
        ((XS[n], y), "-" if traco_no_zero and v == 0 else numero_pt(v)) for n, v in enumerate(valores.values())]


def _cabecalho_2016(ordem=rreo_layouts.ORDEM_2016):
    return ([((50, 40), "JANEIRO A FEVEREIRO 2.016/BIMESTRE JANEIRO-FEVEREIRO")]
            + [((x, 185), w) for x, w in zip(XS, ordem)])


def _cabecalho_siconfi(periodo="JANEIRO À FEVEREIRO 2018 / BIMESTRE JANEIRO-FEVEREIRO"):
    textos = [((200, 30), "Tabela 7.2 - Demonstrativo dos Restos a Pagar por Poder e Órgão - Municípios"),
              ((200, 50), periodo)]
    for x, c in zip(XS, "abcdefghijkL"):
        if c in "ekL":
            textos += [((x, 100), c), ((x + 6, 100), "="), ((x + 12, 100), "(...)")]
        else:
            textos += [((x, 100), "("), ((x + 4, 100), c), ((x + 9, 100), ")")]
    return textos


def test_SINTETICO_layout_2016_le_pelo_cabecalho_em_ordem_fixa():
    corpo = _pdf(_cabecalho_2016() + _linha(EXCETO_RREO, 220, V) + _linha(EXECUTIVO_2016, 230, V)
                 + _linha(TOTAL_RREO, 240, V))
    versao, escopo, ano, df, _, cel = rreo_layouts.extrair(corpo, {"rotulo": "1º Bimestre"})
    assert (versao, escopo, ano, df) == ("rp-rreo-2016/1", "entidade", 2016, "2016-02-29")
    assert cel[("PODER EXECUTIVO", "g")] == V["g"] and cel[("TOTAL (III)", "L")] == V["L"]
    assert len(cel) == 36


def test_SINTETICO_layout_2016_com_cabecalho_fora_da_ordem_e_recusado():
    ordem = list(rreo_layouts.ORDEM_2016)
    ordem[2], ordem[3] = ordem[3], ordem[2]              # Cancelados before Pagos: not the known layout
    with pytest.raises(LayoutDesconhecido, match="cabeçalho do layout 2016"):
        rreo_layouts.extrair(_pdf(_cabecalho_2016(ordem) + _linha(TOTAL_RREO, 240, V)), {"rotulo": "1º Bimestre"})


def test_SINTETICO_layout_2016_nao_aceita_traco_como_zero():
    corpo = _pdf(_cabecalho_2016() + _linha(EXCETO_RREO, 220, V, traco_no_zero=True)
                 + _linha(TOTAL_RREO, 240, V, traco_no_zero=True))
    with pytest.raises(LayoutDesconhecido, match="número"):
        rreo_layouts.extrair(corpo, {"rotulo": "1º Bimestre"})


def test_SINTETICO_impressao_do_siconfi_com_traco_no_zero_e_consolidada():
    corpo = _pdf(_cabecalho_siconfi() + _linha(EXCETO_RREO, 220, V, True) + _linha(EXECUTIVO_SICONFI, 230, V, True)
                 + _linha(TOTAL_RREO, 240, V, True))
    versao, escopo, ano, df, _, cel = rreo_layouts.extrair(corpo, {"rotulo": "1º Bimestre"})
    assert (versao, escopo, ano, df) == ("rp-rreo-siconfi/1", "consolidado", 2018, "2018-02-28")
    assert cel[("TOTAL (III)", "d")] == 0 and cel[("PODER EXECUTIVO", "h")] == V["h"]


def test_SINTETICO_impressao_do_siconfi_sem_periodo_ou_sem_identidade_e_recusada():
    with pytest.raises(LayoutDesconhecido, match="período"):
        rreo_layouts.extrair(_pdf(_cabecalho_siconfi("DEMONSTRATIVO") + _linha(TOTAL_RREO, 240, V)), {})
    errado = dict(V, L=V["L"] + 1)                       # L = e + k broken
    with pytest.raises(LayoutDesconhecido, match="identidade"):
        rreo_layouts.extrair(_pdf(_cabecalho_siconfi() + _linha(EXCETO_RREO, 220, errado)
                                  + _linha(TOTAL_RREO, 240, errado)), {})
    parcial = _linha(EXCETO_RREO, 220, V)[:-1]          # one number missing: partial row refused
    with pytest.raises(LayoutDesconhecido, match="transcrição parcial"):
        rreo_layouts.extrair(_pdf(_cabecalho_siconfi() + parcial + _linha(TOTAL_RREO, 240, V)), {})


class _Captura:
    def executemany(self, sql, linhas):
        self.linhas = list(linhas)

        class R:
            rowcount = len(self.linhas)
        return R()


def test_SINTETICO_normalizador_usa_a_regra_de_layout_so_quando_o_extrator_recusa():
    cap = _Captura()
    corpo = _pdf(_cabecalho_siconfi() + _linha(EXCETO_RREO, 220, V) + _linha(TOTAL_RREO, 240, V))
    n, versao = normalizar._transcrever_rreo(cap, 1, 1, {"rotulo": "1º Bimestre"}, corpo)
    assert versao == "rp-rreo-siconfi/1" and n == 24 and all(l[2] == versao for l in cap.linhas)
    with pytest.raises(LayoutDesconhecido, match="regras de layout versionadas"):
        normalizar._transcrever_rreo(cap, 1, 1, {}, _pdf([((50, 40), "OUTRO DOCUMENTO")]))
    assert normalizar.VERSAO == "rp-normalizador/3"
