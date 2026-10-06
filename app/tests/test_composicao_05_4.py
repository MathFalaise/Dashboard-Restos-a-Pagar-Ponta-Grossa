"""Tests of sub-stage 05.4: balance composition (contract M-05 to M-08; plan, section 05.4).

* each dimension adds up ON ITS OWN to the cut-off total, per measure (sum of the groups - total = 0, no tolerance);
  a dimension that does not add up is not shown, even if the others do;
* fixed groups (category, band, creditor type) always present, with 0 when empty; "sem classificacao" always present
  in the budget dimensions;
* band (R3): adds up in values; the count per band is per part and is not summed; text without reference to the RREO
  columns;
* each group leads to a commitment list whose total is the group itself;
* independent validation: composition = recalculation from the raw JSON (recalculo_bruto.py); screen = panel.
SINTETICO = temporary database with invented records (fixture `mundo`).
"""
import re
import time
from urllib.parse import parse_qsl, urlsplit

import pytest
from conftest import chamar, dados, ok, registro_sintetico as _reg, links_permitidos

import recalculo_bruto as rb
from rp.interface import Aplicacao
from rp.painel import Painel
from rp.painel.consulta import (CATEGORIAS, COMPOSICOES, DIMENSOES_ORCAMENTARIAS, MEDIDAS_DA_COMPOSICAO,
                                SEM_CLASSIFICACAO, TEXTO_FAIXA, ErroDoPainel, fechamento)
from rp.painel.publico import TIPOS_CREDOR

T0 = "2026-09-29T20:00:00-03:00"
ORC = {"orgao": "09", "funcao": "12", "programa": "0076", "elemento": "3390390000"}
COLUNAS_RREO = re.compile(r"(?i)coluna|RREO|\([abfg]\)")


def _chave_bruta(d, g):
    """Key of the panel's group in the format of recalculo_bruto.composicao."""
    if d in ("categoria", "faixa", "tipo_credor"):
        return g["chave"]
    if d == "fonte_recurso":
        return (None, None) if g["chave"] is None else (g["chave"]["fonte_recurso"], g["chave"]["descricao_fonte"])
    return (g["chave"],)


def _confere_com_o_bruto(r, bruto, contexto):
    """Panel = raw: total, and in each dimension each group (empty group = 0) and no group of the raw data missing."""
    assert r["total"] == bruto["total"], contexto
    for d in COMPOSICOES:
        x, b = r["dimensoes"][d], bruto["dimensoes"][d]
        assert x["fecha"] and x["exibida"], (contexto, d, x["fechamento"])
        vistos = set()
        for g in x["grupos"]:
            k = _chave_bruta(d, g)
            vistos.add(k)
            esperado = b.get(k, {"registros": 0, "inscricao_total_c": 0, "saldo_total_c": 0})
            medidas = ("registros", "inscricao_total_c") if d == "faixa" else MEDIDAS_DA_COMPOSICAO
            assert {m: g[m] for m in medidas} == {m: esperado[m] for m in medidas}, (contexto, d, k)
        assert set(b) <= vistos, (contexto, d, set(b) - vistos)


def _confere_lista(p, ex, df, ent, d, g):
    """The group leads to a list whose total is the group itself (records, inscription and S1; in the band, the part)."""
    e = p.empenhos(ex, df, ent, limite=1, **g["filtro"])
    assert e["total"] == g["registros"], (ex, df, ent, d, g["ident"])
    if g["registros"] == 0:
        assert e["sem_resultado"] and e["totais"]["valores"] is None
        return
    t = e["totais"]["valores"]
    if d == "faixa":
        assert t[g["total_na_lista"]] == g["inscricao_total_c"], (ex, df, ent, d, g["ident"])
    else:
        assert (t["inscricao_total"], t["saldo_total"]) == (g["inscricao_total_c"], g["saldo_total_c"]), (ex, df, ent, d,
                                                                                                         g["ident"])


# ================================================================== SINTETICO
@pytest.fixture
def composicao(mundo):
    """2025-12-31: entity 1 with 4 records (one of each category; one without budget classification by PF, one without
    a document) and entity 15 without RP (zero records). 2025-10-31: only entity 1 (Municipality unavailable)."""
    mundo.catalogos({1: [2025], 15: [2025]})
    regs = [_reg(1, ano=2024, proc=100.0, aproc=50.0, pagoProc=30.0, fonteRecurso=1000, descricaoFonte="1000-Livres", **ORC),
            _reg(2, ano=2022, aproc=30.0, cnpj="***456***", fonteRecurso=1000, descricaoFonte="1000-Livres", **ORC),
            _reg(3, ano=2023, aproc=0, proc=20.0, cnpj="", fonteRecurso=2000, descricaoFonte="2000-Vinculados"),
            _reg(4, ano=2023, aproc=0, pagoProc=5.0, fonteRecurso=1000, descricaoFonte="1000-Livres")]
    mundo.listagem(1, 2025, "2025-12-31", regs, T0)
    mundo.listagem(15, 2025, "2025-12-31", [], T0)
    mundo.listagem(1, 2025, "2025-10-31", regs, T0)
    mundo.processar()
    return mundo


def _grupos(r, d):
    return {g["ident"]: g for g in r["dimensoes"][d]["grupos"]}


def test_SINTETICO_fechamento_grupos_fixos_e_sem_classificacao(composicao):
    with composicao.painel() as p:
        r = p.composicao(2025, "2025-12-31")
        assert r["situacao"]["codigo"] == "com_dados"
        assert r["total"] == {"registros": 4, "inscricao_total_c": 20000, "saldo_total_c": 16500}
        assert all(x["fecha"] and x["exibida"] for x in r["dimensoes"].values())
        cat = _grupos(r, "categoria")
        assert list(cat) == list(CATEGORIAS)                                    # all of them, in the fixed order
        assert [(cat[k]["registros"], cat[k]["inscricao_total_c"], cat[k]["saldo_total_c"]) for k in CATEGORIAS] == [
            (1, 2000, 2000), (1, 3000, 3000), (1, 15000, 12000), (1, 0, -500)]
        faixa = _grupos(r, "faixa")
        assert {k: (g["registros"], g["inscricao_total_c"]) for k, g in faixa.items()} == {
            "a": (1, 2000), "b": (1, 10000), "f": (1, 3000), "g": (1, 5000)}
        assert r["dimensoes"]["faixa"]["medidas"] == ["inscricao_total_c"]          # R3: only values add up
        assert not r["dimensoes"]["faixa"]["contagem_aditiva"]
        tipo = _grupos(r, "tipo_credor")
        assert [g["chave"] for g in tipo.values()] == list(TIPOS_CREDOR)
        assert [(g["registros"], g["inscricao_total_c"]) for g in tipo.values()] == [(2, 15000), (1, 3000), (1, 2000)]
        orgao = _grupos(r, "orgao")
        assert list(orgao) == ["09", "sem"] and orgao["sem"]["rotulo"] == SEM_CLASSIFICACAO
        assert (orgao["sem"]["registros"], orgao["sem"]["inscricao_total_c"], orgao["sem"]["saldo_total_c"]) == (2, 2000, 1500)
        fonte = _grupos(r, "fonte_recurso")
        assert fonte["sem"]["registros"] == 0 and list(fonte)[-1] == "sem"        # present even when empty, last
        for x in r["dimensoes"].values():
            assert {m: f["diferenca"] for m, f in x["fechamento"].items()} == dict.fromkeys(x["medidas"], 0)


def test_SINTETICO_igual_ao_recalculo_do_bruto(composicao):
    b = rb.Bruto(composicao.con, composicao.armazem)
    with composicao.painel() as p:
        for ent in (None, 1, 15):
            r = p.composicao(2025, "2025-12-31", ent)
            x = b.composicao(2025, "2025-12-31", ent)
            assert r["situacao"]["codigo"] == x["situacao"]
            _confere_com_o_bruto(r, x["composicao"], ent)


def test_SINTETICO_zero_verdadeiro_e_indisponivel(composicao):
    with composicao.painel() as p:
        z = p.composicao(2025, "2025-12-31", 15)                                # existing entity without RP
        assert z["situacao"]["codigo"] == "sem_rp" and z["total"] == dict.fromkeys(MEDIDAS_DA_COMPOSICAO, 0)
        assert [g["registros"] for g in z["dimensoes"]["categoria"]["grupos"]] == [0, 0, 0, 0]
        assert [g["ident"] for g in z["dimensoes"]["elemento"]["grupos"]] == ["sem"]
        for ent, codigo in ((None, "municipio_indisponivel"), (15, "sem_coleta")):
            n = p.composicao(2025, "2025-10-31", ent)
            assert n["situacao"]["codigo"] == codigo and not n["disponivel"]
            assert n["total"] is None and n["dimensoes"] == {} and n["motivo_indisponivel"]


def test_SINTETICO_dimensao_que_nao_fecha_nao_e_exibida(mundo):
    """A negative proc has no band (FAIXA v1 only classifies the positive part): the band does not add up to the
    inscription and leaves the screen; the other dimensions keep adding up and are shown."""
    mundo.catalogos({1: [2025]})
    mundo.listagem(1, 2025, "2025-12-31", [_reg(1, ano=2024, proc=100.0, aproc=50.0),
                                           _reg(2, ano=2023, proc=-10.0, aproc=50.0)], T0)
    mundo.processar()
    with mundo.painel() as p:
        r = p.composicao(2025, "2025-12-31")
        f = r["dimensoes"]["faixa"]
        assert not f["fecha"] and not f["exibida"] and f["grupos"] == []
        assert f["fechamento"]["inscricao_total_c"]["diferenca"] == 1000 and "não é exibida" in f["motivo_nao_exibida"]
        assert all(x["exibida"] for d, x in r["dimensoes"].items() if d != "faixa")
        b = rb.Bruto(mundo.con, mundo.armazem).composicao(2025, "2025-12-31")["composicao"]
        assert rb.fechamento(b["total"]["inscricao_total_c"],                  # the raw data does not add up either
                             [(k, v["inscricao_total_c"]) for k, v in b["dimensoes"]["faixa"].items()])["diferenca_c"] == 1000
    app = Aplicacao(mundo.cfg.banco)
    corpo = ok(app, "/composicao", exercicio=2025, data_final="2025-12-31", dimensao="faixa")
    v = dados(corpo)
    assert 'id="comp-nao-exibida"' in corpo and not any(k.startswith("comp-faixa-") for k in v)
    assert v["fech-faixa-insc"] == 1000 and v["fech-categoria-insc"] == 0
    linha = re.search(r'<tr><td><a [^>]*dimensao=faixa[^>]*>Faixa \(FAIXA v1\)</a></td><td>(.*?)</td>', corpo).group(1)
    assert "não" in linha


def test_SINTETICO_cada_grupo_leva_a_lista_com_o_proprio_total(composicao):
    with composicao.painel() as p:
        for ent in (None, 1, 15):
            r = p.composicao(2025, "2025-12-31", ent)
            for d, x in r["dimensoes"].items():
                for g in x["grupos"]:
                    assert g["filtro"] is not None, (d, g["ident"])
                    _confere_lista(p, 2025, "2025-12-31", ent, d, g)


def test_SINTETICO_fonte_com_duas_descricoes_fica_sem_lista(mundo):
    mundo.catalogos({1: [2025]})
    mundo.listagem(1, 2025, "2025-12-31", [_reg(1, fonteRecurso=1000, descricaoFonte="1000-Livres"),
                                           _reg(2, fonteRecurso=1000, descricaoFonte="1000-Livres (nova)")], T0)
    mundo.processar()
    with mundo.painel() as p:
        x = p.composicao(2025, "2025-12-31")["dimensoes"]["fonte_recurso"]
        dois = [g for g in x["grupos"] if g["chave"] and g["chave"]["fonte_recurso"] == 1000]
        assert len(dois) == 2 and x["fecha"]
        assert all(g["filtro"] is None and "mais de uma descrição" in g["motivo_sem_lista"] for g in dois)


def test_SINTETICO_filtros_novos_validados():
    for kw in ({"faixa": "c"}, {"orgao": "9x"}, {"funcao": ""}, {"sem_classificacao": "categoria"}):
        with pytest.raises(ErroDoPainel):
            Painel._filtros_empenho(**kw)
    sql, params, eco = Painel._filtros_empenho(faixa="g", orgao="09", sem_classificacao="programa")
    assert "d.faixa_nao_processado = ?" in sql and "r.orgao = ?" in sql and "r.programa IS NULL" in sql
    assert params == ("g", "09") and eco == {"faixa": "g", "orgao": "09", "sem_classificacao": "programa"}


def test_SINTETICO_fechamento_do_painel_sem_tolerancia():
    assert fechamento(10, [4, 6])["fecha"] and fechamento(10, [4, 5])["diferenca"] == -1
    for ruim in (True, 1.0, None):
        with pytest.raises(ErroDoPainel):
            fechamento(10, [ruim])


def test_SINTETICO_tela_valores_links_e_texto_da_faixa(composicao):
    app = Aplicacao(composicao.cfg.banco)
    with composicao.painel() as p:
        r = p.composicao(2025, "2025-12-31")
    for d in COMPOSICOES:
        status, cab, corpo = chamar(app, "/composicao", exercicio=2025, data_final="2025-12-31", dimensao=d)
        assert status == "200 OK" and "default-src 'none'" in cab["Content-Security-Policy"]
        v = dados(corpo)
        for g in r["dimensoes"][d]["grupos"]:
            assert v[f"comp-{d}-{g['ident']}-insc"] == g["inscricao_total_c"]
            assert v[f"comp-{d}-{g['ident']}-reg"] == g["registros"]
            if d != "faixa":
                assert v[f"comp-{d}-{g['ident']}-s1"] == g["saldo_total_c"]
        assert v[f"comp-{d}-fech-insc"] == 0 and v["comp-total-insc"] == r["total"]["inscricao_total_c"]
        for href in re.findall(r'href="(/empenhos\?[^"]*)"', corpo):        # each link: list total = group
            q = dict(parse_qsl(urlsplit(href.replace("&amp;", "&")).query))
            lista = dados(ok(app, "/empenhos", **q))
            assert lista["tot-registros"] > 0
        assert links_permitidos(corpo)
        assert "style=" not in corpo and "<script" not in corpo
    corpo = ok(app, "/composicao", exercicio=2025, data_final="2025-12-31", dimensao="faixa")
    secao = re.search(r'<section class="grupo" id="composicao-faixa">.*?</section>', corpo, re.S).group(0)
    assert TEXTO_FAIXA[1:] in secao                       # "composição dos registros da API segundo a regra FAIXA v1"
    assert not COLUNAS_RREO.search(re.sub(r"<[^>]+>", " ", secao))
    lista = dados(ok(app, "/empenhos", exercicio=2025, data_final="2025-12-31", faixa="b"))
    assert lista["tot-proc"] == 10000                                             # band b = processed part
    corpo = ok(app, "/composicao", exercicio=2025, data_final="2025-10-31")
    assert 'id="indisponivel"' in corpo and not any(k.startswith(("comp-", "fech-")) for k in dados(corpo))
    assert "R$" not in corpo.split('id="indisponivel"')[1]
    assert chamar(app, "/empenhos", exercicio=2025, data_final="2025-12-31", faixa="c")[0] == "400 Bad Request"


# ================================================================== real store
@pytest.fixture(scope="module")
def app_real(real):
    return Aplicacao(real["cfg"].banco)


@pytest.fixture(scope="module")
def bruto_real(real):
    return rb.Bruto(real["con"], real["armazem"])


@pytest.fixture(scope="module")
def escopos_reais(real):
    return [None] + [e["entidade"] for e in real["painel"].entidades()["entidades"]]


def test_toda_dimensao_fecha_e_e_igual_ao_bruto_em_todo_corte_disponivel(real, bruto_real, escopos_reais):
    p, n = real["painel"], 0
    for c in p.cortes()["cortes"]:
        ex, df = c["exercicio"], c["data_final"]
        for ent in escopos_reais:
            r = p.composicao(ex, df, ent)
            x = bruto_real.composicao(ex, df, ent)
            assert r["situacao"]["codigo"] == x["situacao"], (ex, df, ent)
            if not r["disponivel"]:
                assert x["composicao"] is None and r["dimensoes"] == {}
                continue
            _confere_com_o_bruto(r, x["composicao"], (ex, df, ent))
            n += 1
    assert n >= 22                                                           # every cut-off has at least one scope


def test_sem_classificacao_presente_com_contagem(real):
    r = real["painel"].composicao(2025, "2025-12-31")
    for d in DIMENSOES_ORCAMENTARIAS:
        sem = r["dimensoes"][d]["grupos"][-1]
        assert sem["ident"] == "sem" and sem["rotulo"] == SEM_CLASSIFICACAO
        assert sem["registros"] == (0 if d == "fonte_recurso" else 16)        # the plan's measurement (section 5.4)


def test_mesma_consulta_de_categorias_e_por_dimensao(real):
    p = real["painel"]
    for ex, df, ent in ((2025, "2025-12-31", None), (2026, "2026-08-31", 1), (2024, "2024-12-31", 15)):
        r = p.composicao(ex, df, ent)
        ind = p.indicadores(ex, df, ent)["categorias"]
        assert [(c["categoria"], c["registros"], c["inscricao_total_c"], c["saldo_total_c"]) for c in ind] == sorted(
            (g["chave"], g["registros"], g["inscricao_total_c"], g["saldo_total_c"])
            for g in r["dimensoes"]["categoria"]["grupos"] if g["registros"])
        for d in DIMENSOES_ORCAMENTARIAS:
            linhas = p.por_dimensao(d, ex, df, ent)["linhas"]
            grupos = [g for g in r["dimensoes"][d]["grupos"] if g["registros"]]
            assert len(linhas) == len(grupos)
            assert sorted((l["registros"], l["inscricao_total_c"], l["saldo_total_c"]) for l in linhas) == sorted(
                (g["registros"], g["inscricao_total_c"], g["saldo_total_c"]) for g in grupos)


@pytest.mark.parametrize("ex,df,ent", [(2025, "2025-12-31", None), (2026, "2026-08-31", 1), (2026, "2026-08-31", 15)])
def test_cada_grupo_real_leva_a_lista_com_o_proprio_total(real, ex, df, ent):
    p = real["painel"]
    r = p.composicao(ex, df, ent)
    for d, x in r["dimensoes"].items():
        for g in x["grupos"]:
            assert g["filtro"] is not None, (d, g["ident"])
            _confere_lista(p, ex, df, ent, d, g)


def test_tela_igual_ao_painel_e_links_reais(real, app_real):
    p = real["painel"]
    for ex, df, ent in ((2025, "2025-12-31", None), (2026, "2026-08-31", 1)):
        r = p.composicao(ex, df, ent)
        for d in COMPOSICOES:
            corpo = ok(app_real, "/composicao", exercicio=ex, data_final=df, entidade=ent, dimensao=d)
            v = dados(corpo)
            medidas = (("insc", "inscricao_total_c"), ("reg", "registros")) + ((("s1", "saldo_total_c"),) if d != "faixa" else ())
            for g in r["dimensoes"][d]["grupos"]:
                for sufixo, m in medidas:
                    assert v[f"comp-{d}-{g['ident']}-{sufixo}"] == g[m], (ex, df, ent, d, g["ident"], m)
            for sufixo, m in medidas[:1] + ((("reg", "registros"), ("s1", "saldo_total_c")) if d != "faixa" else ()):
                assert v[f"comp-{d}-fech-{sufixo}"] == 0
            assert v["comp-total-s1"] == r["total"]["saldo_total_c"]
            assert ('id="aviso-pares"' in corpo) == (r["pares_espelhados_no_corte"] > 0)
            for href in re.findall(r'href="(/empenhos\?[^"]*)"', corpo)[:6]:
                q = dict(parse_qsl(urlsplit(href.replace("&amp;", "&")).query))
                g = next(g for g in r["dimensoes"][d]["grupos"] if g["filtro"] and all(
                    str(q.get(k)) == str(val) for k, val in g["filtro"].items()))
                lista = dados(ok(app_real, "/empenhos", **q))
                assert lista["tot-registros"] == g["registros"]
                if d == "faixa":
                    alvo = {"inscricao_processada": "tot-proc", "inscricao_nao_processada": "tot-aproc"}[g["total_na_lista"]]
                    assert lista[alvo] == g["inscricao_total_c"]
                else:
                    assert lista["tot-s1"] == g["saldo_total_c"]
            if d == "faixa":
                secao = re.search(r'<section class="grupo" id="composicao-faixa">.*?</section>', corpo, re.S).group(0)
                assert not COLUNAS_RREO.search(re.sub(r"<[^>]+>", " ", secao))


def test_desempenho_da_composicao(app_real):
    for ent in (None, 1):
        for d in ("categoria", "fonte_recurso", "programa"):
            t = time.perf_counter()
            status, _, _ = chamar(app_real, "/composicao", exercicio=2025, data_final="2025-12-31", entidade=ent, dimensao=d)
            assert status == "200 OK" and time.perf_counter() - t < 3, (ent, d)
