"""Regression of the post-05 consolidation: the choice of fiscal year and cut-off never swaps what was requested for
something else.

Before: a requested fiscal year or cut-off that did not exist was swapped for the most recent one (with a warning; on
the pairs screen, without one), and the variation swapped the requested pair. Now:
* nothing requested -> default (the most recent cut-off with the full Municipality), as before;
* requested cut-off not processed -> the screen shows that cut-off, warns, lists the fiscal year's processed cut-offs
  and shows the data situation from the panel layer, without any value;
* requested fiscal year without a processed cut-off -> "Sem dados processados", with the available fiscal years;
* impossible pair in the variation -> unavailable with the reason, without swapping either cut-off.
SINTETICO = temporary database with invented records (fixture `mundo`).
"""
import re
from pathlib import Path

import pytest
from conftest import chamar, dados, registro_sintetico as _reg

from rp.interface import Aplicacao

T0 = "2026-09-29T20:00:00-03:00"
ROTAS_DO_CORTE = ("/", "/composicao", "/entidades", "/empenhos", "/pares")
ROTAS_DO_EXERCICIO = ROTAS_DO_CORTE + ("/evolucao", "/variacao")


@pytest.fixture
def app(mundo):
    """2025, entities 1 and 15 (15 without RP): 28/02 and 30/04 with both; 30/06 only entity 1 (Municipality
    unavailable). No cut-off on 31/03/2025 nor in fiscal year 2024."""
    mundo.catalogos({1: [2025], 15: [2025]})
    antes = [_reg(1, ano=2024, aproc=100.0), _reg(2, ano=2024, aproc=50.0)]
    depois = [_reg(1, ano=2024, aproc=100.0, pagoAProc=30.0), _reg(2, ano=2024, aproc=50.0)]
    for df, regs in (("2025-02-28", antes), ("2025-04-30", depois)):
        mundo.listagem(1, 2025, df, regs, T0)
        mundo.listagem(15, 2025, df, [], T0)
    mundo.listagem(1, 2025, "2025-06-30", depois, T0)
    mundo.processar()
    return Aplicacao(mundo.cfg.banco)


def _pagina(app, caminho, **params):
    status, _, corpo = chamar(app, caminho, **params)
    assert status == "200 OK", (caminho, params, status)
    h1 = re.search(r"<h1>(.*?)</h1>", corpo).group(1)
    return corpo, h1


def test_SINTETICO_padrao_sem_pedido_continua_o_mesmo(app):
    for params in ({}, {"exercicio": 2025}):
        corpo, h1 = _pagina(app, "/", **params)
        assert "corte 30/04/2025" in h1                      # most recent with the full Municipality (30/06 does not have it)
        assert "nenhum outro corte é mostrado" not in corpo and dados(corpo)
        corpo, h1 = _pagina(app, "/variacao", **params)
        assert "28/02/2025 → 30/04/2025" in h1 and dados(corpo)


def test_SINTETICO_corte_pedido_nao_processado_nunca_e_trocado(app):
    for rota in ROTAS_DO_CORTE:
        corpo, h1 = _pagina(app, rota, exercicio=2025, data_final="2025-03-31")
        assert "31/03/2025" in h1, (rota, h1)
        for outro in ("28/02/2025", "30/04/2025", "30/06/2025"):
            assert outro not in h1, (rota, h1)
        aviso = re.search(r'<p class="aviso">(Corte 31/03/2025 não processado.*?)</p>', corpo)
        assert aviso, rota
        assert "nenhum outro corte é mostrado" in aviso.group(1)
        assert "28/02/2025, 30/04/2025, 30/06/2025" in aviso.group(1)     # offers the processed cut-offs
        assert dados(corpo) == {}, rota                                    # no value, not even zero
        assert "R$ 0,00" not in corpo, rota
        if rota != "/entidades":                                           # entities: situation per row
            assert 'id="indisponivel"' in corpo, rota
    corpo, _ = _pagina(app, "/", exercicio=2025, data_final="2025-03-31")
    assert "corte não coletado" in corpo                                   # data situation, from the panel layer


def test_SINTETICO_exercicio_pedido_sem_corte_nunca_e_trocado(app):
    for rota in ROTAS_DO_EXERCICIO:
        for params in ({"exercicio": 2024}, {"exercicio": 2024, "data_final": "2024-12-31"}):
            corpo, h1 = _pagina(app, rota, **params)
            assert h1 == "Sem dados processados", (rota, params, h1)
            assert "Exercício 2024 sem corte processado" in corpo and "Exercícios com corte processado: 2025" in corpo
            assert dados(corpo) == {}, rota


def test_SINTETICO_variacao_par_pedido_nunca_e_trocado(app):
    # requested later = first cut-off: there is no earlier one; before, it was swapped for the pair of the first two cut-offs
    corpo, h1 = _pagina(app, "/variacao", exercicio=2025, data_final="2025-02-28")
    assert "não há corte processado anterior a 28/02/2025" in corpo and 'id="indisponivel"' in corpo
    assert dados(corpo) == {} and "30/04/2025" not in h1
    # earlier after the later: before, it was swapped for the cut-off immediately before
    corpo, h1 = _pagina(app, "/variacao", exercicio=2025, anterior="2025-04-30", data_final="2025-02-28")
    assert "o corte anterior (30/04/2025) precisa ser anterior ao posterior (28/02/2025)" in corpo
    assert dados(corpo) == {}
    # requested earlier not processed: goes on to the panel layer, which says why the pair has no value
    corpo, h1 = _pagina(app, "/variacao", exercicio=2025, anterior="2025-03-31", data_final="2025-04-30")
    assert "31/03/2025 → 30/04/2025" in h1 and 'id="indisponivel"' in corpo and dados(corpo) == {}
    # requested later not processed: the default earlier is the processed cut-off immediately before it
    corpo, h1 = _pagina(app, "/variacao", exercicio=2025, data_final="2025-03-31")
    assert "28/02/2025 → 31/03/2025" in h1 and 'id="indisponivel"' in corpo and dados(corpo) == {}


def test_nenhuma_tela_anuncia_troca_de_corte():
    pasta = Path(__file__).resolve().parents[1] / "rp" / "interface" / "paginas"
    fonte = "\n".join(p.read_text(encoding="utf-8") for p in sorted(pasta.glob("*.py")))
    assert "def variacao(" in fonte                     # the pages package was read
    for texto in ("mostrado outro corte", "mostrado o exercício mais recente", "mostrado o par",
                  "mostrado o corte imediatamente anterior"):
        assert texto not in fonte
