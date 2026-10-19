"""Cell-by-cell agreement matrix SICONFI x RREO PDF x Elotech x panel (corrective audit of 13/10/2026, item 6).
READ-ONLY on the database; it adjusts nothing and never invents a correction for a residual.

For every bimester 2016-2026 and every column a..L of Annex VII:
  A. oficial_x_oficial  - consolidated portal PDF (PODER EXECUTIVO row) x SICONFI declaration (PODER EXECUTIVO row):
                          two official documents of the same scope;
  B. elotech_x_pdf      - Elotech records projected by RREO-COL v3 in the PDF's scope (derivation's conciliacao_rreo)
                          x the PDF's TOTAL (III), for every transcribed PDF (entity and consolidated);
  C. elotech_x_siconfi  - Elotech projected by RREO-COL v3 in the PUBLISHED scope (ESCOPO-MUN v2, COPIA-ORIGEM v1,
                          CONS-PAR v4) x SICONFI PODER EXECUTIVO;
  D. painel_x_siconfi   - the published panel indicators (column groups that do not depend on the processed split)
                          x the same groups of SICONFI PODER EXECUTIVO.
Each non-zero difference gets ONE verifiable class:
  concorda | diferenca_de_escopo | versao_ou_retificacao | alteracao_retroativa_na_fonte | falha_de_extracao |
  regra_de_classificacao | falha_de_coleta | divergencia_entre_documentos_oficiais | causa_comprovada_por_empenho |
  causa_nao_determinada
with the evidence that supports it (explanation catalog entry, scope evidence, delivery date). A difference with no
evidence stays 'causa_nao_determinada' and is counted in the residuals.

Usage (from the repository root):
    python docs/audits/rreo/matriz_concordancia.py --banco DB --saida-json OUT.json --saida-md OUT.md
"""
import argparse
import calendar
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "app"))
from rp import governanca, siconfi  # noqa: E402
from rp.painel import Painel, explicacoes  # noqa: E402

COLUNAS = "abcdefghijkL"
GRUPOS = {"inscricao": "abfg", "pagos": "ci", "cancelados": "dj", "liquidados": "h", "saldo": "L"}
INDICADOR = {"inscricao": "inscricao_total", "pagos": "pagamentos", "cancelados": "cancelamentos",
             "liquidados": "liquidacoes", "saldo": "saldo_total"}
# explanation-catalog class -> audit class (item 6.3); 'situacao' of the entry decides explained / not
CLASSE_DO_CATALOGO = {"T": "alteracao_retroativa_na_fonte", "C": "diferenca_de_escopo", "E": "diferenca_de_escopo",
                      "R": "regra_de_classificacao", "P": "regra_de_classificacao", "H": "regra_de_classificacao",
                      "ND": "causa_nao_determinada"}
ESCOPO_E7 = json.loads((RAIZ / "docs/audits/escopo/ESCOPO_ENTIDADE_7.json").read_text(encoding="utf-8"))


def bimestres():
    for ano in range(2016, 2027):
        for bim in range(1, 7):
            mes = 2 * bim
            yield ano, bim, f"{ano}-{mes:02d}-{calendar.monthrange(ano, mes)[1]:02d}"


def br(c):
    return "—" if c is None else f"{c / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class Fontes:
    def __init__(self, banco):
        self.con = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
        self.did = self.con.execute("SELECT MAX(id) FROM derivacao_execucao WHERE vigencia_em IS NULL").fetchone()[0]
        self.nid = self.con.execute("SELECT normalizacao_id FROM derivacao_execucao WHERE id=?", (self.did,)).fetchone()[0]
        self.r3 = self.con.execute("SELECT id FROM regra WHERE codigo='RREO-COL' AND versao=3").fetchone()[0]
        self.v4 = self.con.execute("SELECT id FROM regra WHERE codigo='CONS-PAR' AND versao=4").fetchone()[0]
        self.leitura = siconfi.leituras()[-1]
        self.leituras = siconfi.leituras()
        atual = governanca.situacao_atual(self.con)
        self.aplicadas = frozenset(f"{c} v{v}" for (c, v), g in atual.items()
                                   if g["situacao"] == "operacional" and g["compoe_indicador_publicado"]
                                   and c in ("ESCOPO-MUN", "COPIA-ORIGEM", "CONS-PAR"))
        self.e7 = {(p["exercicio"], p["bimestre"]): p for p in ESCOPO_E7["periodos"]}

    def pdfs(self, ano, df):
        docs = {}
        for cid, uid, esc, emit, linha, col, v in self.con.execute(
                "SELECT v.coleta_id, c.snapshot_uid, v.escopo, v.emitido_em, v.linha, v.coluna, v.valor_c FROM rreo_valor v "
                "JOIN coleta c ON c.id = v.coleta_id WHERE v.normalizacao_id=? AND v.exercicio=? AND v.data_final=?",
                (self.nid, ano, df)):
            d = docs.setdefault(cid, {"coleta_id": cid, "snapshot": uid[:8], "escopo": esc, "emitido_em": emit,
                                      "linhas": defaultdict(dict)})
            d["linhas"][linha][col] = v
        return list(docs.values())

    def elotech_doc(self, cid):
        return dict(self.con.execute("SELECT coluna, valor_api_c FROM conciliacao_rreo WHERE derivacao_id=? AND "
                                     "rreo_coleta_id=? AND regra_agregacao_id=?", (self.did, cid, self.r3)))

    def visao(self, visao, ent, ano, df, cons=None):
        q = ("SELECT componente, valor_c FROM visao_valor WHERE derivacao_id=? AND visao=? AND regra_agregacao_id=? AND "
             "exercicio=? AND data_final=? AND " + ("regra_consolidacao_id IS NULL" if cons is None
                                                     else "regra_consolidacao_id=?")
             + " AND " + ("entidade IS NULL" if ent is None else "entidade=?"))
        p = [self.did, visao, self.r3, ano, df] + ([] if cons is None else [cons]) + ([] if ent is None else [ent])
        return dict(self.con.execute(q, p)) or None

    def elotech_publicado(self, ano, bim, df):
        """RREO-COL v3 per column in the published scope: the derivation's Municipality (ESCOPO-MUN v1 scope; from
        2026 the CONS-PAR v4 analytical view), minus entity 7 in the bimesters ESCOPO-MUN v2 excludes it."""
        if ano >= 2026:
            v = self.visao("analitico", None, ano, df, self.v4)
        else:
            v = self.visao("publicado", None, ano, df)
        if v is None:
            return None
        p = self.e7.get((ano, bim))
        if p and p["v1"] == "inclui" and p["tratamento"] == "exclui":
            e7 = self.visao("entidade", 7, ano, df) or {}
            v = {c: v.get(c, 0) - e7.get(c, 0) for c in COLUNAS}
        return {c: v.get(c) for c in COLUNAS}


PARES_DE_COLUNAS = (("a", "f"), ("b", "g"), ("c", "i"), ("d", "j"), ("e", "k"))


def trocas_de_soma_zero(difs):
    """Columns whose difference is cancelled, to the cent, by the same column of the other block (processed x
    non-processed): the two sides agree on the total and differ only in the split. A verifiable PATTERN; it does not
    say which commitment was reclassified."""
    saida = {}
    for x, y in PARES_DE_COLUNAS:
        if difs.get(x) and difs.get(x) == -difs.get(y, 0):
            saida[x] = saida[y] = f"troca de soma zero entre ({x}) e ({y}): {br(abs(difs[x]))}"
    return saida


def classificar_oficial(dif, col, ano, bim, f, pdf, entrega, trocas):
    """PDF x SICONFI (both official). Only proven patterns get a cause: entity 7 in the contradictory periods and, from
    2026, the 1-15 pairs (the PDF sums both sides). When a proven part explains only PART of the cell, the remainder
    is the residual. The rest is a contradiction WITHOUT a cause, counted in the residuals, with the documents' dates
    as information (dates alone prove nothing). Returns (class, evidence, residual in cents)."""
    if dif == 0:
        return "concorda", None, 0
    df = f"{ano}-{2 * bim:02d}-{calendar.monthrange(ano, 2 * bim)[1]:02d}"
    provado, causa = 0, None
    p = f.e7.get((ano, bim))
    if p and p["situacao"] == "contraditorio":
        provado = (f.visao("entidade", 7, ano, df) or {}).get(col, 0)
        causa = "o RREO do portal inclui a entidade 7 e a declaração ao Siconfi não (ESCOPO_ENTIDADE_7.md)"
    elif ano >= 2026:
        pub, cons = f.visao("publicado", None, ano, df), f.visao("analitico", None, ano, df, f.v4)
        if pub and cons:
            provado = pub.get(col, 0) - cons.get(col, 0)
            causa = "o RREO do portal soma os dois lados dos pares 1-15; a declaração ao Siconfi conta uma vez"
    if provado and dif == provado:
        return "divergencia_entre_documentos_oficiais", f"causa comprovada: {causa}", 0
    if col in trocas:
        return "regra_de_classificacao", f"{trocas[col]} (os documentos concordam no total)", 0
    datas = (f"PDF emitido em {pdf.get('emitido_em') or '—'}; declaração ao Siconfi "
             f"{(entrega or {}).get('situacao') or '—'} em {((entrega or {}).get('data_status') or '—')[:10]}")
    if provado and abs(dif - provado) < abs(dif):
        return ("divergencia_entre_documentos_oficiais_parcial",
                f"{br(provado)} comprovado ({causa}); resto {br(dif - provado)} sem causa; {datas}", dif - provado)
    return "divergencia_entre_documentos_oficiais_sem_causa", f"causa não determinada; {datas}", dif


def classificar_catalogo(ano, df, escopo, col, f):
    achadas, situacao = explicacoes.explicar(ano, df, escopo, col, "RREO-COL v3", f.aplicadas)
    if situacao == "não determinada" or not achadas:
        return "causa_nao_determinada", situacao, None
    classes = {CLASSE_DO_CATALOGO.get(e["classe"], "causa_nao_determinada") for e in achadas}
    classe = classes.pop() if len(classes) == 1 else "+".join(sorted(classes))
    if any("ao centavo" in e["texto"] or "Atribuída" in e["texto"] for e in achadas) and situacao == "explicada":
        classe = f"{classe} (causa_comprovada_por_empenho)"
    return classe, situacao, [e["fonte"] for e in achadas]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--banco", required=True)
    ap.add_argument("--saida-json", required=True)
    ap.add_argument("--saida-md", required=True)
    a = ap.parse_args()
    f = Fontes(a.banco)
    celulas = []
    with Painel.abrir(a.banco) as painel:
        cortes = {(c["exercicio"], c["data_final"]) for c in painel.cortes()["cortes"]}
        for ano, bim, df in bimestres():
            dec = siconfi.declaracao(f.leitura, ano, bim)
            entrega = siconfi.situacao_da_entrega(f.leitura, ano, bim)
            sic = (dec or {}).get("linhas", {}).get("executivo")
            pdfs = f.pdfs(ano, df)
            base = {"exercicio": ano, "bimestre": bim, "data_final": df}
            # A. official x official
            for pdf in (p for p in pdfs if p["escopo"] == "consolidado"):
                exe = pdf["linhas"].get("PODER EXECUTIVO", {})
                difs = {c: exe[c] - sic[c] for c in COLUNAS if sic and c in exe and sic.get(c) is not None}
                trocas = trocas_de_soma_zero(difs)
                for c in COLUNAS:
                    if sic is None or c not in exe or sic.get(c) is None:
                        continue
                    dif = exe[c] - sic[c]
                    classe, ev, residuo = classificar_oficial(dif, c, ano, bim, f, pdf, entrega, trocas)
                    celulas.append({**base, "comparacao": "oficial_x_oficial", "documento": pdf["snapshot"],
                                    "coluna": c, "esperado": sic[c], "observado": exe[c], "diferenca": dif,
                                    "classe": classe, "evidencia": ev, "residuo": residuo})
            # B. Elotech x PDF (every transcribed PDF, its own scope)
            for pdf in pdfs:
                api = f.elotech_doc(pdf["coleta_id"])
                total = pdf["linhas"].get("TOTAL (III)", {})
                trocas = trocas_de_soma_zero({c: api[c] - total[c] for c in COLUNAS if c in api and c in total})
                for c in COLUNAS:
                    if c not in api or c not in total:
                        continue
                    dif = api[c] - total[c]
                    if dif == 0:
                        classe, sit, ev = "concorda", None, None
                    else:
                        classe, sit, ev = classificar_catalogo(ano, df, pdf["escopo"], c, f)
                        if classe == "causa_nao_determinada" and c in trocas:
                            classe, ev = "regra_de_classificacao", [trocas[c] + " (padrão; empenho não atribuído)"]
                    celulas.append({**base, "comparacao": "elotech_x_pdf", "documento": pdf["snapshot"],
                                    "escopo": pdf["escopo"], "coluna": c, "esperado": total[c], "observado": api[c],
                                    "diferenca": dif, "classe": classe, "situacao_catalogo": sit, "evidencia": ev})
            # C. Elotech (published scope) x SICONFI
            elo = f.elotech_publicado(ano, bim, df)
            cons = next((p for p in pdfs if p["escopo"] == "consolidado"), None)
            # the catalog explains Elotech in the DERIVATION's scope (ESCOPO-MUN v1) x the PDF; its explanation is
            # inherited only where the published scope gives the same Elotech value (not where ESCOPO-MUN v2 removed
            # entity 7, nor in the CONS-PAR v4 view)
            api_cons = f.elotech_doc(cons["coleta_id"]) if cons else {}
            trocas = trocas_de_soma_zero({c: elo[c] - sic[c] for c in COLUNAS if elo and sic and elo.get(c) is not None
                                          and sic.get(c) is not None})
            for c in COLUNAS:
                if sic is None or elo is None or sic.get(c) is None or elo.get(c) is None:
                    continue
                dif = elo[c] - sic[c]
                exe_pdf = (cons or {"linhas": {}})["linhas"].get("PODER EXECUTIVO", {}).get(c)
                if dif == 0:
                    classe, ev = "concorda", None
                elif cons and exe_pdf == sic[c] and api_cons.get(c) == elo[c]:
                    classe, sit, ev = classificar_catalogo(ano, df, "consolidado", c, f)   # PDF == SICONFI: inherit
                elif cons and exe_pdf == sic[c]:
                    classe, ev = ("causa_nao_determinada",
                                  "PDF igual ao Siconfi; a explicação do catálogo é do escopo da derivação "
                                  "(ESCOPO-MUN v1), diferente do escopo publicado neste período")
                elif cons and exe_pdf == elo[c]:
                    classe, ev = ("divergencia_entre_documentos_oficiais",
                                  "a fonte Elotech reproduz o RREO do portal; a declaração ao Siconfi diverge (ver A)")
                elif cons:
                    classe, ev = "causa_nao_determinada", "PDF, Siconfi e Elotech diferem entre si nesta coluna"
                else:
                    classe, ev = "causa_nao_determinada", "sem PDF transcrito do período para conferir a causa"
                if classe == "causa_nao_determinada" and c in trocas:
                    classe, ev = "regra_de_classificacao", trocas[c] + " (padrão; empenho não atribuído)"
                celulas.append({**base, "comparacao": "elotech_x_siconfi", "coluna": c, "esperado": sic[c],
                                "observado": elo[c], "diferenca": dif, "classe": classe, "evidencia": ev})
            # D. panel x SICONFI, by groups
            if sic is not None and (ano, df) in cortes:
                r = painel.indicadores(ano, df)
                if r["disponivel"]:
                    g = siconfi.grupos(sic)
                    por_coluna = {x["coluna"]: x["classe"] for x in celulas if x["comparacao"] == "elotech_x_siconfi"
                                  and x["exercicio"] == ano and x["bimestre"] == bim}
                    for nome, cols in GRUPOS.items():
                        obs, esp = r["valores"][INDICADOR[nome]]["valor_c"], g[nome]
                        if obs is None or esp is None:
                            continue
                        dif = obs - esp
                        membros = {por_coluna.get(c) for c in cols}
                        if dif == 0:
                            classe = "concorda"
                        elif membros <= {"concorda"}:
                            classe = "causa_nao_determinada"     # the columns agree, the indicator does not
                        elif any(m is None or m.startswith("causa_nao_determinada") or m.endswith("_sem_causa")
                                 or m.endswith("_parcial") for m in membros):
                            classe = "causa_nao_determinada"
                        else:
                            classe = "+".join(sorted(m for m in membros if m != "concorda"))
                        celulas.append({**base, "comparacao": "painel_x_siconfi", "grupo": nome, "esperado": esp,
                                        "observado": obs, "diferenca": dif, "classe": classe,
                                        "com_ressalva": r["com_ressalva"]})
    # summaries
    resumo = defaultdict(lambda: {"celulas": 0, "concordam": 0, "explicadas": 0, "nao_determinadas": 0,
                                  "valor_nao_determinado_c": 0})
    residuos = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for x in celulas:
        s = resumo[(x["comparacao"], x["exercicio"])]
        s["celulas"] += 1
        if x["classe"] == "concorda":
            s["concordam"] += 1
        elif (x["classe"].startswith("causa_nao_determinada") or x["classe"].endswith("_sem_causa")
              or x["classe"].endswith("_parcial")):
            s["nao_determinadas"] += 1
            resto = abs(x.get("residuo", x["diferenca"]))      # only the part with no proven cause
            s["valor_nao_determinado_c"] += resto
            k = x.get("coluna") or x.get("grupo")
            residuos[(x["comparacao"], x["exercicio"])][k][0] += 1
            residuos[(x["comparacao"], x["exercicio"])][k][1] += resto
        else:
            s["explicadas"] += 1
    Path(a.saida_json).write_text(json.dumps({
        "derivacao": f.did, "normalizacao": f.nid, "siconfi": f.leitura.name, "regras_de_escopo": sorted(f.aplicadas),
        "celulas": celulas,
        "resumo": [{"comparacao": k[0], "exercicio": k[1], **v} for k, v in sorted(resumo.items())],
        "residuos": [{"comparacao": k[0], "exercicio": k[1], "por_coluna": {c: {"celulas": n, "valor_c": v}
                                                                          for c, (n, v) in cols.items()}}
                     for k, cols in sorted(residuos.items())]}, ensure_ascii=False, indent=1), encoding="utf-8")
    nomes = {"oficial_x_oficial": "PDF do portal × Siconfi (Executivo)", "elotech_x_pdf": "Elotech (RREO-COL v3) × PDF",
             "elotech_x_siconfi": "Elotech (escopo publicado) × Siconfi (Executivo)",
             "painel_x_siconfi": "Painel publicado × Siconfi (Executivo), por grupo"}
    md = ["# Matriz de concordância SICONFI × RREO × Elotech × painel", "",
          f"Gerada por `docs/audits/rreo/matriz_concordancia.py`: derivação {f.did} (normalização {f.nid}), leitura do "
          f"Siconfi `{f.leitura.name}`, regras de escopo do indicador publicado: {', '.join(sorted(f.aplicadas))}. "
          "Somente leitura; nenhuma diferença é ajustada. Diferença = observado − esperado.", ""]
    for comp, nome in nomes.items():
        md += [f"## {nome}", "", "| Exercício | Células | Concordam | Explicadas | Não determinadas | Valor não determinado |",
               "|---|---:|---:|---:|---:|---:|"]
        for (cp, ex), v in sorted(resumo.items()):
            if cp == comp:
                md.append(f"| {ex} | {v['celulas']} | {v['concordam']} | {v['explicadas']} | {v['nao_determinadas']} | "
                          f"{br(v['valor_nao_determinado_c'])} |")
        md.append("")
    md += ["## Resíduos não determinados por exercício e coluna (ou grupo)", "",
           "| Comparação | Exercício | Coluna/grupo | Células | Valor absoluto |", "|---|---|---|---:|---:|"]
    for (cp, ex), cols in sorted(residuos.items()):
        for c, (n, v) in sorted(cols.items()):
            md.append(f"| {nomes[cp]} | {ex} | {c} | {n} | {br(v)} |")
    classes = defaultdict(int)
    for x in celulas:
        classes[(x["comparacao"], x["classe"])] += 1
    md += ["", "## Classes das diferenças", "", "| Comparação | Classe | Células |", "|---|---|---:|"]
    for (cp, cl), n in sorted(classes.items()):
        md.append(f"| {nomes[cp]} | {cl} | {n} |")
    Path(a.saida_md).write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({k: sum(v["celulas"] for (cp, _), v in resumo.items() if cp == k) for k in nomes}))


if __name__ == "__main__":
    main()
