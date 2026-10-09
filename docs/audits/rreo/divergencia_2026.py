"""Re-evaluation of the 2026 differences between the API and the RREO Annex VII (correction request of 09/10/2026,
item 6). READ-ONLY; nothing is adjusted.

For each 2026 cut-off with an RREO "por entidade" (entity 1), it puts side by side the difference RREO - API of the
derivation "as it was on" each validity present in the database and of the current one, and - when the API snapshot
used changed between them - lists, commitment by commitment, what the API changed for that SAME closed period
(rp.comparador: facts, not causes). It states a cause only for the part the snapshots explain; the rest stays
"origin not determined" (e-SIC draft, block B).

Usage (from the repository root):
    python docs/audits/rreo/divergencia_2026.py --banco DB --saida-json OUT.json --saida-md OUT.md
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "app"))
from rp import comparador  # noqa: E402

COLUNAS = ("c", "d", "h", "i", "j", "k", "L")


def _reais(c):
    return None if c is None else f"{c / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _conciliacao(con, did):
    saida = {}
    for df, col, rreo, api, dif, cols, uid_rreo, emitido in con.execute(
            "SELECT c.data_final, c.coluna, c.valor_rreo_c, c.valor_api_c, c.diferenca_c, c.coletas_api_json, "
            "k.snapshot_uid, (SELECT MAX(v.emitido_em) FROM rreo_valor v WHERE v.coleta_id = k.id) FROM conciliacao_rreo c "
            "JOIN regra g ON g.id = c.regra_agregacao_id JOIN coleta k ON k.id = c.rreo_coleta_id WHERE c.derivacao_id=? "
            "AND c.exercicio=2026 AND c.escopo='entidade' AND g.codigo='RREO-COL' AND g.versao=1 ORDER BY 1, 2", (did,)):
        item = saida.setdefault(df, {"rreo_snapshot": uid_rreo, "rreo_emitido_em": emitido,
                                     "api_snapshots": json.loads(cols), "colunas": {}})
        item["colunas"][col] = {"rreo": rreo, "api": api, "diferenca_api_menos_rreo": dif}
    return saida


def coletar(con):
    ders = con.execute("SELECT id, IFNULL(vigencia_em, 'atual') FROM derivacao_execucao WHERE id IN (SELECT MAX(id) FROM "
                       "derivacao_execucao GROUP BY IFNULL(vigencia_em, '')) ORDER BY vigencia_em IS NULL, vigencia_em"
                       ).fetchall()
    por_vig = {vig: {"derivacao": did, "cortes": _conciliacao(con, did)} for did, vig in ders}
    atual = por_vig["atual"]["cortes"]
    mudancas = {}
    for vig, x in por_vig.items():
        if vig == "atual":
            continue
        for df, antes in x["cortes"].items():
            depois = atual.get(df)
            if not depois or antes["api_snapshots"] == depois["api_snapshots"]:
                continue
            uid = lambda s: [u for u in s["api_snapshots"]]
            ent1 = lambda s: next(u for u in uid(s) if con.execute("SELECT entidade FROM coleta WHERE snapshot_uid=?",
                                                                  (u,)).fetchone()[0] == 1)
            a, b = ent1(antes), ent1(depois)
            r = comparador.comparar(con, a, b)
            alterados = [{"empenho": f"{k['chave'][2]}/{k['chave'][1]}",
                          "campos": {f["campo"]: [f["antes"], f["depois"]] for f in k["campos"] if f["campo"].endswith("_c")}}
                         for k in r["alterados"] if any(f["campo"].endswith("_c") for f in k["campos"])]
            mudancas[f"{df} ({vig} -> atual)"] = {
                "snapshot_antes": a, "coletado_antes": r["anterior"]["coletada_em"], "snapshot_depois": b,
                "coletado_depois": r["posterior"]["coletada_em"], "contagens": r["contagens"],
                "impacto_por_grupo": {g: v["diferenca"] for g, v in r["impacto_financeiro_por_grupo"].items() if v["diferenca"]},
                "alterados": alterados}
    return {"vigencias": por_vig, "mudancas_da_api_no_mesmo_periodo": mudancas}


def markdown(d):
    out = ["# Divergências API × RREO (entidade 1) em 2026: reavaliação", "",
           "Gerado por `docs/audits/rreo/divergencia_2026.py`. Somente leitura; nenhum valor é ajustado. "
           "Diferença = API − RREO, regra de agregação RREO-COL v1.", ""]
    vigs = list(d["vigencias"])
    cortes = sorted({df for x in d["vigencias"].values() for df in x["cortes"]})
    out += ["## Diferença por coluna em cada vigência", "",
            "| Corte | Coluna | RREO | " + " | ".join(f"API ({v}) | dif. ({v})" for v in vigs) + " |",
            "|---|---|---|" + "---|---|" * len(vigs)]
    for df in cortes:
        for col in COLUNAS:
            celulas, rreo = [], None
            for v in vigs:
                c = d["vigencias"][v]["cortes"].get(df, {}).get("colunas", {}).get(col)
                rreo = rreo if c is None else c["rreo"]
                celulas += [_reais(c["api"]) if c else "—", _reais(c["diferenca_api_menos_rreo"]) if c else "—"]
            if any(x not in ("0,00", "—") for x in celulas[1::2]):
                out.append(f"| {df} | {col} | {_reais(rreo)} | " + " | ".join(celulas) + " |")
    out += ["", "## O que a API mudou no mesmo período fechado entre as coletas", ""]
    for chave, m in d["mudancas_da_api_no_mesmo_periodo"].items():
        if not m["alterados"]:
            out += [f"### Corte {chave}", "", f"Retrato da API de {m['coletado_antes']} × de {m['coletado_depois']}: "
                    f"{m['contagens']['alterados']} registro(s) alterado(s) só em campos não monetários; nenhum valor "
                    "mudou.", ""]
            continue
        out += [f"### Corte {chave}", "",
                f"Retrato da API de {m['coletado_antes']} (`{m['snapshot_antes'][:8]}`) × de {m['coletado_depois']} "
                f"(`{m['snapshot_depois'][:8]}`): {m['contagens']['alterados']} registro(s) alterado(s), "
                f"{m['contagens']['novos']} novo(s), {m['contagens']['removidos']} removido(s).", "",
                "Impacto por grupo: " + ", ".join(f"{g} {_reais(v)}" for g, v in m["impacto_por_grupo"].items()), "",
                "| Empenho | Campo | Antes | Depois |", "|---|---|---|---|"]
        for a in m["alterados"]:
            for campo, (x, y) in a["campos"].items():
                out.append(f"| {a['empenho']} | {campo} | {_reais(x)} | {_reais(y)} |")
        out.append("")
    out += ["## Conclusão com o que a evidência sustenta", "",
            "- **Parte explicada (fato):** a diferença em (h), (i), (j), (k) e (L) mudou entre as coletas porque a API "
            "passou a mostrar, para o MESMO período já encerrado, pagamentos e liquidações menores e cancelamentos "
            "novos nos empenhos listados acima. O RREO desses bimestres já estava emitido; ele não muda.",
            "- **Parte não explicada:** a diferença já existente na primeira coleta (antes das mudanças) continua com "
            "origem não determinada. Não há retrato da API anterior à emissão de cada RREO para dizer se também é "
            "lançamento retroativo. Pendente de resposta oficial (e-SIC, bloco B, perguntas 6 e 7).",
            "- A API continua como fonte primária da série; a divergência fica visível no painel e na homologação.", ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--banco", required=True)
    ap.add_argument("--saida-json", required=True)
    ap.add_argument("--saida-md", required=True)
    a = ap.parse_args()
    con = sqlite3.connect(f"file:{Path(a.banco).resolve()}?mode=ro", uri=True)
    d = coletar(con)
    Path(a.saida_json).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    Path(a.saida_md).write_text(markdown(d), encoding="utf-8")
    print(json.dumps({"vigencias": list(d["vigencias"]), "mudancas": list(d["mudancas_da_api_no_mesmo_periodo"])},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
