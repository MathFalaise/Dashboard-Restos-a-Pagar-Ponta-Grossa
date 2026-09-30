"""Os 26 testes da Etapa 03, executados sobre o CODIGO DE PRODUCAO (app/rp).

Mesmas assercoes e mesmos numeros de etapa03/validacao/tests/test_integridade.py;
nada e importado de etapa03/. Os dados brutos das Etapas 01/02 entram num armazem
TEMPORARIO pelo importador de producao (fixture `producao`, em conftest.py).
"""
import json
import sqlite3

import pytest

from rp import banco, consultas, derivar, normalizar
from rp.armazem import Armazem
from rp.config import carregar
from rp.snapshots import gravar_snapshot


def um(con, sql, *p):
    return con.execute(sql, p).fetchone()


def vig(con, e, ex, di, df):
    return consultas.snapshot_em(con, e, ex, di, df)


# ---------------------------------------------------------------- camada bruta
def test_camada_bruta_imutavel(producao):
    con = producao["con"]
    for sql in ("UPDATE coleta SET status='falhou' WHERE id=1", "DELETE FROM coleta WHERE id=1",
                "UPDATE resposta_bruta SET url='x' WHERE id=1", "DELETE FROM resposta_bruta WHERE id=1",
                "UPDATE objeto_bruto SET tamanho=0", "UPDATE coletor_versao SET versao='x' WHERE id=1"):
        with pytest.raises(sqlite3.DatabaseError, match="imutável"):
            con.execute(sql)


def test_hash_de_cada_resposta_confere(producao):
    con = producao["con"]
    shas = [s for (s,) in con.execute("SELECT sha256 FROM resposta_bruta")]
    assert len(shas) == 224
    for s in set(shas):
        banco.corpo(con, s)  # descomprime e confere tamanho + SHA-256


def test_regra_nao_se_edita(producao):
    with pytest.raises(sqlite3.DatabaseError, match="nova versão"):
        producao["con"].execute("UPDATE regra SET definicao='x' WHERE codigo='S1'")


# ---------------------------------------------------------------- normalizacao
def test_paginacao_completa_e_nenhum_registro_perdido(producao):
    con, nid = producao["con"], producao["nid"]
    for cid, status in con.execute("SELECT id, status FROM coleta WHERE tipo='rp_listagem'").fetchall():
        corpos = [json.loads(banco.corpo(con, s)) for (s,) in
                  con.execute("SELECT sha256 FROM resposta_bruta WHERE coleta_id=? ORDER BY ordem", (cid,))]
        itens = sum(len(d["content"]) for d in corpos)
        assert itens == corpos[-1]["totalElements"] and status == "completa"
        assert um(con, "SELECT COUNT(*) FROM rp_registro WHERE normalizacao_id=? AND coleta_id=?", nid, cid)[0] == itens


def test_chaves_base_sempre_presentes(producao):
    opcionais = {"orgao", "unidade", "funcao", "subFuncao", "programa", "projeto", "elemento"}
    for (aus,) in producao["con"].execute("SELECT DISTINCT chaves_ausentes FROM rp_registro"):
        assert set(json.loads(aus)) <= opcionais
    assert um(producao["con"], "SELECT COUNT(*) FROM rp_registro WHERE chaves_extras <> '[]'")[0] == 0


def test_centavos_recusa_mais_de_duas_casas():
    assert normalizar.centavos("754.32") == 75432 and normalizar.centavos(0) == 0
    with pytest.raises(normalizar.ValorNaoRepresentavel):
        normalizar.centavos("1.005")


def test_movimentacao_guarda_rotulos_como_vieram(producao):
    r = um(producao["con"], "SELECT exercicio_liquidacao_rotulo, no_liquidacao_rotulo, exercicio_pagamento_rotulo, "
                            "no_pagamento_rotulo FROM movimentacao_lancamento WHERE normalizacao_id=? AND empenho=5659 "
                            "AND anoempenho=2025 AND data='2026-01-19'", producao["nid"])
    assert r == (2026, 1089, 2025, 1)


# ---------------------------------------------------------------- derivacao
def test_mov_ref_resolve_rotulos_trocados(producao):
    refs = producao["con"].execute(
        "SELECT DISTINCT i.liquidacao_exercicio, i.liquidacao_numero FROM movimentacao_interpretada i "
        "JOIN movimentacao_lancamento m ON m.resposta_id=i.resposta_id AND m.indice=i.indice AND m.normalizacao_id=? "
        "WHERE i.derivacao_id=? AND m.empenho=5659 AND m.anoempenho=2025 AND m.tipo_lancamento=40",
        (producao["nid"], producao["did"])).fetchall()
    assert refs == [(2025, 1)]


def _derivado(con, did, cid, ano, emp):
    return um(con, "SELECT categoria, s1_saldo_total_c, s2_a_liquidar_c, s3_liquidado_a_pagar_c, cancel_processado_c, "
                   "cancel_nao_processado_c FROM rp_derivado WHERE derivacao_id=? AND coleta_id=? AND anoempenho=? AND empenho=?",
              did, cid, ano, emp)


def test_caso_11963_2016(producao):
    con = producao["con"]
    assert _derivado(con, producao["did"], vig(con, 1, 2026, "2026-01-01", "2026-12-31"), 2016, 11963) == \
        ("processado", 0, 0, 0, 386452, 0)


def test_caso_5659_2025(producao):
    con = producao["con"]
    assert _derivado(con, producao["did"], vig(con, 1, 2026, "2026-01-01", "2026-12-31"), 2025, 5659) == \
        ("processado", 86378534, 0, 86378534, 0, 0)
    cid = vig(con, 1, 2026, "2026-02-01", "2026-03-31")
    assert um(con, "SELECT proc_c, pago_proc_c FROM rp_registro WHERE normalizacao_id=? AND coleta_id=? AND "
                   "anoempenho=2025 AND empenho=5659", producao["nid"], cid) == (300137339, 88972602)


def test_empenhos_nas_duas_abas_tem_os_mesmos_valores_da_consulta_sem_tipo(producao):
    con, nid = producao["con"], producao["nid"]
    cols = "entidade, anoempenho, empenho, proc_c, aproc_c, pago_proc_c, pago_aproc_c, cancelado_aproc_c, liquidado_c, retencao_c"
    base = ("SELECT id FROM coleta WHERE tipo='rp_listagem' AND entidade=1 AND exercicio=2026 AND data_inicial='2026-01-01' "
            "AND data_final='2026-08-31' AND tipo_pesquisa")
    semtipo = um(con, base + " IS NULL ORDER BY coletada_em LIMIT 1")[0]
    S = {r[:3]: r for r in con.execute(f"SELECT {cols} FROM rp_registro WHERE normalizacao_id=? AND coleta_id=?", (nid, semtipo))}
    for aba, cond in (("Processados", lambda r: r[3] > 0), ("NaoProcessados", lambda r: r[4] > 0)):
        cid = um(con, base + "=?", aba)[0]
        A = {r[:3]: r for r in con.execute(f"SELECT {cols} FROM rp_registro WHERE normalizacao_id=? AND coleta_id=?", (nid, cid))}
        assert A == {k: r for k, r in S.items() if cond(r)}
    assert len([k for k, r in S.items() if r[3] > 0 and r[4] > 0]) == 197


def test_identidade_de_estoque_entre_periodos(producao):
    con, nid = producao["con"], producao["nid"]
    q = ("SELECT anoempenho, empenho, proc_c, aproc_c, pago_proc_c, pago_aproc_c, cancelado_aproc_c, liquidado_c "
         "FROM rp_registro WHERE normalizacao_id=? AND coleta_id=?")
    J = {r[:2]: r[2:] for r in con.execute(q, (nid, vig(con, 1, 2026, "2026-01-01", "2026-01-31")))}
    F = {r[:2]: r[2:] for r in con.execute(q, (nid, vig(con, 1, 2026, "2026-02-01", "2026-03-31")))}
    assert len(F) == 3403
    for k, (p, a, *_) in F.items():
        jp, ja, jpp, jpa, jc, jl = J[k]
        assert a == ja - jl - jc and p == jp - jpp + jl - jpa
    for k in J.keys() - F.keys():
        jp, ja, jpp, jpa, jc, jl = J[k]
        assert jp + ja - jpp - jpa - jc == 0


def test_continuidade_entre_exercicios_sem_falhas(producao):
    con, did = producao["con"], producao["did"]
    total, falhas = um(con, "SELECT SUM(verificados), SUM(falhas) FROM verificacao WHERE derivacao_id=? AND descricao LIKE 'continuidade%'", did)
    assert total == 3990 + 4 + 360 + 8 + 1516 and falhas == 0
    assert um(con, "SELECT COUNT(*) FROM anomalia WHERE derivacao_id=? AND tipo IN ('DESCONTINUIDADE','SALDO-SEM-CONTINUIDADE')", did)[0] == 0


def test_anomalias_do_corte_2026(producao):
    con, did = producao["con"], producao["did"]
    cid = vig(con, 1, 2026, "2026-01-01", "2026-12-31")
    cont = dict(con.execute("SELECT tipo, COUNT(*) FROM anomalia WHERE derivacao_id=? AND coleta_id=? GROUP BY tipo", (did, cid)))
    assert cont.get("LIQ-NEG") == 5 and cont.get("COPIA-24") == 731 and cont.get("PAGOPROC-SEM-PROC") == 1
    assert "CANCPROC-NZ" not in cont and "CHAVE-DUP" not in cont
    assert um(con, "SELECT anoempenho, empenho FROM anomalia WHERE derivacao_id=? AND coleta_id=? AND tipo='PAGOPROC-SEM-PROC'",
              did, cid) == (2025, 2410946)


# ---------------------------------------------------------------- espelhamento
def test_espelhamento_2026_execucao_so_na_copia(producao):
    con, did = producao["con"], producao["did"]
    lados = dict(con.execute("SELECT lado_com_execucao, COUNT(*) FROM espelhamento_par WHERE derivacao_id=? AND exercicio=2026 GROUP BY 1", (did,)))
    assert sum(lados.values()) == 731 and set(lados) <= {"A", "nenhum"}
    assert um(con, "SELECT MIN(mesma_inscricao) FROM espelhamento_par WHERE derivacao_id=? AND exercicio=2026", did)[0] == 1


def test_espelhamento_2025_execucao_no_original_e_copia_e_saldo_remanescente(producao):
    rel = producao["con"].execute("SELECT relacao_inscricao, lado_com_execucao, COUNT(*) FROM espelhamento_par "
                                  "WHERE derivacao_id=? AND exercicio=2025 GROUP BY 1, 2", (producao["did"],)).fetchall()
    assert sorted(rel) == [("a_e_saldo_final_de_b", "B", 9), ("igual", "nenhum", 11)]


def test_nenhum_registro_espelhado_foi_removido(producao):
    con, did = producao["con"], producao["did"]
    for ra, ia, rb, ib in con.execute("SELECT resposta_a_id, indice_a, resposta_b_id, indice_b FROM espelhamento_par WHERE derivacao_id=?", (did,)):
        for r, i in ((ra, ia), (rb, ib)):
            assert um(con, "SELECT COUNT(*) FROM rp_derivado WHERE derivacao_id=? AND resposta_id=? AND indice=?", did, r, i)[0] == 1


def _visao(con, did, visao, ex, df, versao=None, agregacao=1):
    q = ("SELECT v.componente, v.valor_c FROM visao_valor v LEFT JOIN regra r ON r.id=v.regra_consolidacao_id "
         "JOIN regra g ON g.id=v.regra_agregacao_id WHERE v.derivacao_id=? AND v.visao=? AND v.exercicio=? "
         "AND v.data_final=? AND g.versao=?" + (" AND r.versao=?" if versao else ""))
    return dict(con.execute(q, (did, visao, ex, df, agregacao) + ((versao,) if versao else ())))


def test_visoes_publicado_e_analiticas(producao):
    con, did = producao["con"], producao["did"]
    pub, v1, v2 = (_visao(con, did, "publicado", 2026, "2026-04-30"), _visao(con, did, "analitico", 2026, "2026-04-30", 1),
                   _visao(con, did, "analitico", 2026, "2026-04-30", 2))
    assert pub["b"] == 3882432969 and pub["g"] == 14525037054
    assert pub["b"] - v1["b"] == 1134582815 and pub["g"] - v1["g"] == 1954237470
    for f in ("c", "d", "h", "i", "j"):
        assert v1[f] == pub[f] == v2[f]
    assert v1 == v2
    assert _visao(con, did, "analitico", 2025, "2025-12-31", 1)["S1"] > _visao(con, did, "analitico", 2025, "2025-12-31", 2)["S1"]


def test_regras_de_consolidacao_sao_experimentais(producao):
    for uso, status in producao["con"].execute("SELECT uso, status_evidencia FROM regra WHERE codigo='CONS-PAR'"):
        assert (uso, status) == ("experimental", "HIPÓTESE")


# ---------------------------------------------------------------- RREO
def _conc(con, did, escopo, ex, df, agregacao=1):
    return dict(con.execute("SELECT c.coluna, c.diferenca_c FROM conciliacao_rreo c JOIN regra g ON g.id=c.regra_agregacao_id "
                            "WHERE c.derivacao_id=? AND c.escopo=? AND c.exercicio=? AND c.data_final=? AND g.versao=?",
                            (did, escopo, ex, df, agregacao)))


def test_conciliacao_reproduz_etapa02(producao):
    con, did = producao["con"], producao["did"]
    d4 = _conc(con, did, "entidade", 2026, "2026-08-31")
    assert all(d4[c] == 0 for c in "abcdefgj") and d4["h"] == -34547956 and d4["i"] == -23772825
    assert {c: v for c, v in _conc(con, did, "consolidado", 2026, "2026-04-30").items() if v} == {"h": 64416}
    d25 = _conc(con, did, "entidade", 2025, "2025-12-31")
    assert d25["g"] == 91729262 and d25["h"] == 0 and d25["i"] == 0


def test_rreo_col_v2_fecha_c_e_i_de_2025_pela_categoria_do_registro(producao):
    con, did = producao["con"], producao["did"]
    assert _conc(con, did, "entidade", 2025, "2025-12-31", 1)["c"] == -46200
    assert _conc(con, did, "entidade", 2025, "2025-12-31", 2)["c"] == 0
    assert _conc(con, did, "consolidado", 2025, "2025-12-31", 1)["i"] == -255425
    assert _conc(con, did, "consolidado", 2025, "2025-12-31", 2)["i"] == 0
    assert _conc(con, did, "entidade", 2026, "2026-08-31", 2)["i"] == -23772825 + 4950


def test_rreo_col_v2_torna_L_igual_a_S1_em_todas_as_visoes(producao):
    q = ("SELECT v.visao, IFNULL(v.entidade,0), IFNULL(v.regra_consolidacao_id,0), v.exercicio, v.data_final, v.componente, v.valor_c "
         "FROM visao_valor v JOIN regra g ON g.id=v.regra_agregacao_id WHERE v.derivacao_id=? AND g.versao=2 AND v.componente IN ('L','S1')")
    val = {}
    for *k, comp, v in producao["con"].execute(q, (producao["did"],)):
        val.setdefault(tuple(k), {})[comp] = v
    assert val and all(d["L"] == d["S1"] for d in val.values())


def test_rreo_sem_snapshot_correspondente_e_registrado_nao_inventado(producao):
    n = um(producao["con"], "SELECT COUNT(*) FROM verificacao WHERE derivacao_id=? AND descricao LIKE 'RREO sem snapshot%'", producao["did"])[0]
    assert n == 2 * 2


# ---------------------------------------------------------------- snapshots no tempo
def test_mesmo_corte_em_datas_diferentes(producao):
    con, nid = producao["con"], producao["nid"]
    hist = consultas.historico(con, 1, 2026, "2026-01-01", "2026-08-31")
    assert len(hist) == 2
    (c1, t1, o1), (c2, t2, o2) = hist
    assert o1 == "manifesto" and o2 == "mtime_arquivo"
    assert consultas.snapshot_em(con, 1, 2026, "2026-01-01", "2026-08-31", em=t1) == c1
    assert consultas.snapshot_em(con, 1, 2026, "2026-01-01", "2026-08-31") == c2
    assert consultas.diferencas(con, nid, c1, c2) == {"novos": [], "sumidos": [], "alterados": []}


def test_SINTETICO_alteracao_retroativa_preserva_os_dois_retratos(tmp_path):
    """SINTETICO: dois snapshots do mesmo corte com um valor alterado (entidade ficticia 999)."""
    cfg = carregar(dados_locais=tmp_path / "l", snapshots=tmp_path / "s", backups=tmp_path / "b")
    con, armazem = banco.abrir(cfg), Armazem(cfg.snapshots)
    col = {"nome": "teste-sintetico", "versao": "1", "sha256_codigo": None}

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
        gravar_snapshot(con, armazem, tipo="rp_listagem", endpoint="/sintetico", parametros=p, coletada_em=quando,
                        origem_carimbo="relogio_coletor", status="completa", coletor=col,
                        respostas=[{"url": "sintetico", "corpo": corpo(aproc)}])
    nid, _ = normalizar.normalizar(con)
    derivar.derivar(con, nid)
    c_mar = consultas.snapshot_em(con, 999, 2026, "2026-01-01", "2026-12-31", em="2026-04-01T00:00:00-03:00")
    c_hoje = consultas.snapshot_em(con, 999, 2026, "2026-01-01", "2026-12-31")
    assert c_mar != c_hoje
    assert consultas.diferencas(con, nid, c_mar, c_hoje)["alterados"] == [((999, 2025, 1), "aproc_c", 10000, 8000)]
    assert um(con, "SELECT COUNT(*) FROM coleta")[0] == 2


# ---------------------------------------------------------------- reprocessamento
def test_reprocessamento_deterministico(producao):
    con, nid, did = producao["con"], producao["nid"], producao["did"]
    did2 = derivar.derivar(con, nid)
    h1, h2 = (um(con, "SELECT hash_resultado FROM derivacao_execucao WHERE id=?", d)[0] for d in (did, did2))
    assert did2 != did and h1 == h2
