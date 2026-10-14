"""Proof that rp-normalizador/3 (layout rules for the refused RREO PDFs) only ADDS rows (corrective audit of
13/10/2026, item 6.5). READ-ONLY.

Compares two normalizations of the same snapshots (old N1 with rp-normalizador/2, new N2 with /3) and their current
derivations (D1, D2):
  * normalization: rp_registro, movimentacao_lancamento, entidade_ref, exercicio_ref and valor_recusado identical (by
    stable identifiers); rreo_valor of N1 is a subset of N2's, and every added row belongs to a PDF that N1 refused;
    rreo_extracao identical except for those PDFs (and the extraction timestamp);
  * derivation: derivar.resultado_estavel identical once the rows tied to those PDFs are left out (their reconciliation
    rows, now present, and their 'RREO sem valores extraídos' checks, now gone).

Usage (from app/):  python ../docs/audits/rreo/prova_acrescimo_layouts.py --banco DB --n1 17 --d1 35 --n2 18 --d2 37
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "app"))
from rp import derivar  # noqa: E402


def estaveis(con, nid, tabela, colunas):
    uid = dict(con.execute("SELECT id, snapshot_uid FROM coleta"))
    resp = {i: (uid[c], o) for i, c, o in con.execute("SELECT id, coleta_id, ordem FROM resposta_bruta")}
    linhas = con.execute(f"SELECT {', '.join(colunas)} FROM {tabela} WHERE normalizacao_id=?", (nid,)).fetchall()
    saida = []
    for r in linhas:
        d = dict(zip(colunas, r))
        if "resposta_id" in d:
            d["resposta_id"] = resp[d["resposta_id"]]
        if "coleta_id" in d:
            d["coleta_id"] = uid[d["coleta_id"]]
        saida.append(tuple(d.values()))
    return sorted(saida, key=repr)


def colunas(con, tabela):
    return [r[1] for r in con.execute(f"PRAGMA table_info({tabela})") if r[1] != "normalizacao_id"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--banco", required=True)
    for k in ("n1", "d1", "n2", "d2"):
        ap.add_argument(f"--{k}", type=int, required=True)
    a = ap.parse_args()
    con = sqlite3.connect(f"file:{a.banco}?mode=ro", uri=True)
    uid = dict(con.execute("SELECT id, snapshot_uid FROM coleta"))
    recusados_n1 = {uid[c] for (c,) in con.execute("SELECT coleta_id FROM rreo_extracao WHERE normalizacao_id=? AND "
                                                   "valores=0", (a.n1,))}
    transcritos_n2 = {uid[c] for (c,) in con.execute("SELECT DISTINCT coleta_id FROM rreo_valor WHERE "
                                                     "normalizacao_id=?", (a.n2,))}
    novos = recusados_n1 & transcritos_n2
    r = {"pdfs_recusados_em_n1": len(recusados_n1), "pdfs_novos_em_n2": sorted(x[:8] for x in novos)}
    for t in ("rp_registro", "movimentacao_lancamento", "entidade_ref", "exercicio_ref", "valor_recusado"):
        cols = colunas(con, t)
        r[t] = estaveis(con, a.n1, t, cols) == estaveis(con, a.n2, t, cols)
    cols = colunas(con, "rreo_valor")
    v1, v2 = set(estaveis(con, a.n1, "rreo_valor", cols)), set(estaveis(con, a.n2, "rreo_valor", cols))
    i_col = cols.index("coleta_id")
    r["rreo_valor"] = {"n1_contido_em_n2": v1 <= v2, "linhas_acrescidas": len(v2 - v1),
                       "acrescimos_so_de_pdfs_recusados_em_n1": all(x[i_col] in novos for x in v2 - v1)}
    cols = [c for c in colunas(con, "rreo_extracao") if c not in ("extraida_em",)]
    i_col, i_erro = cols.index("coleta_id"), cols.index("erro")
    e1 = {x[i_col]: x for x in estaveis(con, a.n1, "rreo_extracao", cols) if x[i_col] not in novos}
    e2 = {x[i_col]: x for x in estaveis(con, a.n2, "rreo_extracao", cols) if x[i_col] not in novos}
    # a PDF refused by both: the only accepted change is the reason, which now also carries the layout rules' reason
    mudou_so_o_motivo = [k for k in e1 if e1[k] != e2.get(k) and e1[k][i_erro] and e2.get(k)
                         and e2[k][i_erro].startswith(e1[k][i_erro] + "; regras de layout versionadas: ")
                         and e1[k][:i_erro] + e1[k][i_erro + 1:] == e2[k][:i_erro] + e2[k][i_erro + 1:]]
    r["rreo_extracao_motivo_ampliado"] = sorted(k[:8] for k in mudou_so_o_motivo)
    r["rreo_extracao_fora_dos_novos_igual"] = (e1.keys() == e2.keys()
                                               and all(e1[k] == e2[k] for k in e1 if k not in mudou_so_o_motivo))

    def sem_novos(res):
        res = dict(res)
        res["conciliacao_rreo"] = [x for x in res["conciliacao_rreo"] if x[0] not in novos]
        res["verificacao"] = [x for x in res["verificacao"]
                              if json.loads(x[2]).get("rreo_snapshot") not in novos]
        return res
    s1, s2 = sem_novos(derivar.resultado_estavel(con, a.d1)), sem_novos(derivar.resultado_estavel(con, a.d2))
    r["derivacao_fora_dos_novos"] = {t: s1[t] == s2[t] for t in s1}
    full1, full2 = derivar.resultado_estavel(con, a.d1), derivar.resultado_estavel(con, a.d2)
    r["conciliacao_acrescida"] = len(full2["conciliacao_rreo"]) - len(full1["conciliacao_rreo"])
    r["verificacoes_removidas"] = sorted(json.loads(x[2]).get("rreo_snapshot", "")[:8] for x in full1["verificacao"]
                                         if x not in full2["verificacao"])
    r["prova"] = (all(r[t] for t in ("rp_registro", "movimentacao_lancamento", "entidade_ref", "exercicio_ref",
                                     "valor_recusado")) and all(r["rreo_valor"].values())
                  and r["rreo_extracao_fora_dos_novos_igual"] and all(r["derivacao_fora_dos_novos"].values()))
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r["prova"] else 1


if __name__ == "__main__":
    sys.exit(main())
