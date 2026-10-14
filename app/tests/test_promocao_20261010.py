"""Regression tests of CONS-PAR v4, promoted on 10/10/2026 (docs/audits/rreo/RP_2024_2026.md section 8, D1): in the
Municipality, the original of a 1 <-> 15 pair with the same inscription and no execution is not summed; the RP is
counted once, in the copy. They are the `teste_regressao` of the promotion decision (decision D7).
SINTETICO = temporary database with invented records (fixture `mundo`)."""
from conftest import registro_sintetico as _reg

from rp import derivar, governanca

T0 = "2026-09-29T20:00:00-03:00"
TESTE = "tests/test_promocao_20261010.py::"
CORTE = (2026, "2026-02-28")


def _analitico(con, did, cons, exercicio, data_final, agregacao=3):
    linhas = con.execute(
        "SELECT v.componente, v.valor_c FROM visao_valor v JOIN regra g ON g.id = v.regra_agregacao_id JOIN regra k ON "
        "k.id = v.regra_consolidacao_id WHERE v.derivacao_id=? AND v.visao='analitico' AND g.codigo='RREO-COL' AND "
        "g.versao=? AND k.codigo='CONS-PAR' AND k.versao=? AND v.exercicio=? AND v.data_final=?",
        (did, agregacao, cons, exercicio, data_final)).fetchall()
    return dict(linhas) or None


def _promover(con, codigo, versao, teste):
    governanca.registrar_decisao(con, codigo, versao, "operacional", "FORTE EVIDÊNCIA", True, "promocao de teste",
                                 "docs/audits/rreo/RP_2024_2026.md", "teste",
                                 teste_regressao=TESTE + teste, ressalva="teste sintetico")


def _mundo_2026(mundo, original=None):
    """Entity 1: one own record (100) and the copy 2400005 (30, paid 10). Entity 15: the original 5 (30) and one own
    record (50). `original`: extra fields of the original (e.g. an execution)."""
    mundo.catalogos({1: [2026], 15: [2026]})
    mundo.listagem(1, 2026, CORTE[1], [_reg(10, ano=2025, aproc=100.0),
                                       _reg(2400005, ano=2025, aproc=30.0, liquidado=10.0, pagoAProc=10.0)], T0)
    mundo.listagem(15, 2026, CORTE[1], [_reg(5, ano=2025, entidade=15, aproc=30.0, **(original or {})),
                                        _reg(6, ano=2025, entidade=15, aproc=50.0)], T0)
    return mundo.processar()[1]


def _verificacao(con, did):
    return con.execute("SELECT verificados, falhas FROM verificacao WHERE derivacao_id=? AND descricao=?",
                       (did, derivar.VERIF_CONS_PAR_V4)).fetchall()


# ================================================================== CONS-PAR v4
def test_cons_par_v4_conta_cada_par_uma_vez(mundo):
    did = _mundo_2026(mundo)
    v3 = _analitico(mundo.con, did, 4, *CORTE)
    assert v3["g"] == 18000 and v3["S1"] == 17000            # 100 + 30 + 50: the original (30) is not summed
    assert _analitico(mundo.con, did, 1, *CORTE)["g"] == 18000     # same as v1 when B has no execution
    assert _verificacao(mundo.con, did) == [(1, 0)]
    with mundo.painel() as p:                                  # not promoted: both sides counted, as before
        assert p.indicadores(*CORTE)["valores"]["inscricao_total"]["valor_c"] == 21000
        assert p.tratamento_dos_pares().startswith("Os dois lados continuam nos valores")
    _promover(mundo.con, "CONS-PAR", 4, "test_cons_par_v4_conta_cada_par_uma_vez")
    with mundo.painel() as p:
        mun = p.indicadores(*CORTE)
        v = {k: x["valor_c"] for k, x in mun["valores"].items()}
        assert v["inscricao_total"] == 18000 and v["saldo_total"] == 17000 and v["registros"] == 3
        assert v["pagamentos"] == 1000                          # the copy's flows stay
        assert (v["inscricao_total"], v["saldo_total"]) == (v3["a"] + v3["b"] + v3["f"] + v3["g"], v3["S1"])
        assert "CONS-PAR v4" in mun["escopo"] and any(r["codigo"] == "CONS-PAR" for r in mun["regras_de_escopo"])
        assert any("CONS-PAR v4" in a and "1 registro(s) da entidade 15" in a for a in mun["avisos"])
        # each entity's own view does not change
        assert p.indicadores(*CORTE, entidade=15)["valores"]["inscricao_total"]["valor_c"] == 8000
        assert p.indicadores(*CORTE, entidade=1)["valores"]["inscricao_total"]["valor_c"] == 13000
        # the pie by entity uses each entity's share of the Municipality, so the parts close
        pizza = p.visao_geral(*CORTE)["por_entidade"]
        assert pizza["fechamento"]["fecha"] and {i["chave"]: i["valor_c"] for i in pizza["itens"]} == {1: 12000, 15: 5000}
        ents = p.entidades_do_corte(*CORTE)
        assert ents["consolidacao"] == {"regra": "CONS-PAR v4", "registros": 1, "inscricao_c": 3000}
        # every notice about the pairs (screens, pairs note, methodology) states the rule in force
        assert "CONS-PAR v4" in p.tratamento_dos_pares() and "dois lados continuam" not in p.tratamento_dos_pares()
        assert any("CONS-PAR v4" in x for x in p.metodologia()["limitacoes"])
        assert "CONS-PAR v4" in p.pares(*CORTE)["nota"]
        # the detail of the original says where it is counted; an ordinary record has no notice
        assert "2025/2400005" in p.detalhe_empenho(15, 2025, 5, *CORTE)["fora_do_indicador"]
        assert p.detalhe_empenho(15, 2025, 6, *CORTE)["fora_do_indicador"] is None


def test_cons_par_v4_nao_consolida_original_com_execucao(mundo):
    did = _mundo_2026(mundo, original={"canceladoAProc": 5.0})
    assert _verificacao(mundo.con, did) == [(1, 1)]             # the pair is still counted twice: recorded
    assert _analitico(mundo.con, did, 4, *CORTE)["g"] == 21000
    _promover(mundo.con, "CONS-PAR", 4, "test_cons_par_v4_nao_consolida_original_com_execucao")
    with mundo.painel() as p:
        mun = p.indicadores(*CORTE)
        assert mun["valores"]["inscricao_total"]["valor_c"] == 21000
        assert not any("não são somados no Município" in a for a in mun["avisos"])     # nothing consolidated
        # corrective audit 13/10/2026 (item 5.3): the pair counted on both sides is no longer silent
        assert [a for a in mun["avisos"] if a.startswith("Município com ressalva (CONS-PAR v4)")]
        assert mun["com_ressalva"]


def test_cons_par_v4_respeita_copia_origem(mundo):
    """Before 2026 the copy is out (COPIA-ORIGEM v1): nothing to consolidate, the original is counted."""
    mundo.catalogos({1: [2025], 15: [2025]})
    mundo.listagem(1, 2025, "2025-12-31", [_reg(2400005, ano=2024, aproc=30.0)], T0)
    mundo.listagem(15, 2025, "2025-12-31", [_reg(5, ano=2024, entidade=15, aproc=30.0)], T0)
    _, did = mundo.processar()
    assert _verificacao(mundo.con, did) == []
    assert _analitico(mundo.con, did, 4, 2025, "2025-12-31")["g"] == 3000
    _promover(mundo.con, "COPIA-ORIGEM", 1, "test_cons_par_v4_respeita_copia_origem")
    _promover(mundo.con, "CONS-PAR", 4, "test_cons_par_v4_respeita_copia_origem")
    with mundo.painel() as p:
        mun = p.indicadores(2025, "2025-12-31")
        assert mun["valores"]["inscricao_total"]["valor_c"] == 3000 and mun["valores"]["registros"]["valor_c"] == 1
        assert p.detalhe_empenho(15, 2024, 5, 2025, "2025-12-31")["fora_do_indicador"] is None


def test_cons_par_v4_entra_no_catalogo_como_experimental(mundo):
    mundo.catalogos({1: [2026]})
    mundo.processar()
    g = governanca.situacao_atual(mundo.con)[("CONS-PAR", 4)]
    assert g["situacao"] == "experimental" and not g["compoe_indicador_publicado"]
