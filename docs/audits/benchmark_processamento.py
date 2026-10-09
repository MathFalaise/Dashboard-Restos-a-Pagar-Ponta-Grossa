"""Reproducible benchmark of processing and panel queries for one version of the code (correction request of
09/10/2026, item 10). It never touches the active database: it copies it (SQLite backup API, read-only on the source).

Usage:  python docs/audits/benchmark_processamento.py --codigo APP_DIR --pasta WORK_DIR --saida OUT.json
            [--banco ACTIVE_DB] [--sem-gatilhos-camada1] [--repeticoes N]
  APP_DIR: folder that contains the `rp` package of the version to measure (e.g. an export of `git archive`);
  WORK_DIR: empty folder for the copy (created).
Measures, on the same machine and data: opening (migration + rows from the store, when the code is newer than the
copy), normalization, current derivation, "as it was on" derivation, panel calls (median of N), file size after
VACUUM. --sem-gatilhos-camada1 drops the v8 layer-1 triggers from the copy before normalizing, to isolate their cost.
"""
import argparse
import json
import os
import sqlite3
import statistics
import sys
import time
from pathlib import Path

EM = "2026-09-29T23:59:59-03:00"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--codigo", required=True)
    ap.add_argument("--pasta", required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--banco")
    ap.add_argument("--sem-gatilhos-camada1", action="store_true")
    ap.add_argument("--repeticoes", type=int, default=3)
    a = ap.parse_args()
    sys.path.insert(0, str(Path(a.codigo).resolve()))
    from rp import banco, derivar, normalizar
    from rp.config import carregar
    from rp.painel import Painel

    ativo = carregar()
    pasta = Path(a.pasta).resolve()
    cfg = carregar(dados_locais=pasta, snapshots=ativo.snapshots, backups=pasta / "backups")
    assert not cfg.banco.exists() and cfg.banco != ativo.banco
    cfg.banco.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(f"file:{Path(a.banco or ativo.banco)}?mode=ro", uri=True)
    dst = sqlite3.connect(cfg.banco)
    src.backup(dst)
    dst.close()
    src.close()
    out = {"codigo": str(Path(a.codigo).resolve()), "sem_gatilhos_camada1": a.sem_gatilhos_camada1, "tempos_s": {}}

    t = time.perf_counter()
    con = banco.abrir(cfg)
    out["tempos_s"]["abrir_e_migrar"] = round(time.perf_counter() - t, 2)
    out["esquema"] = banco.versao_esquema(con)
    if a.sem_gatilhos_camada1:
        for (nome,) in con.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'ri_%_coleta_%'"
                                   ).fetchall():
            con.execute(f"DROP TRIGGER {nome}")
        con.commit()
    t = time.perf_counter()
    nid, _ = normalizar.normalizar(con)
    out["tempos_s"]["normalizar"] = round(time.perf_counter() - t, 2)
    t = time.perf_counter()
    did = derivar.derivar(con, nid)
    out["tempos_s"]["derivar_atual"] = round(time.perf_counter() - t, 2)
    t = time.perf_counter()
    derivar.derivar(con, nid, EM)
    out["tempos_s"]["derivar_como_estava_em"] = round(time.perf_counter() - t, 2)
    out["hash_atual"] = con.execute("SELECT hash_resultado FROM derivacao_execucao WHERE id=?", (did,)).fetchone()[0]
    con.commit()
    con.execute("VACUUM")
    con.close()
    out["tamanho_mb_apos_vacuum"] = round(os.path.getsize(cfg.banco) / 2 ** 20, 1)

    consultas = {}
    with Painel.abrir(cfg.banco) as p:
        cortes = p.cortes()["cortes"]
        ult = [c for c in cortes if c["municipio_disponivel"]][-1]
        ex, df = ult["exercicio"], ult["data_final"]
        chamadas = [("cortes", lambda: p.cortes()), ("indicadores Municipio", lambda: p.indicadores(ex, df)),
                    ("indicadores Municipio como estava em", lambda: p.indicadores(ex, df, None, EM)),
                    ("evolucao Municipio", lambda: p.evolucao(ex)),
                    ("serie entre exercicios", lambda: p.serie_entre_exercicios()),
                    ("composicao Municipio", lambda: p.composicao(ex, df)), ("qualidade", lambda: p.qualidade()),
                    ("reconciliacao", lambda: p.reconciliacao()), ("entidades do corte", lambda: p.entidades_do_corte(ex, df))]
        if hasattr(p, "visao_geral"):
            chamadas.append(("visao geral (pagina inicial)", lambda: p.visao_geral(ex, df)))
        for nome, f in chamadas:
            f()                                        # warm-up
            ts = []
            for _ in range(a.repeticoes):
                t = time.perf_counter()
                f()
                ts.append(time.perf_counter() - t)
            consultas[nome] = round(statistics.median(ts), 3)
    out["consultas_painel_mediana_s"] = consultas
    Path(a.saida).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
