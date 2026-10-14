"""Mandatory real cases (section 24 of the corrective review specification) over the project's REAL store.

The database is built in a temporary directory from data/snapshots/ (the 466 snapshots of the homologated base,
stages 01-04.4; snapshots of later loads stay out), by only reading the store: sync -> normalize -> derive
(current and 'as it was on' 29/09/2026). The test checks that no store file changes and that the result hashes
are the ones recorded in 04.4.
Expected values: docs/stages/02-accounting-validation/REPORT.md section 4, docs/stages/03-data-model/REPORT.md,
docs/stages/04-pipeline/REPORT_04_3.md, docs/stages/04-pipeline/REPORT_04_4.md sections 7-13 and
docs/stages/04-pipeline/batches/consistencia_rreo.md.
"""
import re

from conftest import ARMAZEM_REAL, RAIZ_PROJETO, SNAPSHOTS_HOMOLOGADOS, evidencias_homologadas, manifestos_homologados

from rp import banco, derivar

HASH_ATUAL = "2f6b4e295ce795934f7051fba31d9d3c1b5bc42c8858d4622a3e89ec88e3f2a5"      # REPORT_04_4.md, Lote M
HASH_EM_2909 = "b8a0b2ed2328bf093f3f44d4a51dd70f0063d2c9c827b981520a8f921f142a68"
# Promotion of 09/10/2026 (RREO-COL v3, CANC v2, ESCOPO-MUN v1, COPIA-ORIGEM v1; docs/audits/rreo/CONCILIACAO_20261009.md):
# the complete result of the same homologated base gains the rows of the new rules. The homologated hashes above stay
# the reference: WITHOUT those rows the result must be exactly the homologated one (the promotion only adds rows).
HASH_ATUAL_20261009 = "adc55b1913d0b553a2644f0c783e388074cbd1da1eb2e90902b6e07fc29952f2"
HASH_EM_2909_20261009 = "96777ec6a17da54b09812422695b14a9bb0dc89b4d3563a3712f9964ccc699a4"
# Promotion of 10/10/2026 (CONS-PAR v4; docs/audits/rreo/RP_2024_2026.md): one step later, same proof. Without the
# CONS-PAR v4 rows the result is exactly the one of 09/10 (the hashes above); the complete result is recorded here.
HASH_ATUAL_20261010 = "15e9199534d862c030d13ce7b3036df1d6926dc8de31c3506f9bf7583c27f530"
HASH_EM_2909_20261010 = "4002ccc2634021abf2e3ace910b8d18dc3311f572405912ffe389728277ea791"


def test_armazem_real_intacto_e_integro(real):
    assert real["armazem_antes"] == real["armazem_depois"]
    homologados = manifestos_homologados(real["armazem"])
    assert real["importacao"]["sincronizados"] == len(homologados) == SNAPSHOTS_HOMOLOGADOS
    # the whole homologated base is intact; the store may only have, IN ADDITION, the snapshots of later loads (D1)
    todos = {p.relative_to(ARMAZEM_REAL).as_posix() for p in (ARMAZEM_REAL / "coletas").rglob("*.json")}
    posteriores = todos - {rel for rel, _ in homologados}
    # ... and the external evidence recorded after it (the first one: Siconfi declarations, 09/10/2026)
    ev_homologadas = {rel for rel, _ in evidencias_homologadas(real["armazem"])}
    ev_posteriores = [rel for rel, _ in real["armazem"].evidencias() if rel not in ev_homologadas]
    assert sorted(banco.verificar(real["con"], real["armazem"])) == sorted(
        [f"manifesto fora do banco: {rel}" for rel in posteriores] + [f"evidencia fora do banco: {rel}" for rel in ev_posteriores])


def test_hashes_de_resultado_iguais_aos_da_04_4(real):
    con = real["con"]
    sem = derivar.REGRAS_DE_20261009 | derivar.REGRAS_DE_20261010
    assert derivar.hash_resultado(con, real["did"], sem) == HASH_ATUAL               # homologated part: unchanged
    assert derivar.hash_resultado(con, real["did_2909"], sem) == HASH_EM_2909
    sem = derivar.REGRAS_DE_20261010                                                 # 09/10 result: unchanged
    assert derivar.hash_resultado(con, real["did"], sem) == HASH_ATUAL_20261009
    assert derivar.hash_resultado(con, real["did_2909"], sem) == HASH_EM_2909_20261009
    h = dict(con.execute("SELECT id, hash_resultado FROM derivacao_execucao").fetchall())
    assert (h[real["did"]], h[real["did_2909"]]) == (HASH_ATUAL_20261010, HASH_EM_2909_20261010)


def test_caso_5659_2025(real):
    p = real["painel"]
    d = p.detalhe_empenho(1, 2025, 5659, 2026, "2026-12-31")
    (o,) = d["ocorrencias"]
    assert (o["campos"]["proc_c"]["valor"], o["campos"]["pago_proc_c"]["valor"]) == (314153040, 227774506)
    assert o["derivados"]["s1_saldo_total_c"]["valor"] == 86378534 and o["derivados"]["categoria"]["valor"] == "processado"
    assert o["campos"]["pago_proc_c"]["campo_api"] == "pagoProc"
    pagamentos = [l for l in d["movimentacao"]["lancamentos"] if l["tipo_lancamento"] == 40]
    assert pagamentos and {l["liquidacao_referida"] for l in pagamentos} == {"1/2025"}   # MOV-REF v1


def test_caso_11963_2016(real):
    d = real["painel"].detalhe_empenho(1, 2016, 11963, 2026, "2026-12-31")
    (o,) = d["ocorrencias"]
    c, dv = o["campos"], o["derivados"]
    assert (c["proc_c"]["valor"], c["cancelado_aproc_c"]["valor"], c["liquidado_c"]["valor"]) == (386452, 386452, -386452)
    assert (dv["categoria"]["valor"], dv["s1_saldo_total_c"]["valor"]) == ("processado", 0)
    # the cancellation split (CANC v1) is still computed, but comes out as analytical: the rule is no longer recommended
    assert dv["cancel_processado_c"]["valor"] == 386452 and dv["cancel_processado_c"]["natureza"] == "analitico"


def test_caso_2401751_2023_e_seu_par(real):
    p = real["painel"]
    a = p.detalhe_empenho(1, 2023, 2401751, 2024, "2024-12-31")["ocorrencias"][0]
    b = p.detalhe_empenho(15, 2023, 1751, 2024, "2024-12-31")["ocorrencias"][0]
    assert a["campos"]["proc_c"]["valor"] + a["campos"]["aproc_c"]["valor"] == 841000
    par = a["par_espelhado"]
    assert par["este_registro_e_o_lado"] == "A" and b["par_espelhado"]["este_registro_e_o_lado"] == "B"
    assert (par["b"]["entidade"], par["b"]["empenho"], par["b"]["inscrito_c"]) == (15, 1751, 1975000)
    assert (par["relacao_inscricao"], par["lado_com_execucao"]) == ("outra", "B")
    assert a["proveniencia"]["snapshot_uid"] != b["proveniencia"]["snapshot_uid"]      # two raw records
    for df in ("2025-02-28", "2025-04-30", "2025-06-30", "2025-08-31", "2025-10-31", "2025-12-31"):
        o = p.detalhe_empenho(1, 2023, 2401751, 2025, df)["ocorrencias"][0]
        assert o["campos"]["proc_c"]["valor"] + o["campos"]["aproc_c"]["valor"] == 841000, df


def test_caso_entidade_5_empenho_1485_2025(real):
    p = real["painel"]
    o = p.detalhe_empenho(5, 2025, 1485, 2026, "2026-08-31")["ocorrencias"][0]
    proc, pago = o["campos"]["proc_c"]["valor"], o["campos"]["pago_proc_c"]["valor"]
    assert (proc, pago, pago - proc) == (608077, 977302, 369225)
    (c,) = [x for x in p.reconciliacao(2026, "2026-08-31", "consolidado")["linhas"]
            if x["coluna"] == "c" and x["regra_agregacao"]["regra"] == "RREO-COL v2"]
    assert c["diferenca_c"] == 369225 and c["situacao_da_diferenca"] == "hipótese"
    assert [e["classe"] for e in c["explicacoes"]] == ["E"]


def test_pares_1_15_em_2025(real):
    p = real["painel"]
    for df in ("2025-02-28", "2025-04-30", "2025-06-30", "2025-08-31", "2025-10-31", "2025-12-31"):
        r = p.pares(2025, df)["resumo"]
        assert r["pares"] == 20, df
        assert set(r["lado_com_execucao"]) <= {"B", "nenhum"}, df
    ini, fim = p.pares(2025, "2025-02-28")["resumo"]["relacao"], p.pares(2025, "2025-12-31")["resumo"]["relacao"]
    assert ini == {"igual": 11, "a_e_saldo_final_de_b": 2, "outra": 7}
    assert fim == {"igual": 11, "a_e_saldo_final_de_b": 9}


def test_espelhamento_2026(real):
    p = real["painel"]
    esperado_lado_a = {"2026-04-30": 356, "2026-06-30": 530, "2026-08-31": 562}
    for df in ("2026-02-28", "2026-04-30", "2026-06-30", "2026-08-31"):
        r = p.pares(2026, df)["resumo"]
        assert r["pares"] == 731 and r["relacao"] == {"igual": 731}, df
        assert "B" not in r["lado_com_execucao"] and "ambos" not in r["lado_com_execucao"], df
        if df in esperado_lado_a:
            assert r["lado_com_execucao"]["A"] == esperado_lado_a[df], df
    assert p.pares(2026, "2026-08-31")["resumo"]["anoempenho"] == {2023: 1, 2024: 19, 2025: 711}
    # both sides enter the indicators: nothing is discounted because of mirroring
    ind = p.indicadores(2026, "2026-08-31")
    assert ind["disponivel"] and ind["valores"]["registros"]["valor_c"] == sum(
        e["snapshot"]["registros"] for e in ind["entidades"] if e["entra_no_total"])


def test_divergencias_h_i_de_2026(real):
    p = real["painel"]

    def dif(df, col, versao):
        (x,) = [x for x in p.reconciliacao(2026, df, "entidade")["linhas"]
                if x["coluna"] == col and x["regra_agregacao"]["regra"] == f"RREO-COL v{versao}"]
        return x

    assert dif("2026-08-31", "h", 1)["diferenca_c"] == dif("2026-08-31", "h", 2)["diferenca_c"] == -34547956
    assert dif("2026-08-31", "i", 1)["diferenca_c"] == -23772825 and dif("2026-08-31", "i", 2)["diferenca_c"] == -23767875
    assert dif("2026-06-30", "h", 1)["diferenca_c"] == -21691324 and dif("2026-06-30", "i", 1)["diferenca_c"] == -10911243
    for x in (dif("2026-08-31", "h", 1), dif("2026-06-30", "i", 2)):
        assert x["situacao_da_diferenca"] == "não determinada" and x["rreo_natureza"] == "publicado"
    assert dif("2026-04-30", "h", 2)["diferenca_c"] == 64416


def _consistencia_da_04_4():
    """Rows of docs/stages/04-pipeline/batches/consistencia_rreo.md: (scope, from) -> (L of A, (a)+(f) of A+1,
    difference, API S1, API a+f)."""
    c = lambda s: None if s.strip() in ("—", "") else int(re.sub(r"[^\d-]", "", s.split("(")[0]))
    saida = {}
    for linha in (RAIZ_PROJETO / "docs/stages/04-pipeline/batches/consistencia_rreo.md").read_text(encoding="utf-8").splitlines()[2:]:
        cel = [x.strip() for x in linha.strip("|").split("|")]
        de = int(cel[1][:4])
        saida[(cel[0], de)] = tuple(c(x) for x in cel[2:7])
    return saida


def test_674_426_01_e_coerencia_entre_publicacoes(real):
    coe = real["painel"].coerencia_entre_publicacoes()["comparacoes"]
    (x,) = [x for x in coe if (x["escopo"], x["de"], x["data_final_para"]) == ("entidade", 2024, "2025-12-31")]
    assert x["diferenca_c"] == 67442601 and (x["rreo_L_de_c"], x["rreo_a_mais_f_para_c"]) == (1784893028, 1852335629)
    assert x["api_s1_de_c"] == x["api_a_mais_f_para_c"] == 1853176629          # the API reproduces the later publication
    assert x["situacao_da_diferenca"] == "explicada"       # attributed to records on 09/10/2026 (before: partially)
    # the whole 04.4 table that the production extractor can read (2020 onwards) is reproduced to the cent
    tabela = _consistencia_da_04_4()
    conferidas = 0
    for x in coe:
        k = (x["escopo"], x["de"])
        if k in tabela and x["data_final_para"] in (f"{x['para']}-12-31", "2026-08-31"):
            L, af, d, s1, api_af = tabela[k]
            assert (x["rreo_L_de_c"], x["rreo_a_mais_f_para_c"], x["diferenca_c"], x["api_s1_de_c"]) == (L, af, d, s1), k
            if api_af is not None:
                assert x["api_a_mais_f_para_c"] == api_af, k
            conferidas += 1
    assert conferidas == 12


def test_entidade_inexistente_no_exercicio_nao_e_zero(real):
    p = real["painel"]
    for ent, ex in ((15, 2016), (15, 2018), (10, 2023), (10, 2025)):
        r = p.indicadores(ex, f"{ex}-12-31", ent)
        assert not r["disponivel"] and "não é RP zero" in r["motivo_indisponivel"], (ent, ex)
    r = p.indicadores(2019, "2019-12-31", 15)       # entity 15's first official fiscal year: a legitimate zero
    assert r["disponivel"] and r["valores"]["registros"]["valor_c"] == 0
    mun = p.indicadores(2016, "2016-12-31")
    assert mun["disponivel"] and [e["entidade"] for e in mun["entidades"] if not e["entra_no_total"]] == [15]


def test_retrato_historico_29_09(real):
    p = real["painel"]
    r = p.indicadores(2025, "2025-12-31", entidade=1, em="2026-09-29")
    assert r["retrato"]["texto"] == ("Como a base estava em 29/09/2026: exercício de 2025, corte 31/12/2025, "
                                     "coletado em 29/09/2026")
    assert r["reconciliacao"].startswith("36 comparações coluna a coluna")      # 12 columns x RREO-COL v1/v2/v3 (09/10/2026)
    atual = p.indicadores(2025, "2025-12-31", entidade=1)
    assert atual["retrato"]["texto"].startswith("Estado atual da base para o exercício de 2025, corte 31/12/2025")
    assert atual["valores"]["saldo_total"]["valor_c"] == r["valores"]["saldo_total"]["valor_c"]   # identical re-collection
