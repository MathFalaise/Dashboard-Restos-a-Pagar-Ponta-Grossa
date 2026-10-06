"""Tests of sub-stage 05.6: data quality and the situation of the differences (contract section 6; plan, section
05.6).

"derivacao" regime (contract section 4.1): anomalies and checks are NOT recalculated; the panel reads what the
derivation recorded and the tests check counts, scope and links against the derivation's tables.
* anomalies by type with the derivation's count; drill-down only with a complete key (and exact only in the current
  snapshot); an anomaly without a key only in the aggregate;
* set-level checks, interpreted by description (R5); a description outside the catalog = "significado nao
  catalogado"; never listed as commitments;
* the five situations of the differences with the RREO apart and equal to the reconciliation's; a zero difference is
  never counted as explained.
SINTETICO = temporary database with invented records (fixture `mundo`).
"""
import re
import time
from collections import Counter

import pytest
from conftest import chamar, dados, ok, registro_sintetico as _reg, links_permitidos

from rp import derivar
from rp.interface import Aplicacao
from rp.painel.consulta import NAO_CATALOGADA, SITUACOES_DAS_DIFERENCAS, ErroDoPainel

T0, T1 = "2026-09-29T20:00:00-03:00", "2026-09-30T08:00:00-03:00"


def _secao(corpo, ident):
    return re.search(rf'<section class="grupo" id="{ident}">.*?</section>', corpo, re.S).group(0)


# ================================================================== SINTETICO
@pytest.fixture
def qualidade(mundo):
    """Entity 1, cut-off 31/12/2025 collected twice (the second snapshot is the current one): LIQ-NEG, COPIA-24 and
    PAGOPROC-SEM-PROC + SEM-SALDO-ABERTURA, each in both snapshots. After processing, it adds by hand: an anomaly
    WITHOUT a commitment key; two checks outside the catalog (unknown description; known description recorded by
    another rule); and a 2024 -> 2025 continuity of entity 1 with 1 failure and the matching
    SALDO-SEM-CONTINUIDADE anomaly (in the 2025 snapshot), for the link by rule and scope."""
    mundo.catalogos({1: [2025]})
    regs = [_reg(1, aproc=100.0, liquidado=-5.0), _reg(2400001, aproc=10.0), _reg(3, aproc=0, pagoProc=2.0)]
    mundo.listagem(1, 2025, "2025-12-31", regs, T0)
    mundo.listagem(1, 2025, "2025-12-31", regs, T1)
    _, did = mundo.processar()
    regra = dict(((c, v), i) for i, c, v in mundo.con.execute("SELECT id, codigo, versao FROM regra"))
    cid = mundo.con.execute("SELECT MAX(id) FROM coleta WHERE tipo='rp_listagem'").fetchone()[0]
    with mundo.con:
        mundo.con.execute("INSERT INTO anomalia VALUES (?,?,?,?,?,?,?,?)",
                          (did, regra[("ANOM-REG", 1)], "LIQ-NEG", cid, None, None, None, '{"liquidado_c": -1}'))
        mundo.con.execute("INSERT INTO verificacao VALUES (?,?,?,?,?,?)",
                          (did, regra[("ANOM-CONT", 1)], "verificação inventada", '{"exercicio": 2025}', 5, 2))
        mundo.con.execute("INSERT INTO verificacao VALUES (?,?,?,?,?,?)",
                          (did, regra[("PAR-24", 1)], "continuidade fechamento→abertura", '{"exercicio": 2025}', 4, 1))
        mundo.con.execute("INSERT INTO verificacao VALUES (?,?,?,?,?,?)",
                          (did, regra[("ANOM-CONT", 1)], "continuidade fechamento→abertura",
                           '{"de": 2024, "entidade": 1, "para": 2025, "snapshots": []}', 7, 1))
        mundo.con.execute("INSERT INTO anomalia VALUES (?,?,?,?,?,?,?,?)",
                          (did, regra[("ANOM-CONT", 1)], "SALDO-SEM-CONTINUIDADE", cid, 1, 2023, 9, '{"s1_final_c": 100}'))
    return mundo


def test_SINTETICO_anomalias_por_tipo_e_sem_ocorrencia(qualidade):
    with qualidade.painel() as p:
        q = p.qualidade()
        t = {x["tipo"]: x for x in q["anomalias"]["por_tipo"]}
        assert sorted(t) == ["COPIA-24", "LIQ-NEG", "PAGOPROC-SEM-PROC", "SALDO-SEM-CONTINUIDADE", "SEM-SALDO-ABERTURA"]
        assert (t["LIQ-NEG"]["ocorrencias"], t["LIQ-NEG"]["em_snapshots_vigentes"], t["LIQ-NEG"]["com_chave_de_empenho"]) == (3, 2, 2)
        assert (t["COPIA-24"]["ocorrencias"], t["COPIA-24"]["em_snapshots_vigentes"], t["COPIA-24"]["snapshots"]) == (2, 1, 2)
        assert t["LIQ-NEG"]["regra"] == "ANOM-REG v1" and t["LIQ-NEG"]["exercicios"] == [2025]
        assert "CHAVE-DUP" in {x["tipo"] for x in q["anomalias"]["tipos_sem_ocorrencia"]}
        assert q["anomalias"]["total"] == 3 + 2 + 2 + 2 + 1


def test_SINTETICO_ligacao_so_com_chave_e_exata_so_no_vigente(qualidade):
    with qualidade.painel() as p:
        a = p.anomalias("LIQ-NEG")
        itens = a["itens"]
        assert (len(itens), a["total"], a["sem_chave"]) == (2, 2, 1)             # without a key: only in the aggregate
        assert all(x["chave"] for x in itens)
        vig = [x for x in itens if x["vigente"]]
        ant = [x for x in itens if not x["vigente"]]
        assert len(vig) == len(ant) == 1
        assert vig[0]["ligacao"]["destino"] == "empenho" and vig[0]["retrato"] == "vigente"
        assert ant[0]["ligacao"]["destino"] == "retratos" and ant[0]["retrato"] == "retrato anterior do corte"
        d = p.detalhe_empenho(1, 2024, 1, 2025, "2025-12-31")                    # the linked record
        assert d["ocorrencias"][0]["campos"]["liquidado_c"]["valor"] == vig[0]["detalhe"]["liquidado_c"] == -500
        assert len(p.anomalias("LIQ-NEG", limite=1, deslocamento=1)["itens"]) == 1
        assert p.anomalias("CHAVE-DUP")["itens"] == []
        with pytest.raises(ErroDoPainel):
            p.anomalias("NAO-EXISTE")


def test_SINTETICO_verificacao_fora_do_catalogo_nao_e_interpretada(qualidade):
    with qualidade.painel() as p:
        vs = {(v["descricao"], v["regra"]): v for v in p.qualidade()["verificacoes"]}
        inventada = vs[("verificação inventada", "ANOM-CONT v1")]
        outra_regra = vs[("continuidade fechamento→abertura", "PAR-24 v1")]
        for v in (inventada, outra_regra):
            assert not v["catalogada"] and v["situacao"] == NAO_CATALOGADA and v["significado_de_falhas"] == NAO_CATALOGADA
            assert v["anomalias_ligadas"] == [] and all(i["situacao"] == NAO_CATALOGADA for i in v["itens"])
        assert (inventada["verificados"], inventada["falhas"]) == (5, 2)                 # raw numbers preserved


def test_SINTETICO_ligacao_da_verificacao_por_regra_e_escopo(qualidade):
    with qualidade.painel() as p:
        v = {(x["descricao"], x["regra"]): x for x in p.qualidade()["verificacoes"]}[
            ("continuidade fechamento→abertura", "ANOM-CONT v1")]
        assert v["situacao"] == "com falhas" and v["itens"][0]["situacao"] == "com falhas"
        assert v["itens"][0]["anomalias_do_escopo"] == [
            {"tipo": "SALDO-SEM-CONTINUIDADE", "exercicio": 2025, "entidade": 1},
            {"tipo": "DESCONTINUIDADE", "exercicio": 2025, "entidade": 1}]
        lista = p.anomalias("SALDO-SEM-CONTINUIDADE", exercicio=2025, entidade=1)
        assert lista["total"] == 1 and lista["itens"][0]["chave"] == {"entidade": 1, "anoempenho": 2023, "empenho": 9}
        assert p.anomalias("SALDO-SEM-CONTINUIDADE", exercicio=2024, entidade=1)["total"] == 0
    corpo = ok(Aplicacao(qualidade.cfg.banco), "/qualidade")
    assert 'href="/qualidade?tipo=SALDO-SEM-CONTINUIDADE&amp;exercicio=2025&amp;entidade=1"' in _secao(corpo, "verificacoes")


def test_SINTETICO_tela_da_qualidade(qualidade):
    app = Aplicacao(qualidade.cfg.banco)
    status, cab, corpo = chamar(app, "/qualidade", tipo="LIQ-NEG")
    assert status == "200 OK" and "default-src 'none'" in cab["Content-Security-Policy"]
    v = dados(corpo)
    assert (v["anom-LIQ-NEG"], v["anom-LIQ-NEG-vig"]) == (3, 2)
    oc = _secao(corpo, "ocorrencias")
    assert oc.count('href="/empenho?') == 1 and oc.count('href="/retratos?') == 1      # 1 current, 1 earlier snapshot
    assert v["ocorr-sem-chave"] == 1 and 'id="sem-chave"' in oc
    assert "/empenho?" not in _secao(corpo, "verificacoes")                             # a check does not become a commitment
    assert NAO_CATALOGADA in _secao(corpo, "verificacoes")
    assert links_permitidos(corpo) and "style=" not in corpo
    assert 'id="sem-ocorrencia"' in ok(app, "/qualidade", tipo="CHAVE-DUP")
    assert chamar(app, "/qualidade", tipo="NAO-EXISTE")[0] == "400 Bad Request"


# ================================================================== real store
@pytest.fixture(scope="module")
def q_real(real):
    return real["painel"].qualidade()


def test_anomalias_iguais_a_derivacao(real, q_real):
    con, did = real["con"], real["did"]
    esperado = dict(con.execute("SELECT tipo, COUNT(*) FROM anomalia WHERE derivacao_id=? GROUP BY tipo", (did,)))
    vig = set(derivar.coletas_vigentes(con).values())
    nos_vigentes = Counter(t for t, c in con.execute("SELECT tipo, coleta_id FROM anomalia WHERE derivacao_id=?", (did,))
                           if c in vig)
    t = {x["tipo"]: x for x in q_real["anomalias"]["por_tipo"]}
    assert {k: x["ocorrencias"] for k, x in t.items()} == esperado == {
        "COPIA-24": 17434, "LIQ-NEG": 2096, "PAGOPROC-SEM-PROC": 99, "PAR-INSCRICAO-DIVERGENTE": 55}
    assert {k: x["em_snapshots_vigentes"] for k, x in t.items()} == dict(nos_vigentes)
    catalogo = {c for (c,) in con.execute("SELECT codigo FROM anomalia_tipo")}
    assert {x["tipo"] for x in q_real["anomalias"]["tipos_sem_ocorrencia"]} == catalogo - set(esperado)
    assert all(x["com_chave_de_empenho"] == x["ocorrencias"] for x in t.values())       # today all of them have a key


def test_verificacoes_iguais_a_derivacao_e_interpretadas(real, q_real):
    esperado = {(d, f"{c} v{v}"): (n, ver, fal) for d, c, v, n, ver, fal in real["con"].execute(
        "SELECT v.descricao, g.codigo, g.versao, COUNT(*), SUM(v.verificados), SUM(v.falhas) FROM verificacao v JOIN regra g "
        "ON g.id = v.regra_id WHERE v.derivacao_id=? GROUP BY 1, 2, 3", (real["did"],))}
    vs = {(v["descricao"], v["regra"]): v for v in q_real["verificacoes"]}
    assert {k: (len(v["itens"]), v["verificados"], v["falhas"]) for k, v in vs.items()} == esperado
    assert {v["descricao"]: v["situacao"] for v in vs.values()} == {
        "continuidade fechamento→abertura": "sem falha", "pareamento de cópias 24xxxxx": "sem falha",
        "conciliação RREO × API (colunas com diferença)": "colunas com diferença: 466 de 792",
        "RREO sem valores extraídos (ver problemas da normalização)": "PDFs não lidos: 3"}
    assert all(v["catalogada"] for v in vs.values())
    cont = vs[("continuidade fechamento→abertura", "ANOM-CONT v1")]
    assert [a["tipo"] for a in cont["anomalias_ligadas"]] == ["SALDO-SEM-CONTINUIDADE", "DESCONTINUIDADE"]
    assert all(len(i["snapshots"]) == 2 for i in cont["itens"])                         # the scope carries both snapshots


def test_cinco_situacoes_iguais_a_reconciliacao(real, q_real):
    p, dr = real["painel"], q_real["diferencas_rreo"]
    linhas = p.reconciliacao()["linhas"]
    for regra in ("RREO-COL v1", "RREO-COL v2"):
        assert dr["por_regra"][regra] == {s: sum(1 for x in linhas if x["regra_agregacao"]["regra"] == regra and
                                                 x["situacao_da_diferenca"] == s) for s in SITUACOES_DAS_DIFERENCAS}
        assert dr["por_regra"][regra]["sem diferença"] == sum(1 for x in linhas if x["regra_agregacao"]["regra"] == regra
                                                               and x["diferenca_c"] == 0)
    assert dr["sem_diferenca_contada_como_explicada"] == 0
    assert not any(x["diferenca_c"] == 0 and x["situacao_da_diferenca"] != "sem diferença" for x in linhas)
    assert (dr["documentos"], dr["linhas"], dr["total_por_regra"]) == (32, 768, {"RREO-COL v1": 384, "RREO-COL v2": 384})
    coe = p.coerencia_entre_publicacoes()["comparacoes"]
    exibidas = [x for x in coe if x["mais_recente"]]
    assert len(exibidas) == 12 and dr["total_coerencia"] == {"exibida": 12, "todas": len(coe)}
    contagem = Counter(x["situacao_da_diferenca"] for x in exibidas)
    assert dr["coerencia"]["exibida"] == {s: contagem[s] for s in SITUACOES_DAS_DIFERENCAS}
    c = dr["conferencia_com_a_verificacao"]
    assert c["confere"] and (c["verificacao"]["com_diferenca"], c["pdfs_repetidos"]["com_diferenca"],
                             c["reconciliacao"]["com_diferenca"]) == (466, 8, 458)


def test_drill_down_real_leva_ao_registro(real):
    p = real["painel"]
    for tipo, campo in (("LIQ-NEG", "liquidado_c"), ("PAGOPROC-SEM-PROC", "pago_proc_c")):
        itens = [x for x in p.anomalias(tipo, limite=200)["itens"] if x["ligacao"] and x["ligacao"]["destino"] == "empenho"]
        assert itens
        for x in itens[:40]:
            c, lig = x["chave"], x["ligacao"]
            d = p.detalhe_empenho(c["entidade"], c["anoempenho"], c["empenho"], lig["exercicio"], lig["data_final"])
            assert d["encontrado"] and any(o["campos"][campo]["valor"] == x["detalhe"][campo] for o in d["ocorrencias"])
            assert any(o["proveniencia"]["snapshot_uid"] == x["snapshot"] for o in d["ocorrencias"])


def test_tela_igual_ao_painel_reais(real, q_real):
    app = Aplicacao(real["cfg"].banco)
    t = time.perf_counter()
    corpo = ok(app, "/qualidade", tipo="PAR-INSCRICAO-DIVERGENTE")
    assert time.perf_counter() - t < 3
    v = dados(corpo)
    for x in q_real["anomalias"]["por_tipo"]:
        assert (v[f"anom-{x['tipo']}"], v[f"anom-{x['tipo']}-vig"]) == (x["ocorrencias"], x["em_snapshots_vigentes"])
    for i, x in enumerate(q_real["verificacoes"], 1):
        assert (v[f"verif-{i}-v"], v[f"verif-{i}-f"]) == (x["verificados"], x["falhas"])
        assert re.search(rf'id="verif-{i}-sit">([^<]*)<', corpo).group(1) == x["situacao"]
    dr = q_real["diferencas_rreo"]
    for s, curta in (("sem diferença", "sem"), ("explicada", "exp"), ("parcialmente explicada", "parc"), ("hipótese", "hip"),
                     ("não determinada", "nd")):
        assert (v[f"sit-v1-{curta}"], v[f"sit-v2-{curta}"], v[f"sit-coe-{curta}"], v[f"sit-coe-todas-{curta}"]) == (
            dr["por_regra"]["RREO-COL v1"][s], dr["por_regra"]["RREO-COL v2"][s], dr["coerencia"]["exibida"][s],
            dr["coerencia"]["todas"][s])
    assert "As contagens conferem." in corpo and "/empenho?" not in _secao(corpo, "verificacoes")
    assert _secao(corpo, "ocorrencias").count('href="/empenho?') == 50                 # PAR-24: all in the current one
    reconc = ok(app, "/reconciliacao")                                                   # the consistency shown stays the same
    assert len(re.findall(r'id="coe-', reconc)) == dr["total_coerencia"]["exibida"]
    for x in q_real["anomalias"]["por_tipo"]:                                            # no creditor identification
        chaves = {k for i in real["painel"].anomalias(x["tipo"], limite=500)["itens"] for k in (i["detalhe"] or {})}
        assert not chaves & {"nome", "cnpj", "cnpj_nome", "fornecedor"}, (x["tipo"], chaves)
