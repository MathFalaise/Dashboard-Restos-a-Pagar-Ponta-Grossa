"""Retention of processing runs in the ACTIVE database (corrective audit of 13/10/2026, item 10).

Every normalization copies hundreds of thousands of records and every derivation as many derived rows; keeping all of
them makes the active database grow without adding evidence, because each run is reproducible from the immutable
store (`python -m rp homologar` proves it) and is kept byte for byte in the structural backup taken here.

Policy (reproducible, no judgement call):
  * KEEP the most recent normalization and, on it, the most recent derivation of each validity (current and each
    'as it was on' date) - what the panel and the gates use;
  * KEEP any run listed in <dados_locais>/PRESERVAR_EXECUCOES.txt ("normalizacao N" / "derivacao N", one per line);
  * every other run is removed, ONLY after a structural backup that is checked (integrity_check, row count of every
    table, SHA-256 recorded) - never the raw layer, the rules, the parameters, the governance or the evidence.
Flow (`python -m rp manutencao`): preview by default; with --confirmar: backup -> check the backup -> delete inside ONE
transaction, refused (rolled back) if foreign_key_check finds anything -> integrity_check, raw layer hash, store
check and the kept derivations' hash_resultado recalculated -> VACUUM. A failed check after the commit stops before
VACUUM and names the backup to restore.
"""
import hashlib
import sqlite3
from pathlib import Path

from . import banco, execucoes

PRESERVAR = "PRESERVAR_EXECUCOES.txt"


class ManutencaoRecusada(Exception):
    pass


def _preservadas(cfg):
    arq = Path(cfg.dados_locais) / PRESERVAR
    saida = {"normalizacao": set(), "derivacao": set()}
    if arq.exists():
        for linha in arq.read_text(encoding="utf-8").splitlines():
            partes = linha.split("#")[0].split()
            if len(partes) == 2 and partes[0] in saida and partes[1].isdigit():
                saida[partes[0]].add(int(partes[1]))
    return saida


def plano(con, cfg):
    """Runs kept and removed, with their row counts. Reads only."""
    pres = _preservadas(cfg)
    ultima = con.execute("SELECT MAX(id) FROM normalizacao_execucao").fetchone()[0]
    manter_d = {d for (d,) in con.execute("SELECT MAX(id) FROM derivacao_execucao WHERE normalizacao_id=? GROUP BY "
                                          "IFNULL(vigencia_em, '')", (ultima,))} | pres["derivacao"]
    todas_d = [d for (d,) in con.execute("SELECT id FROM derivacao_execucao ORDER BY id")]
    manter_n = ({ultima} | pres["normalizacao"]
                | {n for (n,) in con.execute(f"SELECT normalizacao_id FROM derivacao_execucao WHERE id IN "
                                            f"({','.join('?' * len(manter_d)) or 'NULL'})", tuple(manter_d))})
    todas_n = [n for (n,) in con.execute("SELECT id FROM normalizacao_execucao ORDER BY id")]
    apagar_d = [d for d in todas_d if d not in manter_d]
    apagar_n = [n for n in todas_n if n not in manter_n]
    linhas = lambda tabelas, col, i: sum(con.execute(f"SELECT COUNT(*) FROM {t} WHERE {col}=?", (i,)).fetchone()[0]
                                         for t in tabelas)
    return {"manter": {"normalizacoes": sorted(manter_n), "derivacoes": sorted(manter_d)},
            "apagar": {"derivacoes": [{"id": d, "linhas": linhas(execucoes.TABELAS_DERIVACAO, "derivacao_id", d)}
                                      for d in apagar_d],
                       "normalizacoes": [{"id": n, "linhas": linhas(execucoes.TABELAS_NORMALIZACAO, "normalizacao_id", n)}
                                         for n in apagar_n]},
            "preservadas_pela_lista": {k: sorted(v) for k, v in pres.items()}}


def _contagens(con):
    return {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for (t,) in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")}


def _sha256(arq):
    h = hashlib.sha256()
    with open(arq, "rb") as f:
        while b := f.read(1 << 22):
            h.update(b)
    return h.hexdigest()


def conferir_backup(con, arquivo):
    """The backup opens, passes integrity_check and has exactly the active database's row count in every table."""
    b = sqlite3.connect(f"file:{Path(arquivo).resolve().as_posix()}?mode=ro", uri=True)
    try:
        integro = b.execute("PRAGMA integrity_check").fetchone()[0]
        iguais = _contagens(b) == _contagens(con)
    finally:
        b.close()
    if integro != "ok" or not iguais:
        raise ManutencaoRecusada(f"backup {arquivo} não confere (integrity_check={integro}, contagens iguais={iguais}): "
                                 "nada foi apagado")
    return {"arquivo": str(arquivo), "sha256": _sha256(arquivo), "integrity_check": integro, "contagens_iguais": True}


def executar(con, cfg, armazem, caminho):
    """Applies the plan (see the module docstring). Returns the report; raises ManutencaoRecusada on any failed check."""
    from . import derivar
    p = plano(con, cfg)
    if not p["apagar"]["derivacoes"] and not p["apagar"]["normalizacoes"]:
        return {"plano": p, "executada": False, "motivo": "nada fora da retenção"}
    antes_bytes = Path(caminho).stat().st_size
    camada0 = execucoes.hash_camada0(con)
    mantidas = {d: h for d, h in con.execute("SELECT id, hash_resultado FROM derivacao_execucao")
                if d in p["manter"]["derivacoes"]}
    arq = banco.backup(con, cfg, "antes-manutencao-retencao")
    bk = conferir_backup(con, arq)
    con.commit()
    with con:      # ONE transaction: an exception (a foreign_key_check finding included) rolls everything back
        for d in p["apagar"]["derivacoes"]:
            for t in execucoes.TABELAS_DERIVACAO:
                con.execute(f"DELETE FROM {t} WHERE derivacao_id=?", (d["id"],))
            con.execute("DELETE FROM derivacao_execucao WHERE id=?", (d["id"],))
        for n in p["apagar"]["normalizacoes"]:
            for t in execucoes.TABELAS_NORMALIZACAO:
                con.execute(f"DELETE FROM {t} WHERE normalizacao_id=?", (n["id"],))
            con.execute("DELETE FROM normalizacao_execucao WHERE id=?", (n["id"],))
        fk = con.execute("PRAGMA foreign_key_check").fetchall()
        if fk:
            raise ManutencaoRecusada(f"foreign_key_check com {len(fk)} problema(s): exclusão desfeita")
    problemas = []
    if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        problemas.append("integrity_check")
    if execucoes.hash_camada0(con) != camada0:
        problemas.append("camada bruta mudou")
    if banco.verificar(con, armazem):
        problemas.append("verificar (armazém x banco)")
    for d, h in mantidas.items():
        if derivar.hash_resultado(con, d) != h:
            problemas.append(f"hash_resultado da derivação {d}")
    if problemas:
        raise ManutencaoRecusada(f"verificação depois da exclusão falhou ({problemas}); VACUUM não executado; restaure "
                                 f"o backup {arq}")
    con.execute("VACUUM")
    return {"plano": p, "executada": True, "backup": bk, "bytes_antes": antes_bytes,
            "bytes_depois": Path(caminho).stat().st_size, "camada0_intacta": True,
            "hash_das_derivacoes_mantidas": mantidas, "integrity_check": "ok", "foreign_key_check": []}
