"""Regressao da consolidacao pos-05: a selecao de exercicio e corte nunca troca o que foi pedido por outro.

Antes: exercicio ou corte pedido inexistente era trocado pelo mais recente (com aviso; na tela de pares, sem aviso),
e a variacao trocava o par pedido. Agora:
* nada pedido -> padrao (o corte mais recente com o Municipio completo), como antes;
* corte pedido nao processado -> a tela mostra esse corte, avisa, lista os cortes processados do exercicio e mostra a
  situacao do dado vinda da camada painel, sem nenhum valor;
* exercicio pedido sem corte processado -> "Sem dados processados", com os exercicios disponiveis;
* par impossivel na variacao -> indisponivel com o motivo, sem trocar nenhum dos dois cortes.
SINTETICO = banco temporario com registros inventados (fixture `mundo`).
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
    """2025, entidades 1 e 15 (a 15 sem RP): 28/02 e 30/04 com as duas; 30/06 so a entidade 1 (Municipio
    indisponivel). Nenhum corte em 31/03/2025 nem no exercicio 2024."""
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
        assert "corte 30/04/2025" in h1                      # mais recente com o Municipio completo (30/06 nao tem)
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
        assert "28/02/2025, 30/04/2025, 30/06/2025" in aviso.group(1)     # oferece os cortes processados
        assert dados(corpo) == {}, rota                                    # nenhum valor, nem zero
        assert "R$ 0,00" not in corpo, rota
        if rota != "/entidades":                                           # entidades: situacao por linha
            assert 'id="indisponivel"' in corpo, rota
    corpo, _ = _pagina(app, "/", exercicio=2025, data_final="2025-03-31")
    assert "corte não coletado" in corpo                                   # situacao do dado, da camada painel


def test_SINTETICO_exercicio_pedido_sem_corte_nunca_e_trocado(app):
    for rota in ROTAS_DO_EXERCICIO:
        for params in ({"exercicio": 2024}, {"exercicio": 2024, "data_final": "2024-12-31"}):
            corpo, h1 = _pagina(app, rota, **params)
            assert h1 == "Sem dados processados", (rota, params, h1)
            assert "Exercício 2024 sem corte processado" in corpo and "Exercícios com corte processado: 2025" in corpo
            assert dados(corpo) == {}, rota


def test_SINTETICO_variacao_par_pedido_nunca_e_trocado(app):
    # posterior pedido = primeiro corte: nao ha anterior; antes era trocado pelo par dos dois primeiros cortes
    corpo, h1 = _pagina(app, "/variacao", exercicio=2025, data_final="2025-02-28")
    assert "não há corte processado anterior a 28/02/2025" in corpo and 'id="indisponivel"' in corpo
    assert dados(corpo) == {} and "30/04/2025" not in h1
    # anterior depois do posterior: antes era trocado pelo corte imediatamente anterior
    corpo, h1 = _pagina(app, "/variacao", exercicio=2025, anterior="2025-04-30", data_final="2025-02-28")
    assert "o corte anterior (30/04/2025) precisa ser anterior ao posterior (28/02/2025)" in corpo
    assert dados(corpo) == {}
    # anterior pedido nao processado: segue para a camada painel, que diz por que o par nao tem valor
    corpo, h1 = _pagina(app, "/variacao", exercicio=2025, anterior="2025-03-31", data_final="2025-04-30")
    assert "31/03/2025 → 30/04/2025" in h1 and 'id="indisponivel"' in corpo and dados(corpo) == {}
    # posterior pedido nao processado: o anterior padrao e o corte processado imediatamente anterior a ele
    corpo, h1 = _pagina(app, "/variacao", exercicio=2025, data_final="2025-03-31")
    assert "28/02/2025 → 31/03/2025" in h1 and 'id="indisponivel"' in corpo and dados(corpo) == {}


def test_nenhuma_tela_anuncia_troca_de_corte():
    fonte = (Path(__file__).resolve().parents[1] / "rp" / "interface" / "paginas.py").read_text(encoding="utf-8")
    for texto in ("mostrado outro corte", "mostrado o exercício mais recente", "mostrado o par",
                  "mostrado o corte imediatamente anterior"):
        assert texto not in fonte
