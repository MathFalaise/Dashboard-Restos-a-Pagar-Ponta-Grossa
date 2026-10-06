"""Teste (somente leitura) de uma HIPOTESE de divisao de cancelamento - nao e regra, nao grava nada.
CANC v1 (em uso): registro com aproc>0 -> todo o cancelamento em (j); so processado -> (d).
H-CANC-EXCEDENTE: registro 'ambos' -> (j) recebe ate aproc; o que exceder aproc vai para (d).
Compara (d) e (j) das duas com o RREO por entidade (1) e consolidado."""
import sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "app"))
from rp.config import carregar

sys.stdout.reconfigure(errors="backslashreplace")   # saida em cp1252 (arquivo) nao derruba o script
br = lambda c: f"{c/100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
con = sqlite3.connect(f"file:{carregar().banco}?mode=ro", uri=True)
nid = con.execute("SELECT MAX(id) FROM normalizacao_execucao").fetchone()[0]
did = con.execute("SELECT MAX(id) FROM derivacao_execucao WHERE vigencia_em IS NULL").fetchone()[0]
docs = con.execute("SELECT DISTINCT escopo, exercicio, data_final FROM rreo_valor WHERE normalizacao_id=? AND linha='TOTAL (III)' ORDER BY 2,3,1", (nid,)).fetchall()
print("| RREO | d RREO | j RREO | Δd v1 | Δj v1 | Δd H | Δj H | registros 'ambos' com excedente |\n|---|--:|--:|--:|--:|--:|--:|--:|")
for escopo, ex, df in docs:
    rv = dict(con.execute("SELECT coluna, valor_c FROM rreo_valor WHERE normalizacao_id=? AND escopo=? AND exercicio=? AND data_final=? AND linha='TOTAL (III)' AND coluna IN ('d','j')", (nid, escopo, ex, df)))
    snaps = con.execute("SELECT coletas_json FROM visao_valor WHERE derivacao_id=? AND exercicio=? AND data_final=? AND " +
                        ("visao='entidade' AND entidade=1" if escopo == "entidade" else "visao='publicado'") + " LIMIT 1", (did, ex, df)).fetchone()
    if not snaps:
        print(f"| {ex} {df[5:]} {escopo} | — | — | sem corte da API | | | | |"); continue
    import json
    ids = [i for (i,) in con.execute(f"SELECT id FROM coleta WHERE snapshot_uid IN ({','.join('?'*len(json.loads(snaps[0])))})", json.loads(snaps[0]))]
    d1 = j1 = dh = jh = n = 0
    for proc, aproc, ca in con.execute(f"SELECT proc_c, aproc_c, cancelado_aproc_c FROM rp_registro WHERE normalizacao_id=? AND coleta_id IN ({','.join('?'*len(ids))})", (nid, *ids)):
        if proc > 0 and aproc == 0:
            d1 += ca; dh += ca
        elif aproc > 0:
            j1 += ca
            if proc > 0 and ca > aproc:
                dh += ca - aproc; jh += aproc; n += 1
            else:
                jh += ca
    print(f"| {ex} {df[5:]} {escopo} | {br(rv['d'])} | {br(rv['j'])} | {br(d1-rv['d'])} | {br(j1-rv['j'])} | {br(dh-rv['d'])} | {br(jh-rv['j'])} | {n} |")
