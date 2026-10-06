"""'Origem do dado: onde conferir no Portal' (requested by the owner, 06/10/2026): each value leads to the place in
the Portal da Transparencia where it is found, with the conditions of each path; the technical record (snapshot) stays
collapsed. Uses the temporary database built from the real store (fixture `real`): read-only, no network connection."""
import html
import re
from urllib.parse import parse_qs, urlsplit

import pytest
from conftest import ok

from rp.interface import Aplicacao
from rp.interface import portal as P


@pytest.fixture(scope="module")
def app(real):
    return Aplicacao(real["cfg"].banco)


def _links(corpo):
    return [(html.unescape(h), t) for h, t in re.findall(r'<a href="([^"]+)" rel="external noopener noreferrer">([^<]+)</a>',
                                                         corpo)]


def _q(url):
    return parse_qs(urlsplit(url).query)


def test_enderecos_do_portal():
    assert P.url_empenho(1, 2025, 5659) == ("https://servicos.pontagrossa.pr.gov.br/portaltransparencia/1/empenhos/detalhe"
                                            "?search=id.entidade==1&entidade=1&exercicio=2025&empenho=5659")
    u = P.url_integra(15, 2026, "2026-04-30", 2, empenho=7, anoempenho=2024)
    assert u.startswith("https://servicos.pontagrossa.pr.gov.br/portaltransparencia-api/empenhos/restos-a-pagar?")
    q = _q(u)
    assert (q["entidade"], q["exercicio"], q["dataInicial"], q["dataFinal"]) == (["15"], ["2026"], ["2026-01-01"],
                                                                                  ["2026-04-30"])
    assert (q["empenho"], q["anoempenho"], q["size"], q["page"], q["sort"]) == (["7"], ["2024"], ["2000"], ["2"],
                                                                                ["anoempenho,asc", "empenho,asc"])
    assert P.url_consulta(15) == "https://servicos.pontagrossa.pr.gov.br/portaltransparencia/15/restos-a-pagar"
    assert P.url_pdf(2560662) == "https://servicos.pontagrossa.pr.gov.br/portaltransparencia-api/api/files/arquivo/2560662"
    assert P.url_publicacoes_rreo() == "https://servicos.pontagrossa.pr.gov.br/portaltransparencia/1/publicacoes/1/15"
    assert [P.paginas(n) for n in (0, 1, 2000, 2001, 4557)] == [1, 1, 1, 2, 3]


def test_resumo_traz_a_integra_de_cada_entidade_do_total_e_as_condicoes(app):
    corpo = ok(app, "/", exercicio=2026, data_final="2026-08-31")
    secao = corpo[corpo.index('id="onde-conferir"'):]
    secao = secao[:secao.index("</section>")]
    integras = [u for u, _ in _links(secao) if "/empenhos/restos-a-pagar?" in u]
    prefeitura = [u for u in integras if _q(u)["entidade"] == ["1"]]
    assert [_q(u)["page"] for u in prefeitura] == [["0"], ["1"], ["2"]]           # 4,557 records: 3 pages
    assert all(_q(u)["dataFinal"] == ["2026-08-31"] for u in integras)
    assert any(u == P.url_consulta(15) for u, _ in _links(secao))
    for condicao in ("o portal não soma", "Íntegra:", "equivale ao corte 31/12", "sem retenção nem estorno"):
        assert condicao in secao, condicao


def test_cartao_diz_em_que_coluna_da_tela_e_guarda_o_registro_tecnico(app):
    corpo = ok(app, "/", exercicio=2026, data_final="2026-08-31")
    cartoes = dict(re.findall(r'<data class="valor" id="ind-([a-z_]+)".*?(<details class="origem">.*?</details></details>)',
                              corpo, re.S))
    assert "aba Processados, coluna “Valor Pago”" in cartoes["pago_processado"]
    assert "aba Não Processados, coluna “Valor Liquidado”" in cartoes["liquidacoes"]
    assert "não aparece na tela de consulta" in cartoes["retencoes"]
    assert "O portal não mostra este total" in cartoes["saldo_total"]
    for c in cartoes.values():
        assert 'href="#onde-conferir"' in c and "Registro técnico (auditoria)" in c
        assert re.search(r"<code>[0-9a-f]{32}</code>", c.split("Registro técnico")[1])   # the snapshot is still there


def test_empenho_leva_ao_proprio_empenho_no_corte_ao_detalhe_e_a_tela(app):
    corpo = ok(app, "/empenho", entidade=1, anoempenho=2025, empenho=5659, exercicio=2026, data_final="2026-08-31")
    origem = corpo[corpo.index('id="origem"'):]
    links = dict((t, u) for u, t in _links(origem))
    q = _q(links["Este empenho no corte"])
    assert (q["empenho"], q["anoempenho"], q["dataFinal"], q["exercicio"]) == (["5659"], ["2025"], ["2026-08-31"], ["2026"])
    assert links["Detalhe do empenho no portal"] == P.url_empenho(1, 2025, 5659)       # exercicio = year of the COMMITMENT
    assert links["Página da íntegra onde ele estava na coleta"].startswith(P.API + "/empenhos/restos-a-pagar?")
    assert links["Tela de consulta"] == P.url_consulta(1)
    assert "exercício 2026 no topo, Empenho 5659, Ano 2025" in origem
    assert "Registro técnico (auditoria)" in origem and "Objeto bruto (SHA-256)" in origem
    assert P.url_empenho(1, 2025, 5659) in html.unescape(corpo[corpo.index("<h2>Movimentações</h2>"):])


def test_rreo_leva_ao_pdf_publicado(app):
    corpo = ok(app, "/reconciliacao", exercicio=2026, data_final="2026-08-31", escopo="entidade")
    pdfs = [u for u, _ in _links(corpo) if "/api/files/arquivo/" in u]
    assert pdfs and all(re.fullmatch(re.escape(P.API) + r"/api/files/arquivo/\d+", u) for u in pdfs)
    assert any(u == P.url_publicacoes_rreo() for u, _ in _links(corpo))
