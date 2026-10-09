"""RREO Annex VII: PDF published on the municipal portal x declaration to the National Treasury (SICONFI). READ-ONLY.

Three independent channels meet here: the Elotech API (the project's primary source), the RREO PDF of the portal
(transcribed by the production extractor) and the SICONFI declaration (raw/, downloaded by baixar_siconfi.py). This
script compares the SECOND with the THIRD, cell by cell (rows (I), PODER EXECUTIVO, (II) and TOTAL (III); columns a..L),
for every period with both. It does not touch the reconciliation with the API and adjusts nothing.

Column mapping: the letter of the SICONFI column label ("Pagos (c)", "Saldo e = ...", "Saldo Total L = ..."); 2016
uses older labels, mapped explicitly below. The mapping is checked on every declaration by the document's own
identities (e = a + b - c - d, k = f + g - i - j, L = e + k): a wrong mapping would break them.

Usage (from the repository root):
    python docs/audits/rreo/siconfi/conferencia_siconfi.py --banco DB --saida-json OUT.json --saida-md OUT.md
"""
import argparse
import calendar
import json
import re
import sqlite3
from decimal import Decimal
from pathlib import Path

PASTA = Path(__file__).resolve().parent
COLUNAS = "abcdefghijkL"
LINHAS = (("RESTOS A PAGAR (EXCETO", "RESTOS A PAGAR (EXCETO"), ("PODER EXECUTIVO", "PODER EXECUTIVO"),
          ("RESTOS A PAGAR (INTRA", "RESTOS A PAGAR (INTRA"), ("TOTAL (III)", "TOTAL (III)"))
ROTULOS_2016 = {   # 2016 layout: processed + liquidated block, then non-processed block
    "RPP e RPNP Liquidados em Exercícios Anteriores - Inscritos Em Exercícios Anteriores": "a",
    "RPP e RPNP Liquidados em Exercícios Anteriores - Inscritos Em 31 de Dezembro de 2015": "b",
    "RPP e RPNP Liquidados Em Exercícios Anteriores - Pagos": "c",
    "RPP e RPNP Liquidados Em Exercícios Anteriores - Cancelados": "d",
    "Saldo (a)": "e",
    "RPNP - Inscritos Em Exercícios Anteriores": "f",
    "RPNP - Inscritos Em 31 de Dezembro de 2015": "g",
    "RPNP - Liquidados": "h",
    "RPNP - Pagos": "i",
    "RPNP - Cancelados": "j",
    "Saldo (b)": "k",
    "Saldo Total (a+b)": "L",
}


def coluna_de(rotulo):
    if rotulo in ROTULOS_2016:
        return ROTULOS_2016[rotulo]
    if rotulo.startswith("Saldo Total L"):
        return "L"
    if rotulo.startswith("Saldo e"):
        return "e"
    if rotulo.startswith("Saldo k"):
        return "k"
    m = re.search(r"\(([a-j])\)\s*$", rotulo)
    if m:
        return m.group(1)
    raise ValueError(f"coluna SICONFI sem mapeamento: {rotulo!r}")


def ler_siconfi(arquivo):
    """{line: {column: cents}} of one declaration, + identities that fail."""
    itens = json.loads(arquivo.read_text(encoding="utf-8"))["items"]
    linhas = {}
    for i in itens:
        nome = next((n for p, n in LINHAS if i["conta"].startswith(p)), None)
        if nome is None:
            continue                       # e.g. PODER LEGISLATIVO / Câmara: not transcribed from the PDF either
        col = coluna_de(i["coluna"])
        v = int((Decimal(str(i["valor"])) * 100).to_integral_value())
        if col in linhas.setdefault(nome, {}) and linhas[nome][col] != v:
            raise ValueError(f"{arquivo.name}: {nome} ({col}) com dois valores")
        linhas[nome][col] = v
    falhas, zeros = [], []
    for nome, v in linhas.items():
        # SICONFI leaves out an item whose value is zero (13 declarations without column (d)). An absent column is
        # taken as 0 ONLY if the declaration's own identities close with it; otherwise it is reported as a failure
        ausentes = sorted(set(COLUNAS) - set(v))
        if ausentes:
            com_zero = {**{c: 0 for c in ausentes}, **v}
            fecha = (com_zero["e"] == com_zero["a"] + com_zero["b"] - com_zero["c"] - com_zero["d"] and
                     com_zero["k"] == com_zero["f"] + com_zero["g"] - com_zero["i"] - com_zero["j"] and
                     com_zero["L"] == com_zero["e"] + com_zero["k"])
            if not fecha:
                falhas.append(f"{nome}: colunas {ausentes} ausentes e as identidades não fecham com zero")
                continue
            zeros.append(f"{nome}: {ausentes}")
            v.update({c: 0 for c in ausentes})
        for rot, ok in (("e = a + b - c - d", v["e"] == v["a"] + v["b"] - v["c"] - v["d"]),
                        ("k = f + g - i - j", v["k"] == v["f"] + v["g"] - v["i"] - v["j"]),
                        ("L = e + k", v["L"] == v["e"] + v["k"])):
            if not ok:
                falhas.append(f"{nome}: {rot}")
    return linhas, falhas, zeros


def coletar(con):
    nid = con.execute("SELECT MAX(id) FROM normalizacao_execucao").fetchone()[0]
    did = con.execute("SELECT MAX(id) FROM derivacao_execucao WHERE vigencia_em IS NULL AND normalizacao_id=?",
                      (nid,)).fetchone()[0]
    manifesto = json.loads((PASTA / "manifest.json").read_text(encoding="utf-8"))
    pdfs = {}
    for cid, uid, escopo, ex, df, rotulo, arq in con.execute(
            "SELECT DISTINCT v.coleta_id, k.snapshot_uid, v.escopo, v.exercicio, v.data_final, "
            "json_extract(k.parametros_json, '$.rotulo'), k.id_arquivo FROM rreo_valor v JOIN coleta k ON k.id = v.coleta_id "
            "WHERE v.normalizacao_id=? ORDER BY v.exercicio, v.data_final, k.coletada_em, k.snapshot_uid", (nid,)):
        valores = {}
        for linha, col, val in con.execute("SELECT linha, coluna, valor_c FROM rreo_valor WHERE normalizacao_id=? AND "
                                           "coleta_id=?", (nid, cid)):
            valores.setdefault(linha, {})[col] = val
        pdfs.setdefault((ex, df), []).append({"snapshot": uid, "escopo": escopo, "rotulo": rotulo, "id_arquivo": arq,
                                              "valores": valores})
    periodos = []
    for nome in sorted(manifesto["arquivos"]):
        ano, per = (int(x) for x in re.match(r"rreo_anexo07_(\d{4})_(\d)\.json", nome).groups())
        mes = 2 * per
        df = f"{ano}-{mes:02d}-{calendar.monthrange(ano, mes)[1]:02d}"
        sic, falhas, zeros = ler_siconfi(PASTA / "raw" / nome)
        item = {"exercicio": ano, "bimestre": per, "data_final": df, "arquivo": nome,
                "sha256": manifesto["arquivos"][nome]["sha256"], "identidades_siconfi_que_falham": falhas,
                "colunas_ausentes_tomadas_como_zero": zeros,
                "siconfi_L_total": sic.get("TOTAL (III)", {}).get("L"), "pdfs": []}
        for pdf in pdfs.get((ano, df), []):
            comparadas, diferentes = 0, []
            for linha, cols in pdf["valores"].items():
                for col, v in cols.items():
                    s = sic.get(linha, {}).get(col)
                    if s is None:
                        if v != 0:      # a zero INTRA row may be absent from the declaration
                            diferentes.append({"linha": linha, "coluna": col, "pdf": v, "siconfi": None})
                        continue
                    comparadas += 1
                    if s != v:
                        diferentes.append({"linha": linha, "coluna": col, "pdf": v, "siconfi": s})
            item["pdfs"].append({k: pdf[k] for k in ("snapshot", "escopo", "rotulo", "id_arquivo")} |
                                {"celulas_comparadas": comparadas, "diferencas": diferentes,
                                 "pdf_L_total": pdf["valores"].get("TOTAL (III)", {}).get("L"),
                                 "igual": comparadas > 0 and not diferentes})
        item["api"] = _api(con, did, ano, df, sic.get("TOTAL (III)", {}))
        periodos.append(item)
    return {"normalizacao": nid, "derivacao": did, "periodos": periodos,
            "sem_declaracao": manifesto.get("sem_declaracao", {})}


def _api(con, did, ano, df, sic_total):
    """The API projected on the Annex VII columns (aggregation RREO-COL v1), Município, in the official view (both sides
    of the mirrored pairs) and in the experimental CONS-PAR views, x the SICONFI TOTAL row. None without a derivation
    value at that cut-off (no API snapshot of every entity)."""
    saida = {}
    for nome, filtro, p in (("oficial (dois lados)", "v.visao='publicado'", ()),
                            ("CONS-PAR v1 (experimental)", "v.visao='analitico' AND gc.versao=1", ()),
                            ("CONS-PAR v2 (experimental)", "v.visao='analitico' AND gc.versao=2", ())):
        valores = dict(con.execute(
            "SELECT v.componente, v.valor_c FROM visao_valor v JOIN regra ga ON ga.id = v.regra_agregacao_id LEFT JOIN "
            "regra gc ON gc.id = v.regra_consolidacao_id WHERE v.derivacao_id=? AND v.exercicio=? AND v.data_final=? AND "
            f"ga.codigo='RREO-COL' AND ga.versao=1 AND {filtro}", (did, ano, df, *p)).fetchall())
        if not valores:
            continue
        cols = [c for c in COLUNAS if c in valores and c in sic_total]
        saida[nome] = {"L": valores.get("L"), "L_siconfi": sic_total.get("L"),
                       "diferenca_L": None if valores.get("L") is None or sic_total.get("L") is None
                       else valores["L"] - sic_total["L"],
                       "colunas_iguais": sum(1 for c in cols if valores[c] == sic_total[c]), "colunas": len(cols)}
    return saida


def _reais(c):
    return "—" if c is None else f"{c / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def markdown(d):
    ps = d["periodos"]
    com_pdf = [p for p in ps if p["pdfs"]]
    iguais = [p for p in com_pdf if any(x["igual"] for x in p["pdfs"])]
    out = ["# RREO Anexo VII: PDF do portal × declaração ao Tesouro (Siconfi)", "",
           "Gerado por `docs/audits/rreo/siconfi/conferencia_siconfi.py` sobre as declarações em `raw/` "
           "(baixadas por `baixar_siconfi.py`, SHA-256 em `manifest.json`) e a transcrição dos PDFs na normalização "
           f"{d['normalizacao']}. Somente leitura; nada é ajustado.", "",
           f"Declarações no Siconfi: {len(ps)} · com PDF transcrito no mesmo período: {len(com_pdf)} · "
           f"com algum PDF idêntico à declaração (todas as células): {len(iguais)} · identidades do Anexo VII que "
           f"falham nas declarações: {sum(len(p['identidades_siconfi_que_falham']) for p in ps)}", "",
           "| Exercício | Bimestre | L total Siconfi | PDF (escopo) | L total PDF | Células comparadas | Diferentes | Resultado |",
           "|---|---|---|---|---|---|---|---|"]
    for p in ps:
        if not p["pdfs"]:
            out.append(f"| {p['exercicio']} | {p['bimestre']}º | {_reais(p['siconfi_L_total'])} | sem PDF transcrito | — | — | — | — |")
        for x in p["pdfs"]:
            res = "igual" if x["igual"] else "diferente"
            out.append(f"| {p['exercicio']} | {p['bimestre']}º | {_reais(p['siconfi_L_total'])} | {x['rotulo']} ({x['escopo']}) | "
                       f"{_reais(x['pdf_L_total'])} | {x['celulas_comparadas']} | {len(x['diferencas'])} | {res} |")
    dif = [(p, x) for p in ps for x in p["pdfs"] if x["diferencas"] and not any(y["igual"] for y in p["pdfs"])]
    if dif:
        out += ["", "## Períodos em que nenhum PDF coincide com a declaração", ""]
        for p, x in dif:
            out.append(f"- **{p['exercicio']}, {p['bimestre']}º bimestre, {x['rotulo']} ({x['escopo']})**: " + "; ".join(
                f"{y['linha']} ({y['coluna']}): PDF {_reais(y['pdf'])} × Siconfi {_reais(y['siconfi'])}"
                for y in x["diferencas"][:6]))
    out += ["", "## API (Município) × declaração ao Tesouro: saldo final L (agregação RREO-COL v1)", "",
            "Oficial = os dois lados dos pares 1 ↔ 15 somados, como a API publica. CONS-PAR = visões experimentais "
            "sem a inscrição de um dos lados. Diferença = API − Siconfi.", "",
            "| Exercício | Bimestre | Siconfi L | API oficial L | dif. | CONS-PAR v1 L | dif. | CONS-PAR v2 L | dif. |",
            "|---|---|---|---|---|---|---|---|---|"]
    for p in ps:
        a = p["api"]
        if not a:
            continue
        cel = lambda k: (a.get(k, {}).get("L"), a.get(k, {}).get("diferenca_L"))
        o, v1, v2 = cel("oficial (dois lados)"), cel("CONS-PAR v1 (experimental)"), cel("CONS-PAR v2 (experimental)")
        out.append(f"| {p['exercicio']} | {p['bimestre']}º | {_reais(p['siconfi_L_total'])} | {_reais(o[0])} | {_reais(o[1])} | "
                   f"{_reais(v1[0])} | {_reais(v1[1])} | {_reais(v2[0])} | {_reais(v2[1])} |")
    if d["sem_declaracao"]:
        out += ["", "Sem declaração no Siconfi na data da consulta: " + ", ".join(sorted(d["sem_declaracao"])) + "."]
    return "\n".join(out) + "\n"


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
    ps = d["periodos"]
    print(json.dumps({"declaracoes": len(ps), "com_pdf": sum(1 for p in ps if p["pdfs"]),
                      "algum_pdf_igual": sum(1 for p in ps if any(x["igual"] for x in p["pdfs"])),
                      "identidades_que_falham": sum(len(p["identidades_siconfi_que_falham"]) for p in ps)}))


if __name__ == "__main__":
    main()
