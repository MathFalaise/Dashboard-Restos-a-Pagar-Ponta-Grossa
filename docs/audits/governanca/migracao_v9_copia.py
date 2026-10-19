"""Proof of the schema v8 -> v9 migration on a COPY of the active database (external review of 19/10/2026).

The active database is only read (URI mode=ro). Everything else happens in --pasta, which must be a local folder
outside any synced or network folder (the copy holds creditor records):
  1. consistent copy of the active database (SQLite backup API);
  2. content of every table (SHA-256 per table, rows in rowid order), schema fingerprint and the recomputed
     hash_resultado of every derivation, BEFORE;
  3. banco.abrir on the copy: backup first, then the migration;
  4. AFTER: schema v9 with its fingerprint, every table identical except esquema_versao (+1 row), only the
     trigger regra_sem_delete added, every hash_resultado unchanged;
  5. the backup is restored (file copy) and must be the v8 copy: integrity, version, fingerprint, same content;
  6. DELETE FROM regra with PRAGMA foreign_keys = OFF: accepted on the restored v8, refused on the v9 (each one inside
     a transaction that is rolled back).
The JSON output has only table names, counts and hashes: no record content.

Usage (from app/):
    python ../docs/audits/governanca/migracao_v9_copia.py --banco ~/RestosAPagar_local/banco/restos_a_pagar.sqlite \
        --pasta ~/RestosAPagar_local/verificacao_v9_20261019 --saida-json ../docs/audits/governanca/ESQUEMA_V9_20261019.json
"""
import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "app"))


def _ro(caminho):
    con = sqlite3.connect(f"{Path(caminho).resolve().as_uri()}?mode=ro", uri=True)
    con.execute("PRAGMA query_only = ON")
    return con


def _sha_arquivo(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def conteudo(con):
    """{table: [rows, SHA-256 of the rows in rowid order]} for every table (no WITHOUT ROWID table in the schema)."""
    saida = {}
    for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
        h, n = hashlib.sha256(), 0
        for linha in con.execute(f"SELECT * FROM {t} ORDER BY rowid"):
            h.update(repr(linha).encode())
            n += 1
        saida[t] = [n, h.hexdigest()]
    return saida


def gatilhos(con):
    return sorted(n for (n,) in con.execute("SELECT name FROM sqlite_master WHERE type='trigger'"))


def hashes_das_derivacoes(con):
    from rp import derivar
    return {str(d): {"gravado": h, "recalculado": derivar.hash_resultado(con, d)}
            for d, h in con.execute("SELECT id, hash_resultado FROM derivacao_execucao ORDER BY id").fetchall()}


def apagar_regra_sem_fk(caminho):
    """Tries DELETE FROM regra with foreign_keys OFF inside a transaction that is always rolled back."""
    con = sqlite3.connect(caminho)
    try:
        con.execute("PRAGMA foreign_keys = OFF")
        con.execute("BEGIN")
        try:
            n = con.execute("DELETE FROM regra").rowcount
            return {"aceito": True, "linhas": n}
        except sqlite3.DatabaseError as e:
            return {"aceito": False, "erro": str(e)}
        finally:
            con.rollback()
    finally:
        con.close()


def main(argv=None):
    from rp import banco
    from rp.config import carregar
    ap = argparse.ArgumentParser()
    ap.add_argument("--banco", required=True)
    ap.add_argument("--pasta", required=True)
    ap.add_argument("--saida-json", required=True)
    a = ap.parse_args(argv)
    pasta = Path(a.pasta).expanduser()
    if banco.em_pasta_sincronizada(pasta):
        raise SystemExit(f"{pasta} is in a synced or network folder: the copy holds creditor records")
    pasta.mkdir(parents=True, exist_ok=False)             # a new folder each run: nothing is overwritten
    copia, restaurado = pasta / "copia.sqlite", pasta / "restaurado.sqlite"

    ativo = _ro(Path(a.banco).expanduser())
    destino = sqlite3.connect(copia)
    with destino:
        ativo.backup(destino)
    destino.close()
    ativo.close()

    con = _ro(copia)
    antes = {"versao": banco.versao_esquema(con), "impressao": banco.impressao_esquema(con),
             "conteudo": conteudo(con), "gatilhos": gatilhos(con), "derivacoes": hashes_das_derivacoes(con)}
    con.close()
    sha_copia_antes = _sha_arquivo(copia)

    cfg = carregar(dados_locais=pasta / "l", snapshots=pasta / "armazem_nao_usado", backups=pasta / "b")
    con = banco.abrir(cfg, copia)                          # backup first, then v8 -> v9
    con.close()
    con = _ro(copia)
    depois = {"versao": banco.versao_esquema(con), "impressao": banco.impressao_esquema(con),
              "conteudo": conteudo(con), "gatilhos": gatilhos(con), "derivacoes": hashes_das_derivacoes(con)}
    backup_antes = con.execute("SELECT backup_antes FROM esquema_versao WHERE versao=?",
                               (banco.VERSAO_ESQUEMA,)).fetchone()[0]
    con.close()

    (arquivo_backup,) = list((pasta / "b").glob("*.sqlite"))
    shutil.copyfile(arquivo_backup, restaurado)
    con = _ro(restaurado)
    rest = {"integridade": con.execute("PRAGMA integrity_check").fetchone()[0], "versao": banco.versao_esquema(con),
            "impressao": banco.impressao_esquema(con), "conteudo": conteudo(con)}
    con.close()

    mudaram = sorted(t for t in antes["conteudo"] if antes["conteudo"][t] != depois["conteudo"].get(t))
    r = {
        "data": "2026-10-19",
        "banco_ativo": "aberto so para leitura (mode=ro); nao foi migrado",
        "copia": {"sha256_antes_da_migracao": sha_copia_antes},
        "antes": {"versao": antes["versao"], "impressao": antes["impressao"],
                  "impressao_confere_v8": antes["impressao"] == banco.IMPRESSAO_ESQUEMA[8]},
        "depois": {"versao": depois["versao"], "impressao": depois["impressao"],
                   "impressao_confere_v9": depois["impressao"] == banco.IMPRESSAO_ESQUEMA[9],
                   "backup_registrado_em_esquema_versao": Path(backup_antes).name if backup_antes else None},
        "tabelas_com_conteudo_diferente": mudaram,
        "esquema_versao": {"antes": antes["conteudo"]["esquema_versao"][0],
                           "depois": depois["conteudo"]["esquema_versao"][0]},
        "gatilhos_novos": sorted(set(depois["gatilhos"]) - set(antes["gatilhos"])),
        "gatilhos_removidos": sorted(set(antes["gatilhos"]) - set(depois["gatilhos"])),
        "derivacoes": {d: {"gravado": v["gravado"], "antes_confere": v["gravado"] == v["recalculado"],
                           "depois_confere": depois["derivacoes"][d]["recalculado"] == v["gravado"]}
                       for d, v in antes["derivacoes"].items()},
        "backup": {"arquivo": arquivo_backup.name, "sha256": _sha_arquivo(arquivo_backup),
                   "restaurado_sha256_igual": _sha_arquivo(restaurado) == _sha_arquivo(arquivo_backup),
                   "integridade": rest["integridade"], "versao": rest["versao"],
                   "impressao_confere_v8": rest["impressao"] == banco.IMPRESSAO_ESQUEMA[8],
                   "conteudo_igual_ao_da_copia_antes": rest["conteudo"] == antes["conteudo"]},
        "apagar_regra_sem_foreign_keys": {"v8_restaurado": apagar_regra_sem_fk(restaurado),
                                          "v9_migrado": apagar_regra_sem_fk(copia)},
        "linhas_por_tabela": {t: v[0] for t, v in depois["conteudo"].items()},
    }
    r["conclusao_ok"] = bool(
        r["antes"]["impressao_confere_v8"] and r["depois"]["versao"] == 9 and r["depois"]["impressao_confere_v9"]
        and mudaram == ["esquema_versao"] and r["esquema_versao"]["depois"] == r["esquema_versao"]["antes"] + 1
        and r["gatilhos_novos"] == ["regra_sem_delete"] and not r["gatilhos_removidos"]
        and all(v["antes_confere"] and v["depois_confere"] for v in r["derivacoes"].values())
        and r["backup"]["restaurado_sha256_igual"] and r["backup"]["integridade"] == "ok"
        and r["backup"]["versao"] == 8 and r["backup"]["impressao_confere_v8"]
        and r["backup"]["conteudo_igual_ao_da_copia_antes"]
        and r["apagar_regra_sem_foreign_keys"]["v8_restaurado"]["aceito"]
        and not r["apagar_regra_sem_foreign_keys"]["v9_migrado"]["aceito"])
    Path(a.saida_json).write_text(json.dumps(r, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: r[k] for k in ("antes", "depois", "tabelas_com_conteudo_diferente", "gatilhos_novos",
                                        "backup", "apagar_regra_sem_foreign_keys", "conclusao_ok")},
                     ensure_ascii=False, indent=2))
    return 0 if r["conclusao_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
