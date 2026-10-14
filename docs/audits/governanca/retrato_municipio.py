"""Snapshot of the PUBLISHED Municipality indicators at every processed cut-off (READ-ONLY), to record the impact of a
governance decision: run before and after it, then compare the two JSON files.

Usage (from app/):
    python ../docs/audits/governanca/retrato_municipio.py --banco DB --saida OUT.json
    python ../docs/audits/governanca/retrato_municipio.py --comparar ANTES.json DEPOIS.json --saida-md IMPACTO.md
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "app"))

INDICADORES = ("inscricao_total", "pagamentos", "cancelamentos", "liquidacoes", "saldo_total", "registros")


def retrato(banco):
    from rp.painel import Painel
    saida = {}
    with Painel.abrir(banco) as p:
        for c in p.cortes()["cortes"]:
            r = p.indicadores(c["exercicio"], c["data_final"])
            chave = f"{c['exercicio']}|{c['data_final']}"
            saida[chave] = {"disponivel": r["disponivel"], "escopo": r["escopo"], "com_ressalva": r["com_ressalva"],
                            "regras_de_escopo": [f"{x['codigo']} v{x['versao']}" for x in r["regras_de_escopo"]],
                            "valores": {k: r["valores"][k]["valor_c"] for k in INDICADORES}}
    return saida


def br(c):
    return "—" if c is None else f"{c / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def comparar(antes, depois):
    linhas = []
    for chave in sorted(set(antes) | set(depois)):
        a, d = antes.get(chave), depois.get(chave)
        if a is None or d is None:
            linhas.append((chave, "corte só num dos retratos", None, None))
            continue
        for k in INDICADORES:
            if a["valores"][k] != d["valores"][k]:
                dif = None if None in (a["valores"][k], d["valores"][k]) else d["valores"][k] - a["valores"][k]
                linhas.append((chave, k, a["valores"][k], d["valores"][k], dif))
    return linhas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--banco")
    ap.add_argument("--saida")
    ap.add_argument("--comparar", nargs=2)
    ap.add_argument("--saida-md")
    a = ap.parse_args()
    if a.comparar:
        antes, depois = (json.loads(Path(x).read_text(encoding="utf-8")) for x in a.comparar)
        linhas = comparar(antes, depois)
        md = ["| Exercício | Corte | Indicador | Antes | Depois | Diferença |", "|---|---|---|---:|---:|---:|"]
        for chave, k, *v in linhas:
            ex, df = chave.split("|")
            fmt = (lambda x: "—" if x is None else str(x)) if k == "registros" else br     # a count, not money
            md.append(f"| {ex} | {df} | {k} | {fmt(v[0])} | {fmt(v[1])} | {fmt(v[2]) if len(v) > 2 else '—'} |")
        resumo = f"{len({x[0] for x in linhas})} corte(s) com valor diferente, {len(linhas)} valor(es)."
        Path(a.saida_md).write_text(resumo + "\n\n" + "\n".join(md) + "\n", encoding="utf-8")
        print(resumo)
        return
    Path(a.saida).write_text(json.dumps(retrato(a.banco), ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
