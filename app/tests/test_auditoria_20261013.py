"""Regression tests of the corrective audit of 13/10/2026 (phase P1). SINTETICO = temporary database with invented
records (fixture `mundo`); no real data, no network.

* ESCOPO-MUN v2: entity 7 in the Municipality period by period, following the scope proven in the official statement
  (docs/audits/escopo/ESCOPO_ENTIDADE_7.md); outside 'comprovado' the Municipality carries a reservation.
* CONS-PAR v4 in the eight scenarios of item 5.3: the rule is not changed; what is tested is that a pair is only
  consolidated when it should be and that every uncertain case is flagged ("Município com ressalva"), never hidden.
* Methodology in force on a date (item 8): governance decisions up to the date, refused before the first one.
"""
import pytest
from conftest import chamar, registro_sintetico as _reg

from rp import derivar, governanca
from rp.painel.consulta import ErroDoPainel

T0 = "2026-09-29T20:00:00-03:00"
T1 = "2026-10-05T20:00:00-03:00"
TESTE = "tests/test_auditoria_20261013.py::"


def _promover(con, codigo, versao, teste, quando=None):
    governanca.registrar_decisao(con, codigo, versao, "operacional", "FORTE EVIDÊNCIA", True, "promocao de teste",
                                 "docs/audits/escopo/ESCOPO_ENTIDADE_7.md", "teste", decidido_em=quando,
                                 teste_regressao=TESTE + teste, ressalva="teste sintetico")


def _total(p, ex, df, em=None):
    r = p.indicadores(ex, df, em=em)
    return r["valores"]["inscricao_total"]["valor_c"], r


# ================================================================== ESCOPO-MUN v2
# cut-offs and what the recorded period map says about them (regras.PARAMETROS[("ESCOPO-MUN", 2)])
CORTES_V2 = {
    "2018-04-30": ("exclui", None),                 # 2nd bimester 2018: SICONFI proves the exclusion
    "2019-10-31": ("inclui", "inconclusivo"),       # 5th bimester 2019: nothing proves it; v1 kept, with reservation
    "2020-02-29": ("inclui", None),                 # 1st bimester 2020: SICONFI and the portal PDF include it
    "2020-06-30": ("exclui", "contraditorio"),      # 3rd bimester 2020: PDF includes, SICONFI excludes
    "2027-02-28": ("exclui", "sem_demonstrativo"),  # outside the map: no statement checked yet
}


def _mundo_entidade_7(mundo):
    anos = sorted({int(df[:4]) for df in CORTES_V2})
    mundo.catalogos({1: anos})
    for df in CORTES_V2:
        ano = int(df[:4])
        mundo.listagem(1, ano, df, [_reg(1, ano=ano - 1, aproc=100.0)], T0)
        mundo.listagem(7, ano, df, [_reg(5, ano=ano - 1, entidade=7, aproc=40.0)], T0)
    return mundo.processar()[1]


def test_escopo_mun_v2_entra_no_catalogo_como_experimental(mundo):
    mundo.catalogos({1: [2026]})
    mundo.processar()
    g = governanca.situacao_atual(mundo.con)[("ESCOPO-MUN", 2)]
    assert g["situacao"] == "experimental" and not g["compoe_indicador_publicado"]


def test_escopo_mun_v2_segue_o_demonstrativo_de_cada_periodo(mundo):
    _mundo_entidade_7(mundo)
    _promover(mundo.con, "ESCOPO-MUN", 1, "test_escopo_mun_v2_segue_o_demonstrativo_de_cada_periodo")
    with mundo.painel() as p:      # v1 only: entity 7 in every year up to 2020
        assert _total(p, 2018, "2018-04-30")[0] == 14000
        assert _total(p, 2020, "2020-06-30")[0] == 14000
    _promover(mundo.con, "ESCOPO-MUN", 2, "test_escopo_mun_v2_segue_o_demonstrativo_de_cada_periodo")
    with mundo.painel() as p:      # v2 operational: it prevails over v1, period by period
        for df, (tratamento, situacao) in CORTES_V2.items():
            total, r = _total(p, int(df[:4]), df)
            assert total == (14000 if tratamento == "inclui" else 10000), df
            ressalvas = [a for a in r["avisos"] if a.startswith("Município com ressalva (ESCOPO-MUN v2")]
            assert bool(ressalvas) == (situacao is not None) == r["com_ressalva"], df
            if situacao == "contraditorio":
                assert "Siconfi" in ressalvas[0] and "contraditórios" in ressalvas[0]
            (e7,) = [e for e in r["entidades"] if e["entidade"] == 7]
            assert e7["entra_no_total"] == (tratamento == "inclui"), df
            assert "ESCOPO-MUN v2" in r["escopo"]
            assert {"codigo": "ESCOPO-MUN", "versao": 2} == {k: r["regras_de_escopo"][0][k] for k in ("codigo", "versao")}
        # the entity's own view never changes
        assert p.indicadores(2018, "2018-04-30", entidade=7)["valores"]["inscricao_total"]["valor_c"] == 4000


def test_escopo_mun_v2_contraditorio_tem_explicacao_na_conferencia_do_saldo():
    from rp.painel import explicacoes
    achadas, situacao = explicacoes.explicar(2020, "2020-06-30", "consolidado", "L", "S1 v1",
                                             frozenset({"ESCOPO-MUN v2"}))
    assert situacao == "explicada" and "contraditórios" in achadas[0]["texto"]
    sem_v2 = explicacoes.explicar(2020, "2020-06-30", "consolidado", "L", "S1 v1", frozenset())[0]
    assert not any("ESCOPO-MUN v2" in e["texto"] for e in sem_v2)      # only while v2 is in the indicator


def test_escopo_mun_v2_parametros_transcrevem_a_evidencia():
    import json
    from conftest import RAIZ_PROJETO
    from rp import regras
    ev = json.loads((RAIZ_PROJETO / "docs/audits/escopo/ESCOPO_ENTIDADE_7.json").read_text(encoding="utf-8"))
    norm = {"comprovado pelo RREO do portal": "comprovado_rreo_portal"}
    esperado = {f"{x['exercicio']}-{x['bimestre']}": [x["tratamento"], norm.get(x["situacao"], x["situacao"])]
                for x in ev["periodos"]}
    assert regras.PARAMETROS[("ESCOPO-MUN", 2)]["periodos"] == esperado


# ================================================================== CONS-PAR v4: the eight scenarios of item 5.3
CORTE = (2026, "2026-02-28")


def _pares(mundo, copia=None, original=None, sem_original=False, original_duplicado=False, cnpj="11.222.333/0001-44",
           quando=T0, catalogos=True):
    """Entity 1: own record 10 (100) and the copy 2400005 (30). Entity 15: the original 5 (30) and own record 6 (50)."""
    if catalogos:
        mundo.catalogos({1: [2026], 15: [2026]})
    mundo.listagem(1, 2026, CORTE[1], [_reg(10, ano=2025, aproc=100.0),
                                       _reg(2400005, ano=2025, **{"aproc": 30.0, "cnpj": cnpj, **(copia or {})})],
                   quando)
    lado_b = [_reg(6, ano=2025, entidade=15, aproc=50.0)]
    if not sem_original:
        b = _reg(5, ano=2025, entidade=15, **{"aproc": 30.0, "cnpj": cnpj, **(original or {})})
        lado_b += [b, b] if original_duplicado else [b]
    mundo.listagem(15, 2026, CORTE[1], lado_b, quando)


def _promover_pares(mundo, teste):
    for codigo, versao in (("COPIA-ORIGEM", 1), ("CONS-PAR", 4)):
        _promover(mundo.con, codigo, versao, teste)


def _ressalva_pares(r):
    return [a for a in r["avisos"] if a.startswith("Município com ressalva (CONS-PAR v4)")]


def _anomalias(con, did, codigo):
    return con.execute("SELECT COUNT(*) FROM anomalia WHERE derivacao_id=? AND tipo=?", (did, codigo)).fetchone()[0]


def test_par_cenario_1_inscricao_nos_dois_lados_execucao_so_na_copia(mundo):
    _pares(mundo, copia={"liquidado": 10.0, "pagoAProc": 10.0})
    mundo.processar()
    _promover_pares(mundo, "test_par_cenario_1_inscricao_nos_dois_lados_execucao_so_na_copia")
    with mundo.painel() as p:
        total, r = _total(p, *CORTE)
        assert total == 18000                                   # counted once
        assert r["valores"]["pagamentos"]["valor_c"] == 1000    # the copy's execution stays
        assert not _ressalva_pares(r) and not r["com_ressalva"]


@pytest.mark.parametrize("original", [
    {"pagoAProc": 5.0, "liquidado": 5.0},          # scenario 2: payment in the original
    {"canceladoAProc": 5.0},                       # scenario 3: cancellation in the original
    {"liquidado": 5.0},                            # scenario 4: liquidation in the original
    {"liquidado": -5.0},                           # scenario 4: reversal of a liquidation in the original
], ids=["pagamento", "cancelamento", "liquidacao", "estorno_de_liquidacao"])
def test_par_cenarios_2_a_4_execucao_no_original_nao_consolida_e_avisa(mundo, original):
    _pares(mundo, original=original)
    _, did = mundo.processar()
    assert mundo.con.execute("SELECT verificados, falhas FROM verificacao WHERE derivacao_id=? AND descricao=?",
                             (did, derivar.VERIF_CONS_PAR_V4)).fetchall() == [(1, 1)]
    _promover_pares(mundo, "test_par_cenarios_2_a_4_execucao_no_original_nao_consolida_e_avisa")
    with mundo.painel() as p:
        total, r = _total(p, *CORTE)
        assert total == 21000                                   # nothing is dropped: both sides stay ...
        (aviso,) = _ressalva_pares(r)                           # ... and the possible double counting is stated
        assert "1 par(es)" in aviso and "R$ 30,00" in aviso and r["com_ressalva"]


def test_par_cenario_5_execucao_nos_dois_lados(mundo):
    _pares(mundo, copia={"pagoAProc": 10.0, "liquidado": 10.0}, original={"pagoAProc": 5.0, "liquidado": 5.0})
    _, did = mundo.processar()
    assert _anomalias(mundo.con, did, "PAR-EXECUCAO-DOIS-LADOS") == 1
    _promover_pares(mundo, "test_par_cenario_5_execucao_nos_dois_lados")
    with mundo.painel() as p:
        total, r = _total(p, *CORTE)
        assert total == 21000 and len(_ressalva_pares(r)) == 1
        assert r["valores"]["pagamentos"]["valor_c"] == 1500    # the flows of both sides are kept


def test_par_cenario_6_alteracao_retrospectiva_no_mesmo_corte(mundo):
    _pares(mundo, quando=T0)                                    # first snapshot: original without execution
    _pares(mundo, original={"canceladoAProc": 30.0}, quando=T1, catalogos=False)   # later: cancelled, same cut-off
    mundo.processar()
    _promover_pares(mundo, "test_par_cenario_6_alteracao_retrospectiva_no_mesmo_corte")
    with mundo.painel() as p:
        antes, r_antes = _total(p, *CORTE, em="2026-10-01T00:00:00-03:00")
        depois, r_depois = _total(p, *CORTE)
        assert antes == 18000 and not _ressalva_pares(r_antes)          # as it was: consolidated
        assert depois == 21000 and len(_ressalva_pares(r_depois)) == 1  # now: the original has execution
        assert r_antes["retrato"]["snapshots"] != r_depois["retrato"]["snapshots"]


def test_par_cenario_7_par_ausente_nao_consolida_nada(mundo):
    _pares(mundo, sem_original=True)
    _, did = mundo.processar()
    assert _anomalias(mundo.con, did, "COPIA-SEM-PAR") == 1
    _promover_pares(mundo, "test_par_cenario_7_par_ausente_nao_consolida_nada")
    with mundo.painel() as p:
        total, r = _total(p, *CORTE)
        assert total == 18000 and not _ressalva_pares(r)        # the copy counts once; no double counting


def test_par_cenario_7_inscricao_divergente_nao_consolida_e_avisa(mundo):
    _pares(mundo, original={"aproc": 25.0})
    _, did = mundo.processar()
    assert _anomalias(mundo.con, did, "PAR-INSCRICAO-DIVERGENTE") == 1
    _promover_pares(mundo, "test_par_cenario_7_inscricao_divergente_nao_consolida_e_avisa")
    with mundo.painel() as p:
        total, r = _total(p, *CORTE)
        assert total == 20500 and len(_ressalva_pares(r)) == 1


def test_par_cenario_8_chave_repetida_deixa_o_municipio_indisponivel(mundo):
    _pares(mundo, original_duplicado=True)
    mundo.processar()
    _promover_pares(mundo, "test_par_cenario_8_chave_repetida_deixa_o_municipio_indisponivel")
    with mundo.painel() as p:
        r = p.indicadores(*CORTE)
        assert not r["disponivel"] and r["valores"]["inscricao_total"]["valor_c"] is None   # never a guessed total


def test_par_cenario_8_evidencia_incompleta_e_sinalizada(mundo):
    """CONS-PAR v4 compares the matching fields with IS: two null CNPJ are 'equal'. The rule is not changed (a semantic
    fix would be a new version); the consolidation is flagged as a reservation instead of passing silently."""
    _pares(mundo, cnpj=None)
    mundo.processar()
    _promover_pares(mundo, "test_par_cenario_8_evidencia_incompleta_e_sinalizada")
    with mundo.painel() as p:
        total, r = _total(p, *CORTE)
        assert total == 18000
        (aviso,) = _ressalva_pares(r)
        assert "campo de conferência nulo" in aviso and r["com_ressalva"]


# ================================================================== methodology in force on a date (item 8)
def test_metodologia_vigente_na_data_usa_so_as_decisoes_ate_ela(mundo):
    _mundo_entidade_7(mundo)
    _promover(mundo.con, "ESCOPO-MUN", 1, "test_metodologia_vigente_na_data_usa_so_as_decisoes_ate_ela",
              "2026-10-09T21:00:00-03:00")
    _promover(mundo.con, "ESCOPO-MUN", 2, "test_metodologia_vigente_na_data_usa_so_as_decisoes_ate_ela",
              "2026-10-13T12:00:00-03:00")
    with mundo.painel() as p:
        assert _total(p, 2018, "2018-04-30")[0] == 10000                       # today: v2
        p.definir_metodologia("vigente", "2026-10-10T00:00:00-03:00")
        total, r = _total(p, 2018, "2018-04-30", em="2026-10-10T00:00:00-03:00")
        assert total == 14000                                                    # on 10/10: only v1 was in force
        assert r["retrato"]["metodologia"]["modo"] == "vigente"
        assert r["retrato"]["metodologia"]["regras_de_escopo"] == ["ESCOPO-MUN v1"]
        with pytest.raises(ErroDoPainel, match="indisponível"):            # the catalog events start on 29/09:
            p.definir_metodologia("vigente", "2026-09-28T00:00:00-03:00")   # before any decision, refused
        with pytest.raises(ErroDoPainel, match="exige a data"):
            p.definir_metodologia("vigente")
        p.definir_metodologia("atual")
        r = p.indicadores(2018, "2018-04-30")
        assert r["retrato"]["metodologia"]["modo"] == "atual"
        assert r["retrato"]["metodologia"]["regras_de_escopo"] == ["ESCOPO-MUN v2"]


def test_metodologia_na_interface(mundo):
    from rp.interface import Aplicacao
    _mundo_entidade_7(mundo)
    mundo.con.commit()
    app = Aplicacao(mundo.cfg.banco)
    status, _, html = chamar(app, "/", exercicio=2018, data_final="2018-04-30", em="2026-09-01", metodologia="vigente")
    assert status.startswith("400") and "indisponível" in html     # before the first decision: nothing to reconstruct
    _promover(mundo.con, "ESCOPO-MUN", 1, "test_metodologia_na_interface", "2026-10-09T21:00:00-03:00")
    mundo.con.commit()
    status, _, html = chamar(app, "/", exercicio=2018, data_final="2018-04-30", em="2026-10-10", metodologia="vigente")
    assert status.startswith("200") and "metodologia vigente na data" in html
    status, _, html = chamar(app, "/", exercicio=2018, data_final="2018-04-30", metodologia="vigente")
    assert status.startswith("400") and "exige a data" in html
    status, _, _ = chamar(app, "/", exercicio=2018, metodologia="outra")
    assert status.startswith("400")
