"""Testes da Subetapa 05.5: investigacao de variacoes (contrato M-09 a M-12; plano, secao 05.5).

* par de cortes do mesmo exercicio, escolhido explicitamente (adjacente ou nao); indisponivel com motivo se um lado
  nao tem valor, se o Municipio soma conjuntos de entidades diferentes (R6) ou se ha chave repetida;
* contribuicao por chave com sinal posterior - anterior e classe (nos dois cortes, so no posterior, so no anterior);
* fechamento ao centavo da lista, dos grupos do resumo (TOP N, outros, sem variacao) e das classes;
* lista completa paginada: subtotal por pagina e acumulado; a ultima pagina fecha com a variacao total;
* historico de um empenho em todos os cortes do exercicio, com a situacao nos cortes sem valor;
* validacao independente: recalculo do JSON bruto (recalculo_bruto.Bruto.contribuicoes e empenho_nos_cortes).
SINTETICO = banco temporario com registros inventados (fixture `mundo`).
"""
import re
import time

import pytest
from conftest import chamar, dados, ok, registro_sintetico as _reg

import recalculo_bruto as rb
from rp.interface import Aplicacao
from rp.painel.consulta import CAMPOS_DO_HISTORICO, LIMITE_LISTA, ErroDoPainel

T0 = "2026-09-29T20:00:00-03:00"
BRUTO = {"proc_c": "proc", "aproc_c": "aproc", "pago_proc_c": "pago_proc", "pago_aproc_c": "pago_aproc",
         "liquidado_c": "liquidado", "cancelado_aproc_c": "cancelado_aproc", "s1_saldo_total_c": "s1"}


def _lista_completa(p, *args, **kw):
    """Todas as paginas da lista completa de contribuicoes (limite maximo por pagina)."""
    itens, desloc = [], 0
    while True:
        r = p.variacao(*args, limite=LIMITE_LISTA, deslocamento=desloc, **kw)
        itens += r["lista"]["itens"]
        if r["lista"]["ultima_pagina"]:
            return r, itens
        desloc += LIMITE_LISTA


def _chave(x):
    c = x["chave"]
    return (c["entidade"], c["anoempenho"], c["empenho"])


def _confere_com_o_bruto(p, b, ex, ant, post, ent, metrica):
    x = b.contribuicoes(ex, ant, post, ent, metrica, top=10)
    r = p.variacao(ex, ant, post, ent, metrica)
    assert r["disponivel"] == x["disponivel"], (ex, ant, post, ent, metrica, r["motivo_indisponivel"], x.get("motivo"))
    if not r["disponivel"]:
        return r
    r, itens = _lista_completa(p, ex, ant, post, ent, metrica)
    assert r["variacao_c"] == x["variacao_c"]
    assert [(_chave(i), i["classe"], i["contribuicao_c"]) for i in itens] == [
        (l["chave"], l["classe"], l["contribuicao_c"]) for l in x["linhas"] if l["contribuicao_c"]]
    assert [(g["id"], g["soma_c"]) for g in r["resumo"]["grupos"]] == x["grupos"]
    assert [(c["id"], c["soma_c"]) for c in r["classes"]] == x["classes"]
    assert r["chaves"]["sem_variacao"] == x["sem_variacao"]
    assert all(f["fecha"] for f in r["fechamentos"].values())
    for i in itens:                                                        # proveniencia dos dois lados
        for lado in ("anterior", "posterior"):
            assert i[lado] is None or (i[lado]["proveniencia"]["snapshot_uid"] in r[lado]["snapshots"]
                                       and len(i[lado]["proveniencia"]["objeto_bruto_sha256"]) == 64)
    return r


# ================================================================== SINTETICO
@pytest.fixture
def variacao(mundo):
    """2025, entidades 1 e 15 (a 15 sem RP). 28/02 -> 30/04 na entidade 1: emp 1 paga 30 (S1 -30), emp 2 some (-50),
    emp 3 igual (0), emp 4 sobe 20, emp 5 e 6 entram (+25, +20). 30/06: so a entidade 1 (Municipio indisponivel)."""
    mundo.catalogos({1: [2025], 15: [2025]})
    antes = [_reg(1, ano=2024, aproc=100.0), _reg(2, ano=2024, aproc=50.0), _reg(3, ano=2024, aproc=30.0),
             _reg(4, ano=2023, aproc=20.0)]
    depois = [_reg(1, ano=2024, aproc=100.0, pagoAProc=30.0), _reg(3, ano=2024, aproc=30.0), _reg(4, ano=2023, aproc=40.0),
              _reg(5, ano=2024, aproc=25.0), _reg(6, ano=2024, aproc=20.0)]
    mundo.listagem(1, 2025, "2025-02-28", antes, T0)
    mundo.listagem(1, 2025, "2025-04-30", depois, T0)
    mundo.listagem(15, 2025, "2025-02-28", [], T0)
    mundo.listagem(15, 2025, "2025-04-30", [], T0)
    mundo.listagem(1, 2025, "2025-06-30", depois, T0)
    mundo.processar()
    return mundo


def test_SINTETICO_contribuicoes_classes_grupos_e_fechamento(variacao):
    with variacao.painel() as p:
        for ent in (None, 1):                                  # a entidade 15 tem zero registros: mesmo resultado
            r = p.variacao(2025, "2025-02-28", "2025-04-30", ent, "s1", top=1)
            assert r["disponivel"] and r["variacao_c"] == -1500 and r["natureza"] == "diferenca"
            assert (r["anterior"]["total_c"], r["posterior"]["total_c"]) == (20000, 18500)
            itens = r["lista"]["itens"]
            assert [(i["chave"]["empenho"], i["classe"], i["contribuicao_c"]) for i in itens] == [
                (5, "so_posterior", 2500), (4, "nos_dois", 2000), (6, "so_posterior", 2000),   # empate: chave (2023 < 2024)
                (1, "nos_dois", -3000), (2, "so_anterior", -5000)]
            assert [i["posicao"] for i in itens] == [1, 2, 3, 4, 5]
            assert itens[4]["posterior"] is None and itens[0]["anterior"] is None              # um lado so: sem zero
            g = {x["id"]: x for x in r["resumo"]["grupos"]}
            assert [(k, g[k]["quantidade"], g[k]["soma_c"]) for k in g] == [
                ("top_aumentos", 1, 2500), ("outros_aumentos", 2, 4000), ("top_reducoes", 1, -5000),
                ("outras_reducoes", 1, -3000), ("sem_variacao", 1, 0)]
            assert [i["chave"]["empenho"] for i in g["top_reducoes"]["itens"]] == [2]          # a mais negativa primeiro
            assert [(c["id"], c["quantidade"], c["soma_c"]) for c in r["classes"]] == [
                ("nos_dois", 3, -1000), ("so_posterior", 2, 4500), ("so_anterior", 1, -5000)]
            assert all(f["fecha"] and f["diferenca"] == 0 for f in r["fechamentos"].values())
        m = p.variacao(2025, "2025-02-28", "2025-04-30", None, "pagamentos")
        assert m["variacao_c"] == 3000 and [(i["chave"]["empenho"], i["contribuicao_c"]) for i in m["lista"]["itens"]] == [(1, 3000)]
        assert m["chaves"] == {"total": 6, "com_variacao": 1, "sem_variacao": 5}
        assert [(c["id"], c["soma_c"]) for c in m["classes"]] == [("nos_dois", 3000), ("so_posterior", 0), ("so_anterior", 0)]


def test_SINTETICO_paginas_com_subtotal_e_acumulado(variacao):
    with variacao.painel() as p:
        paginas = [p.variacao(2025, "2025-02-28", "2025-04-30", None, "s1", limite=2, deslocamento=d) for d in (0, 2, 4)]
        assert [(x["lista"]["subtotal_c"], x["lista"]["acumulado_c"], x["lista"]["ultima_pagina"]) for x in paginas] == [
            (4500, 4500, False), (-1000, 3500, False), (-5000, -1500, True)]
        assert paginas[-1]["lista"]["acumulado_c"] == paginas[-1]["variacao_c"]


def test_SINTETICO_igual_ao_recalculo_do_bruto(variacao):
    b = rb.Bruto(variacao.con, variacao.armazem)
    with variacao.painel() as p:
        for ent in (None, 1, 15):
            for metrica in ("s1", "pagamentos"):
                for ant, post in (("2025-02-28", "2025-04-30"), ("2025-04-30", "2025-06-30"), ("2025-02-28", "2025-06-30")):
                    _confere_com_o_bruto(p, b, 2025, ant, post, ent, metrica)


def test_SINTETICO_par_indisponivel_e_zero_verdadeiro(variacao):
    with variacao.painel() as p:
        r = p.variacao(2025, "2025-04-30", "2025-06-30")                     # Municipio incompleto em 30/06
        assert not r["disponivel"] and "30/06/2025" in r["motivo_indisponivel"] and r["lista"] is None
        assert r["anterior"]["total_c"] == 18500 and r["posterior"]["total_c"] is None
        z = p.variacao(2025, "2025-02-28", "2025-04-30", 15)                 # entidade sem RP: zero verdadeiro
        assert z["disponivel"] and z["variacao_c"] == 0 and z["lista"]["itens"] == []
        u = p.variacao(2025, "2025-04-30", "2025-06-30", 1)                  # mesmos registros: tudo sem variacao
        assert u["variacao_c"] == 0 and u["chaves"] == {"total": 5, "com_variacao": 0, "sem_variacao": 5}
        assert "sem processamento" in p.variacao(2025, "2025-02-28", "2025-05-31")["motivo_indisponivel"]
        for kw in ({"anterior": "2025-04-30", "posterior": "2025-02-28"}, {"anterior": "2025-02-28", "posterior": "2025-02-28"}):
            with pytest.raises(ErroDoPainel):
                p.variacao(2025, entidade=1, **kw)
        with pytest.raises(ErroDoPainel):
            p.variacao(2025, "2025-02-28", "2025-04-30", metrica="liquidacoes")


def test_SINTETICO_chave_repetida_bloqueia_o_par(mundo):
    mundo.catalogos({1: [2025]})
    mundo.listagem(1, 2025, "2025-02-28", [_reg(1, aproc=10.0)], T0)
    mundo.listagem(1, 2025, "2025-04-30", [_reg(1, aproc=10.0), _reg(1, aproc=5.0)], T0)
    mundo.processar()
    with mundo.painel() as p:
        r = p.variacao(2025, "2025-02-28", "2025-04-30")
        assert not r["disponivel"] and r["lista"] is None and "mais de uma vez" in r["motivo_indisponivel"]
        assert r["chaves_repetidas"] == [{"chave": {"entidade": 1, "anoempenho": 2024, "empenho": 1}, "anterior": 1,
                                          "posterior": 2}]
        h = p.historico_empenho(1, 2024, 1, 2025)
        assert [len(c["ocorrencias"]) for c in h["cortes"]] == [1, 2] and h["nota"]   # mostra as duas, sem escolher
    assert not rb.Bruto(mundo.con, mundo.armazem).contribuicoes(2025, "2025-02-28", "2025-04-30")["disponivel"]


def test_SINTETICO_municipio_com_entidades_diferentes_bloqueia_o_par(mundo):
    """Entidade 7 fora do catalogo de entidades, com snapshot so no primeiro corte: o Municipio soma {1, 7} e depois
    {1}; os dois cortes tem valor, mas o par nao e comparavel (R6)."""
    mundo.catalogos({1: [2025]})
    mundo.listagem(1, 2025, "2025-02-28", [_reg(1, aproc=10.0)], T0)
    mundo.listagem(7, 2025, "2025-02-28", [_reg(1, entidade=7, aproc=5.0)], T0)
    mundo.listagem(1, 2025, "2025-04-30", [_reg(1, aproc=10.0)], T0)
    mundo.processar()
    with mundo.painel() as p:
        r = p.variacao(2025, "2025-02-28", "2025-04-30")
        assert not r["disponivel"] and "(R6)" in r["motivo_indisponivel"] and "[7]" in r["motivo_indisponivel"]
        assert p.variacao(2025, "2025-02-28", "2025-04-30", 1)["disponivel"]
    x = rb.Bruto(mundo.con, mundo.armazem).contribuicoes(2025, "2025-02-28", "2025-04-30")
    assert not x["disponivel"] and "R6" in x["motivo"]


def test_SINTETICO_historico_do_empenho_e_bruto(variacao):
    b = rb.Bruto(variacao.con, variacao.armazem)
    with variacao.painel() as p:
        for ent, ano, emp in ((1, 2024, 2), (1, 2024, 5), (15, 2024, 1), (1, 2023, 4)):
            h = p.historico_empenho(ent, ano, emp, 2025)
            x = b.empenho_nos_cortes(ent, ano, emp, 2025)
            assert [c["data_final"] for c in h["cortes"]] == [c["data_final"] for c in x] == [
                "2025-02-28", "2025-04-30", "2025-06-30"]
            for c, y in zip(h["cortes"], x):
                assert c["situacao"]["codigo"] == y["situacao"]
                if not c["tem_valor"]:
                    assert y["ocorrencias"] is None and c["ocorrencias"] == [] and c["motivo_indisponivel"]
                    continue
                assert [{k: o["valores"][k] for k in CAMPOS_DO_HISTORICO} for o in c["ocorrencias"]] == [
                    {k: v[BRUTO[k]] for k in CAMPOS_DO_HISTORICO} for v in y["ocorrencias"]]
                assert c["presente"] == bool(y["ocorrencias"])
                assert c["motivo_ausencia"] == (None if c["presente"] else "empenho ausente deste corte")
        h = p.historico_empenho(1, 2024, 2, 2025)
        assert [c["presente"] for c in h["cortes"]] == [True, False, False]
        h = p.historico_empenho(15, 2024, 1, 2025)
        assert [c["situacao"]["codigo"] for c in h["cortes"]] == ["sem_rp", "sem_rp", "sem_coleta"]


def test_SINTETICO_tela_da_variacao_e_do_empenho(variacao):
    app = Aplicacao(variacao.cfg.banco)
    with variacao.painel() as p:
        r = p.variacao(2025, "2025-02-28", "2025-04-30")
    status, cab, corpo = chamar(app, "/variacao", exercicio=2025, anterior="2025-02-28", data_final="2025-04-30")
    assert status == "200 OK" and "default-src 'none'" in cab["Content-Security-Policy"]
    v = dados(corpo)
    assert (v["var-anterior"], v["var-posterior"], v["var-total"]) == (20000, 18500, -1500)
    assert [v[f"lst-{i}"] for i in range(1, 6)] == [i["contribuicao_c"] for i in r["lista"]["itens"]]
    assert {g["id"]: v[f"grp-{g['id']}"] for g in r["resumo"]["grupos"]} == {g["id"]: g["soma_c"] for g in r["resumo"]["grupos"]}
    assert {c["id"]: v[f"cls-{c['id']}"] for c in r["classes"]} == {c["id"]: c["soma_c"] for c in r["classes"]}
    assert (v["fech-grupos"], v["fech-classes"], v["fech-lista"]) == (0, 0, 0)
    assert (v["lst-subtotal"], v["lst-acumulado"]) == (-1500, -1500)
    linha = re.search(r"<tr><td>5</td>.*?</tr>", corpo, re.S).group(0)            # emp 2: ausente no posterior
    assert "ausente do corte posterior" in linha and "R$ 0,00" not in linha
    assert all(h.startswith("/") for h in re.findall(r'href="([^"]*)"', corpo)) and "style=" not in corpo
    corpo = ok(app, "/variacao", exercicio=2025, anterior="2025-04-30", data_final="2025-06-30")
    assert 'id="indisponivel"' in corpo and not any(k.startswith(("lst-", "grp-", "cls-", "fech-")) for k in dados(corpo))
    assert dados(corpo)["var-anterior"] == 18500 and "var-posterior" not in dados(corpo)
    corpo = ok(app, "/variacao", exercicio=2025, anterior="2025-04-30", data_final="2025-02-28")
    assert "imediatamente anterior" in corpo                                     # par invertido: aviso, sem erro
    assert chamar(app, "/variacao", exercicio=2025, metrica="liquidacoes")[0] == "400 Bad Request"
    corpo = ok(app, "/empenho/cortes", entidade=1, anoempenho=2024, empenho=2, exercicio=2025)
    v = dados(corpo)
    assert v["emp-2025-02-28-1-s1_saldo_total_c"] == 5000 and 'id="emp-ausente-2025-04-30"' in corpo
    assert not any(k.startswith("emp-2025-04-30") for k in v)
    corpo = ok(app, "/empenho/cortes", entidade=15, anoempenho=2024, empenho=1, exercicio=2025)
    assert 'id="emp-lacuna-2025-06-30"' in corpo and "R$" not in corpo.split('id="emp-lacuna-2025-06-30"')[1].split("</tr>")[0]
    assert 'href="/empenho/cortes?' in ok(app, "/empenho", entidade=1, anoempenho=2024, empenho=1, exercicio=2025)
    assert 'href="/variacao?' in ok(app, "/evolucao", exercicio=2025, entidade=1)


# ================================================================== armazem real
@pytest.fixture(scope="module")
def app_real(real):
    return Aplicacao(real["cfg"].banco)


@pytest.fixture(scope="module")
def bruto_real(real):
    return rb.Bruto(real["con"], real["armazem"])


def _pares(p, ex):
    cortes = [c["data_final"] for c in p.cortes()["cortes"] if c["exercicio"] == ex]
    return list(zip(cortes, cortes[1:]))


def test_todos_os_pares_adjacentes_e_o_que_salta_lacuna_iguais_ao_bruto(real, bruto_real):
    p = real["painel"]
    escopos = [None] + [e["entidade"] for e in p.entidades()["entidades"]]
    pares = [(2025, a, b) for a, b in _pares(p, 2025)] + [(2026, a, b) for a, b in _pares(p, 2026)]
    pares.append((2026, "2026-02-28", "2026-04-30"))                       # salta a lacuna de 31/03 (Municipio)
    disponiveis = 0
    for ex, a, b in pares:
        for ent in escopos:
            for metrica in ("s1", "pagamentos"):
                r = _confere_com_o_bruto(p, bruto_real, ex, a, b, ent, metrica)
                assert not r["chaves_repetidas"]                           # criterio de parada: nenhuma chave repetida
                if r["disponivel"]:
                    disponiveis += 1
                    chave = {"s1": "saldo_total", "pagamentos": "pagamentos"}[metrica]
                    ind = {lado: p.indicadores(ex, d, ent)["valores"][chave]["valor_c"] for lado, d in (("a", a), ("b", b))}
                    assert r["variacao_c"] == ind["b"] - ind["a"], (ex, a, b, ent, metrica)
    assert len(pares) == 12 and disponiveis == 144                         # 264 combinacoes; as demais sem valor num lado


def test_salto_de_lacuna_e_pares_com_lacuna_no_municipio(real):
    p = real["painel"]
    assert p.variacao(2026, "2026-02-28", "2026-04-30")["disponivel"]
    for a, b in (("2026-01-31", "2026-02-28"), ("2026-02-28", "2026-03-31"), ("2026-08-31", "2026-12-31")):
        r = p.variacao(2026, a, b)
        assert not r["disponivel"] and "Município indisponível" in r["motivo_indisponivel"]


def test_pagina_a_pagina_ate_a_variacao_total(real):
    p = real["painel"]
    acumulado, desloc, n = 0, 0, 0
    while True:
        r = p.variacao(2026, "2026-02-28", "2026-04-30", None, "s1", limite=50, deslocamento=desloc)
        acumulado += r["lista"]["subtotal_c"]
        assert r["lista"]["acumulado_c"] == acumulado
        n += len(r["lista"]["itens"])
        if r["lista"]["ultima_pagina"]:
            break
        desloc += 50
    assert acumulado == r["variacao_c"] and n == r["chaves"]["com_variacao"] and n > 50


def test_casos_reais_5659_2025_e_2401751_2023(real, bruto_real):
    p = real["painel"]
    for ent, ano, emp, ex in ((1, 2025, 5659, 2026), (1, 2023, 2401751, 2025), (1, 2023, 2401751, 2026),
                              (15, 2023, 1751, 2026)):
        h = p.historico_empenho(ent, ano, emp, ex)
        x = bruto_real.empenho_nos_cortes(ent, ano, emp, ex)
        assert [(c["data_final"], c["situacao"]["codigo"]) for c in h["cortes"]] == [(y["data_final"], y["situacao"]) for y in x]
        for c, y in zip(h["cortes"], x):
            if c["tem_valor"]:
                assert [{k: o["valores"][k] for k in CAMPOS_DO_HISTORICO} for o in c["ocorrencias"]] == [
                    {k: v[BRUTO[k]] for k in CAMPOS_DO_HISTORICO} for v in y["ocorrencias"]], (ent, ano, emp, c["data_final"])
    h = p.historico_empenho(1, 2025, 5659, 2026)
    assert all(c["presente"] for c in h["cortes"]) and len(h["cortes"]) == 7
    assert h["cortes"][-1]["rotulos"]                                      # 31/12/2026: corte posterior a coleta
    h15 = p.historico_empenho(15, 2023, 1751, 2026)                        # 31/01, 31/03 e 31/12: corte nao coletado
    assert [c["data_final"] for c in h15["cortes"] if c["situacao"]["codigo"] == "sem_coleta"] == [
        "2026-01-31", "2026-03-31", "2026-12-31"]
    r, itens = _lista_completa(p, 2026, "2026-08-31", "2026-12-31", 1, "s1")
    x = {(l["chave"]): l["contribuicao_c"] for l in bruto_real.contribuicoes(2026, "2026-08-31", "2026-12-31", 1, "s1")["linhas"]}
    assert {_chave(i): i["contribuicao_c"] for i in itens}.get((1, 2025, 5659), 0) == x[(1, 2025, 5659)]


def test_tela_igual_ao_painel_reais(real, app_real):
    p = real["painel"]
    for pagina in (1, 9):
        r = p.variacao(2025, "2025-10-31", "2025-12-31", None, "s1", limite=50, deslocamento=(pagina - 1) * 50)
        corpo = ok(app_real, "/variacao", exercicio=2025, anterior="2025-10-31", data_final="2025-12-31", pagina=pagina)
        v = dados(corpo)
        assert v["var-total"] == r["variacao_c"] and v["lst-acumulado"] == r["lista"]["acumulado_c"]
        assert all(v[f"lst-{i['posicao']}"] == i["contribuicao_c"] for i in r["lista"]["itens"])
        assert (v["fech-grupos"], v["fech-classes"], v["fech-lista"]) == (0, 0, 0)
        assert 'id="aviso-pares"' in corpo
    assert r["lista"]["ultima_pagina"] and v["lst-acumulado"] == v["var-total"]          # pagina 9 de 9
    h = p.historico_empenho(1, 2025, 5659, 2026)
    v = dados(ok(app_real, "/empenho/cortes", entidade=1, anoempenho=2025, empenho=5659, exercicio=2026))
    for c in h["cortes"]:
        assert v[f"emp-{c['data_final']}-1-s1_saldo_total_c"] == c["ocorrencias"][0]["valores"]["s1_saldo_total_c"]


def test_desempenho_com_o_corte_inteiro(app_real):
    for caminho, q in (("/variacao", dict(exercicio=2026, anterior="2026-02-28", data_final="2026-04-30")),
                       ("/variacao", dict(exercicio=2025, anterior="2025-02-28", data_final="2025-12-31", metrica="pagamentos")),
                       ("/empenho/cortes", dict(entidade=1, anoempenho=2023, empenho=2401751, exercicio=2026))):
        t = time.perf_counter()
        status, _, _ = chamar(app_real, caminho, **q)
        assert status == "200 OK" and time.perf_counter() - t < 3, (caminho, q)
