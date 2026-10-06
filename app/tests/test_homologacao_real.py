"""Homologation of the interface (sub-stage 04.6) over the project's REAL store.

A temporary database built by only reading data/snapshots/ (the conftest `real` fixture). Three levels are compared:
  1. INDEPENDENT recalculation from the API's raw JSON kept in the store (no normalization, no derivation);
  2. the panel layer (rp.painel.Painel);
  3. the value shown on the page (<data value> in cents).
Specification sections: 4 (indicators), 5 (truth against Elotech), 6 (no contamination by the RREO),
7 (provenance), 8 (snapshot), 14 (performance), 17 (filters), 18 (detail), 19 (reconciliation), 20 (experimental
rules). The databases changed in the RREO tests are temporary COPIES; the store is only read.
"""
import hashlib
import json
import re
import sqlite3
import time
from decimal import Decimal

import pytest
from conftest import chamar, dados, ok

from rp.interface import Aplicacao, paginas
from rp.painel import Painel

CAMPOS_API = {"proc": "proc_c", "aproc": "aproc_c", "pagoProc": "pago_proc_c", "pagoAProc": "pago_aproc_c",
              "liquidado": "liquidado_c", "canceladoAProc": "cancelado_aproc_c", "canceladoProc": "cancelado_proc_c",
              "retencao": "retencao_c", "pagoProcEstornado": "pago_proc_estornado_c",
              "pagoAProcEstornado": "pago_aproc_estornado_c"}
CORTES = [(2024, "2024-12-31", None), (2025, "2025-12-31", None), (2026, "2026-08-31", None), (2026, "2026-08-31", 1),
          (2026, "2026-08-31", 15), (2025, "2025-06-30", 5), (2016, "2016-12-31", None), (2026, "2026-04-30", None)]
UID = re.compile(r"[0-9a-f]{32}")


@pytest.fixture(scope="module")
def app(real):
    return Aplicacao(real["cfg"].banco)


# ------------------------------------------------------------------ independent recalculation (raw JSON)
def _c(v):
    """API value (float read as Decimal) -> cents, without going through the normalizer."""
    return int(Decimal(str(v)) * 100) if v is not None else 0


def registros_brutos(real, uid):
    """content[] items of all pages of the snapshot, read from the store (manifest -> objects -> JSON)."""
    rel = real["con"].execute("SELECT manifesto FROM coleta WHERE snapshot_uid=?", (uid,)).fetchone()[0]
    m = real["armazem"].ler_manifesto(rel)
    itens = []
    for resp in m["respostas"]:
        corpo = real["armazem"].ler_objeto(resp["sha256"])
        itens += json.loads(corpo, parse_float=Decimal)["content"]
    return itens


def recalcular(itens):
    """The same indicators as the screen, recalculated from the raw data with the documented formulas (stage 02, S1-S3)."""
    s = {k: 0 for k in ("registros", "inscricao_processada", "inscricao_nao_processada", "inscricao_total",
                        "pago_processado", "pago_nao_processado", "pagamentos", "liquidacoes", "cancelamentos",
                        "retencoes", "saldo_total", "saldo_a_liquidar", "saldo_liquidado_a_pagar")}
    for r in itens:
        v = {k: _c(r.get(k)) for k in CAMPOS_API}
        s["registros"] += 1
        s["inscricao_processada"] += v["proc"]
        s["inscricao_nao_processada"] += v["aproc"]
        s["inscricao_total"] += v["proc"] + v["aproc"]
        s["pago_processado"] += v["pagoProc"]
        s["pago_nao_processado"] += v["pagoAProc"]
        s["pagamentos"] += v["pagoProc"] + v["pagoAProc"]
        s["liquidacoes"] += v["liquidado"]
        s["cancelamentos"] += v["canceladoAProc"] + v["canceladoProc"]
        s["retencoes"] += v["retencao"]
        s["saldo_total"] += v["proc"] + v["aproc"] - v["pagoProc"] - v["pagoAProc"] - v["canceladoAProc"]
        s["saldo_a_liquidar"] += v["aproc"] - v["liquidado"] - v["canceladoAProc"]
        s["saldo_liquidado_a_pagar"] += v["proc"] - v["pagoProc"] + v["liquidado"] - v["pagoAProc"]
    return s


def snapshot_vigente(real, entidade, ex, df):
    """Independent choice of the snapshot: the most recent complete collection of the cut-off."""
    row = real["con"].execute(
        "SELECT snapshot_uid FROM coleta WHERE tipo='rp_listagem' AND status='completa' AND tipo_pesquisa IS NULL AND "
        "entidade=? AND exercicio=? AND data_inicial=? AND data_final=? ORDER BY coletada_em DESC, snapshot_uid DESC "
        "LIMIT 1", (entidade, ex, f"{ex}-01-01", df)).fetchone()
    return row and row[0]


# ================================================================== sections 4 and 5: indicators = raw = panel = screen
@pytest.mark.parametrize("ex, df, ent", CORTES)
def test_indicadores_recalculados_do_bruto_iguais_ao_painel_e_a_tela(app, real, ex, df, ent):
    ind = real["painel"].indicadores(ex, df, ent)
    assert ind["disponivel"], (ex, df, ent, ind["motivo_indisponivel"])
    usados = [e for e in ind["entidades"] if e["entra_no_total"]]
    itens = []
    for e in usados:                                   # the snapshot used is the current one, chosen independently
        assert e["snapshot"]["snapshot_uid"] == snapshot_vigente(real, e["entidade"], ex, df)
        itens += registros_brutos(real, e["snapshot"]["snapshot_uid"])
    assert sorted(ind["retrato"]["snapshots"]) == sorted(e["snapshot"]["snapshot_uid"] for e in usados)
    esperado = recalcular(itens)
    painel = {k: v["valor_c"] for k, v in ind["valores"].items() if k in esperado}
    assert painel == esperado, (ex, df, ent)
    tela = dados(ok(app, "/", exercicio=ex, data_final=df, entidade=ent))
    mostrados = [i for _, ids in paginas.GRUPOS for i in ids]
    assert {k: tela[f"ind-{k}"] for k in mostrados} == {k: esperado[k] for k in mostrados}, (ex, df, ent)


def test_municipio_so_soma_entidades_do_catalogo_oficial(real):
    """The Municipality total = entities whose official catalog (the API's fiscal years) contains the fiscal year."""
    con = real["con"]
    for ex, df in ((2016, "2016-12-31"), (2024, "2024-12-31"), (2026, "2026-08-31")):
        ind = real["painel"].indicadores(ex, df)
        for e in ind["entidades"]:
            cid = con.execute("SELECT id FROM coleta WHERE tipo='exercicios' AND status='completa' AND entidade=? "
                              "ORDER BY coletada_em DESC, snapshot_uid DESC LIMIT 1", (e["entidade"],)).fetchone()
            anos = set()
            if cid:
                corpo = registros_catalogo(real, cid[0])
                anos = {x["id"]["exercicio"] for x in corpo}
            no_catalogo = ex in anos
            assert e["entra_no_total"] == (no_catalogo and e["snapshot"] is not None), (ex, e["entidade"])
            if anos and not no_catalogo:
                assert e["situacao_do_dado"]["codigo"] == "inexistente"


def registros_catalogo(real, coleta_id):
    rel = real["con"].execute("SELECT manifesto FROM coleta WHERE id=?", (coleta_id,)).fetchone()[0]
    m = real["armazem"].ler_manifesto(rel)
    return json.loads(real["armazem"].ler_objeto(m["respostas"][0]["sha256"]))


def test_valores_de_2024_2025_2026_fixados_na_linha_de_base(real):
    """Municipality values recorded in the 04.6 starting state (docs/stages/04-pipeline/results/04_6_estado_antes.json):
    the homologated interface cannot introduce any divergence from them."""
    esperado = {
        (2024, "2024-12-31"): (dict(registros=6427, inscricao_total=16290699167, saldo_total=1897498899,
                                    pagamentos=12519386373, cancelamentos=1873813895), 67817165, "parcialmente explicada"),
        (2025, "2025-12-31"): (dict(registros=5878, inscricao_total=25055105773, saldo_total=2126717428,
                                    pagamentos=19756547960, cancelamentos=3171840385), 92570262, "explicada"),
        (2026, "2026-08-31"): (dict(registros=5760, inscricao_total=20534187451, saldo_total=8084409029,
                                    pagamentos=11619906788, cancelamentos=829871634), 23767875, "não determinada"),
    }
    for (ex, df), (v, dif, situacao) in esperado.items():
        ind = real["painel"].indicadores(ex, df)
        assert {k: ind["valores"][k]["valor_c"] for k in v} == v
        conf = ind["conferencia_rreo"]
        assert (conf["diferenca_c"], conf["situacao_da_diferenca"]) == (dif, situacao)
        assert conf["api"]["valor_c"] == v["saldo_total"]           # the API is still the main value


def test_hash_da_derivacao_igual_ao_do_banco_ativo(real):
    h = real["con"].execute("SELECT hash_resultado FROM derivacao_execucao WHERE id=?", (real["did"],)).fetchone()[0]
    h2909 = real["con"].execute("SELECT hash_resultado FROM derivacao_execucao WHERE id=?", (real["did_2909"],)).fetchone()[0]
    assert h.startswith("2f6b4e295ce79593") and h2909.startswith("b8a0b2ed2328bf09")


# ================================================================== section 5: regression cases against the raw data
@pytest.mark.parametrize("ent, ano, emp, ex, df", [(1, 2025, 5659, 2026, "2026-12-31"), (1, 2016, 11963, 2026, "2026-12-31"),
                                                   (1, 2023, 2401751, 2024, "2024-12-31"),
                                                   (15, 2023, 1751, 2024, "2024-12-31"),
                                                   (5, 2025, 1485, 2026, "2026-08-31")])
def test_casos_reais_detalhe_igual_ao_json_da_api(app, real, ent, ano, emp, ex, df):
    corpo = ok(app, "/empenho", entidade=ent, anoempenho=ano, empenho=emp, exercicio=ex, data_final=df)
    v = dados(corpo)
    uid = re.search(r"Snapshot</dt><dd><code>([0-9a-f]{32})", corpo).group(1)
    brutos = [r for r in registros_brutos(real, uid) if (r["entidade"], r["anoempenho"], r["empenho"]) == (ent, ano, emp)]
    assert len(brutos) == 1
    for campo_api, col in CAMPOS_API.items():
        assert v[f"campo-{col}"] == _c(brutos[0].get(campo_api)), (emp, campo_api)
    s1 = recalcular(brutos)["saldo_total"]
    assert v["derivado-s1_saldo_total_c"] == s1


# ================================================================== section 6: no contamination by the RREO
def _copia(real, tmp_path):
    destino = tmp_path / "copia.sqlite"
    with sqlite3.connect(destino) as d:
        real["con"].backup(d)
    d.close()
    return destino


def _indicadores(caminho, cortes):
    with Painel.abrir(caminho) as p:
        return {c: {k: v["valor_c"] for k, v in p.indicadores(*c)["valores"].items()} for c in cortes}


RREO_CORTES = [(2024, "2024-12-31", None), (2026, "2026-08-31", None), (2026, "2026-08-31", 1)]


def test_indicador_principal_usa_elotech_e_sobrevive_sem_rreo(real, tmp_path):
    antes = _indicadores(real["cfg"].banco, RREO_CORTES)
    copia = _copia(real, tmp_path)
    with sqlite3.connect(copia) as con:           # removes every RREO data from the COPY (normalized and derived)
        for t in ("conciliacao_rreo", "rreo_valor", "rreo_extracao"):
            con.execute(f"DELETE FROM {t}")
    con.close()
    assert _indicadores(copia, RREO_CORTES) == antes
    app = Aplicacao(copia)
    for ex, df, ent in RREO_CORTES:
        corpo = ok(app, "/", exercicio=ex, data_final=df, entidade=ent)
        assert "sem RREO transcrito" in corpo and 'id="conf-rreo"' not in corpo
        assert {k: v for k, v in dados(corpo).items() if k.startswith("ind-")} == {
            f"ind-{k}": antes[(ex, df, ent)][k] for _, ids in paginas.GRUPOS for k in ids}
    assert ok(app, "/reconciliacao")


def test_alterar_o_rreo_nao_altera_a_api_e_a_divergencia_aparece(real, tmp_path):
    antes = _indicadores(real["cfg"].banco, RREO_CORTES)
    with Painel.abrir(real["cfg"].banco) as p:
        conf0 = p.indicadores(2026, "2026-08-31")["conferencia_rreo"]
    copia = _copia(real, tmp_path)
    delta = 1234567                                # R$ 12.345,67 more in the published RREO (only in the copy)
    with sqlite3.connect(copia) as con:
        con.execute("UPDATE conciliacao_rreo SET valor_rreo_c = valor_rreo_c + ?, diferenca_c = diferenca_c - ?",
                    (delta, delta))
        con.execute("UPDATE rreo_valor SET valor_c = valor_c + ?", (delta,))
    con.close()
    assert _indicadores(copia, RREO_CORTES) == antes          # the API does not change when the RREO changes
    with Painel.abrir(copia) as p:
        conf = p.indicadores(2026, "2026-08-31")["conferencia_rreo"]
        rec = p.reconciliacao(2026, "2026-08-31", "consolidado")["linhas"]
    assert conf["api"]["valor_c"] == conf0["api"]["valor_c"] == antes[(2026, "2026-08-31", None)]["saldo_total"]
    assert conf["rreo"]["valor_c"] == conf0["rreo"]["valor_c"] + delta
    assert conf["diferenca_c"] == conf0["diferenca_c"] - delta and conf["situacao_do_dado"]["codigo"] == "divergente"
    assert all(x["diferenca_c"] != 0 and x["api_c"] != x["rreo_c"] for x in rec)   # no column "closed" by force
    corpo = ok(Aplicacao(copia), "/", exercicio=2026, data_final="2026-08-31")
    v = dados(corpo)
    assert v["ind-saldo_total"] == v["conf-api"] == antes[(2026, "2026-08-31", None)]["saldo_total"]
    assert v["conf-dif"] == v["conf-api"] - v["conf-rreo"] != 0 and "diferença" in corpo


def test_nunca_substitui_api_por_rreo_nem_quando_o_rreo_coincide_com_outro_valor(real, tmp_path):
    """Even with the RREO set to any value, the indicator is still the API sum."""
    copia = _copia(real, tmp_path)
    with sqlite3.connect(copia) as con:
        con.execute("UPDATE conciliacao_rreo SET valor_rreo_c = 0, diferenca_c = valor_api_c")
    con.close()
    antes = _indicadores(real["cfg"].banco, RREO_CORTES)
    assert _indicadores(copia, RREO_CORTES) == antes


# ================================================================== section 7: provenance
def _objeto_no_armazem(real, sha):
    corpo = real["armazem"].ler_objeto(sha)            # checks the SHA-256 of the content
    return hashlib.sha256(corpo).hexdigest() == sha


def test_todo_indicador_principal_tem_proveniencia_ate_o_bruto(app, real):
    con = real["con"]
    for c in real["painel"].cortes()["cortes"]:
        ex, df = c["exercicio"], c["data_final"]
        corpo = ok(app, "/", exercicio=ex, data_final=df)
        if 'id="indisponivel"' in corpo:
            assert not re.search(r'id="ind-', corpo)
            continue
        cartoes = re.findall(r'<div class="indicador[^"]*">.*?</details></div>', corpo, re.S)
        assert len(cartoes) == sum(len(ids) for _, ids in paginas.GRUPOS)
        for cartao in cartoes:
            assert "Fonte: API Elotech" in cartao and "Natureza:" in cartao and "Origem do dado" in cartao
            uids = UID.findall(cartao.split("Snapshots</dt>")[1].split("</dd>")[0])
            assert uids, (ex, df)
            for uid in uids:
                row = con.execute("SELECT manifesto FROM coleta WHERE snapshot_uid=?", (uid,)).fetchone()
                assert row and (real["armazem"].raiz / row[0]).is_file()
            assert re.search(r"Derivação</dt><dd>\d+ \(hash <code>[0-9a-f]{64}</code>\)", cartao)


def test_dado_da_fonte_aponta_para_resposta_e_objeto_bruto(app, real):
    corpo = ok(app, "/empenho", entidade=1, anoempenho=2025, empenho=5659, exercicio=2026, data_final="2026-08-31")
    origem = corpo[corpo.index('id="origem"'):]
    assert "/empenhos/restos-a-pagar" in origem and "Resposta HTTP" in origem
    sha = re.search(r"Objeto bruto \(SHA-256\)</dt><dd><code>([0-9a-f]{64})", origem).group(1)
    uid = re.search(r"Snapshot</dt><dd><code>([0-9a-f]{32})", origem).group(1)
    assert _objeto_no_armazem(real, sha)
    assert real["con"].execute("SELECT 1 FROM resposta_bruta b JOIN coleta c ON c.id=b.coleta_id WHERE c.snapshot_uid=? "
                               "AND b.sha256=?", (uid, sha)).fetchone()


def test_valor_publicado_aponta_para_pdf_extracao_e_snapshot(app, real):
    corpo = ok(app, "/reconciliacao", exercicio=2026, data_final="2026-08-31", escopo="entidade")
    sha = re.search(r"SHA-256 do PDF</dt><dd><code>([0-9a-f]{64})", corpo).group(1)
    assert _objeto_no_armazem(real, sha) and real["armazem"].ler_objeto(sha)[:5] == b"%PDF-"
    assert re.search(r"Extração</dt><dd>rp-rreo-coordenadas/\d+ — PyMuPDF [\d.]+", corpo)
    assert re.search(r"Emitido em \(rodapé\)</dt><dd>29/set/2026", corpo)
    assert re.search(r"Snapshot do PDF</dt><dd><code>[0-9a-f]{32}</code>", corpo)


def test_diferenca_aponta_para_as_duas_fontes(app, real):
    corpo = ok(app, "/", exercicio=2024, data_final="2024-12-31")
    conf = corpo[corpo.index('id="conferencia-rreo"'):]
    conf = conf[:conf.index("</section>")]
    assert 'id="conf-api"' in conf and 'id="conf-rreo"' in conf and 'id="conf-dif"' in conf
    assert "API Elotech" in conf and "RREO Anexo VII" in conf and "emitido em" in conf
    rec = ok(app, "/reconciliacao", exercicio=2024, data_final="2024-12-31", escopo="consolidado")
    assert "Snapshots da API" in rec and "Snapshot do PDF" in rec


# ================================================================== section 8: snapshot
def test_todo_corte_diz_exercicio_corte_coleta_tipo_e_snapshot(app, real):
    for c in real["painel"].cortes()["cortes"]:
        ex, df = c["exercicio"], c["data_final"]
        br = f"{df[8:10]}/{df[5:7]}/{df[:4]}"
        for caminho in ("/", "/entidades", "/empenhos"):
            corpo = ok(app, caminho, exercicio=ex, data_final=df)
            h1 = re.search(r"<h1>(.*?)</h1>", corpo).group(1)
            assert f"exercício {ex}, corte {br}" in h1 and "(estado atual da base)" in h1, (caminho, h1)
            assert not re.search(r"Restos a Pagar de \d{4}", corpo)
            if 'id="retrato"' in corpo:
                texto = re.search(r'id="retrato">(.*?)</p>', corpo).group(1)
                assert texto.startswith(f"Estado atual da base para o exercício de {ex}, corte {br}, coletado ")
                assert "Retrato</dt><dd>atual" in corpo and "Snapshots usados" in corpo
    corpo = ok(app, "/", exercicio=2025, data_final="2025-12-31", em="2026-09-30")
    assert "(como a base estava em 30/09/2026)" in re.search(r"<h1>(.*?)</h1>", corpo).group(1)
    assert "Retrato</dt><dd>histórico — como a base estava em 30/09/2026" in corpo


# ================================================================== section 17: filters
def _subconjunto(real, ex, df, ent, pred):
    ind = real["painel"].indicadores(ex, df, ent)
    itens = [r for e in ind["entidades"] if e["entra_no_total"]
             for r in registros_brutos(real, e["snapshot"]["snapshot_uid"])]
    return recalcular([r for r in itens if pred(r)])


def _categoria(r):
    proc, aproc = _c(r.get("proc")), _c(r.get("aproc"))
    return ("ambos" if proc > 0 and aproc > 0 else "processado" if proc > 0 else "nao_processado" if aproc > 0
            else "sem_saldo_abertura")


FILTROS = [
    (2026, "2026-08-31", None, dict(categoria="nao_processado"), lambda r: _categoria(r) == "nao_processado"),
    (2026, "2026-08-31", 1, dict(categoria="ambos", programatica="09"),
     lambda r: _categoria(r) == "ambos" and str(r.get("programatica") or "").startswith("09")),
    (2025, "2025-12-31", None, dict(fonte_recurso=1), lambda r: r.get("fonteRecurso") == 1),
    (2024, "2024-12-31", 15, dict(anoempenho=2023), lambda r: r["anoempenho"] == 2023),
    (2026, "2026-08-31", 1, dict(anoempenho=2025, empenho=5659), lambda r: (r["anoempenho"], r["empenho"]) == (2025, 5659)),
    (2026, "2026-08-31", None, dict(empenho=1485), lambda r: r["empenho"] == 1485),
    (2016, "2016-12-31", None, dict(categoria="processado", fonte_recurso=1),
     lambda r: _categoria(r) == "processado" and r.get("fonteRecurso") == 1),
]


@pytest.mark.parametrize("ex, df, ent, filtro, pred", FILTROS)
def test_filtros_produzem_o_subconjunto_do_bruto(app, real, ex, df, ent, filtro, pred):
    esperado = _subconjunto(real, ex, df, ent, pred)
    assert esperado["registros"] > 0, filtro
    r = real["painel"].empenhos(ex, df, ent, limite=500, **filtro)
    assert r["total"] == esperado["registros"] and not r["sem_resultado"]
    assert r["totais"]["valores"]["saldo_total"] == esperado["saldo_total"]
    v = dados(ok(app, "/empenhos", exercicio=ex, data_final=df, entidade=ent, **filtro))
    assert (v["tot-registros"], v["tot-s1"], v["tot-proc"], v["tot-aproc"], v["tot-pagamentos"], v["tot-cancelamentos"]) == (
        esperado["registros"], esperado["saldo_total"], esperado["inscricao_processada"],
        esperado["inscricao_nao_processada"], esperado["pagamentos"], esperado["cancelamentos"]), filtro


@pytest.mark.parametrize("filtro", [dict(programatica="99999999999"), dict(empenho=999999999),
                                    dict(anoempenho=2026), dict(cnpj="00.000.000/0000-00"),
                                    dict(categoria="ambos", empenho=1, anoempenho=1999)])
def test_filtro_sem_resultado_mostra_nenhum_resultado_e_nunca_zero(app, real, filtro):
    corpo = ok(app, "/empenhos", exercicio=2026, data_final="2026-08-31", **filtro)
    v = dados(corpo)
    assert "Nenhum resultado encontrado" in corpo and v["tot-registros"] == 0
    assert not any(k.startswith("tot-") and k != "tot-registros" for k in v)
    assert "R$ 0,00" not in corpo and "<table" not in corpo.split('id="sem-resultado"')[1]


# ================================================================== section 18: detail
CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\*+\d{3}\*+")       # a complete CPF or one masked by the API


def test_detalhe_separa_fonte_derivado_e_analise_sem_dado_pessoal(app, real):
    corpo = ok(app, "/empenho", entidade=1, anoempenho=2016, empenho=11963, exercicio=2026, data_final="2026-12-31")
    fonte = corpo[corpo.index("Valores (API Elotech)"):corpo.index("Classificação e saldos")]
    derivado = corpo[corpo.index("Classificação e saldos"):corpo.index('id="analise-experimental"')]
    analise = corpo[corpo.index('id="analise-experimental"'):corpo.index("Classificação orçamentária")]
    assert "natureza-da_fonte" in fonte and "natureza-derivado" not in fonte and "natureza-analitico" not in fonte
    assert "natureza-derivado" in derivado and "CANC" not in derivado and "natureza-analitico" not in derivado
    assert "ANÁLISE EXPERIMENTAL" in analise and "CANC v1 (não recomendada)" in analise
    assert "natureza-analitico" in analise
    assert not re.search(r"natureza-(derivado|da_fonte|publicado)", analise)
    assert "Origem do dado" in corpo
    # individual: no name, no CPF; no bank data on any detail page
    con = real["con"]
    pf = con.execute("SELECT r.entidade, r.anoempenho, r.empenho, c.exercicio, c.data_final FROM rp_registro r JOIN coleta c "
                     "ON c.id=r.coleta_id WHERE r.cnpj LIKE '%***%' AND c.data_inicial = c.exercicio || '-01-01' "
                     "ORDER BY c.coletada_em DESC LIMIT 3").fetchall()
    assert pf
    for e, ano, emp, ex, df in pf:
        corpo = ok(app, "/empenho", entidade=e, anoempenho=ano, empenho=emp, exercicio=ex, data_final=df)
        nome = con.execute("SELECT nome FROM rp_registro WHERE entidade=? AND anoempenho=? AND empenho=? LIMIT 1",
                           (e, ano, emp)).fetchone()[0]
        assert "pessoa física" in corpo and nome not in corpo
        assert not CPF.search(re.sub(r"<code>.*?</code>", "", corpo))
        assert not re.search(r"(?i)ag[êe]ncia|conta corrente|banco do|\bpix\b", corpo)


# ================================================================== section 19: reconciliation
def test_reconciliacao_mostra_periodo_escopo_coluna_pdf_extracao_e_explicacao(app):
    corpo = ok(app, "/reconciliacao", exercicio=2026, data_final="2026-08-31", escopo="entidade")
    for trecho in ("Período</dt><dd>janeiro a agosto de 2026", "Escopo</dt><dd>entidade — entidade 1", "Coluna do RREO",
                   "Não processados — liquidados", "Documento</dt>", "Emitido em (rodapé)", "PyMuPDF",
                   "Explicação documentada", "Fonte primária:", "Fonte de reconciliação:"):
        assert trecho in corpo, trecho
    principal = re.sub(r"<[^>]+>", " ", corpo[corpo.index("<main"):corpo.index("</main>")])
    assert not re.search(r"(?i)\berros?\b|\bincorret", principal)
    linhas = re.findall(r"<tr><td><strong>([a-lL])</strong>.*?</tr>", corpo, re.S)
    assert len(linhas) == 24


# ================================================================== section 20: experimental rules
def test_regras_experimentais_so_aparecem_rotuladas_como_analise(app, real):
    rec = ok(app, "/reconciliacao", exercicio=2026, data_final="2026-08-31", escopo="consolidado")
    for linha in re.findall(r"<tr><td><strong>[a-lL]</strong>.*?</tr>", rec, re.S):
        if "RREO-COL v2" in linha:
            assert "ANÁLISE EXPERIMENTAL" in linha
        if "RREO-COL v1" in linha:
            assert "REGRA NÃO RECOMENDADA" in linha
        api = linha.split("</td>")[2]
        assert "valor analítico" in api and "dado da fonte" not in api and "valor publicado" not in api
    for ex, df in ((2026, "2026-08-31"), (2024, "2024-12-31")):
        corpo = ok(app, "/", exercicio=ex, data_final=df)
        cartoes = corpo[corpo.index('<section class="grupo"><h2>Restos a Pagar inscritos'):corpo.index("Entidades abrangidas")]
        assert "experimental" not in cartoes.lower() and "CONS-PAR" not in cartoes and "RREO-COL" not in cartoes
        assert "CANC" not in cartoes and "analítico" not in cartoes
    for caminho, params in (("/", {}), ("/entidades", {}), ("/empenhos", {}), ("/retratos", {})):
        assert "CONS-PAR" not in ok(app, caminho, **params)


# ================================================================== section 14: performance
def test_desempenho_das_operacoes_no_banco_real(app):
    operacoes = [("abertura", "/", {}), ("troca de exercício", "/", dict(exercicio=2019, data_final="2019-12-31")),
                 ("filtro de entidade", "/", dict(exercicio=2025, data_final="2025-12-31", entidade=15)),
                 ("consulta detalhada", "/empenho", dict(entidade=1, anoempenho=2025, empenho=5659, exercicio=2026)),
                 ("busca", "/empenhos", dict(exercicio=2026, data_final="2026-08-31", empenho=5659)),
                 ("navegação", "/empenhos", dict(exercicio=2016, data_final="2016-12-31", pagina=40)),
                 ("entidades", "/entidades", dict(exercicio=2026, data_final="2026-08-31")),
                 ("reconciliação", "/reconciliacao", {}),
                 ("reconciliação do documento", "/reconciliacao", dict(exercicio=2026, data_final="2026-08-31",
                                                                       escopo="consolidado"))]
    for nome, caminho, params in operacoes:
        t = time.perf_counter()
        status, _, _ = chamar(app, caminho, **params)
        assert status == "200 OK" and time.perf_counter() - t < 3, nome
