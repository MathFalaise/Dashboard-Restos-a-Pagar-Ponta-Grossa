"""Money field missing, null or invalid (correction request of 09/10/2026, item 2; schema v6, normalizer v2).

Before: `centavos(r.get(campo, 0))` typed a missing money field as ZERO, and the record composed every indicator as if
the value were known. Now the record does not become an rp_registro row; each refused field becomes a valor_recusado
row (field name + nature), the snapshot is never the current one (VALOR-RECUSADO), the gate fails, and the panel says
why. A real zero is still a zero. Historical rows are not transformed.

Synthetic world (fixture `mundo`): the snapshot is written directly as 'completa', like an old or imported snapshot
that did not go through the collector's strict contract (contrato.py v2) - the later layers must hold on their own.
"""
import json
import sqlite3

import pytest
from conftest import chamar, dados, registro_sintetico

from rp import derivar, normalizar, portoes
from rp.interface import Aplicacao

CORTE = (2025, "2025-12-31")
T1, T2 = "2026-09-20T10:00:00-03:00", "2026-09-25T10:00:00-03:00"
R1 = registro_sintetico(1, ano=2024, aproc=100.0)
R2 = registro_sintetico(2, ano=2024, aproc=50.0)


def _sem(r, campo):
    return {k: v for k, v in r.items() if k != campo}


def _cenario(mundo, retratos):
    mundo.catalogos({1: [2025]})
    snaps = [mundo.listagem(1, *CORTE, regs, quando) for quando, regs in retratos]
    nid, did = mundo.processar()
    return snaps, nid, did


def _recusas(con, nid):
    return con.execute("SELECT indice, campo, natureza, valor_bruto, entidade, anoempenho, empenho FROM valor_recusado "
                       "WHERE normalizacao_id=? ORDER BY indice, campo", (nid,)).fetchall()


# ------------------------------------------------------------------ normalization
@pytest.mark.parametrize("campo", normalizar.DINHEIRO)
def test_SINTETICO_ausencia_em_cada_campo_monetario_nunca_vira_zero(mundo, campo):
    _, nid, _ = _cenario(mundo, [(T1, [R1, _sem(R2, campo)])])
    con = mundo.con
    assert _recusas(con, nid) == [(1, campo, "ausente", None, 1, 2024, 2)]
    # the record with the missing field is not a row with zero: it is not a row at all
    assert con.execute("SELECT empenho FROM rp_registro WHERE normalizacao_id=?", (nid,)).fetchall() == [(1,)]


@pytest.mark.parametrize("valor, natureza, bruto", [(None, "nulo", None), ("1,50", "invalido", '"1,50"'),
                                                    (True, "invalido", "true"), (1.234, "invalido", "1.234"),
                                                    ({"v": 1}, "invalido", '{"v": 1}')])
def test_SINTETICO_nulo_e_invalido_sao_recusados_com_o_valor_bruto(mundo, valor, natureza, bruto):
    _, nid, _ = _cenario(mundo, [(T1, [R1, dict(R2, liquidado=valor)])])
    assert _recusas(mundo.con, nid) == [(1, "liquidado", natureza, bruto, 1, 2024, 2)]


def test_SINTETICO_zero_valido_continua_zero(mundo):
    zeros = dict(R2, **{c: 0 for c in normalizar.DINHEIRO})
    _, nid, did = _cenario(mundo, [(T1, [R1, zeros])])
    con = mundo.con
    assert _recusas(con, nid) == []
    assert con.execute("SELECT proc_c, aproc_c, liquidado_c FROM rp_registro WHERE normalizacao_id=? AND empenho=2",
                       (nid,)).fetchone() == (0, 0, 0)
    assert not con.execute("SELECT 1 FROM anomalia WHERE derivacao_id=? AND tipo='VALOR-RECUSADO'", (did,)).fetchone()


def test_SINTETICO_varios_campos_do_mesmo_registro(mundo):
    r = dict(_sem(R2, "proc"), aproc=None)
    _, nid, did = _cenario(mundo, [(T1, [r])])
    assert [x[1:3] for x in _recusas(mundo.con, nid)] == [("aproc", "nulo"), ("proc", "ausente")]
    [d] = mundo.con.execute("SELECT detalhe_json FROM anomalia WHERE derivacao_id=? AND tipo='VALOR-RECUSADO'",
                            (did,)).fetchall()
    assert json.loads(d[0]) == {"campos": {"aproc": "nulo", "proc": "ausente"}, "posicao": [0, 0]}


# ------------------------------------------------------------------ the database refuses the inconsistent relation
def test_SINTETICO_gatilhos_da_v6(mundo):
    _, nid, _ = _cenario(mundo, [(T1, [R1, _sem(R2, "proc")])])
    con = mundo.con
    rid, cid = con.execute("SELECT resposta_id, coleta_id FROM valor_recusado WHERE normalizacao_id=?", (nid,)).fetchone()
    linha = con.execute("SELECT * FROM rp_registro WHERE normalizacao_id=?", (nid,)).fetchone()
    with pytest.raises(sqlite3.IntegrityError, match="posicao com valor recusado"):
        con.execute(f"INSERT INTO rp_registro VALUES ({','.join('?' * len(linha))})", (*linha[:2], 1, *linha[3:]))
    with pytest.raises(sqlite3.IntegrityError, match="outra coleta"):
        con.execute("INSERT INTO valor_recusado VALUES (?,?,?,?,1,2024,9,'aproc','ausente',NULL)", (nid, rid, 5, cid + 99))
    with pytest.raises(sqlite3.IntegrityError, match="registro ja normalizado"):
        con.execute("INSERT INTO valor_recusado VALUES (?,?,?,?,1,2024,1,'aproc','ausente',NULL)", (nid, rid, 0, cid))
    with pytest.raises(sqlite3.IntegrityError):          # 'invalido' requires the raw value, the others forbid it
        con.execute("INSERT INTO valor_recusado VALUES (?,?,?,?,1,2024,9,'aproc','invalido',NULL)", (nid, rid, 7, cid))
    with pytest.raises(sqlite3.IntegrityError, match="nao se edita"):
        con.execute("UPDATE valor_recusado SET natureza='nulo'")
    with pytest.raises(sqlite3.IntegrityError, match="apague antes as derivacoes"):
        con.execute("DELETE FROM valor_recusado")


# ------------------------------------------------------------------ derivation, panel and gate
def test_SINTETICO_retrato_com_valor_recusado_nunca_e_o_vigente(mundo):
    (s1, s2), _, did = _cenario(mundo, [(T1, [R1, R2]), (T2, [R1, _sem(R2, "aproc")])])
    con = mundo.con
    assert derivar.coletas_vigentes(con)[(1, 2025, "2025-01-01", "2025-12-31")] == s1["coleta_id"]
    verif = con.execute("SELECT escopo_json, verificados, falhas FROM verificacao WHERE derivacao_id=? AND descricao=?",
                        (did, derivar.VERIF_RETRATO_VALOR_RECUSADO)).fetchall()
    assert [(json.loads(e)["snapshot_recusado"], json.loads(e)["snapshot_vigente"], v, f) for e, v, f in verif] == \
           [(s2["snapshot_uid"], s1["snapshot_uid"], 1, 1)]
    with mundo.painel() as p:
        ind = p.indicadores(*CORTE, entidade=1)
        assert ind["valores"]["inscricao_total"]["valor_c"] == 15000         # the previous valid snapshot: 100 + 50
        assert any("campo monetário ausente, nulo ou inválido (VALOR-RECUSADO)" in a for a in ind["avisos"])


def test_SINTETICO_so_retrato_com_valor_recusado_deixa_o_dado_indisponivel(mundo):
    _cenario(mundo, [(T1, [R1, _sem(R2, "pagoProc")])])
    with mundo.painel() as p:
        ind = p.indicadores(*CORTE, entidade=1)
        assert not ind["disponivel"] and "VALOR-RECUSADO" in ind["motivo_indisponivel"]
    status, _, corpo = chamar(Aplicacao(mundo.cfg.banco), "/resumo", exercicio=2025, data_final="2025-12-31")
    assert status == "200 OK" and dados(corpo) == {} and "R$ 0,00" not in corpo


def test_SINTETICO_portao_reprova_valor_recusado(mundo):
    _cenario(mundo, [(T1, [R1, dict(R2, retencao="x")])])
    r = portoes.avaliar(mundo.cfg.banco, mundo.armazem)
    p = next(p for p in r["portoes"] if p["id"] == "campos_monetarios_ausentes")
    assert p["ok"] is False and p["detalhe"]["registros"] == 1 and p["detalhe"]["recusados_v2"] == 1
    assert p["detalhe"]["campos_recusados"] == {"retencao:invalido": 1} and r["apto"] is False


def test_SINTETICO_sem_recusa_nada_novo_e_gravado(mundo):
    _, _, did = _cenario(mundo, [(T1, [R1, R2])])
    con = mundo.con
    assert con.execute("SELECT COUNT(*) FROM valor_recusado").fetchone()[0] == 0
    assert not con.execute("SELECT 1 FROM verificacao WHERE derivacao_id=? AND descricao=?",
                           (did, derivar.VERIF_RETRATO_VALOR_RECUSADO)).fetchone()
    r = portoes.avaliar(mundo.cfg.banco, mundo.armazem)
    assert next(p for p in r["portoes"] if p["id"] == "campos_monetarios_ausentes")["ok"] is True


# ------------------------------------------------------------------ v5 -> v6 migration
def test_banco_v5_migra_para_v6_com_backup_e_sem_mudar_linha(tmp_path, monkeypatch):
    from rp import banco
    from rp.config import carregar
    cfg = carregar(dados_locais=tmp_path / "l", snapshots=tmp_path / "s", backups=tmp_path / "b")
    monkeypatch.setattr(banco, "VERSAO_ESQUEMA", 5)        # a v5 database, like the active one before v6
    con = banco.abrir(cfg)
    assert banco.versao_esquema(con) == 5 and banco.impressao_esquema(con) == banco.IMPRESSAO_ESQUEMA[5]
    tabelas = [t for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    antes = {t: con.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall() for t in tabelas if t != "esquema_versao"}
    con.close()
    monkeypatch.undo()
    novo = banco.abrir(cfg)                                # migrates to v6, with a backup first
    assert banco.versao_esquema(novo) == 6 and banco.impressao_esquema(novo) == banco.IMPRESSAO_ESQUEMA[6]
    assert {t: novo.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall() for t in antes} == antes
    assert novo.execute("SELECT COUNT(*) FROM valor_recusado").fetchone()[0] == 0
    (backup,) = novo.execute("SELECT backup_antes FROM esquema_versao WHERE versao = 6").fetchone()
    assert "antes-migracao-v5-v6" in backup
    restaurado = sqlite3.connect(backup)                   # the backup opens and is the v5 database
    try:
        assert restaurado.execute("SELECT MAX(versao) FROM esquema_versao").fetchone()[0] == 5
        assert restaurado.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        restaurado.close()
    novo.close()
