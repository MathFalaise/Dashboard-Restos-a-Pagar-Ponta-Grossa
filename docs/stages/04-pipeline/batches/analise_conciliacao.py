"""RREO x API reconciliation matrix with the experimental rules SIDE BY SIDE (read-only).

For each transcribed RREO PDF: RREO-COL v1/v2 x (no consolidation, CONS-PAR v1, CONS-PAR v2).
* consolidated: the 'publicado' and 'analitico' views written by the derivation;
* entity 1: the 'entidade' view and, for CONS-PAR, the same removal of inscription the derivation does in the
  consolidated view, applied to the side that belongs to entity 1 (A = 24xxxxx copy). CONS-PAR v1 removes B
  (entity 15), so it does not touch entity 1's RREO.
Nothing is written to the database. Usage: python analise_conciliacao.py [exercicio ...]
"""
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "app"))
from rp.config import carregar  # noqa: E402
from rp.derivar import _fechar, _lado_excluido  # noqa: E402

COLS = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "L"]


def br(c):
    return f"{c / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main(anos):
    con = sqlite3.connect(f"file:{carregar().banco}?mode=ro", uri=True)
    nid = con.execute("SELECT MAX(id) FROM normalizacao_execucao").fetchone()[0]
    did = con.execute("SELECT MAX(id) FROM derivacao_execucao WHERE vigencia_em IS NULL").fetchone()[0]
    rg = {(c, v): i for i, c, v in con.execute("SELECT id, codigo, versao FROM regra")}
    docs = con.execute("SELECT DISTINCT v.coleta_id, v.escopo, v.exercicio, v.data_final, v.emitido_em FROM rreo_valor v "
                       "WHERE v.normalizacao_id=? AND v.linha='TOTAL (III)' ORDER BY 3,4,2,1", (nid,)).fetchall()
    # pairs per cut-off, with the band of each side
    pares = defaultdict(list)
    for r in con.execute(
            "SELECT p.exercicio, p.data_final, p.mesma_inscricao, p.relacao_inscricao, p.lado_com_execucao, "
            "ra.proc_c, ra.aproc_c, da.faixa_processado, da.faixa_nao_processado, rb.proc_c, rb.aproc_c, db.faixa_processado, db.faixa_nao_processado "
            "FROM espelhamento_par p "
            "JOIN rp_registro ra ON ra.normalizacao_id=? AND ra.resposta_id=p.resposta_a_id AND ra.indice=p.indice_a "
            "JOIN rp_derivado da ON da.derivacao_id=p.derivacao_id AND da.resposta_id=p.resposta_a_id AND da.indice=p.indice_a "
            "JOIN rp_registro rb ON rb.normalizacao_id=? AND rb.resposta_id=p.resposta_b_id AND rb.indice=p.indice_b "
            "JOIN rp_derivado db ON db.derivacao_id=p.derivacao_id AND db.resposta_id=p.resposta_b_id AND db.indice=p.indice_b "
            "WHERE p.derivacao_id=? AND p.data_inicial = p.exercicio || '-01-01'", (nid, nid, did)):
        ex, df, mesma, rel, lado, pa, aa, fpa, fna, pb, ab, fpb, fnb = r
        pares[(ex, df)].append({"mesma": mesma, "relacao": rel, "lado": lado,
                                "a": {"proc_c": pa, "aproc_c": aa, "faixa_processado": fpa, "faixa_nao_processado": fna},
                                "b": {"proc_c": pb, "aproc_c": ab, "faixa_processado": fpb, "faixa_nao_processado": fnb}})
    saida = ["| RREO | Emitido | RREO-COL | CONS-PAR | Colunas iguais | Diferenças (API − RREO) |", "|---|---|---|---|--:|---|"]
    vistos = set()
    for rc, escopo, ex, df, emit in docs:
        if anos and ex not in anos:
            continue
        if (escopo, ex, df) in vistos:   # same PDF collected twice (identical content): a single row
            continue
        vistos.add((escopo, ex, df))
        rv = dict(con.execute("SELECT coluna, valor_c FROM rreo_valor WHERE normalizacao_id=? AND coleta_id=? AND linha='TOTAL (III)'",
                              (nid, rc)))
        for vagg in (1, 2):
            for cons in (None, 1, 2):
                if escopo == "consolidado":
                    if cons is None:
                        q = ("visao='publicado'", ())
                    else:
                        q = ("visao='analitico' AND regra_consolidacao_id=?", (rg[("CONS-PAR", cons)],))
                    api = dict(con.execute(f"SELECT componente, valor_c FROM visao_valor WHERE derivacao_id=? AND {q[0]} AND "
                                           "regra_agregacao_id=? AND exercicio=? AND data_final=?",
                                           (did, *q[1], rg[("RREO-COL", vagg)], ex, df)))
                else:
                    api = dict(con.execute("SELECT componente, valor_c FROM visao_valor WHERE derivacao_id=? AND visao='entidade' "
                                           "AND entidade=1 AND regra_agregacao_id=? AND exercicio=? AND data_final=?",
                                           (did, rg[("RREO-COL", vagg)], ex, df)))
                    if api and cons:
                        for p in pares.get((ex, df), []):
                            if _lado_excluido(cons, p) == "a":     # only side A belongs to entity 1
                                x = p["a"]
                                if x["proc_c"] > 0:
                                    api[x["faixa_processado"]] -= x["proc_c"]
                                if x["aproc_c"] > 0:
                                    api[x["faixa_nao_processado"]] -= x["aproc_c"]
                        api = _fechar(api)
                if not api:
                    saida.append(f"| {ex} {df[5:]} {escopo} | {emit} | v{vagg} | {cons or '—'} | — | sem corte completo da API |")
                    continue
                difs = [(c, api[c] - rv[c]) for c in COLS if api[c] != rv[c]]
                saida.append(f"| {ex} {df[5:]} {escopo} | {emit} | v{vagg} | {'v' + str(cons) if cons else '—'} | "
                             f"{12 - len(difs)}/12 | {'; '.join(f'({c}) {br(d)}' for c, d in difs) or '**todas iguais**'} |")
    print("\n".join(saida))


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="backslashreplace")   # cp1252 output (file) does not crash the script
    main({int(a) for a in sys.argv[1:]})
