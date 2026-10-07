"""Tests of sub-stage 05.2: evolution within the fiscal year (contract M-01 and M-02; plan, section 05.2).

* panel layer: `Painel.evolucao` with the full universe of cut-offs (R1), the situation of each point, the label of a
  cut-off after the collection (R4) and a difference only between adjacent points with a value;
* interface: /evolucao screen with an SVG chart (a gap is a gap), a table of exact values and a table of differences;
* independent validation: the panel's series = the one recalculated from the raw JSON (recalculo_bruto.py), to the cent.
SINTETICO = temporary database with invented records (fixture `mundo`).
"""
import ast
import re
import time
from pathlib import Path

import pytest
from conftest import RAIZ_PROJETO, chamar, dados, ok, registro_sintetico as _reg, links_permitidos

import recalculo_bruto as rb
from rp.interface import Aplicacao
from rp.painel.consulta import INDICADORES_DA_SERIE, ROTULO_POSTERIOR_A_COLETA, SITUACOES_DO_PONTO

T0 = "2026-09-29T20:00:00-03:00"


# ================================================================== SINTETICO
@pytest.fixture
def serie_sintetica(mundo):
    """2025: entity 1 at 3 cut-offs; entity 15 without the 30/04 cut-off (a gap in the middle). 2026: a 31/12 cut-off
    collected on 29/09/2026 (after the collection) only for entity 1; entity 15 existing with zero records on 31/08/2026."""
    mundo.catalogos({1: [2025, 2026], 15: [2025, 2026]})
    for df, pago in (("2025-02-28", 10.0), ("2025-04-30", 30.0), ("2025-06-30", 35.0)):
        mundo.listagem(1, 2025, df, [_reg(1, aproc=100.0, pagoAProc=pago, liquidado=pago)], T0)
    mundo.listagem(15, 2025, "2025-02-28", [_reg(1, entidade=15, aproc=50.0)], T0)
    mundo.listagem(15, 2025, "2025-06-30", [_reg(1, entidade=15, aproc=50.0, pagoAProc=20.0)], T0)
    mundo.listagem(1, 2026, "2026-08-31", [_reg(1, ano=2025, aproc=10.0)], T0)
    mundo.listagem(15, 2026, "2026-08-31", [], T0)
    mundo.listagem(1, 2026, "2026-12-31", [_reg(1, ano=2025, aproc=10.0, pagoAProc=2.0)], T0)
    mundo.processar()
    return mundo


def test_SINTETICO_serie_tem_todos_os_cortes_e_lacuna_nunca_vira_zero(serie_sintetica):
    with serie_sintetica.painel() as p:
        s15 = p.evolucao(2025, 15)["serie"]
        assert [x["data_final"] for x in s15] == ["2025-02-28", "2025-04-30", "2025-06-30"]          # R1
        assert [x["situacao"]["codigo"] for x in s15] == ["com_dados", "sem_coleta", "com_dados"]
        lacuna = s15[1]
        assert not lacuna["tem_valor"] and all(v["valor_c"] is None for v in lacuna["valores"].values())
        assert lacuna["situacao"]["texto"] == SITUACOES_DO_PONTO["sem_coleta"]
        for x in s15[1:]:                                                     # never against a gap nor skipping one
            d = x["diferenca_para_o_anterior"]
            assert d["motivo_indisponivel"] and all(v is None for v in d["valores"].values())
        mun = p.evolucao(2025)["serie"]
        assert [x["situacao"]["codigo"] for x in mun] == ["com_dados", "municipio_indisponivel", "com_dados"]
        assert "corte não coletado para a(s) entidade(s) [15]" in mun[1]["motivo_indisponivel"]


def test_SINTETICO_diferenca_posterior_menos_anterior_com_proveniencia_dos_dois_lados(serie_sintetica):
    with serie_sintetica.painel() as p:
        s1 = p.evolucao(2025, 1)["serie"]
        assert s1[0]["diferenca_para_o_anterior"] is None
        d = s1[1]["diferenca_para_o_anterior"]
        assert d["natureza"] == "diferenca" and d["sinal"] == "posterior − anterior" and d["anterior"] == "2025-02-28"
        assert d["valores"]["pagamentos"] == 2000 and d["valores"]["saldo_total"] == -2000
        assert d["valores"]["inscricao_total"] == 0 and d["valores"]["liquidacoes"] == 2000
        assert s1[2]["diferenca_para_o_anterior"]["valores"]["saldo_total"] == -500
        assert d["proveniencia"]["anterior"]["snapshots"] != d["proveniencia"]["posterior"]["snapshots"]
        for lado in ("anterior", "posterior"):
            assert d["proveniencia"][lado]["derivacao_id"] == p.contexto()["derivacao"]["id"]


def test_SINTETICO_zero_verdadeiro_e_corte_posterior_a_coleta(serie_sintetica):
    with serie_sintetica.painel() as p:
        s15 = {x["data_final"]: x for x in p.evolucao(2026, 15)["serie"]}
        zero = s15["2026-08-31"]
        assert zero["situacao"]["codigo"] == "sem_rp" and zero["valores"]["saldo_total"]["valor_c"] == 0
        assert s15["2026-12-31"]["situacao"]["codigo"] == "sem_coleta" and s15["2026-12-31"]["rotulos"] == []
        s1 = {x["data_final"]: x for x in p.evolucao(2026, 1)["serie"]}
        assert s1["2026-12-31"]["rotulos"] == [ROTULO_POSTERIOR_A_COLETA] and s1["2026-08-31"]["rotulos"] == []   # R4
        mun = {x["data_final"]: x for x in p.evolucao(2026)["serie"]}
        assert mun["2026-12-31"]["situacao"]["codigo"] == "municipio_indisponivel" and mun["2026-12-31"]["rotulos"] == []


def test_SINTETICO_tela_mostra_lacunas_e_o_grafico_e_conforme(serie_sintetica):
    app = Aplicacao(serie_sintetica.cfg.banco)
    status, cab, corpo = chamar(app, "/evolucao", exercicio=2025, entidade=15)
    assert status == "200 OK" and "default-src 'none'" in cab["Content-Security-Policy"]
    assert 'id="lacuna-2025-04-30"' in corpo and 'id="dif-lacuna-2025-04-30"' in corpo
    assert 'id="dif-lacuna-2025-06-30"' in corpo and "dif-2025-06-30-" not in corpo      # does not skip the gap
    linha = re.search(r'id="lacuna-2025-04-30".*?</tr>', corpo, re.S).group(0)
    assert "R$" not in linha and "sem valor" in linha
    svg = re.search(r"<svg.*?</svg>", corpo, re.S).group(0)
    assert "style=" not in svg and "<style" not in svg and "<script" not in corpo.lower()
    assert svg.count('class="ponto"') == 3 and svg.count('class="lacuna"') == 1
    assert links_permitidos(corpo)
    assert re.search(r'role="img" aria-labelledby="graf-s1-t graf-s1-d"', svg)
    zero = ok(app, "/evolucao", exercicio=2026, entidade=15)
    svg0 = re.search(r"<svg.*?</svg>", zero, re.S).group(0)
    assert svg0.count('class="zero"') == 1 and svg0.count('class="lacuna"') == 1   # zero drawn as zero
    assert dados(zero)["ser-2026-08-31-saldo_total"] == 0
    assert ROTULO_POSTERIOR_A_COLETA in ok(app, "/evolucao", exercicio=2026, entidade=1)


def test_grafico_nao_faz_aritmetica_de_valores_monetarios():
    arvore = ast.parse((RAIZ_PROJETO / "app" / "rp" / "interface" / "grafico.py").read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, ast.BinOp) and isinstance(no.op, (ast.Add, ast.Sub)):
            for lado in (no.left, no.right):
                chave = getattr(getattr(lado, "slice", None), "value", None)
                assert not (isinstance(lado, ast.Subscript) and isinstance(chave, str) and chave.endswith("_c")), no.lineno
        assert not (isinstance(no, ast.Call) and getattr(no.func, "id", None) == "sum"), no.lineno


# ================================================================== real store
@pytest.fixture(scope="module")
def app_real(real):
    return Aplicacao(real["cfg"].banco)


@pytest.fixture(scope="module")
def bruto_real(real):
    return rb.Bruto(real["con"], real["armazem"])


@pytest.mark.parametrize("ex", [2025, 2026])
def test_serie_do_painel_igual_a_recalculada_do_bruto(real, bruto_real, ex):
    p = real["painel"]
    for ent in [None] + [e["entidade"] for e in p.entidades()["entidades"]]:
        serie, esperado = p.evolucao(ex, ent)["serie"], bruto_real.serie(ex, ent)
        assert [x["data_final"] for x in serie] == [x["data_final"] for x in esperado], (ex, ent)
        anterior = None
        for x, e in zip(serie, esperado):
            assert x["situacao"]["codigo"] == e["situacao"] and x["tem_valor"] == e["tem_valor"], (ex, ent, x["data_final"])
            valores = {k: v["valor_c"] for k, v in x["valores"].items()}
            assert valores == (e["valores"] or dict.fromkeys(valores)), (ex, ent, x["data_final"])
            if anterior is not None:                  # difference recalculated from the raw data, independently
                d = x["diferenca_para_o_anterior"]["valores"]
                for k in INDICADORES_DA_SERIE:
                    ant = anterior["valores"] and anterior["valores"][k]
                    pos = e["valores"] and e["valores"][k]
                    assert d[k] == rb.diferenca(ant, pos), (ex, ent, x["data_final"], k)
            anterior = e


def test_lacunas_reais_de_2026(real):
    p = real["painel"]
    mun = {x["data_final"]: x for x in p.evolucao(2026)["serie"]}
    for df in ("2026-01-31", "2026-03-31", "2026-12-31"):
        assert mun[df]["situacao"]["codigo"] == "municipio_indisponivel"
        assert mun[df]["motivo_indisponivel"] == "corte não coletado para a(s) entidade(s) [4, 5, 8, 15]"
    for ent in (5, 15):
        s = {x["data_final"]: x["situacao"]["codigo"] for x in p.evolucao(2026, ent)["serie"]}
        assert len(s) == 7 and [df for df, c in s.items() if c == "sem_coleta"] == ["2026-01-31", "2026-03-31",
                                                                                   "2026-12-31"]
    um = {x["data_final"]: x for x in p.evolucao(2026, 1)["serie"]}
    assert um["2026-12-31"]["rotulos"] == [ROTULO_POSTERIOR_A_COLETA]                                    # R4


def test_inscricao_estavel_dentro_do_exercicio(real):
    """05.2 stopping criterion: the inscription does not vary between cut-offs of the same fiscal year (that would be a
    retroactive change)."""
    p = real["painel"]
    for ex in (2025, 2026):
        for ent in [None] + [e["entidade"] for e in p.entidades()["entidades"]]:
            inscricoes = {x["valores"]["inscricao_total"]["valor_c"] for x in p.evolucao(ex, ent)["serie"] if x["tem_valor"]}
            assert len(inscricoes) <= 1, (ex, ent, inscricoes)


@pytest.mark.parametrize("ex, ent", [(2025, None), (2026, None), (2026, 15), (2026, 1)])
def test_tela_igual_ao_painel(real, app_real, ex, ent):
    serie = real["painel"].evolucao(ex, ent)["serie"]
    corpo = ok(app_real, "/evolucao", exercicio=ex, entidade=ent)
    v = dados(corpo)
    assert corpo.count("<tr><td><a href=\"/resumo?") == len(serie)                     # one row per cut-off of the universe
    svg = re.search(r"<svg.*?</svg>", corpo, re.S).group(0)
    assert svg.count('class="ponto"') == len(serie) and svg.count('class="lacuna"') == sum(1 for x in serie
                                                                                          if not x["tem_valor"])
    for x in serie:
        df = x["data_final"]
        if x["tem_valor"]:
            for k in INDICADORES_DA_SERIE:
                assert v[f"ser-{df}-{k}"] == x["valores"][k]["valor_c"], (df, k)
        else:
            assert f'id="lacuna-{df}"' in corpo and not any(k.startswith(f"ser-{df}-") for k in v)
        d = x["diferenca_para_o_anterior"]
        if d and not d["motivo_indisponivel"]:
            for k in INDICADORES_DA_SERIE:
                assert v[f"dif-{df}-{k}"] == d["valores"][k], (df, k)
        elif d:
            assert f'id="dif-lacuna-{df}"' in corpo and not any(k.startswith(f"dif-{df}-") for k in v)
    if ent in (None, 1, 15):
        assert 'id="aviso-pares"' in corpo


def test_metodologia_e_navegacao(app_real):
    assert SITUACOES_DO_PONTO["municipio_indisponivel"] in ok(app_real, "/metodologia")
    resumo = ok(app_real, "/resumo", exercicio=2025, data_final="2025-12-31")
    assert 'href="/evolucao?exercicio=2025"' in resumo
    assert '<a href="/evolucao"' in resumo                                         # menu item


def test_desempenho_da_tela_de_evolucao(app_real):
    for ex, ent in ((2025, None), (2026, None), (2026, 1)):
        t = time.perf_counter()
        status, _, _ = chamar(app_real, "/evolucao", exercicio=ex, entidade=ent)
        assert status == "200 OK" and time.perf_counter() - t < 3, (ex, ent)
