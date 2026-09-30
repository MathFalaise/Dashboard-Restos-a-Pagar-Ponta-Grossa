"""Reconciliacao da Etapa 04.3 (artefato de validacao, nao e producao). Sem acesso a internet.

A) ARMAZEM REAL, derivacao "como estava em 29/09 23:59"  x  investigacao da Etapa 03  -> tem de ser iguais
B) ARMAZEM REAL, derivacao "atual"  x  derivacao "como estava em"  -> o que as coletas novas acrescentaram
C) Foco pedido na revisao: 2025/2026 x entidades 1 e 15

Uso: python reconciliar_04_3.py PASTA_TEMPORARIA BANCO_ATIVO DERIVACAO_ATUAL DERIVACAO_COMO_ESTAVA
"""
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

from reconciliar_04_2 import RAIZ, chaves_snapshot, inv, tabelas


def br(c):
    return f"{c / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def restringir(t, chaves):
    """Tabelas por registro, so dos snapshots cujas chaves de conteudo estao em `chaves`."""
    out = {}
    for nome in ("rp_registro", "rp_derivado", "movimentacao_lancamento", "movimentacao_interpretada"):
        out[nome] = {k: v for k, v in t[nome].items() if k[0][0] in chaves}
    out["anomalia"] = Counter({k: n for k, n in t["anomalia"].items() if k[2] in chaves})
    out["espelhamento_par"] = {k: v for k, v in t["espelhamento_par"].items() if k[3][0] in chaves}
    return out


def visoes(t):
    return {k: v[0] for k, v in t["visao_valor"].items()}


def conciliacao(t):
    """Por (conteudo do PDF, regra, coluna) -> valores; um PDF baixado duas vezes aparece uma vez, se igual."""
    out = defaultdict(set)
    for (rk, agg, col), v in t["conciliacao_rreo"].items():
        out[(rk[2], agg, col)].add(v[:7])
    return out


def main(tmp, banco_ativo, d_atual, d_antes):
    d_atual, d_antes = int(d_atual), int(d_antes)
    Path(tmp).mkdir(parents=True, exist_ok=True)
    ci, ni, di, _, _ = inv.construir(Path(tmp) / "investigacao.sqlite")
    E = tabelas(ci, ni, di)
    chaves_inv = set(chaves_snapshot(ci).values())
    ca = sqlite3.connect(banco_ativo)
    na = ca.execute("SELECT normalizacao_id FROM derivacao_execucao WHERE id=?", (d_antes,)).fetchone()[0]
    A = tabelas(ca, na, d_antes)
    T = tabelas(ca, na, d_atual)
    chaves_real = set(chaves_snapshot(ca).values())
    out = ["# Reconciliação da Etapa 04.3", "", "Gerado por `etapa04/reconciliacao/reconciliar_04_3.py`, sem acesso à internet.", "",
           f"- Snapshots da investigação (Etapa 03): {len(chaves_inv)}; no armazém real: {len(chaves_real)}; "
           f"**investigação contida no real: {chaves_inv <= chaves_real}** (mesmo conteúdo e mesmo horário).", "",
           "## A) Armazém real, \"como estava em 29/09 23:59\" × investigação da Etapa 03", "",
           "| Comparação | Esperado | Obtido | Igual? |", "|---|--:|--:|---|"]
    ok = chaves_inv <= chaves_real
    Er, Ar = restringir(E, chaves_inv), restringir(A, chaves_inv)
    for nome in Er:
        n_e = sum(Er[nome].values()) if isinstance(Er[nome], Counter) else len(Er[nome])
        n_a = sum(Ar[nome].values()) if isinstance(Ar[nome], Counter) else len(Ar[nome])
        igual = Er[nome] == Ar[nome]
        ok &= igual
        out.append(f"| `{nome}` (snapshots da investigação) | {n_e} | {n_a} | {'**SIM**' if igual else '**NÃO**'} |")
    ve, va = visoes(E), visoes(A)
    igual = ve == va
    ok &= igual
    out.append(f"| valores de todas as visões (entidade, publicada, analíticas; v1/v2) | {len(ve)} | {len(va)} | {'**SIM**' if igual else '**NÃO**'} |")
    ce, cA = conciliacao(E), conciliacao(A)
    unicos = all(len(v) == 1 for v in cA.values())
    igual = ce == cA and unicos
    ok &= igual
    out.append(f"| conciliação RREO × API por PDF, regra e coluna | {len(ce)} | {len(cA)} | {'**SIM**' if igual else '**NÃO**'} |")
    out += ["", "No armazém real, o PDF 2560662 aparece duas vezes: a importação da Etapa 02 e a coleta da 04.1, com bytes idênticos.",
            f"As conciliações das duas cópias são iguais entre si: {unicos}.", ""]

    # B) atual x como estava
    vt = visoes(T)
    comuns = va.keys() & vt.keys()
    mudou = {k: (va[k], vt[k]) for k in comuns if va[k] != vt[k]}
    novos_cortes = sorted({(k[0], k[4], k[5]) for k in vt.keys() - va.keys()})
    out += ["## B) Armazém real: derivação \"atual\" × \"como estava em 29/09\"", "",
            f"- Valores de visão em cortes presentes nas duas: {len(comuns)}; **diferentes: {len(mudou)}**.",
            f"- Cortes que só existem na \"atual\" (coletas novas): {len(novos_cortes)} → "
            + ", ".join(f"{v} {ex} até {df}" for v, ex, df in novos_cortes[:12]), ""]
    cT = conciliacao(T)
    novos_rreo = sorted({(k[0], k[2]) for k in cT} - {(k[0], k[2]) for k in cA})
    out.append(f"- Conciliações novas: {len(novos_rreo)} (PDF × coluna), vindas dos cortes e PDFs coletados hoje.")
    ok &= not mudou

    # C) foco: 2025/2026 x entidades 1 e 15, na derivacao atual
    q = lambda sql, *p: ca.execute(sql, (d_atual, *p)).fetchall()
    out += ["", "## C) Foco: 2025/2026 × entidades 1 e 15 (derivação atual)", "", "### Pares espelhados por corte", "",
            "| Corte | Relação entre inscrições | Lado com execução | Pares | Inscrito A (ent. 1) | Inscrito B (ent. 15) | Execução A | Execução B |",
            "|---|---|---|--:|--:|--:|--:|--:|"]
    for r in q("SELECT exercicio, data_final, relacao_inscricao, lado_com_execucao, COUNT(*), SUM(inscrito_a_c), SUM(inscrito_b_c), "
               "SUM(execucao_a_c), SUM(execucao_b_c) FROM espelhamento_par WHERE derivacao_id=? GROUP BY 1,2,3,4 ORDER BY 1,2,3,4"):
        out.append(f"| {r[0]} até {r[1]} | {r[2]} | {r[3]} | {r[4]} | {br(r[5])} | {br(r[6])} | {br(r[7])} | {br(r[8])} |")
    out += ["", "### Visões por entidade (RREO-COL v1), entidades 1 e 15", "",
            "| Entidade | Corte | (a)+(b) | (f)+(g) | (c) | (h) | (i) | (j) | S1 |", "|---|---|--:|--:|--:|--:|--:|--:|--:|"]
    for e, ex, df in q("SELECT DISTINCT v.entidade, v.exercicio, v.data_final FROM visao_valor v WHERE v.derivacao_id=? "
                       "AND v.visao='entidade' AND v.entidade IN (1,15) AND v.data_final IN ('2025-12-31','2026-04-30','2026-08-31') ORDER BY 2,3,1"):
        v = dict(q("SELECT v.componente, v.valor_c FROM visao_valor v JOIN regra g ON g.id=v.regra_agregacao_id WHERE v.derivacao_id=? "
                   "AND v.visao='entidade' AND g.versao=1 AND v.entidade=? AND v.exercicio=? AND v.data_final=?", e, ex, df))
        out.append(f"| {e} | {ex} até {df} | {br(v['a']+v['b'])} | {br(v['f']+v['g'])} | {br(v['c'])} | {br(v['h'])} | {br(v['i'])} | {br(v['j'])} | {br(v['S1'])} |")
    out += ["", "### Município: publicado × analíticas × RREO consolidado (RREO-COL v2)", "",
            "| Corte | Componente | Publicado | Analítico CONS-PAR v1 | Analítico CONS-PAR v2 | RREO consolidado |", "|---|---|--:|--:|--:|--:|"]
    for ex, df in q("SELECT DISTINCT exercicio, data_final FROM visao_valor WHERE derivacao_id=? AND visao='publicado' ORDER BY 1,2"):
        def V(visao, cons=None):
            s = ("SELECT v.componente, v.valor_c FROM visao_valor v JOIN regra g ON g.id=v.regra_agregacao_id LEFT JOIN regra r ON "
                 "r.id=v.regra_consolidacao_id WHERE v.derivacao_id=? AND g.versao=2 AND v.visao=? AND v.exercicio=? AND v.data_final=?")
            return dict(q(s + (" AND r.versao=?" if cons else ""), visao, ex, df, *((cons,) if cons else ())))
        p, a1, a2 = V("publicado"), V("analitico", 1), V("analitico", 2)
        rr = dict(q("SELECT c.coluna, c.valor_rreo_c FROM conciliacao_rreo c JOIN regra g ON g.id=c.regra_agregacao_id WHERE c.derivacao_id=? "
                    "AND g.versao=2 AND c.escopo='consolidado' AND c.exercicio=? AND c.data_final=?", ex, df))
        for comp in ("b", "g", "c", "i", "L"):
            out.append(f"| {ex} até {df} | {comp} | {br(p[comp])} | {br(a1[comp])} | {br(a2[comp])} | {br(rr[comp]) if comp in rr else '—'} |")
    out += ["", "### Conciliação do RREO consolidado do 4º bim/2026 (nova: exigia todas as entidades no corte 31/08)", "",
            "| Coluna | RREO | API RREO-COL v1 | Dif. v1 | API RREO-COL v2 | Dif. v2 |", "|---|--:|--:|--:|--:|--:|"]
    c4 = {}
    for col, g, vr, va_, d in q("SELECT c.coluna, g.versao, c.valor_rreo_c, c.valor_api_c, c.diferenca_c FROM conciliacao_rreo c "
                                "JOIN regra g ON g.id=c.regra_agregacao_id WHERE c.derivacao_id=? AND c.escopo='consolidado' "
                                "AND c.data_final='2026-08-31' ORDER BY 1"):
        c4.setdefault(col, {})[g] = (vr, va_, d)
    for col in "abcdefghijkL":
        if col in c4:
            (vr, a1, d1), (_, a2, d2) = c4[col][1], c4[col][2]
            out.append(f"| ({col}) | {br(vr)} | {br(a1)} | {br(d1)} | {br(a2)} | {br(d2)} |")
    out += ["", f"## Resultado: {'**A) IGUAL À ETAPA 03 e B) SEM MUDANÇA NOS CORTES COMUNS**' if ok else '**HÁ DIFERENÇAS — ver acima**'}", ""]
    texto = "\n".join(out)
    print(texto)
    (RAIZ / "etapa04" / "resultados" / "04_3_reconciliacao.md").write_text(texto + "\n", encoding="utf-8")
    return ok


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="backslashreplace")   # saida em cp1252 (arquivo) nao derruba o script
    sys.exit(0 if main(*sys.argv[1:5]) else 1)
