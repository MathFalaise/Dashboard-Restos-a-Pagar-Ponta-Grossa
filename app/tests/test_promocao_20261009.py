"""Regression tests of the four rules promoted on 09/10/2026 (docs/audits/rreo/CONCILIACAO_20261009.md section 3):
CANC v2, RREO-COL v3, ESCOPO-MUN v1 and COPIA-ORIGEM v1. They are the `teste_regressao` of each promotion decision
(decision D7). SINTETICO = temporary database with invented records (fixture `mundo`)."""
import pytest
from conftest import registro_sintetico as _reg

from rp import derivar, governanca

T0 = "2026-09-29T20:00:00-03:00"
TESTE = "tests/test_promocao_20261009.py::"


def _visao(con, did, visao, versao, exercicio, data_final, entidade=None):
    linhas = con.execute(
        "SELECT v.componente, v.valor_c FROM visao_valor v JOIN regra g ON g.id = v.regra_agregacao_id WHERE "
        "v.derivacao_id=? AND v.visao=? AND g.codigo='RREO-COL' AND g.versao=? AND v.exercicio=? AND v.data_final=? "
        "AND IFNULL(v.entidade, 0)=? AND v.regra_consolidacao_id IS NULL",
        (did, visao, versao, exercicio, data_final, entidade or 0)).fetchall()
    return dict(linhas) or None


def _promover(con, codigo, versao, teste):
    governanca.registrar_decisao(con, codigo, versao, "operacional", "FORTE EVIDÊNCIA", True, "promocao de teste",
                                 "docs/audits/rreo/CONCILIACAO_20261009.md", "teste",
                                 teste_regressao=TESTE + teste, ressalva="teste sintetico")


# ================================================================== CANC v2
def test_canc_v2_cancela_primeiro_o_nao_processado_a_liquidar():
    f = derivar.cancelamento_v2
    assert f(10000, 0, -10000, 10000) == (10000, 0)                     # processed only: all processed
    assert f(130000, 470000, -81968, 551968) == (81968, 470000)         # mixed: RPNP first, the excess is processed
    assert f(0, 522771781, 414356633, 108415148) == (0, 108415148)      # cancels what was still to be liquidated
    assert f(0, 10000, 0, -1000) == (0, -1000)                          # reversal of a cancellation: not processed (v1)
    assert f(0, 10000, 0, 4000) == (0, 4000)                            # within the RPNP balance: same as v1
    assert f(0, 0, 0, 500) == (0, 0)                                    # no opening balance: like v1, nowhere


# ================================================================== RREO-COL v3
def test_rreo_col_v3_pagamento_por_categoria_e_cancelamento_v2(mundo):
    mundo.catalogos({1: [2025]})
    regs = [_reg(1, proc=13.0, aproc=47.0, liquidado=-8.0, canceladoAProc=55.0),      # mixed: d 8, j 47
            _reg(2, proc=100.0, aproc=0, pagoProc=40.0, pagoAProc=10.0),             # processed only, pagoAProc -> c
            _reg(3, aproc=50.0, pagoProc=20.0, liquidado=20.0)]                      # not processed only, pagoProc -> i
    mundo.listagem(1, 2025, "2025-12-31", regs, T0)
    _, did = mundo.processar()
    v1 = _visao(mundo.con, did, "entidade", 1, 2025, "2025-12-31", 1)
    v2 = _visao(mundo.con, did, "entidade", 2, 2025, "2025-12-31", 1)
    v3 = _visao(mundo.con, did, "entidade", 3, 2025, "2025-12-31", 1)
    assert (v1["d"], v1["j"]) == (0, 5500) and (v2["d"], v2["j"]) == (0, 5500)       # CANC v1: all not processed
    assert (v3["d"], v3["j"]) == (800, 4700)                                         # CANC v2
    assert (v3["c"], v3["i"]) == (v2["c"], v2["i"]) == (5000, 2000)                  # payments: same as v2
    assert v3["L"] == v3["e"] + v3["k"] and v3["L"] == v2["L"]                       # the split never changes the balance
    conc = {r[0] for r in mundo.con.execute(
        "SELECT g.versao FROM visao_valor v JOIN regra g ON g.id=v.regra_agregacao_id WHERE v.derivacao_id=? AND "
        "g.codigo='RREO-COL'", (did,))}
    assert conc == {1, 2, 3}


# ================================================================== COPIA-ORIGEM v1
def test_copia_origem_exclui_copias_antes_de_2026(mundo):
    mundo.catalogos({1: [2025, 2026]})
    for ano, df in ((2025, "2025-12-31"), (2026, "2026-02-28")):
        mundo.listagem(1, ano, df, [_reg(10, ano=ano - 1, aproc=100.0), _reg(2400010, ano=ano - 1, aproc=30.0)], T0)
    _, did = mundo.processar()
    v2_25 = _visao(mundo.con, did, "entidade", 2, 2025, "2025-12-31", 1)
    v3_25 = _visao(mundo.con, did, "entidade", 3, 2025, "2025-12-31", 1)
    v3_26 = _visao(mundo.con, did, "entidade", 3, 2026, "2026-02-28", 1)
    assert v2_25["g"] == 13000 and v3_25["g"] == 10000                  # the copy only leaves v3 before 2026
    assert v3_26["g"] == 13000                                           # from 2026 on it is part of the entity
    assert _visao(mundo.con, did, "publicado", 3, 2025, "2025-12-31")["g"] == 10000
    (verif,) = mundo.con.execute("SELECT verificados, falhas FROM verificacao WHERE derivacao_id=? AND descricao=?",
                                 (did, "cópias 24xxxxx fora do indicador (COPIA-ORIGEM v1)")).fetchall()
    assert verif == (1, 0)
    # the copy stays in the raw data, the normalization and the anomalies (never deleted)
    assert mundo.con.execute("SELECT COUNT(*) FROM anomalia WHERE derivacao_id=? AND tipo='COPIA-24'", (did,)).fetchone()[0] == 2
    # published indicator: only after the promotion
    with mundo.painel() as p:
        assert p.indicadores(2025, "2025-12-31")["valores"]["inscricao_total"]["valor_c"] == 13000
    _promover(mundo.con, "COPIA-ORIGEM", 1, "test_copia_origem_exclui_copias_antes_de_2026")
    with mundo.painel() as p:
        r25, r26 = p.indicadores(2025, "2025-12-31"), p.indicadores(2026, "2026-02-28")
        assert r25["valores"]["inscricao_total"]["valor_c"] == 10000 and r25["valores"]["registros"]["valor_c"] == 1
        assert r26["valores"]["inscricao_total"]["valor_c"] == 13000
        assert "COPIA-ORIGEM v1" in r25["escopo"] and r25["regras_de_escopo"][0]["codigo"] == "COPIA-ORIGEM"
        # the detail of ONE commitment still shows the copy, flagged as out of the indicator
        d = p.detalhe_empenho(1, 2024, 2400010, 2025, "2025-12-31")
        assert d["encontrado"] and "COPIA-ORIGEM v1" in d["fora_do_indicador"]
        assert p.detalhe_empenho(1, 2025, 2400010, 2026, "2026-02-28")["fora_do_indicador"] is None


# ================================================================== ESCOPO-MUN v1
def test_escopo_mun_inclui_entidade_7_ate_2020_quando_conhecida(mundo):
    mundo.catalogos({1: [2020, 2021]})
    for ano in (2020, 2021):
        df = f"{ano}-12-31"
        mundo.listagem(1, ano, df, [_reg(1, ano=ano - 1, aproc=100.0)], T0)
        mundo.listagem(7, ano, df, [_reg(5, ano=ano - 1, entidade=7, aproc=40.0)], T0)
    mundo.listagem(1, 2020, "2020-06-30", [_reg(1, ano=2019, aproc=100.0)], T0)     # entity 7 not collected here
    _, did = mundo.processar()
    assert _visao(mundo.con, did, "publicado", 3, 2020, "2020-12-31")["g"] == 14000   # entity 7 up to 2020
    assert _visao(mundo.con, did, "publicado", 3, 2021, "2021-12-31")["g"] == 10000   # not from 2021 on
    assert _visao(mundo.con, did, "publicado", 2, 2020, "2020-12-31")["g"] == 10000   # v2: catalog scope, still there
    assert _visao(mundo.con, did, "publicado", 3, 2020, "2020-06-30") is None          # known and missing: no Municipality
    assert _visao(mundo.con, did, "publicado", 2, 2020, "2020-06-30")["g"] == 10000
    falhas = dict(mundo.con.execute("SELECT json_extract(escopo_json, '$.data_final'), falhas FROM verificacao WHERE "
                                    "derivacao_id=? AND descricao=?",
                                    (did, "entidade fora do catálogo no Município (ESCOPO-MUN v1)")))
    assert falhas == {"2020-06-30": 1, "2020-12-31": 0}
    with mundo.painel() as p:
        # not promoted: the behaviour before the rule - an entity outside the catalog WITH a snapshot is summed in every
        # year (that is what put entity 7 into 2021 too); the promoted rule is what restricts it
        assert p.indicadores(2021, "2021-12-31")["valores"]["inscricao_total"]["valor_c"] == 14000
    _promover(mundo.con, "ESCOPO-MUN", 1, "test_escopo_mun_inclui_entidade_7_ate_2020_quando_conhecida")
    with mundo.painel() as p:
        r20, r21, meio = (p.indicadores(2020, "2020-12-31"), p.indicadores(2021, "2021-12-31"),
                          p.indicadores(2020, "2020-06-30"))
        assert r20["valores"]["inscricao_total"]["valor_c"] == 14000
        assert r21["valores"]["inscricao_total"]["valor_c"] == 10000
        (e7,) = [e for e in r21["entidades"] if e["entidade"] == 7]
        assert e7["situacao_do_dado"]["codigo"] == "fora_do_escopo" and not e7["entra_no_total"]
        assert not meio["disponivel"]                                  # never zero: the Municipality is unavailable
        assert "Agência Reguladora" in [e for e in r20["entidades"] if e["entidade"] == 7][0]["nome"]


def test_escopo_mun_nao_se_aplica_a_base_que_nao_conhece_a_entidade(mundo):
    """A base without any collection of entity 7 keeps the catalog scope (the entity is unknown to it), like the
    homologated base of 30/09/2026."""
    mundo.catalogos({1: [2020]})
    mundo.listagem(1, 2020, "2020-12-31", [_reg(1, ano=2019, aproc=100.0)], T0)
    _, did = mundo.processar()
    assert _visao(mundo.con, did, "publicado", 3, 2020, "2020-12-31")["g"] == 10000
    _promover(mundo.con, "ESCOPO-MUN", 1, "test_escopo_mun_nao_se_aplica_a_base_que_nao_conhece_a_entidade")
    with mundo.painel() as p:
        assert p.indicadores(2020, "2020-12-31")["disponivel"]


@pytest.mark.parametrize("codigo, versao", [("CANC", 2), ("RREO-COL", 3), ("ESCOPO-MUN", 1), ("COPIA-ORIGEM", 1),
                                           ("MOV-REF", 2)])
def test_regras_novas_entram_no_catalogo_como_experimentais(mundo, codigo, versao):
    mundo.catalogos({1: [2025]})
    mundo.processar()
    g = governanca.situacao_atual(mundo.con)[(codigo, versao)]
    assert g["situacao"] == "experimental" and not g["compoe_indicador_publicado"]


# ================================================================== MOV-REF v2 (finding of the movement collection)
def _lanc(data, tipo, valor, a_liquidar, a_pagar, exl=0, nol=0, exp=0, nop=0, doc=""):
    return {"data": data, "tipoLancamento": tipo, "descricaoTipoLancamento": str(tipo), "valor": valor,
            "valorALiquidar": a_liquidar, "valorAPagar": a_pagar, "exercicioLiquidacao": exl, "noLiquidacao": nol,
            "exercicioPagamento": exp, "noPagamento": nop, "nroDocumento": doc}


def test_mov_ref_v2_em_liquidacao_sem_efeito(mundo):
    from rp.coletor import EP_MOV
    movs = [_lanc("2022-11-29", 20, 1888.24, 1888.24, 1888.24, doc="Emp: 20042"),
            _lanc("2022-12-01", 33, 1888.24, 1888.24, 1888.24, 2022, 1, doc="Em Liq. 1/2022"),     # balances unchanged
            _lanc("2023-01-02", 30, 1888.24, 0, 1888.24, 2023, 2, doc="Liq: 2/2023"),
            _lanc("2023-03-03", 40, 26.82, 0, 1861.42, 2023, 8468, 2023, 2, doc="Pagto No. 8468/2023")]
    mundo._snap("movimentacao", EP_MOV, {"entidade": 1, "anoempenho": 2022, "empenho": 20042, "size": 500},
                {"content": movs, "last": True, "totalElements": len(movs)}, T0)
    _, did = mundo.processar()
    ef = dict(mundo.con.execute("SELECT m.tipo_lancamento, i.efeito || '|' || i.valor_com_sinal_c || '|' || "
                                "IFNULL(i.liquidacao_exercicio, '') || '/' || IFNULL(i.liquidacao_numero, '') FROM "
                                "movimentacao_lancamento m JOIN movimentacao_interpretada i ON i.resposta_id=m.resposta_id "
                                "AND i.indice=m.indice AND i.derivacao_id=?", (did,)))
    assert ef[33] == "em_liquidacao|0|2022/1"                       # known, no effect, refers to its liquidation
    assert ef[40] == "pagamento|2682|2023/2" and ef[30] == "liquidacao|188824|2023/2"     # v1 behaviour kept
    assert not mundo.con.execute("SELECT COUNT(*) FROM movimentacao_interpretada WHERE derivacao_id=? AND "
                                 "efeito='desconhecido'", (did,)).fetchone()[0]
