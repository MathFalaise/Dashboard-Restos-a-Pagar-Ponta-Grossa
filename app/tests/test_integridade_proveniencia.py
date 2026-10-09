"""Relational integrity and provenance (correction request of 09/10/2026, items 1 and 7; schema v8).

  * layer 1 refuses, on write, a row whose collection is not the one of its response, is of another type or is beyond
    what its normalization read;
  * every rule a derived row cites must be declared by its derivation (derivacao_regra);
  * the JSON relations get normalized tables with FOREIGN KEYs (derivacao_regra, visao_valor_coleta,
    conciliacao_rreo_coleta), refused if they disagree with the JSON;
  * each manifest's SHA-256 (coleta_manifesto), the code/rule hashes and the environment of each run;
  * the chain of any value (`rastrear`) and the root manifest (`raiz`), to keep OUTSIDE the database.
SINTETICO = temporary database and store with invented records (fixture `mundo`).
"""
import json
import sqlite3

import pytest
from conftest import registro_sintetico as _reg

from rp import banco, cli, execucoes, hash_do_codigo, portoes, proveniencia, regras

T1, T2 = "2026-09-20T10:00:00-03:00", "2026-09-25T10:00:00-03:00"


def _processado(mundo, retratos=((T1, [_reg(1), _reg(2, proc=50.0)]),)):
    mundo.catalogos({1: [2025]})
    snaps = [mundo.listagem(1, 2025, "2025-12-31", regs, quando) for quando, regs in retratos]
    nid, did = mundo.processar()
    mundo.con.commit()
    return snaps, nid, did


def _portao(mundo, ident):
    return next(p for p in portoes.avaliar(mundo.cfg.banco, mundo.armazem)["portoes"] if p["id"] == ident)


# ------------------------------------------------------------------ item 1: layer 1 x collection
def test_SINTETICO_camada1_recusa_coleta_de_outro_tipo_de_outra_resposta_ou_nao_lida(mundo):
    (s,), nid, _ = _processado(mundo)
    con = mundo.con
    linha = list(con.execute("SELECT * FROM rp_registro WHERE normalizacao_id=? LIMIT 1", (nid,)).fetchone())
    catalogo = con.execute("SELECT id FROM coleta WHERE tipo='entidades'").fetchone()[0]
    resp_catalogo = con.execute("SELECT id FROM resposta_bruta WHERE coleta_id=?", (catalogo,)).fetchone()[0]
    nova = con.execute("INSERT INTO normalizacao_execucao (normalizador_versao, executada_em, ultima_coleta_id) VALUES "
                       "('teste', '2026-10-09T10:00:00-03:00', ?)", (s["coleta_id"] - 1,)).lastrowid
    casos = [
        [nid, resp_catalogo, 99, catalogo, *linha[4:]],          # a catalog collection (another type)
        [nid, resp_catalogo, 98, s["coleta_id"], *linha[4:]],    # the response of another collection
        [nova, linha[1], linha[2], s["coleta_id"], *linha[4:]],  # beyond what normalization `nova` read
    ]
    for c in casos:
        with pytest.raises(sqlite3.IntegrityError, match="coleta de outro tipo, de outra resposta ou alem"):
            con.execute(f"INSERT INTO rp_registro VALUES ({','.join('?' * len(c))})", c)
    with pytest.raises(sqlite3.IntegrityError, match="coleta de outro tipo"):
        con.execute("UPDATE rp_registro SET coleta_id=? WHERE normalizacao_id=?", (catalogo, nid))
    with pytest.raises(sqlite3.IntegrityError, match="entidade_ref: coleta de outro tipo"):
        con.execute("INSERT INTO entidade_ref VALUES (?,?,1,'X',NULL,NULL)", (nid, s["coleta_id"]))
    with pytest.raises(sqlite3.IntegrityError, match="rreo_valor: coleta de outro tipo"):
        con.execute("INSERT INTO rreo_valor VALUES (?,?,'x','entidade',2025,'2025-12-31',NULL,'TOTAL (III)','L',1)",
                    (nid, s["coleta_id"]))


# ------------------------------------------------------------------ item 1: rules and JSON relations
def test_SINTETICO_linha_derivada_so_cita_regra_declarada(mundo):
    _, _, did = _processado(mundo)
    con = mundo.con
    nao_declarada = con.execute("INSERT INTO regra (codigo, versao, tipo, uso, status_evidencia, definicao, fonte) VALUES "
                                "('TESTE', 1, 'anomalia', 'experimental', 'HIPÓTESE', 'x', 'x')").lastrowid
    with pytest.raises(sqlite3.IntegrityError, match="anomalia cita regra que a sua derivacao nao declarou"):
        con.execute("INSERT INTO anomalia VALUES (?,?,'LIQ-NEG',NULL,NULL,NULL,NULL,NULL)", (did, nao_declarada))
    with pytest.raises(sqlite3.IntegrityError, match="fora do regras_json"):
        con.execute("INSERT INTO derivacao_regra VALUES (?,?)", (did, nao_declarada))


def test_SINTETICO_relacoes_normalizadas_batem_com_o_json(mundo):
    (s,), _, did = _processado(mundo)
    con = mundo.con
    regras_json = json.loads(con.execute("SELECT regras_json FROM derivacao_execucao WHERE id=?", (did,)).fetchone()[0])
    assert sorted(r for (r,) in con.execute("SELECT regra_id FROM derivacao_regra WHERE derivacao_id=?", (did,))) == \
        sorted(regras_json)
    for vid, coletas in con.execute("SELECT id, coletas_json FROM visao_valor WHERE derivacao_id=?", (did,)):
        ligadas = [u for (u,) in con.execute("SELECT k.snapshot_uid FROM visao_valor_coleta l JOIN coleta k ON k.id = "
                                             "l.coleta_id WHERE l.visao_valor_id=?", (vid,))]
        assert sorted(ligadas) == sorted(json.loads(coletas))
    vid = con.execute("SELECT id FROM visao_valor WHERE derivacao_id=? LIMIT 1", (did,)).fetchone()[0]
    outra = con.execute("SELECT id FROM coleta WHERE tipo='entidades'").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError, match="fora do coletas_json"):
        con.execute("INSERT INTO visao_valor_coleta VALUES (?,?,?)", (did, vid, outra))
    p = _portao(mundo, "proveniencia_completa")
    assert p["ok"] is True and p["detalhe"]["valores"] > 0


def test_SINTETICO_apagar_derivacao_apaga_as_ligacoes_antes(mundo):
    _, nid, did = _processado(mundo)
    con = mundo.con
    from rp import derivar
    derivar.derivar(con, nid)            # a newer current derivation: the old one can be deleted
    r = execucoes.apagar(con, mundo.cfg, "derivacao", did, did)
    assert all(v == 0 for v in r["restantes"].values()) and r["camada0_intacta"]
    assert r["restantes"].keys() >= {"visao_valor_coleta", "conciliacao_rreo_coleta", "derivacao_regra"}


# ------------------------------------------------------------------ item 7: identification of each run
def test_SINTETICO_execucoes_registram_codigo_regras_e_ambiente(mundo):
    _, nid, did = _processado(mundo)
    con = mundo.con
    cod_n, amb_n = con.execute("SELECT sha256_codigo, ambiente_json FROM normalizacao_execucao WHERE id=?", (nid,)).fetchone()
    cod_d, h_regras, amb_d, rj = con.execute("SELECT sha256_codigo, sha256_regras, ambiente_json, regras_json FROM "
                                             "derivacao_execucao WHERE id=?", (did,)).fetchone()
    assert cod_n == cod_d == hash_do_codigo()
    assert h_regras == regras.impressao(con, json.loads(rj))
    assert {"python", "sqlite", "pymupdf"} <= json.loads(amb_n).keys() and json.loads(amb_d) == json.loads(amb_n)
    p = _portao(mundo, "execucao_identificada")
    assert p["ok"] is True and p["detalhe"]["derivacao_feita_com_o_codigo_atual"] is True


def test_impressao_das_regras_depende_do_conteudo_nao_do_id(mundo):
    _, _, did = _processado(mundo)
    con = mundo.con
    ids = json.loads(con.execute("SELECT regras_json FROM derivacao_execucao WHERE id=?", (did,)).fetchone()[0])
    h = regras.impressao(con, ids)
    assert regras.impressao(con, list(reversed(ids))) == h
    assert regras.impressao(con, ids[:-1]) != h


# ------------------------------------------------------------------ item 7: manifest hash, chain, root
def test_SINTETICO_hash_do_manifesto_e_conferido(mundo):
    (s,), _, _ = _processado(mundo)
    con = mundo.con
    h, n = con.execute("SELECT sha256, tamanho FROM coleta_manifesto WHERE coleta_id=?", (s["coleta_id"],)).fetchone()
    assert (h, n) == banco.hash_do_manifesto(mundo.armazem, s["manifesto"])
    assert banco.verificar(con, mundo.armazem) == []
    arq = mundo.armazem.raiz / s["manifesto"]
    arq.write_bytes(arq.read_bytes().replace(b'"observacao"', b' "observacao"'))   # same content, other bytes
    assert any("hash_do_manifesto" in p for p in banco.verificar(con, mundo.armazem))


def test_SINTETICO_cadeia_de_um_valor_ate_o_bruto(mundo):
    (s,), _, did = _processado(mundo)
    con = mundo.con
    vid = con.execute("SELECT id FROM visao_valor WHERE derivacao_id=? AND visao='entidade' AND componente='S1' LIMIT 1",
                      (did,)).fetchone()[0]
    c = proveniencia.cadeia(con, mundo.armazem, vid)
    assert c["ok"] is True and c["problemas"] == []
    assert [x["snapshot_uid"] for x in c["snapshots"]] == [s["snapshot_uid"]]
    [snap] = c["snapshots"]
    assert snap["manifesto_confere"] and snap["registros_normalizados"] == 2
    assert all(r["objeto_confere"] for r in snap["respostas"])
    assert c["derivacao"]["sha256_codigo"] == hash_do_codigo() and c["regras"][0].startswith("RREO-COL")
    arq = mundo.armazem.raiz / s["manifesto"]
    arq.write_bytes(arq.read_bytes() + b"\r\n")
    c = proveniencia.cadeia(con, mundo.armazem, vid)
    assert c["ok"] is False and any("hash do manifesto" in p for p in c["problemas"])


def test_SINTETICO_raiz_grava_confere_e_acusa(mundo, tmp_path):
    _processado(mundo)
    con = mundo.con
    raiz = proveniencia.gerar_raiz(con)
    assert proveniencia.conferir_raiz(con, raiz) == [] and raiz["coletas_sem_hash_de_manifesto"] == 0
    mundo.listagem(1, 2025, "2025-12-31", [_reg(1)], T2)                     # the raw layer only grows: still ok
    assert proveniencia.conferir_raiz(con, raiz) == []
    alterada = json.loads(json.dumps(raiz))
    alterada["snapshots"][0][2] = "incompleta"
    assert any("arquivo alterado" in p for p in proveniencia.conferir_raiz(con, alterada))
    copia = sqlite3.connect(tmp_path / "copia.sqlite")
    con.commit()
    con.backup(copia)
    copia.execute("DROP TRIGGER coleta_manifesto_sem_update")                # an edit made outside the code
    copia.execute("UPDATE coleta_manifesto SET sha256 = substr(sha256, 2) || '0'")
    assert any("manifesto ou status diferente" in p for p in proveniencia.conferir_raiz(copia, raiz))
    copia.close()


def test_SINTETICO_cli_rastrear_e_raiz(mundo, tmp_path, monkeypatch, capsys):
    from test_auditoria_processamento import _config_do_mundo
    monkeypatch.delenv("RP_DADOS_LOCAIS", raising=False)
    _, _, did = _processado(mundo)
    cfg = _config_do_mundo(mundo, tmp_path)
    vid = mundo.con.execute("SELECT MIN(id) FROM visao_valor WHERE derivacao_id=?", (did,)).fetchone()[0]
    assert cli.main(["--config", cfg, "rastrear", "--valor", str(vid)]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    arq = tmp_path / "raiz.json"
    assert cli.main(["--config", cfg, "raiz", "--gravar", str(arq)]) == 0
    capsys.readouterr()
    assert cli.main(["--config", cfg, "raiz", "--gravar", str(arq)]) == 4          # never overwrites
    capsys.readouterr()
    assert cli.main(["--config", cfg, "raiz", "--conferir", str(arq)]) == 0
    assert json.loads(capsys.readouterr().out)["problemas"] == []


# ------------------------------------------------------------------ migration v7 -> v8
def test_banco_v7_migra_para_v8_preenchendo_relacoes_e_hashes(tmp_path, monkeypatch):
    from conftest import Mundo
    monkeypatch.setattr(banco, "VERSAO_ESQUEMA", 7)
    mundo = Mundo(tmp_path)
    (s,), nid, did = _processado(mundo)
    tabelas = [t for (t,) in mundo.con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    antes = {t: mundo.con.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall() for t in tabelas
             if t not in ("esquema_versao", "normalizacao_execucao", "derivacao_execucao")}
    execs = {t: mundo.con.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall()
             for t in ("normalizacao_execucao", "derivacao_execucao")}
    mundo.con.close()
    monkeypatch.undo()
    con = banco.abrir(mundo.cfg)
    assert banco.versao_esquema(con) == 8 and banco.impressao_esquema(con) == banco.IMPRESSAO_ESQUEMA[8]
    assert {t: con.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall() for t in antes} == antes
    for t, linhas in execs.items():           # old runs: the new columns stay NULL (never back-filled with today's code)
        assert [r[:len(linhas[0])] for r in con.execute(f"SELECT * FROM {t} ORDER BY 1")] == linhas
        assert all(x is None for r in con.execute(f"SELECT * FROM {t} ORDER BY 1") for x in r[len(linhas[0]):])
    assert con.execute("SELECT COUNT(*) FROM derivacao_regra WHERE derivacao_id=?", (did,)).fetchone()[0] == \
        len(json.loads(con.execute("SELECT regras_json FROM derivacao_execucao WHERE id=?", (did,)).fetchone()[0]))
    assert con.execute("SELECT COUNT(*) FROM visao_valor_coleta").fetchone()[0] == \
        con.execute("SELECT COUNT(*) FROM visao_valor v, json_each(v.coletas_json)").fetchone()[0] > 0
    assert con.execute("SELECT COUNT(*) FROM coleta_manifesto").fetchone()[0] == \
        con.execute("SELECT COUNT(*) FROM coleta").fetchone()[0]
    assert banco.verificar(con, mundo.armazem) == []
    (backup,) = con.execute("SELECT backup_antes FROM esquema_versao WHERE versao = 8").fetchone()
    assert "antes-migracao-v7-v8" in backup
    from rp import proveniencia as prov
    assert all(v == 0 for k, v in prov.conferir(con, did).items() if k != "valores")
    con.close()


# ------------------------------------------------------------------ review of phase C
def test_SINTETICO_comparar_bancos_ve_tempo_e_hash_de_manifesto(mundo, tmp_path):
    from rp import equivalencia
    _processado(mundo)
    mundo.con.commit()
    copia = sqlite3.connect(tmp_path / "copia.sqlite")
    mundo.con.backup(copia)
    r = equivalencia.comparar(mundo.con, copia)
    assert r["equivalentes"] and r["complementos_camada0_iguais"] == {"coleta_tempo": True, "coleta_manifesto": True}
    copia.execute("DROP TRIGGER coleta_manifesto_sem_update")           # an edit made outside the code
    copia.execute("UPDATE coleta_manifesto SET tamanho = tamanho + 1")
    r = equivalencia.comparar(mundo.con, copia)
    assert not r["equivalentes"] and r["complementos_camada0_iguais"]["coleta_manifesto"] is False
    copia.close()
