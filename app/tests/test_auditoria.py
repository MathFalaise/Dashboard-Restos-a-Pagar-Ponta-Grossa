"""Regression of the technical audit findings (docs/audits/TECHNICAL_AUDIT.md).

Each test cites the finding's ID. The API cases follow phase 15 of the audit (simulated transport: no real request).
SINTETICO = temporary database with invented records.
"""
import json
import sqlite3

import pytest

from rp import banco


# ------------------------------------------------------------------ G1: atomic migrations and creation
def _tabelas(caminho):
    c = sqlite3.connect(caminho)
    try:
        return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        c.close()


def test_MIG01_migracao_que_falha_no_meio_nao_deixa_esquema_pela_metade(ambiente, monkeypatch):
    cfg = ambiente["cfg"]
    ambiente["con"].close()
    v = banco.VERSAO_ESQUEMA
    ruim = {**banco.MIGRACOES, v + 1: ("teste", ["CREATE TABLE nova_a (x)", "CREATE TABLE nova_b (y)",
                                                 "ALTER TABLE tabela_que_nao_existe ADD COLUMN z"])}
    monkeypatch.setattr(banco, "MIGRACOES", ruim)
    monkeypatch.setattr(banco, "VERSAO_ESQUEMA", v + 1)
    with pytest.raises(sqlite3.OperationalError):
        banco.abrir(cfg)
    assert not {"nova_a", "nova_b"} & _tabelas(cfg.banco)                    # nothing of the migration was left
    c = sqlite3.connect(cfg.banco)
    assert c.execute("SELECT MAX(versao) FROM esquema_versao").fetchone()[0] == v
    c.close()
    assert any(f"antes-migracao-v{v}-v{v + 1}" in p.name for p in cfg.backups.iterdir())  # backup first, as always
    boa = {**banco.MIGRACOES, v + 1: ("teste", ["CREATE TABLE nova_a (x)", "CREATE TABLE nova_b (y)"])}
    monkeypatch.setattr(banco, "MIGRACOES", boa)
    con = banco.abrir(cfg)                                                   # the retry works
    assert banco.versao_esquema(con) == v + 1 and {"nova_a", "nova_b"} <= _tabelas(cfg.banco)
    con.close()


def test_MIG02_criacao_interrompida_nao_deixa_arquivo_no_destino(ambiente, tmp_path, monkeypatch):
    destino = tmp_path / "novo" / "banco.sqlite"

    def falha(con):
        raise RuntimeError("falha simulada na semeadura")
    monkeypatch.setattr(banco, "_semear_catalogo", falha)
    with pytest.raises(RuntimeError):
        banco.abrir(ambiente["cfg"], destino)
    assert not destino.exists()
    assert list(destino.parent.iterdir()) == []                             # not even the temporary file is left


def test_MIG02_arquivo_sem_versao_de_esquema_e_recusado_sem_alteracao(ambiente, tmp_path):
    vazio = tmp_path / "vazio.sqlite"
    sqlite3.connect(vazio).close()
    antes = vazio.read_bytes()
    with pytest.raises(banco.MigracaoPendente, match="não tem versão de esquema"):
        banco.abrir(ambiente["cfg"], vazio)
    assert vazio.read_bytes() == antes
