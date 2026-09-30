"""Testes de integridade do MODELO sobre a carga descartável (dados reais das Etapas 01/02).

VALIDAÇÃO DO MODELO — Etapa 03. Não é código de produção. Nenhum teste faz requisição.
Os testes marcados SINTÉTICO usam dados inventados, explicitamente, para simular
uma alteração retroativa que os dados reais não contêm em duas coletas.
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from construir_banco import construir  # noqa: E402
from rpval import bruto, consultas, derivar, normalizar  # noqa: E402


@pytest.fixture(scope="session")
def banco(tmp_path_factory):
    con, nid, did, resumo, _ = construir(tmp_path_factory.mktemp("db") / "validacao.sqlite")
    return {"con": con, "nid": nid, "did": did}


def um(con, sql, *p):
    return con.execute(sql, p).fetchone()


def vig(con, e, ex, di, df):
    return consultas.snapshot_em(con, e, ex, di, df)


# ---------------------------------------------------------------- camada bruta
def test_camada_bruta_imutavel(banco):
    con = banco["con"]
    for sql in ("UPDATE coleta SET status='falhou' WHERE id=1", "DELETE FROM coleta WHERE id=1",
                "UPDATE resposta_bruta SET corpo=x'00' WHERE id=1", "DELETE FROM resposta_bruta WHERE id=1",
                "UPDATE coletor_versao SET versao='x' WHERE id=1"):
        with pytest.raises(sqlite3.DatabaseError, match="imutável"):
            con.execute(sql)


def test_hash_de_cada_resposta_confere(banco):
    import hashlib
    for corpo, h in banco["con"].execute("SELECT corpo, sha256 FROM resposta_bruta"):
        assert hashlib.sha256(corpo).hexdigest() == h


def test_regra_nao_se_edita(banco):
    with pytest.raises(sqlite3.DatabaseError, match="nova versão"):
        banco["con"].execute("UPDATE regra SET definicao='x' WHERE codigo='S1'")


# ---------------------------------------------------------------- normalização
def test_paginacao_completa_e_nenhum_registro_perdido(banco):
    """Regra 6: cada item de content[] vira exatamente uma linha; soma bate com totalElements."""
    con, nid = banco["con"], banco["nid"]
    for cid, status in con.execute("SELECT id, status FROM coleta WHERE tipo='rp_listagem'").fetchall():
        corpos = [json.loads(c) for (c,) in con.execute("SELECT corpo FROM resposta_bruta WHERE coleta_id=? ORDER BY ordem", (cid,))]
        itens = sum(len(d["content"]) for d in corpos)
        assert itens == corpos[-1]["totalElements"] and status == "completa"
        assert um(con, "SELECT COUNT(*) FROM rp_registro WHERE normalizacao_id=? AND coleta_id=?", nid, cid)[0] == itens


def test_chaves_base_sempre_presentes(banco):
    """Só as 7 chaves de programática detalhada podem faltar (Etapa 01 §8)."""
    opcionais = {"orgao", "unidade", "funcao", "subFuncao", "programa", "projeto", "elemento"}
    for (aus,) in banco["con"].execute("SELECT DISTINCT chaves_ausentes FROM rp_registro"):
        assert set(json.loads(aus)) <= opcionais
    assert um(banco["con"], "SELECT COUNT(*) FROM rp_registro WHERE chaves_extras <> '[]'")[0] == 0


def test_centavos_recusa_mais_de_duas_casas():
    assert normalizar.centavos("754.32") == 75432 and normalizar.centavos(0) == 0
    with pytest.raises(normalizar.ValorNaoRepresentavel):
        normalizar.centavos("1.005")


def test_movimentacao_guarda_rotulos_como_vieram(banco):
    """5659/2025: no 1º pagamento de 2026 a API rotula (2026, 1089) em 'liquidação' e (2025, 1) em 'pagamento'."""
    con, nid = banco["con"], banco["nid"]
    r = um(con, "SELECT exercicio_liquidacao_rotulo, no_liquidacao_rotulo, exercicio_pagamento_rotulo, no_pagamento_rotulo "
                "FROM movimentacao_lancamento WHERE normalizacao_id=? AND empenho=5659 AND anoempenho=2025 AND data='2026-01-19'", nid)
    assert r == (2026, 1089, 2025, 1)


# ---------------------------------------------------------------- derivação
def test_mov_ref_resolve_rotulos_trocados(banco):
    con, did = banco["con"], banco["did"]
    refs = con.execute("SELECT DISTINCT i.liquidacao_exercicio, i.liquidacao_numero FROM movimentacao_interpretada i "
                       "JOIN movimentacao_lancamento m ON m.resposta_id=i.resposta_id AND m.indice=i.indice "
                       "WHERE i.derivacao_id=? AND m.empenho=5659 AND m.anoempenho=2025 AND m.tipo_lancamento=40", (did,)).fetchall()
    assert refs == [(2025, 1)]


def _derivado(con, did, cid, ano, emp):
    return um(con, "SELECT categoria, s1_saldo_total_c, s2_a_liquidar_c, s3_liquidado_a_pagar_c, cancel_processado_c, "
                   "cancel_nao_processado_c FROM rp_derivado WHERE derivacao_id=? AND coleta_id=? AND anoempenho=? AND empenho=?",
              did, cid, ano, emp)


def test_caso_11963_2016(banco):
    con, did = banco["con"], banco["did"]
    cid = vig(con, 1, 2026, "2026-01-01", "2026-12-31")
    assert _derivado(con, did, cid, 2016, 11963) == ("processado", 0, 0, 0, 386452, 0)


def test_caso_5659_2025(banco):
    con, did = banco["con"], banco["did"]
    assert _derivado(con, did, vig(con, 1, 2026, "2026-01-01", "2026-12-31"), 2025, 5659) == ("processado", 86378534, 0, 86378534, 0, 0)
    # proc é o saldo antes de dataInicial: 3.001.373,39 com início em 01/02
    cid = vig(con, 1, 2026, "2026-02-01", "2026-03-31")
    assert um(con, "SELECT proc_c, pago_proc_c FROM rp_registro WHERE coleta_id=? AND anoempenho=2025 AND empenho=5659", cid) == (300137339, 88972602)


def test_empenhos_nas_duas_abas_tem_os_mesmos_valores_da_consulta_sem_tipo(banco):
    con, nid = banco["con"], banco["nid"]
    cols = "entidade, anoempenho, empenho, proc_c, aproc_c, pago_proc_c, pago_aproc_c, cancelado_aproc_c, liquidado_c, retencao_c"
    base = ("SELECT id FROM coleta WHERE tipo='rp_listagem' AND entidade=1 AND exercicio=2026 AND data_inicial='2026-01-01' "
            "AND data_final='2026-08-31' AND tipo_pesquisa")
    semtipo = um(con, base + " IS NULL ORDER BY coletada_em LIMIT 1")[0]
    S = {r[:3]: r for r in con.execute(f"SELECT {cols} FROM rp_registro WHERE normalizacao_id=? AND coleta_id=?", (nid, semtipo))}
    for aba, cond in (("Processados", lambda r: r[3] > 0), ("NaoProcessados", lambda r: r[4] > 0)):
        cid = um(con, base + "=?", aba)[0]
        A = {r[:3]: r for r in con.execute(f"SELECT {cols} FROM rp_registro WHERE normalizacao_id=? AND coleta_id=?", (nid, cid))}
        assert A == {k: r for k, r in S.items() if cond(r)}
    amb = [k for k, r in S.items() if r[3] > 0 and r[4] > 0]
    assert len(amb) == 197


def test_identidade_de_estoque_entre_periodos(banco):
    """aproc[01/02] = aproc − liquidado − canceladoAProc de janeiro; total idem (Etapa 02 §8)."""
    con, nid = banco["con"], banco["nid"]
    jan = vig(con, 1, 2026, "2026-01-01", "2026-01-31")
    fev = vig(con, 1, 2026, "2026-02-01", "2026-03-31")
    q = "SELECT anoempenho, empenho, proc_c, aproc_c, pago_proc_c, pago_aproc_c, cancelado_aproc_c, liquidado_c FROM rp_registro WHERE normalizacao_id=? AND coleta_id=?"
    J = {r[:2]: r[2:] for r in con.execute(q, (nid, jan))}
    F = {r[:2]: r[2:] for r in con.execute(q, (nid, fev))}
    assert len(F) == 3403
    for k, (p, a, *_) in F.items():
        jp, ja, jpp, jpa, jc, jl = J[k]
        assert a == ja - jl - jc and p == jp - jpp + jl - jpa
    for k in J.keys() - F.keys():
        jp, ja, jpp, jpa, jc, jl = J[k]
        assert jp + ja - jpp - jpa - jc == 0


def test_continuidade_entre_exercicios_sem_falhas(banco):
    con, did = banco["con"], banco["did"]
    total, falhas = um(con, "SELECT SUM(verificados), SUM(falhas) FROM verificacao WHERE derivacao_id=? AND descricao LIKE 'continuidade%'", did)
    assert total == 3990 + 4 + 360 + 8 + 1516 and falhas == 0
    assert um(con, "SELECT COUNT(*) FROM anomalia WHERE derivacao_id=? AND tipo IN ('DESCONTINUIDADE','SALDO-SEM-CONTINUIDADE')", did)[0] == 0


def test_anomalias_do_corte_2026(banco):
    con, did = banco["con"], banco["did"]
    cid = vig(con, 1, 2026, "2026-01-01", "2026-12-31")
    cont = dict(con.execute("SELECT tipo, COUNT(*) FROM anomalia WHERE derivacao_id=? AND coleta_id=? GROUP BY tipo", (did, cid)))
    assert cont.get("LIQ-NEG") == 5 and cont.get("COPIA-24") == 731 and cont.get("PAGOPROC-SEM-PROC") == 1
    assert "CANCPROC-NZ" not in cont and "CHAVE-DUP" not in cont
    assert um(con, "SELECT anoempenho, empenho FROM anomalia WHERE derivacao_id=? AND coleta_id=? AND tipo='PAGOPROC-SEM-PROC'", did, cid) == (2025, 2410946)


# ---------------------------------------------------------------- espelhamento
def test_espelhamento_2026_execucao_so_na_copia(banco):
    con, did = banco["con"], banco["did"]
    lados = dict(con.execute("SELECT lado_com_execucao, COUNT(*) FROM espelhamento_par WHERE derivacao_id=? AND exercicio=2026 GROUP BY 1", (did,)))
    assert sum(lados.values()) == 731 and set(lados) <= {"A", "nenhum"}
    assert um(con, "SELECT MIN(mesma_inscricao) FROM espelhamento_par WHERE derivacao_id=? AND exercicio=2026", did)[0] == 1


def test_espelhamento_2025_execucao_no_original_e_copia_e_saldo_remanescente(banco):
    con, did = banco["con"], banco["did"]
    rel = con.execute("SELECT relacao_inscricao, lado_com_execucao, COUNT(*) FROM espelhamento_par "
                      "WHERE derivacao_id=? AND exercicio=2025 GROUP BY 1, 2", (did,)).fetchall()
    assert sorted(rel) == [("a_e_saldo_final_de_b", "B", 9), ("igual", "nenhum", 11)]


def test_nenhum_registro_espelhado_foi_removido(banco):
    """Regra 6: os dois lados de cada par continuam no normalizado e no derivado."""
    con, did = banco["con"], banco["did"]
    for ra, ia, rb, ib in con.execute("SELECT resposta_a_id, indice_a, resposta_b_id, indice_b FROM espelhamento_par WHERE derivacao_id=?", (did,)):
        for r, i in ((ra, ia), (rb, ib)):
            assert um(con, "SELECT COUNT(*) FROM rp_derivado WHERE derivacao_id=? AND resposta_id=? AND indice=?", did, r, i)[0] == 1


def _visao(con, did, visao, ex, df, versao=None, agregacao=1):
    q = ("SELECT v.componente, v.valor_c FROM visao_valor v LEFT JOIN regra r ON r.id=v.regra_consolidacao_id "
         "JOIN regra g ON g.id=v.regra_agregacao_id "
         "WHERE v.derivacao_id=? AND v.visao=? AND v.exercicio=? AND v.data_final=? AND g.versao=?"
         + (" AND r.versao=?" if versao else ""))
    return dict(con.execute(q, (did, visao, ex, df, agregacao) + ((versao,) if versao else ())))


def test_visoes_publicado_e_analiticas(banco):
    con, did = banco["con"], banco["did"]
    pub = _visao(con, did, "publicado", 2026, "2026-04-30")
    v1 = _visao(con, did, "analitico", 2026, "2026-04-30", 1)
    v2 = _visao(con, did, "analitico", 2026, "2026-04-30", 2)
    assert pub["b"] == 3882432969 and pub["g"] == 14525037054          # = RREO consolidado 2º bim
    assert pub["b"] - v1["b"] == 1134582815 and pub["g"] - v1["g"] == 1954237470
    for f in ("c", "d", "h", "i", "j"):                                    # fluxos não mudam
        assert v1[f] == pub[f] == v2[f]
    assert v1 == v2                                                        # 2026: as duas regras coincidem
    p25, a25_1, a25_2 = (_visao(con, did, "publicado", 2025, "2025-12-31"),
                         _visao(con, did, "analitico", 2025, "2025-12-31", 1), _visao(con, did, "analitico", 2025, "2025-12-31", 2))
    assert a25_1["S1"] > a25_2["S1"]                                       # 2025: v2 consolida também os 9 remanescentes


def test_regras_de_consolidacao_sao_experimentais(banco):
    for uso, status in banco["con"].execute("SELECT uso, status_evidencia FROM regra WHERE codigo='CONS-PAR'"):
        assert (uso, status) == ("experimental", "HIPÓTESE")


# ---------------------------------------------------------------- RREO
def _conc(con, did, escopo, ex, df, agregacao=1):
    return dict(con.execute("SELECT c.coluna, c.diferenca_c FROM conciliacao_rreo c JOIN regra g ON g.id=c.regra_agregacao_id "
                            "WHERE c.derivacao_id=? AND c.escopo=? AND c.exercicio=? AND c.data_final=? AND g.versao=?",
                            (did, escopo, ex, df, agregacao)))


def test_conciliacao_reproduz_etapa02(banco):
    con, did = banco["con"], banco["did"]
    d4 = _conc(con, did, "entidade", 2026, "2026-08-31")
    assert all(d4[c] == 0 for c in "abcdefgj") and d4["h"] == -34547956 and d4["i"] == -23772825
    d2 = _conc(con, did, "consolidado", 2026, "2026-04-30")
    assert {c: v for c, v in d2.items() if v} == {"h": 64416}
    d25 = _conc(con, did, "entidade", 2025, "2025-12-31")
    assert d25["g"] == 91729262 and d25["h"] == 0 and d25["i"] == 0


def test_rreo_col_v2_fecha_c_e_i_de_2025_pela_categoria_do_registro(banco):
    """v2: pagamento segue a categoria do registro (15863/2023: 462,00; entidade 15: 2.554,25; 2410946/2025: 49,50)."""
    con, did = banco["con"], banco["did"]
    assert _conc(con, did, "entidade", 2025, "2025-12-31", agregacao=1)["c"] == -46200
    assert _conc(con, did, "entidade", 2025, "2025-12-31", agregacao=2)["c"] == 0
    assert _conc(con, did, "consolidado", 2025, "2025-12-31", agregacao=1)["i"] == -255425
    assert _conc(con, did, "consolidado", 2025, "2025-12-31", agregacao=2)["i"] == 0
    assert _conc(con, did, "entidade", 2026, "2026-08-31", agregacao=2)["i"] == -23772825 + 4950


def test_rreo_col_v2_torna_L_igual_a_S1_em_todas_as_visoes(banco):
    con, did = banco["con"], banco["did"]
    q = ("SELECT v.visao, IFNULL(v.entidade,0), IFNULL(v.regra_consolidacao_id,0), v.exercicio, v.data_final, v.componente, v.valor_c "
         "FROM visao_valor v JOIN regra g ON g.id=v.regra_agregacao_id WHERE v.derivacao_id=? AND g.versao=2 AND v.componente IN ('L','S1')")
    val = {}
    for *k, comp, v in con.execute(q, (did,)):
        val.setdefault(tuple(k), {})[comp] = v
    assert val and all(d["L"] == d["S1"] for d in val.values())


def test_rreo_sem_snapshot_correspondente_e_registrado_nao_inventado(banco):
    con, did = banco["con"], banco["did"]
    n = um(con, "SELECT COUNT(*) FROM verificacao WHERE derivacao_id=? AND descricao LIKE 'RREO sem snapshot%'", did)[0]
    assert n == 2 * 2  # consolidados do 3º e 4º bim/2026 (sem coleta de todas as entidades), × 2 versões de RREO-COL


# ---------------------------------------------------------------- snapshots no tempo
def test_mesmo_corte_em_datas_diferentes(banco):
    con, nid = banco["con"], banco["nid"]
    hist = consultas.historico(con, 1, 2026, "2026-01-01", "2026-08-31")
    assert len(hist) == 2
    (c1, t1, o1), (c2, t2, o2) = hist
    assert o1 == "manifesto" and o2 == "mtime_arquivo"
    assert consultas.snapshot_em(con, 1, 2026, "2026-01-01", "2026-08-31", em=t1) == c1
    assert consultas.snapshot_em(con, 1, 2026, "2026-01-01", "2026-08-31") == c2
    d = consultas.diferencas(con, nid, c1, c2)
    assert d == {"novos": [], "sumidos": [], "alterados": []}


def test_SINTETICO_alteracao_retroativa_preserva_os_dois_retratos(tmp_path):
    """SINTÉTICO: duas coletas do mesmo corte com um valor alterado entre elas (entidade fictícia 999)."""
    con = bruto.criar_banco(tmp_path / "sintetico.sqlite")
    col = bruto.coletor(con, "teste-sintetico", "1")
    def corpo(aproc):
        return json.dumps({"content": [{"entidade": 999, "empenho": 1, "anoempenho": 2025, "empenhoExercicio": "1/2025",
                                        "cnpjNome": "X", "dataEmissao": "2025-01-02", "programatica": "0", "fonteRecurso": 1,
                                        "descricaoFonte": "X", "fornecedor": 1, "nome": "X", "cnpj": "X", "proc": 0, "aproc": aproc,
                                        "canceladoProc": 0, "pagoProc": 0, "pagoProcEstornado": 0, "canceladoAProc": 0,
                                        "pagoAProc": 0, "pagoAProcEstornado": 0, "retencao": 0, "liquidado": 0,
                                        "desdobraDesp": "00", "subDesdobramento": "00"}],
                           "last": True, "totalElements": 1, "numberOfElements": 1}).encode()
    p = {"entidade": 999, "exercicio": 2026, "dataInicial": "2026-01-01", "dataFinal": "2026-12-31", "size": 2000}
    for quando, aproc in (("2026-03-31T10:00:00-03:00", 100.00), ("2026-06-30T10:00:00-03:00", 80.00)):
        bruto.registrar_coleta(con, tipo="rp_listagem", endpoint="/sintetico", parametros=p, coletada_em=quando,
                               origem_carimbo="relogio_coletor", status="completa", coletor_id=col,
                               respostas=[{"url": "sintetico", "corpo": corpo(aproc)}])
    nid = normalizar.normalizar(con)
    derivar.derivar(con, nid)
    c_mar = consultas.snapshot_em(con, 999, 2026, "2026-01-01", "2026-12-31", em="2026-04-01T00:00:00-03:00")
    c_hoje = consultas.snapshot_em(con, 999, 2026, "2026-01-01", "2026-12-31")
    assert c_mar != c_hoje
    assert consultas.diferencas(con, nid, c_mar, c_hoje)["alterados"] == [((999, 2025, 1), "aproc_c", 10000, 8000)]
    assert um(con, "SELECT COUNT(*) FROM coleta")[0] == 2  # nada foi sobrescrito


# ---------------------------------------------------------------- reprocessamento
def test_reprocessamento_deterministico(banco):
    con, nid, did = banco["con"], banco["nid"], banco["did"]
    did2 = derivar.derivar(con, nid)
    h1, h2 = (um(con, "SELECT hash_resultado FROM derivacao_execucao WHERE id=?", d)[0] for d in (did, did2))
    assert did2 != did and h1 == h2
