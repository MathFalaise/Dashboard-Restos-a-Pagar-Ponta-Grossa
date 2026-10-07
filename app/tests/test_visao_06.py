"""Tests of stage 06: the overview (/) with pies and columns (docs/stages/06-bi/SCOPE.md).

* panel layer (Painel.visao_geral): every pie closes against its total to the cent, shares in tenths of a point add
  up to exactly 1000 (100,0%), a negative part never becomes a pie, "demais" is the sum of the groups outside the top;
* independent validation: the partitions recalculated from the raw JSON (recalculo_bruto.py) in every cut-off;
* interface: every <data id> of the page equals the panel layer; a cut-off without data is a gap, never zero; the
  requested cut-off is never swapped; the old summary lives at /resumo;
* charts: geometry (sectors, whole ring, gaps, zero) and the formatting of abbreviated values and shares.
SINTETICO = temporary database with invented records (fixture `mundo`).
"""
import random
import re

import pytest
from conftest import chamar, dados, links_permitidos, ok, registro_sintetico as _reg

import recalculo_bruto as rb
from rp.interface import Aplicacao, formato as fm, grafico
from rp.painel import classificacao
from rp.painel.consulta.visao import decimos_de_percentual, particao, razao_em_decimos

T0 = "2026-09-29T20:00:00-03:00"
ORC = {"orgao": "09", "funcao": "12", "programa": "0076", "elemento": "3390390000"}


# ================================================================== rules of the panel layer (no database)
def test_percentual_pelo_maior_resto_soma_sempre_1000():
    assert decimos_de_percentual([1, 1, 1], 3) == [334, 333, 333]              # tie: the earlier item
    assert decimos_de_percentual([0, 5], 5) == [0, 1000]
    assert decimos_de_percentual([11708659495, 960312350, 7865215606], 20534187451) == [570, 47, 383]
    gerador = random.Random(6)
    for _ in range(3000):
        partes = [gerador.randint(0, 10 ** gerador.randint(0, 12)) for _ in range(gerador.randint(1, 12))]
        total = sum(partes)
        if total == 0:
            continue
        d = decimos_de_percentual(partes, total)
        assert sum(d) == 1000
        assert all(v * 1000 // total <= x <= v * 1000 // total + 1 for v, x in zip(partes, d))
    with pytest.raises(ValueError):
        decimos_de_percentual([5, -1], 4)
    with pytest.raises(ValueError):
        decimos_de_percentual([0], 0)


def test_razao_em_decimos_arredonda_meio_para_cima():
    assert razao_em_decimos(11708659495, 20534187451) == 570
    assert razao_em_decimos(1, 2000) == 1 and razao_em_decimos(1, 2001) == 0       # 0,05% -> 0,1%; 0,0499% -> 0,0%
    assert razao_em_decimos(5, 0) is None and razao_em_decimos(None, 5) is None


def test_particao_fecha_ou_nao_desenha():
    itens = [{"chave": "a", "rotulo": "a", "valor_c": 70}, {"chave": "b", "rotulo": "b", "valor_c": 30}]
    ok_ = particao(100, itens)
    assert ok_["pizza"] and ok_["fechamento"]["fecha"] and [i["decimos"] for i in ok_["itens"]] == [700, 300]
    nao_fecha = particao(101, itens)
    assert not nao_fecha["pizza"] and "não somam o total" in nao_fecha["motivo"]
    assert all("decimos" not in i for i in nao_fecha["itens"])
    negativo = particao(100, [{"chave": "a", "rotulo": "a", "valor_c": 110}, {"chave": "b", "rotulo": "b", "valor_c": -10}])
    assert negativo["fechamento"]["fecha"] and not negativo["pizza"] and "negativa" in negativo["motivo"]
    zero = particao(0, [{"chave": "a", "rotulo": "a", "valor_c": 0}])
    assert not zero["pizza"] and "total zero" in zero["motivo"]


def test_demais_soma_os_grupos_fora_do_topo():
    itens = [{"chave": str(i), "rotulo": str(i), "valor_c": v, "filtro": {"x": i}} for i, v in enumerate([5, 50, 7, 30, 8])]
    r = particao(100, itens, topo=2)
    assert [i["chave"] for i in r["itens"]] == ["1", "3", "demais"]
    demais = r["itens"][-1]
    assert demais["valor_c"] == 20 and demais["agrupa"] == 3 and demais["filtro"] is None
    assert r["pizza"] and sum(i["decimos"] for i in r["itens"]) == 1000
    assert [i["chave"] for i in particao(100, itens[:3], topo=2)["itens"]] == ["0", "1", "2"]   # one left: no "demais"


def test_nomes_das_funcoes_de_governo():
    assert classificacao.nome_da_funcao("10") == "Saúde" and classificacao.nome_da_funcao("4") == "Administração"
    assert classificacao.nome_da_funcao("99") is None and classificacao.nome_da_funcao(None) is None
    assert sorted(classificacao.FUNCOES) == [f"{i:02d}" for i in range(1, 29)]
    assert "Portaria MOG nº 42" in classificacao.FONTE_FUNCOES


# ================================================================== formatting and charts (no database)
def test_valor_abreviado_e_percentual():
    assert fm.abreviado(7865215606) == "R$ 78,7 mi" and fm.abreviado(20534187451) == "R$ 205,3 mi"
    assert fm.abreviado(94999999) == "R$ 950,0 mil" and fm.abreviado(95000000) == "R$ 1,0 mi"
    assert fm.abreviado(12345678901234) == "R$ 123,5 bi" and fm.abreviado(-960312350) == "-R$ 9,6 mi"
    assert fm.abreviado(51230) == "R$ 512,30" and fm.abreviado(0) == "R$ 0,00" and fm.abreviado(None) is None
    with pytest.raises(TypeError):
        fm.abreviado(1.5)
    assert fm.percentual(383) == "38,3%" and fm.percentual(1000) == "100,0%" and fm.percentual(5) == "0,5%"
    html = fm.valor_abreviado(7865215606, "x")
    assert 'value="7865215606"' in html and 'title="R$ 78.652.156,06"' in html and ">R$ 78,7 mi<" in html


def test_pizza_desenha_um_setor_por_parte_positiva():
    fatias = [dict(rotulo="pago", valor_c=600, decimos=600, classe="c3", href="/x"),
              dict(rotulo="cancelado", valor_c=0, decimos=0, classe="c8"),
              dict(rotulo="em aberto", valor_c=400, decimos=400, classe="c2")]
    h = grafico.pizza("p", "Título", "Descrição", 1000, fatias, ("R$ 10,00", "inscrito"))
    assert h.count('<path class="fatia') == 2 and h.count("<li>") == 3          # zero: legend only
    assert 'role="img"' in h and 'id="p-t"' in h and 'id="p-d"' in h and "style" not in h
    assert h.count('<data value="') == 3 and ">60,0%<" in h and ">0,0%<" in h
    inteiro = grafico.pizza("q", "T", "D", 5, [dict(rotulo="a", valor_c=5, decimos=1000, classe="c1")], ("x", "y"))
    assert 'fill-rule="evenodd"' in inteiro and inteiro.count('<path class="fatia') == 1


def test_colunas_lacuna_zero_e_escala():
    grupos = [dict(rotulo="31/01", valores=[None, None], titulos=["a", "b"]),
              dict(rotulo="28/02", valores=[150000, None], titulos=["a", "b"], href="/resumo"),
              dict(rotulo="31/03", valores=[0, 70000], titulos=["a", "b"])]
    h = grafico.colunas("c", "T", "D", grupos, [("Saldo", "c2"), ("Pago", "c3")])
    assert h.count('class="lacuna"') == 2 and h.count(">sem dado<") == 1        # one gap for the empty cut-off
    assert h.count('class="zero"') == 1 and h.count('class="coluna c') == 2 and "style" not in h
    for maior in [1, 9, 10, 99, 647339, 14423603293, 25055105773] + [random.Random(i).randint(1, 10 ** 13) for i in range(500)]:
        passo = grafico._passo(maior)
        assert passo > 0 and 1 <= -(-maior // passo) <= 5, maior


# ================================================================== SINTETICO: panel layer and screen
@pytest.fixture
def visao(mundo):
    """2025-12-31: entity 1 with 4 records (one paid without opening balance: S1 = -5,00 in 'sem saldo de abertura')
    and entity 15 without RP. 2025-10-31: only entity 1 (Municipality unavailable)."""
    mundo.catalogos({1: [2025], 15: [2025]})
    regs = [_reg(1, ano=2024, proc=100.0, aproc=50.0, pagoProc=30.0, descricaoFonte="1000-Livres", **ORC),
            _reg(2, ano=2022, aproc=30.0, canceladoAProc=10.0, descricaoFonte="1000-Livres", **ORC),
            _reg(3, ano=2023, aproc=0, proc=20.0, fonteRecurso=2000, descricaoFonte="2000-Vinculados"),
            _reg(4, ano=2023, aproc=0, pagoProc=5.0, descricaoFonte="1000-Livres")]
    mundo.listagem(1, 2025, "2025-12-31", regs, T0)
    mundo.listagem(15, 2025, "2025-12-31", [], T0)
    mundo.listagem(1, 2025, "2025-10-31", regs, T0)
    mundo.processar()
    return mundo


def test_SINTETICO_particoes_do_corte(visao):
    with visao.painel() as p:
        v = p.visao_geral(2025, "2025-12-31")
        n = v["numeros"]
        assert (n["inscricao_total"], n["pagamentos"], n["cancelamentos"], n["saldo_total"]) == (20000, 3500, 1000, 15500)
        assert n["pago_do_inscrito_decimos"] == 175
        assert [(i["chave"], i["valor_c"], i["decimos"]) for i in v["destino"]["itens"]] == [
            ("pago", 3500, 175), ("cancelado", 1000, 50), ("em_aberto", 15500, 775)]
        assert v["situacao_do_saldo"]["pizza"] and v["situacao_do_saldo"]["fechamento"]["fecha"]
        cat = v["composicao"]["categoria"]
        assert not cat["pizza"] and "negativa" in cat["motivo"]                   # S1 -5,00 in 'sem saldo de abertura'
        assert [i["valor_c"] for i in cat["itens"]][-1] == -500
        ent = v["por_entidade"]
        assert ent["pizza"] and [(i["chave"], i["valor_c"]) for i in ent["itens"]] == [(1, 15500), (15, 0)]
        assert v["composicao"]["funcao"]["itens"][0]["rotulo"] == "Educação (função 12)"


def test_SINTETICO_corte_sem_municipio_mostra_so_as_series(visao):
    app = Aplicacao(visao.cfg.banco)
    with visao.painel() as p:
        v = p.visao_geral(2025, "2025-10-31")
        assert not v["disponivel"] and v["numeros"] is None and v["destino"] is None and v["composicao"] == {}
        assert [x["saldo_total"] for x in v["evolucao"]] == [None, 15500]         # the gap stays a gap
    corpo = ok(app, "/", exercicio=2025, data_final="2025-10-31")
    assert 'id="indisponivel"' in corpo and "vg-saldo_total" not in corpo and "R$ 0,00" not in corpo
    assert "vg-ev-2025-10-31-saldo" not in dados(corpo) and dados(corpo)["vg-ev-2025-12-31-saldo"] == 15500


def test_SINTETICO_corte_pedido_nunca_e_trocado(visao):
    app = Aplicacao(visao.cfg.banco)
    corpo = ok(app, "/", exercicio=2025, data_final="2025-11-30")
    assert "Posição em 30/11/2025" in corpo and "Corte 30/11/2025 não processado" in corpo
    assert "vg-saldo_total" not in corpo                                        # no value of another cut-off
    assert "Sem dados processados" in ok(app, "/", exercicio=2024)


def test_SINTETICO_tela_mostra_os_valores_da_camada_painel(visao):
    app = Aplicacao(visao.cfg.banco)
    corpo = ok(app, "/", exercicio=2025, data_final="2025-12-31")
    with visao.painel() as p:
        esperado = _esperado(p.visao_geral(2025, "2025-12-31"))
    assert dados(corpo) == esperado
    assert links_permitidos(corpo) and "<script" not in corpo and " style=" not in corpo
    assert "Valores exatos" in corpo and "há parte negativa" in corpo


def test_SINTETICO_resumo_mudou_para_resumo(visao):
    app = Aplicacao(visao.cfg.banco)
    resumo = ok(app, "/resumo", exercicio=2025, data_final="2025-12-31")
    assert "<h1>Restos a Pagar — Município, exercício 2025, corte 31/12/2025" in resumo
    inicio = ok(app, "/")
    assert '<a href="/" class="ativo" aria-current="page">Visão geral</a>' in inicio
    assert '<a href="/resumo">Resumo do corte</a>' in inicio
    for caminho in ("/", "/resumo"):
        assert chamar(app, caminho, exercicio="dois mil")[0] == "400 Bad Request"


# ================================================================== real store
@pytest.fixture(scope="module")
def app_real(real):
    return Aplicacao(real["cfg"].banco)


@pytest.fixture(scope="module")
def bruto_real(real):
    return rb.Bruto(real["con"], real["armazem"])


def test_toda_pizza_real_fecha_e_e_igual_ao_bruto(real, bruto_real):
    """Every cut-off with the Municipality available and each entity: destination and balance situation recalculated
    from the raw JSON; every pie closes and its shares add up to 1000."""
    p, n = real["painel"], 0
    escopos = [None] + [e["entidade"] for e in p.entidades()["entidades"]]
    for c in p.cortes()["cortes"]:
        for ent in escopos:
            v = p.visao_geral(c["exercicio"], c["data_final"], ent)
            x = bruto_real.ponto(c["exercicio"], c["data_final"], ent)
            assert v["disponivel"] == x["tem_valor"], (c, ent)
            if not v["disponivel"]:
                continue
            b = x["valores"]
            assert [i["valor_c"] for i in v["destino"]["itens"]] == [b["pagamentos"], b["cancelamentos"], b["saldo_total"]]
            assert v["destino"]["total_c"] == b["inscricao_total"]
            assert [i["valor_c"] for i in v["situacao_do_saldo"]["itens"]] == [b["saldo_a_liquidar"],
                                                                            b["saldo_liquidado_a_pagar"]]
            blocos = [v["destino"], v["situacao_do_saldo"], *v["composicao"].values()]
            if v["por_entidade"]:
                blocos.append(v["por_entidade"])
            for bloco in blocos:
                assert bloco["fechamento"]["fecha"] if "fechamento" in bloco else not bloco["pizza"]
                if bloco["pizza"]:
                    assert sum(i["decimos"] for i in bloco["itens"]) == 1000
                    assert all(i["valor_c"] >= 0 for i in bloco["itens"])
            n += 1
    assert n >= 30


def test_composicao_real_da_visao_igual_ao_bruto(real, bruto_real):
    p = real["painel"]
    for ex, df in ((2025, "2025-12-31"), (2026, "2026-08-31"), (2020, "2020-12-31")):
        v = p.visao_geral(ex, df)
        x = bruto_real.composicao(ex, df)["composicao"]
        cat = {i["chave"]: i["valor_c"] for i in v["composicao"]["categoria"]["itens"]}
        assert cat == {k: g["saldo_total_c"] for k, g in x["dimensoes"]["categoria"].items()} | {
            k: 0 for k in cat if k not in x["dimensoes"]["categoria"]}
        assert v["composicao"]["fonte_recurso"]["total_c"] == x["total"]["saldo_total_c"]
        maiores = sorted((g["saldo_total_c"] for g in x["dimensoes"]["fonte_recurso"].values()), reverse=True)
        fontes = [i["valor_c"] for i in v["composicao"]["fonte_recurso"]["itens"] if not i.get("agrupa")]
        assert fontes == maiores[:len(fontes)]
        ent = v["por_entidade"]
        assert sum(i["valor_c"] for i in ent["itens"]) == x["total"]["saldo_total_c"] == v["numeros"]["saldo_total"]


def test_tela_real_igual_a_camada_painel(real, app_real):
    p = real["painel"]
    for ex, df, ent in ((2026, "2026-09-30", None), (2025, "2025-12-31", None), (2025, "2025-12-31", 15),
                        (2016, "2016-12-31", None), (2026, "2026-01-31", None), (2020, "2020-12-31", None)):
        corpo = ok(app_real, "/", exercicio=ex, data_final=df, entidade=ent)
        v = p.visao_geral(ex, df, ent)
        assert dados(corpo) == _esperado(v), (ex, df, ent)
        assert links_permitidos(corpo) and " style=" not in corpo
        for figura in re.findall(r'<figure class="pizza">.*?</figure>', corpo):
            cores = re.findall(r'<li><span class="amostra (c\d)"', figura)
            assert len(cores) == len(set(cores)), (ex, df, ent, cores)          # no two parts with the same color
    assert any(i.get("agrupa") for i in p.visao_geral(2020, "2020-12-31")["por_entidade"]["itens"])   # 9+ entities
    padrao = ok(app_real, "/")
    assert re.search(r"Posição em \d{2}/\d{2}/\d{4}", padrao) and padrao.count('role="img"') == 9


def test_toda_funcao_real_tem_nome_oficial(real):
    codigos = {r[0] for r in real["con"].execute("SELECT DISTINCT funcao FROM rp_registro WHERE funcao IS NOT NULL")}
    assert codigos and all(classificacao.nome_da_funcao(c) for c in codigos), sorted(codigos)


# ------------------------------------------------------------------ expected <data id> values of the page
def _esperado(v):
    """{id: cents} the page must show, built only from Painel.visao_geral (no recalculation)."""
    e = {}
    if v["disponivel"]:
        for k in ("inscricao_total", "pagamentos", "cancelamentos", "saldo_total"):
            e[f"vg-{k}"] = v["numeros"][k]
        blocos = {"destino": v["destino"], "saldo": v["situacao_do_saldo"], **v["composicao"]}
        if v["por_entidade"]:
            blocos["entidade"] = v["por_entidade"]
        for nome, b in blocos.items():
            for i in b["itens"]:
                e[f"vg-{nome}-{i['chave']}"] = i["valor_c"]
            e[f"vg-{nome}-total"] = b["total_c"]
    for x in v["evolucao"]:
        if x["tem_valor"]:
            e[f"vg-ev-{x['data_final']}-saldo"] = x["saldo_total"]
            e[f"vg-ev-{x['data_final']}-pago"] = x["pagamentos"]
    for x in v["entre_exercicios"]:
        if x["tem_valor"]:
            e[f"vg-ex-{x['exercicio']}-inscrito"] = x["inscricao_total"]
            e[f"vg-ex-{x['exercicio']}-saldo"] = x["saldo_total"]
    return e
