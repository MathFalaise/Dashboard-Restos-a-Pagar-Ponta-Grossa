"""Interface regression cases (section 19 of the 04.5 specification) over the project's REAL store.

Same setup as test_casos_reais.py (the conftest `real` fixture: a temporary database built by only reading
data/snapshots/). Here the values are checked ON THE PAGE, in the <data value> element (exact cents), to make sure
the interface shows what the earlier stages established. Expected values:
docs/stages/02-accounting-validation/REPORT.md section 4, docs/stages/04-pipeline/REPORT_04_3.md,
docs/stages/04-pipeline/REPORT_04_4.md sections 7-13 and docs/stages/04-pipeline/batches/consistencia_rreo.md.
"""
import re

import pytest
from conftest import chamar, dados, ok

from rp.interface import Aplicacao, paginas


@pytest.fixture(scope="module")
def app(real):
    return Aplicacao(real["cfg"].banco)


def test_5659_2025_detalhe(app):
    corpo = ok(app, "/empenho", entidade=1, anoempenho=2025, empenho=5659, exercicio=2026, data_final="2026-12-31")
    v = dados(corpo)
    assert (v["campo-proc_c"], v["campo-pago_proc_c"], v["derivado-s1_saldo_total_c"]) == (314153040, 227774506, 86378534)
    assert "processado" in corpo and "CAT v1 (operacional)" in corpo
    movimentos = corpo[corpo.index("<h2>Movimentações</h2>"):]
    pagamentos = re.findall(r"<td>40</td>.*?</tr>", movimentos)
    assert pagamentos and all("<td>1/2025</td>" in linha for linha in pagamentos)      # MOV-REF v1


def test_11963_2016_detalhe(app):
    corpo = ok(app, "/empenho", entidade=1, anoempenho=2016, empenho=11963, exercicio=2026, data_final="2026-12-31")
    v = dados(corpo)
    assert (v["campo-proc_c"], v["campo-cancelado_aproc_c"], v["campo-liquidado_c"]) == (386452, 386452, -386452)
    assert v["derivado-s1_saldo_total_c"] == 0
    canc = corpo[corpo.index("Cancelamento de processado"):]
    canc = canc[:canc.index("</tr>")]
    assert "CANC v1 (não recomendada)" in canc and "valor analítico (não oficial)" in canc      # never official


def test_2401751_2023_e_seu_par(app):
    a = ok(app, "/empenho", entidade=1, anoempenho=2023, empenho=2401751, exercicio=2024, data_final="2024-12-31")
    b = ok(app, "/empenho", entidade=15, anoempenho=2023, empenho=1751, exercicio=2024, data_final="2024-12-31")
    assert dados(a)["campo-aproc_c"] + dados(a)["campo-proc_c"] == 841000
    assert "Este registro é o lado</dt><dd>A" in a and "Este registro é o lado</dt><dd>B" in b
    assert "entidade 15, empenho 1751/2023" in a and "Relação da inscrição</dt><dd>outra" in a
    assert "Lado com execução</dt><dd>B" in a and "não está determinada" in a
    snap_a = re.search(r"Snapshot</dt><dd><code>([0-9a-f]{32})", a).group(1)
    snap_b = re.search(r"Snapshot</dt><dd><code>([0-9a-f]{32})", b).group(1)
    assert snap_a != snap_b                                   # two raw records, kept apart


def test_entidade_5_empenho_1485_2025(app):
    v = dados(ok(app, "/empenho", entidade=5, anoempenho=2025, empenho=1485, exercicio=2026, data_final="2026-08-31"))
    assert (v["campo-proc_c"], v["campo-pago_proc_c"]) == (608077, 977302)
    rec = ok(app, "/reconciliacao", exercicio=2026, data_final="2026-08-31", escopo="consolidado")
    assert dados(rec)["rec-v2-c-dif"] == 369225 == 977302 - 608077
    linha_c = re.search(r'id="rec-v2-c-dif".*?</tr>', rec, re.S).group(0)
    assert "hipótese" in linha_c


def test_pares_1_15_em_2025(app):
    ini = ok(app, "/pares", exercicio=2025, data_final="2025-02-28")
    fim = ok(app, "/pares", exercicio=2025, data_final="2025-12-31")
    assert dados(ini)["pares-total"] == 20 and dados(fim)["pares-total"] == 20
    assert "a_e_saldo_final_de_b: 2, igual: 11, outra: 7" in ini
    assert "a_e_saldo_final_de_b: 9, igual: 11" in fim and "outra" not in fim.split("Relação da inscrição")[1].split("</dd>")[0]
    for corpo in (ini, fim):
        execucao = corpo.split("Lado com execução</dt><dd>")[1].split("</dd>")[0]
        assert "A:" not in execucao and "ambos" not in execucao


def test_pares_de_2026(app):
    corpo = ok(app, "/pares", exercicio=2026, data_final="2026-08-31")
    assert dados(corpo)["pares-total"] == 731 and "igual: 731" in corpo
    execucao = corpo.split("Lado com execução</dt><dd>")[1].split("</dd>")[0]
    assert "A: 562" in execucao and "B:" not in execucao
    assert "2023: 1, 2024: 19, 2025: 711" in corpo
    assert "não é consolidação" in corpo and "CONS-PAR" in corpo and "não são exibidas" in corpo
    origem = corpo[corpo.index("Origem do dado (snapshots usados)"):]
    origem = origem[:origem.index("</details>")]
    assert len(re.findall(r"<code>[0-9a-f]{32}</code>", origem)) == 2      # snapshots of entities 1 and 15


def test_divergencias_h_i_de_2026(app):
    ago = dados(ok(app, "/reconciliacao", exercicio=2026, data_final="2026-08-31", escopo="entidade"))
    assert ago["rec-v1-h-dif"] == ago["rec-v2-h-dif"] == -34547956
    assert ago["rec-v1-i-dif"] == -23772825 and ago["rec-v2-i-dif"] == -23767875
    jun = ok(app, "/reconciliacao", exercicio=2026, data_final="2026-06-30", escopo="entidade")
    assert dados(jun)["rec-v1-h-dif"] == -21691324 and dados(jun)["rec-v1-i-dif"] == -10911243
    linha_h = re.search(r'id="rec-v1-h-dif".*?</tr>', jun, re.S).group(0)
    assert "não determinada" in linha_h


def test_674_426_01(app):
    corpo = ok(app, "/reconciliacao")
    v = dados(corpo)
    assert v["coe-entidade-2024"] == 67442601 and v["coe-consolidado-2024"] == 66976165
    assert v["coe-entidade-2025"] == v["coe-consolidado-2025"] == 92570262
    linha = re.search(r'id="coe-entidade-2024".*?</tr>', corpo, re.S).group(0)
    assert "parcialmente explicada" in linha and "R$ 18.531.766,29" in linha      # API today = opening published later
    assert "PDFs do RREO" in linha and len(re.findall(r"<code>[0-9a-f]{32}</code>", linha)) >= 3   # 2 PDFs + API


def test_resumo_do_municipio_com_entidade_fora_do_catalogo(app, real):
    corpo = ok(app, "/resumo", exercicio=2016, data_final="2016-12-31")
    v = dados(corpo)
    esperado = real["painel"].indicadores(2016, "2016-12-31")["valores"]
    assert v["ind-saldo_total"] == esperado["saldo_total"]["valor_c"]
    assert v["ind-registros"] == esperado["registros"]["valor_c"]
    linha_15 = re.search(r"<td>15</td>.*?</tr>", corpo, re.S).group(0)
    assert "fora do catálogo oficial" in linha_15 and "não é RP zero" in linha_15


def test_indicadores_da_interface_iguais_aos_da_camada_painel(app, real):
    """The interface recomputes nothing: each card shows exactly the panel layer's value."""
    mostrados = [i for _, ids in paginas.GRUPOS for i in ids]
    for ex, df, ent in ((2024, "2024-12-31", None), (2025, "2025-06-30", 1), (2026, "2026-08-31", None)):
        v = dados(ok(app, "/resumo", exercicio=ex, data_final=df, entidade=ent))
        esperado = real["painel"].indicadores(ex, df, ent)["valores"]
        assert sorted(k[4:] for k in v if k.startswith("ind-")) == sorted(mostrados)
        assert {k: v[f"ind-{k}"] for k in mostrados} == {k: esperado[k]["valor_c"] for k in mostrados}, (ex, df, ent)


def test_desempenho_das_telas_no_banco_completo(app):
    """No screen loads the whole database: all of them answer in a few seconds even on the full database."""
    import time
    for caminho, params in (("/", {}), ("/resumo", {}), ("/entidades", dict(exercicio=2025, data_final="2025-12-31")),
                            ("/empenhos", dict(exercicio=2025, data_final="2025-12-31")),
                            ("/reconciliacao", {}), ("/pares", dict(exercicio=2026, data_final="2026-08-31"))):
        t = time.perf_counter()
        status, _, _ = chamar(app, caminho, **params)
        assert status == "200 OK" and time.perf_counter() - t < 5, caminho
