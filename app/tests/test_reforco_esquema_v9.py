"""Reinforcements from the external review of 19/10/2026 (schema v9). No accounting rule, formula or value changes.

  * a rule row is never deleted, even on a connection without PRAGMA foreign_keys (trigger regra_sem_delete);
  * a failure midway through a derivation leaves nothing of it in the database (one transaction);
  * a database migrated from any earlier version has the same structure as one created by the code.
SINTETICO = temporary database and store with invented records (fixture `mundo`).
"""
import sqlite3

import pytest
from conftest import registro_sintetico as _reg

from rp import banco, derivar, regras
from rp.config import carregar


def _cfg(tmp_path):
    return carregar(dados_locais=tmp_path / "l", snapshots=tmp_path / "s", backups=tmp_path / "b")


def _conteudo(con):
    """Every row of every table (sqlite_sequence included), order-independent: the database content, not its ids."""
    tabelas = [t for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    return {t: sorted(map(repr, con.execute(f"SELECT * FROM {t}"))) for t in tabelas}


def _estrutura(con):
    """Structure only: each sqlite_master object (normalized SQL) plus what SQLite reports of each table (columns with
    type, NOT NULL, default and key; indexes with their columns; foreign keys). No row is read."""
    objetos = sorted((t, nome, tabela, banco._sql_normalizado(sql)) for t, nome, tabela, sql in con.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"))
    tabelas = [t for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE "
                                         "'sqlite_%' ORDER BY name")]
    por_tabela = {}
    for t in tabelas:
        indices = sorted(con.execute(f"PRAGMA index_list({t})").fetchall(), key=lambda r: r[1])
        por_tabela[t] = {
            "colunas": con.execute(f"PRAGMA table_xinfo({t})").fetchall(),
            "indices": [(i[1:], con.execute(f"PRAGMA index_xinfo({i[1]})").fetchall()) for i in indices],
            "chaves_estrangeiras": con.execute(f"PRAGMA foreign_key_list({t})").fetchall(),
        }
    return {"objetos": objetos, "tabelas": por_tabela}


# ------------------------------------------------------------------ item 2: a rule is never deleted
def test_SINTETICO_regra_nao_se_apaga_nem_sem_foreign_keys(mundo):
    con = mundo.con
    rid = regras.ids(con)[("PAR-24", 1)]
    catalogo = _conteudo(con)["regra"]
    con.execute("PRAGMA foreign_keys = OFF")          # like a sqlite3 shell opened by hand: until v8 DELETE went through
    for sql in ("DELETE FROM regra WHERE id=?", "UPDATE regra SET definicao='outra' WHERE id=?"):
        with pytest.raises(sqlite3.DatabaseError, match="regra nao se apaga|regra não se edita"):
            con.execute(sql, (rid,))
    with pytest.raises(sqlite3.DatabaseError, match="regra nao se apaga"):
        con.execute("DELETE FROM regra")
    con.execute("PRAGMA foreign_keys = ON")
    assert _conteudo(con)["regra"] == catalogo                   # history intact


def test_SINTETICO_nova_versao_de_regra_continua_entrando(mundo, monkeypatch):
    con = mundo.con
    antes = _conteudo(con)["regra"]
    nova = ("PAR-24", 99, "pareamento", "experimental", "HIPÓTESE", "versao sintetica de teste", "teste")
    monkeypatch.setattr(regras, "REGRAS", [*regras.REGRAS, nova])
    with con:
        regras.semear(con)                                       # the real path of a new version
    depois = _conteudo(con)["regra"]
    assert set(antes) < set(depois) and len(depois) == len(antes) + 1
    assert ("PAR-24", 99) in regras.ids(con) and ("PAR-24", 1) in regras.ids(con)


# ------------------------------------------------------------------ item 3: failure midway through a derivation
def test_SINTETICO_falha_no_meio_da_derivacao_nao_deixa_nada_gravado(mundo, monkeypatch):
    mundo.catalogos({1: [2025]})
    mundo.listagem(1, 2025, "2025-12-31", [_reg(1), _reg(2, proc=50.0), _reg(2_400_001)], "2026-09-29T20:00:00-03:00")
    from rp import normalizar
    nid, _ = normalizar.normalizar(mundo.con)
    mundo.con.commit()
    antes = _conteudo(mundo.con)
    gravado = {}
    original = derivar.hash_resultado

    def falhar_depois_de_gravar(con, did, *a, **kw):
        # last step inside the transaction: every derived table was already written for this run
        for t in ("derivacao_execucao", "derivacao_regra", "rp_derivado", "visao_valor", "visao_valor_coleta",
                  "anomalia", "verificacao"):
            col = "id" if t == "derivacao_execucao" else "derivacao_id"
            gravado[t] = con.execute(f"SELECT COUNT(*) FROM {t} WHERE {col}=?", (did,)).fetchone()[0]
        raise RuntimeError("falha injetada no meio da derivacao")

    monkeypatch.setattr(derivar, "hash_resultado", falhar_depois_de_gravar)
    with pytest.raises(RuntimeError, match="falha injetada"):
        derivar.derivar(mundo.con, nid)
    assert all(n > 0 for n in gravado.values()), gravado          # rows were written before the failure
    assert _conteudo(mundo.con) == antes                          # and none of them stayed

    monkeypatch.setattr(derivar, "hash_resultado", original)
    did = derivar.derivar(mundo.con, nid)                         # the next run works normally
    h = mundo.con.execute("SELECT hash_resultado FROM derivacao_execucao WHERE id=?", (did,)).fetchone()[0]
    assert h == derivar.hash_resultado(mundo.con, did)
    assert mundo.con.execute("SELECT COUNT(*) FROM derivacao_execucao").fetchone()[0] == 1


# ------------------------------------------------------------------ item 4: migrated structure = created structure
def _banco_na_versao(caminho, versao):
    """A database exactly as the code of `versao` left it: esquema.sql (base) and the migrations up to `versao`, each
    one recorded in esquema_versao. No catalog: the structure is what is compared."""
    con = sqlite3.connect(caminho)
    con.executescript(banco.ESQUEMA.read_text(encoding="utf-8"))
    with con:
        con.execute("INSERT INTO esquema_versao VALUES (?,?,?,NULL)",
                    (banco.VERSAO_BASE, banco.DESCRICAO_BASE, "2026-09-29T00:00:00-03:00"))
    for v in range(banco.VERSAO_BASE + 1, versao + 1):
        con.execute("BEGIN")
        for sql in banco.MIGRACOES[v][1]:
            con.execute(sql)
        con.execute("INSERT INTO esquema_versao VALUES (?,?,?,NULL)", (v, banco.MIGRACOES[v][0],
                                                                       "2026-09-29T00:00:00-03:00"))
        con.commit()
    con.close()


@pytest.mark.parametrize("de", range(2, 9))
def test_SINTETICO_banco_migrado_de_qualquer_versao_tem_a_estrutura_do_criado(tmp_path, de):
    assert banco.VERSAO_ESQUEMA == 9 and de < banco.VERSAO_ESQUEMA
    criado = banco.abrir(_cfg(tmp_path / "criado"))
    esperado = _estrutura(criado)
    assert banco.impressao_esquema(criado) == banco.IMPRESSAO_ESQUEMA[banco.VERSAO_ESQUEMA]
    criado.close()

    cfg = _cfg(tmp_path / "migrado")
    cfg.banco.parent.mkdir(parents=True)
    _banco_na_versao(cfg.banco, de)
    migrado = banco.abrir(cfg)                                    # backup first, then each migration
    assert banco.versao_esquema(migrado) == banco.VERSAO_ESQUEMA
    assert _estrutura(migrado) == esperado
    assert banco.impressao_esquema(migrado) == banco.IMPRESSAO_ESQUEMA[banco.VERSAO_ESQUEMA]
    (backup,) = migrado.execute("SELECT backup_antes FROM esquema_versao WHERE versao=?",
                                (banco.VERSAO_ESQUEMA,)).fetchone()
    migrado.close()
    assert f"antes-migracao-v{de}-v{banco.VERSAO_ESQUEMA}" in backup
    copia = sqlite3.connect(next(cfg.backups.glob(f"*antes-migracao-v{de}-v{banco.VERSAO_ESQUEMA}*.sqlite")))
    try:                                                          # the backup restores the version it came from
        assert copia.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert banco.versao_esquema(copia) == de
    finally:
        copia.close()
