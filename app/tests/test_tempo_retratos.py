"""Temporal precision of the snapshots (correction request of 09/10/2026, item 4; schema v7, rp-vigencia/2).

Before: "as it was on" compared the START of the collection (coletada_em) with the requested instant, so a
collection still running counted as available. Now each collection has start AND conclusion (coleta_tempo), from its
manifest only, in canonical form; a snapshot is available from its conclusion on; "most recent" is ordered by start,
conclusion and snapshot_uid; a snapshot without evidence of conclusion is never available to a query with a date.
SINTETICO = temporary database and store with invented snapshots (fixture `mundo`).
"""
import json
import sqlite3

import pytest
from conftest import COLETOR_SINTETICO, chamar, dados, registro_sintetico

from rp import banco, derivar, instante, portoes, vigencia
from rp.coletor import EP_RP
from rp.interface import Aplicacao
from rp.snapshots import gravar_snapshot

CORTE = (2025, "2025-12-31")
CHAVE = (1, 2025, "2025-01-01", "2025-12-31")
R100 = [registro_sintetico(1, ano=2024, aproc=100.0)]
R200 = [registro_sintetico(1, ano=2024, aproc=200.0)]
R300 = [registro_sintetico(1, ano=2024, aproc=300.0)]


def _retrato(mundo, regs, inicio, fim=None, recebidas=None, segunda=None, origem="relogio_coletor"):
    """RP listing snapshot of entity 1 with an explicit start, conclusion and response times."""
    corpo = json.dumps({"content": regs, "last": True, "totalElements": len(regs)}).encode()
    p = {"entidade": 1, "exercicio": 2025, "dataInicial": "2025-01-01", "dataFinal": "2025-12-31", "size": 2000}
    respostas = [{"url": "sintetico", "http_status": 200, "corpo": corpo, "recebida_em": r} for r in (recebidas or [None])]
    seg = [{"ordem": i, "url": "sintetico", "http_status": 200, "corpo": corpo, "recebida_em": r, "igual": True}
           for i, r in enumerate(segunda)] if segunda else None
    return gravar_snapshot(mundo.con, mundo.armazem, tipo="rp_listagem", endpoint=EP_RP, parametros=p,
                           coletada_em=inicio, origem_carimbo=origem, status="completa", coletor=COLETOR_SINTETICO,
                           respostas=respostas, segunda_leitura=seg, finalizada_em=fim)


def _tempo(con, s):
    return con.execute("SELECT inicio_em, concluida_em, fonte_conclusao, precisao FROM coleta_tempo WHERE coleta_id=?",
                       (s["coleta_id"],)).fetchone()


def _inscricao(mundo, em=None):
    with mundo.painel() as p:
        ind = p.indicadores(*CORTE, entidade=1, em=em)
        return ind["valores"]["inscricao_total"]["valor_c"] if ind["disponivel"] else None


# ------------------------------------------------------------------ a collection that is still running is not available
def test_SINTETICO_coleta_iniciada_antes_e_concluida_depois_nao_vale_no_instante(mundo):
    mundo.catalogos({1: [2025]}, quando="2025-01-01T00:00:00-03:00")
    a = _retrato(mundo, R100, "2026-09-25T09:00:00-03:00", "2026-09-25T09:01:00-03:00")
    b = _retrato(mundo, R200, "2026-09-25T10:00:00-03:00", "2026-09-25T10:30:00-03:00")
    con = mundo.con
    assert vigencia.coletas_vigentes(con, "2026-09-25T10:15:00-03:00", frozenset())[CHAVE] == a["coleta_id"]
    assert vigencia.coletas_vigentes(con, "2026-09-25T10:30:00-03:00", frozenset())[CHAVE] == b["coleta_id"]
    assert CHAVE not in vigencia.coletas_vigentes(con, "2026-09-25T09:00:30-03:00", frozenset())
    mundo.processar()
    for em, esperado in (("2026-09-25T10:15:00-03:00", 10000), ("2026-09-25T10:30:00-03:00", 20000), (None, 20000)):
        assert _inscricao(mundo, em) == esperado, em
    # the derivation "as it was on" follows the same rule (a derivation of its own, as the panel requires)
    nid = con.execute("SELECT MAX(id) FROM normalizacao_execucao").fetchone()[0]
    did = derivar.derivar(con, nid, "2026-09-25T10:15:00-03:00")
    usados = {json.loads(c)[0] for (c,) in con.execute(
        "SELECT DISTINCT coletas_json FROM visao_valor WHERE derivacao_id=? AND visao='entidade'", (did,))}
    assert usados == {a["snapshot_uid"]}


# ------------------------------------------------------------------ time zones
def test_SINTETICO_fusos_equivalentes_comparam_igual(mundo):
    mundo.catalogos({1: [2025]}, quando="2025-01-01T00:00:00-03:00")
    s = _retrato(mundo, R100, "2026-09-25T13:00:00+00:00", "2026-09-25T13:05:00+00:00")
    assert _tempo(mundo.con, s) == ("2026-09-25T10:00:00-03:00", "2026-09-25T10:05:00-03:00", "manifesto", "exata")
    for em in ("2026-09-25T13:05:00+00:00", "2026-09-25T10:05:00-03:00", "2026-09-25T08:05:00-05:00"):
        assert vigencia.coletas_vigentes(mundo.con, instante(em), frozenset())[CHAVE] == s["coleta_id"], em
    assert CHAVE not in vigencia.coletas_vigentes(mundo.con, instante("2026-09-25T13:04:59Z"), frozenset())


# ------------------------------------------------------------------ equal and successive times
@pytest.mark.parametrize("ordem_de_gravacao", [(0, 1), (1, 0)])
def test_SINTETICO_mesmo_inicio_decide_pela_conclusao(mundo, ordem_de_gravacao):
    mundo.catalogos({1: [2025]}, quando="2025-01-01T00:00:00-03:00")
    dados_ = [(R100, "2026-09-25T10:00:00-03:00", "2026-09-25T10:01:00-03:00"),
              (R200, "2026-09-25T10:00:00-03:00", "2026-09-25T10:02:00-03:00")]
    snaps = {i: _retrato(mundo, *dados_[i]) for i in ordem_de_gravacao}
    con = mundo.con
    assert vigencia.coletas_vigentes(con, None, frozenset())[CHAVE] == snaps[1]["coleta_id"]
    assert vigencia.coletas_vigentes(con, "2026-09-25T10:01:30-03:00", frozenset())[CHAVE] == snaps[0]["coleta_id"]


def test_SINTETICO_retratos_sucessivos_do_mesmo_corte(mundo):
    mundo.catalogos({1: [2025]}, quando="2025-01-01T00:00:00-03:00")
    s = [_retrato(mundo, regs, f"2026-09-2{d}T10:00:00-03:00", f"2026-09-2{d}T10:10:00-03:00")
         for d, regs in ((1, R100), (2, R200), (3, R300))]
    mundo.processar()
    casos = {"2026-09-21T10:09:59-03:00": None, "2026-09-21T10:10:00-03:00": 10000,
             "2026-09-22T10:05:00-03:00": 10000, "2026-09-22T10:10:00-03:00": 20000, "2026-09-23T23:59:59-03:00": 30000}
    for em, esperado in casos.items():
        cid = vigencia.coletas_vigentes(mundo.con, em, frozenset()).get(CHAVE)
        assert cid == (None if esperado is None else s[esperado // 10000 - 1]["coleta_id"]), em
        assert _inscricao(mundo, em) == esperado, em


# ------------------------------------------------------------------ where the conclusion comes from
def test_SINTETICO_conclusao_pela_ultima_resposta_inclui_a_segunda_leitura(mundo):
    s = _retrato(mundo, R100, "2026-09-25T10:00:00-03:00", None,
                 recebidas=["2026-09-25T10:00:20-03:00"], segunda=["2026-09-25T10:00:50-03:00"])
    assert _tempo(mundo.con, s) == ("2026-09-25T10:00:00-03:00", "2026-09-25T10:00:50-03:00", "ultima_resposta",
                                    "ultima_resposta")


def test_SINTETICO_data_do_arquivo_e_aproximada_e_o_painel_avisa(mundo):
    mundo.catalogos({1: [2025]}, quando="2025-01-01T00:00:00-03:00")
    s = _retrato(mundo, R100, "2026-09-25T10:00:00-03:00", None, recebidas=["2026-09-25T10:00:00-03:00"],
                 origem="mtime_arquivo")
    assert _tempo(mundo.con, s)[2:] == ("ultima_resposta", "aproximada")
    mundo.processar()
    with mundo.painel() as p:
        ind = p.indicadores(*CORTE, entidade=1, em="2026-09-26")
        assert any("horário de conclusão do retrato" in a and "aproximado" in a for a in ind["avisos"])
        assert not any("aproximado" in a for a in p.indicadores(*CORTE, entidade=1)["avisos"])   # current: no date


def test_SINTETICO_sem_evidencia_de_conclusao_nunca_vale_com_data(mundo):
    mundo.catalogos({1: [2025]}, quando="2025-01-01T00:00:00-03:00")
    s = _retrato(mundo, R100, "2026-09-25T10:00:00-03:00", None)        # no conclusion, no response time
    assert _tempo(mundo.con, s) == ("2026-09-25T10:00:00-03:00", None, "sem_evidencia", "desconhecida")
    assert vigencia.coletas_vigentes(mundo.con, None, frozenset())[CHAVE] == s["coleta_id"]
    assert CHAVE not in vigencia.coletas_vigentes(mundo.con, "2030-01-01T00:00:00-03:00", frozenset())
    mundo.processar()
    assert _inscricao(mundo) == 10000 and _inscricao(mundo, "2030-01-01") is None
    status, _, corpo = chamar(Aplicacao(mundo.cfg.banco), "/resumo", exercicio=2025, data_final="2025-12-31",
                              em="2030-01-01")
    assert status == "200 OK" and dados(corpo) == {} and "R$ 0,00" not in corpo


# ------------------------------------------------------------------ the database refuses inconsistent times
def test_SINTETICO_gatilhos_da_v7(mundo):
    s = _retrato(mundo, R100, "2026-09-25T10:00:00-03:00", "2026-09-25T10:01:00-03:00")
    con, cid = mundo.con, s["coleta_id"]
    with pytest.raises(sqlite3.IntegrityError, match="nao se edita"):
        con.execute("UPDATE coleta_tempo SET concluida_em='2026-09-25T10:02:00-03:00'")
    with pytest.raises(sqlite3.IntegrityError, match="nao se apaga"):
        con.execute("DELETE FROM coleta_tempo")
    s2 = _retrato(mundo, R200, "2026-09-26T10:00:00-03:00", "2026-09-26T10:01:00-03:00")
    con.execute("DROP TRIGGER coleta_tempo_sem_delete")          # only to re-insert in this test's database
    con.execute("DELETE FROM coleta_tempo WHERE coleta_id=?", (s2["coleta_id"],))
    for linha in [("2026-09-26T13:00:00+00:00", "2026-09-26T13:01:00+00:00", "manifesto", "exata"),   # not canonical
                  ("2026-09-26T10:00:00-03:00", "2026-09-26T09:59:00-03:00", "manifesto", "exata"),   # ends before
                  ("2026-09-26T10:00:01-03:00", "2026-09-26T10:01:00-03:00", "manifesto", "exata")]:  # other start
        with pytest.raises(sqlite3.IntegrityError, match="coleta_tempo fora da forma canonica"):
            con.execute(banco.SQL_TEMPO, (s2["coleta_id"], *linha))
    with pytest.raises(sqlite3.IntegrityError):                   # conclusion without evidence must say so
        con.execute(banco.SQL_TEMPO, (s2["coleta_id"], "2026-09-26T10:00:00-03:00", None, "manifesto", "exata"))
    assert cid


# ------------------------------------------------------------------ migration v6 -> v7 and checks
def test_banco_v6_migra_para_v7_preenchendo_pelos_manifestos(tmp_path, monkeypatch):
    from conftest import Mundo
    monkeypatch.setattr(banco, "VERSAO_ESQUEMA", 6)             # a v6 database, like the active one before v7
    mundo = Mundo(tmp_path)
    exata = _retrato(mundo, R100, "2026-09-25T10:00:00-03:00", "2026-09-25T10:01:00-03:00")
    ultima = _retrato(mundo, R200, "2026-09-26T10:00:00-03:00", None, recebidas=["2026-09-26T10:00:30-03:00"])
    sem = _retrato(mundo, R300, "2026-09-27T10:00:00-03:00", None)
    assert banco.versao_esquema(mundo.con) == 6
    tabelas = [t for (t,) in mundo.con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    antes = {t: mundo.con.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall() for t in tabelas if t != "esquema_versao"}
    mundo.con.close()
    monkeypatch.undo()
    monkeypatch.setattr(banco, "VERSAO_ESQUEMA", 7)             # the code of v7 (v8 exists since phase C)
    con = banco.abrir(mundo.cfg)                                # v7: backup, migration, rows from the manifests
    assert banco.versao_esquema(con) == 7 and banco.impressao_esquema(con) == banco.IMPRESSAO_ESQUEMA[7]
    assert {t: con.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall() for t in antes} == antes
    assert _tempo(con, exata) == ("2026-09-25T10:00:00-03:00", "2026-09-25T10:01:00-03:00", "manifesto", "exata")
    assert _tempo(con, ultima)[1:] == ("2026-09-26T10:00:30-03:00", "ultima_resposta", "ultima_resposta")
    assert _tempo(con, sem)[1:] == (None, "sem_evidencia", "desconhecida")
    (backup,) = con.execute("SELECT backup_antes FROM esquema_versao WHERE versao = 7").fetchone()
    assert "antes-migracao-v6-v7" in backup
    assert banco.verificar(con, mundo.armazem) == []
    con.close()


def test_SINTETICO_verificar_acusa_tempo_diferente_do_manifesto(mundo):
    _retrato(mundo, R100, "2026-09-25T10:00:00-03:00", "2026-09-25T10:01:00-03:00")
    con = mundo.con
    assert banco.verificar(con, mundo.armazem) == []
    con.execute("DROP TRIGGER coleta_tempo_sem_update")         # simulating an edit made outside the code
    con.execute("UPDATE coleta_tempo SET concluida_em='2026-09-25T10:00:30-03:00'")
    assert any("tempo_da_coleta" in p for p in banco.verificar(con, mundo.armazem))


def test_SINTETICO_portao_dos_tempos(mundo):
    mundo.catalogos({1: [2025]}, quando="2025-01-01T00:00:00-03:00")
    _retrato(mundo, R100, "2026-09-25T10:00:00-03:00", None)
    mundo.processar()
    mundo.con.commit()
    p = next(x for x in portoes.avaliar(mundo.cfg.banco, mundo.armazem)["portoes"] if x["id"] == "tempos_das_coletas")
    assert p["ok"] is True and p["detalhe"]["coletas_sem_tempo"] == 0
    assert p["detalhe"]["por_precisao"] == {"desconhecida": 1, "exata": 2}       # the 2 catalog snapshots + the listing


# ------------------------------------------------------------------ review of phase B
def test_SINTETICO_instante_nao_canonico_e_normalizado_no_filtro(mundo):
    from rp import consultas
    mundo.catalogos({1: [2025]}, quando="2025-01-01T00:00:00-03:00")
    s = _retrato(mundo, R100, "2026-09-25T10:00:00-03:00", "2026-09-25T10:05:00-03:00")
    for em in ("2026-09-25", "2026-09-25T13:05:00+00:00", "2026-09-25T10:05:00"):     # end of day, UTC, naive (BRT)
        assert consultas.snapshot_em(mundo.con, *CHAVE, em=em) == s["coleta_id"], em
    for em in ("2026-09-24", "2026-09-25T13:04:59+00:00"):
        assert consultas.snapshot_em(mundo.con, *CHAVE, em=em) is None, em
