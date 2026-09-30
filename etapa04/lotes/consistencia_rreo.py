"""Coerencia ENTRE publicacoes oficiais (somente leitura): o saldo L do RREO do 6o bim de A deveria ser igual
a (a)+(f) - RP de exercicios anteriores - do RREO de A+1 (qualquer bimestre: sao colunas de inscricao).
Ao lado, a API: soma de S1 no fechamento de A (RREO-COL v2, L) e (a)+(f) de A+1.
2018 e 2019 (consolidado) vem da leitura de investigacao `rreo_layout_antigo.py` (identidades conferidas)."""
import sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app"))
from rp.config import carregar

sys.stdout.reconfigure(errors="backslashreplace")   # saida em cp1252 (arquivo) nao derruba o script
br = lambda c: f"{c/100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if c is not None else "—"
con = sqlite3.connect(f"file:{carregar().banco}?mode=ro", uri=True)
nid = con.execute("SELECT MAX(id) FROM normalizacao_execucao").fetchone()[0]
did = con.execute("SELECT MAX(id) FROM derivacao_execucao WHERE vigencia_em IS NULL").fetchone()[0]
v2 = con.execute("SELECT id FROM regra WHERE codigo='RREO-COL' AND versao=2").fetchone()[0]
MANUAL = {("consolidado", 2018): {"L": 1897453687, "a": 456752771, "f": 1283420454, "emit": "12/04/2019"},
          ("consolidado", 2019): {"L": 2140132559, "a": 525073739, "f": 1372690097, "emit": "20/02/2020"}}
def rreo(escopo, ex):
    if (escopo, ex) in MANUAL: return MANUAL[(escopo, ex)]
    r = con.execute("SELECT coluna, valor_c, emitido_em FROM rreo_valor WHERE normalizacao_id=? AND escopo=? AND exercicio=? AND linha='TOTAL (III)' "
                    "AND data_final=(SELECT MAX(data_final) FROM rreo_valor WHERE normalizacao_id=? AND escopo=? AND exercicio=?)", (nid, escopo, ex, nid, escopo, ex)).fetchall()
    if not r: return None
    d = {c: v for c, v, _ in r}; d["emit"] = r[0][2]; d["df"] = True; return d
def api(escopo, ex, comp):
    q = "visao='publicado'" if escopo == "consolidado" else "visao='entidade' AND entidade=1"
    r = con.execute(f"SELECT valor_c FROM visao_valor WHERE derivacao_id=? AND {q} AND regra_agregacao_id=? AND exercicio=? AND data_final=? AND componente=?",
                    (did, v2, ex, f"{ex}-12-31", comp)).fetchone()
    return r[0] if r else None
print("| Escopo | A → A+1 | RREO L(A) (emissão) | RREO (a)+(f) de A+1 (emissão) | Δ entre publicações | API ΣS1(A) | API (a)+(f) de A+1 |")
print("|---|---|--:|--:|--:|--:|--:|")
for escopo in ("entidade", "consolidado"):
    for ex in range(2016, 2026):
        x, y = rreo(escopo, ex), rreo(escopo, ex + 1)
        if not x or not y or "L" not in x: continue
        af = y["a"] + y["f"]
        a1 = api(escopo, ex, "L")
        aa, af_api = api(escopo, ex + 1, "a"), api(escopo, ex + 1, "f")
        print(f"| {escopo} | {ex} → {ex+1} | {br(x['L'])} ({x['emit'][:11]}) | {br(af)} ({y['emit'][:11]}) | **{br(af - x['L'])}** | {br(a1)} | "
              f"{br(aa + af_api) if aa is not None else '—'} |")
