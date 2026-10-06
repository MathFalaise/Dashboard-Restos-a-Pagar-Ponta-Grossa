"""Source check (05/10/2026), step 1: re-collects from the API, into a TEMPORARY store and database, everything the
active database has.

Read-only on the active database. The list of what to collect comes from it: each listing cut-off (entidade, exercicio,
dataFinal, without tipoPesquisa), each movement, the catalogs and the RREO publications of each fiscal year (with the
Annex VII PDFs the active database has, by the same idArquivo). The collection uses the project's own Coletor (same
pause, same page checks, second read).

Usage (inside app/):  python ../docs/audits/source-check/recoletar_tudo.py --config C:/rpaud/prova/config.toml
Progress goes to <dados_locais>/prova_progresso.jsonl; a collection already done (same parameters) is skipped on resume.
"""
import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "app"))

from rp import banco                      # noqa: E402
from rp.armazem import Armazem            # noqa: E402
from rp.coletor import Coletor            # noqa: E402
from rp.config import carregar            # noqa: E402
from rp.http import Cliente               # noqa: E402

ATIVO = Path.home() / "RestosAPagar_local" / "banco" / "restos_a_pagar.sqlite"


def plano():
    con = sqlite3.connect(f"file:{ATIVO.as_posix()}?mode=ro", uri=True)
    try:
        cortes, movs, pubs, ents, pdfs = set(), set(), set(), set(), {}
        for tipo, p in con.execute("SELECT tipo, parametros_json FROM coleta"):
            p = json.loads(p)
            if tipo == "rp_listagem" and "tipoPesquisa" not in p:
                cortes.add((p["entidade"], p["exercicio"], p["dataFinal"]))
            elif tipo == "movimentacao":
                movs.add((p["entidade"], p["anoempenho"], p["empenho"]))
            elif tipo == "publicacoes":
                pubs.add(p["exercicio"])
            elif tipo == "exercicios":
                ents.add(p["entidade"])
            elif tipo == "rreo_pdf":
                pdfs.setdefault(p["exercicio"], set()).add(p["id_arquivo"])
        return sorted(cortes), sorted(movs), sorted(pubs), sorted(ents), pdfs
    finally:
        con.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    cfg = carregar(a.config)
    assert "OneDrive" not in str(cfg.banco) and cfg.banco.resolve() != ATIVO.resolve()
    con, armazem = banco.abrir(cfg), Armazem(cfg.snapshots)
    coletor = Coletor(cfg, con, armazem, Cliente(cfg))
    progresso = cfg.dados_locais / "prova_progresso.jsonl"
    feitos = set()
    if progresso.exists():
        feitos = {json.loads(l)["passo"] for l in progresso.read_text(encoding="utf-8").splitlines() if l.strip()}
    cortes, movs, pubs, ents, pdfs = plano()
    passos = ([("catalogos", tuple(ents))]
              + [("listagem", c) for c in cortes]
              + [("movimentacao", m) for m in movs]
              + [("rreo", (x, sorted(pdfs.get(x, ())))) for x in pubs])
    print(json.dumps({"cortes": len(cortes), "movimentacoes": len(movs), "exercicios_rreo": len(pubs),
                      "entidades_catalogo": ents}), flush=True)
    with progresso.open("a", encoding="utf-8") as log:
        for tipo, args in passos:
            passo = f"{tipo}:{json.dumps(args)}"
            if passo in feitos:
                continue
            t0, antes = time.time(), coletor.cliente.requisicoes
            if tipo == "catalogos":
                r = coletor.catalogos(list(args))
            elif tipo == "listagem":
                r = [coletor.listagem(*args)]
            elif tipo == "movimentacao":
                r = [coletor.movimentacao(*args)]
            else:
                # only the PDFs the active database has (the same idArquivo): nothing else is downloaded from the portal
                r = coletor.rreo(args[0], ids=set(args[1]) or {-1})
            linha = {"passo": passo, "segundos": round(time.time() - t0, 1),
                     "requisicoes": coletor.cliente.requisicoes - antes,
                     "snapshots": [{k: s.get(k) for k in ("snapshot_uid", "tipo", "status", "observacao")} for s in r]}
            log.write(json.dumps(linha, ensure_ascii=False) + "\n")
            log.flush()
            ruins = [s for s in r if s.get("status") != "completa"]
            print(passo, "ok" if not ruins else f"ATENCAO {[(s.get('status'), s.get('observacao')) for s in ruins]}",
                  flush=True)
    print(json.dumps({"fim": True, "requisicoes": coletor.cliente.requisicoes}), flush=True)


if __name__ == "__main__":
    main()
