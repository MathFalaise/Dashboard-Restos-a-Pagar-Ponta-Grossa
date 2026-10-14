"""Entity 7 (ARAS) in each official statement, period by period (corrective audit of 13/10/2026, item 5.2). READ-ONLY.

For every bimester with an official consolidated statement it answers one question: does the statement include the
four RP of entity 7? The test uses only the INSCRIPTION columns (a + b + f + g), which payments, cancellations and
backdated entries do not move:

    residual = statement(a+b+f+g) - Elotech Municipality WITHOUT entity 7 (a+b+f+g)

  * residual == entity 7's inscription, to the cent  -> the statement INCLUDES it (proven);
  * residual == 0, to the cent                        -> the statement EXCLUDES it (proven);
  * anything else                                     -> not determined by this statement (other differences mask it).

Statements: the SICONFI declaration (PODER EXECUTIVO row, the same scope as the Elotech source) of the newest reading in
docs/audits/rreo/siconfi/raw, and the consolidated RREO PDF of the portal transcribed in the database (TOTAL (III)).
Elotech side: the derivation's per-entity view with RREO-COL v3 (visao_valor), entity 7 subtracted from the published
Municipality up to 2020 (ESCOPO-MUN v1 includes it there) - the same numbers the panel uses.

The period decision (ESCOPO-MUN v2 parameters) follows a fixed order, written down before looking at any total:
  1. SICONFI proves the scope                                -> follow it ("comprovado");
  2. SICONFI does not, the portal PDF does                   -> follow the PDF ("comprovado pelo RREO do portal");
  3. both prove and disagree                                 -> follow SICONFI, the declaration with legal effect
                                                                (LRF art. 48 and 51), flagged "contraditorio";
  4. neither proves: the treatment whose residual is smaller in absolute value, flagged "provavel" when that residual
     is under 5% of entity 7's inscription, otherwise ESCOPO-MUN v1's treatment kept, flagged "inconclusivo".

Usage (from the repository root):
    python docs/audits/escopo/escopo_entidade7.py --banco DB --derivacao N --saida-json OUT.json --saida-md OUT.md
"""
import argparse
import calendar
import json
import re
import sqlite3
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
SICONFI = RAIZ / "docs" / "audits" / "rreo" / "siconfi" / "raw"
INSCRICAO = "abfg"
ENTIDADE = 7
ROTULOS_2016 = {   # 2016 SICONFI labels (older layout), inscription columns only
    "RPP e RPNP Liquidados em Exercícios Anteriores - Inscritos Em Exercícios Anteriores": "a",
    "RPP e RPNP Liquidados em Exercícios Anteriores - Inscritos Em 31 de Dezembro de 2015": "b",
    "RPNP - Inscritos Em Exercícios Anteriores": "f",
    "RPNP - Inscritos Em 31 de Dezembro de 2015": "g",
    "Saldo (a)": "e",          # in 2016 "(a)" and "(b)" name the two BALANCES, not columns a and b
    "Saldo (b)": "k",
}
LIMIAR_PROVAVEL = Decimal("0.05")
PRIMEIRO_ANO_PARES = 2026      # COPIA-ORIGEM v1 primeiro_exercicio: from here the copies are inside the indicator


def leitura_siconfi():
    """Folder of the newest SICONFI reading (raw/coleta_*), or raw/ itself (first reading)."""
    coletas = sorted(SICONFI.glob("coleta_*"))
    return coletas[-1] if coletas else SICONFI


def siconfi(pasta, ano, bim):
    f = pasta / f"rreo_anexo07_{ano}_{bim}.json"
    if not f.exists():
        return None, None
    v = {}
    for i in json.loads(f.read_text(encoding="utf-8"))["items"]:
        if not i["conta"].startswith("PODER EXECUTIVO"):
            continue
        col = ROTULOS_2016.get(i["coluna"])
        if col is None:
            m = re.search(r"\(([a-j])\)\s*$", i["coluna"])
            col = m.group(1) if m else None
        if col is not None and col in INSCRICAO:
            v[col] = int((Decimal(str(i["valor"])) * 100).to_integral_value())
    if not v:
        return None, f.name
    return sum(v.get(c, 0) for c in INSCRICAO), f.name     # SICONFI omits a zero item


def visao(con, did, ent, ex, df, visao_nome="entidade", consolidacao=None):
    """RREO-COL v3 inscription (a+b+f+g) of a derived view. `consolidacao` = (codigo, versao) of the analytical view
    (from 2026 the 1 <-> 15 pairs are counted once in the Municipality by CONS-PAR v4, as SICONFI does)."""
    q = ("SELECT SUM(valor_c) FROM visao_valor WHERE derivacao_id=? AND visao=? AND regra_agregacao_id=("
         "SELECT id FROM regra WHERE codigo='RREO-COL' AND versao=3) AND exercicio=? AND data_final=? AND "
         f"componente IN ({','.join('?' * len(INSCRICAO))}) AND "
         + ("regra_consolidacao_id IS NULL AND " if consolidacao is None else
            "regra_consolidacao_id=(SELECT id FROM regra WHERE codigo=? AND versao=?) AND ")
         + ("entidade IS NULL" if ent is None else "entidade=?"))
    p = ([did, visao_nome, ex, df, *INSCRICAO] + ([] if consolidacao is None else list(consolidacao))
         + ([] if ent is None else [ent]))
    return con.execute(q, p).fetchone()[0]


def pdfs(con, nid, ex, df):
    saida = []
    for cid, uid in con.execute(
            "SELECT DISTINCT v.coleta_id, c.snapshot_uid FROM rreo_valor v JOIN coleta c ON c.id=v.coleta_id WHERE "
            "v.normalizacao_id=? AND v.exercicio=? AND v.data_final=? AND v.escopo='consolidado' AND "
            "v.linha='TOTAL (III)'", (nid, ex, df)):
        v = dict(con.execute("SELECT coluna, valor_c FROM rreo_valor WHERE normalizacao_id=? AND coleta_id=? AND "
                             "linha='TOTAL (III)'", (nid, cid)))
        if all(c in v for c in INSCRICAO):
            saida.append((uid, sum(v[c] for c in INSCRICAO)))
    return saida


def classificar(residual, e7):
    if residual == e7:
        return "inclui"
    if residual == 0:
        return "exclui"
    return None


def decidir(sic, pdf, e7, sem, inscricao_sic, ate_v1, ex):
    v1 = "inclui" if ex <= ate_v1 else "exclui"
    if sic and pdf and sic != pdf:
        return sic, "contraditorio"
    if sic:
        return sic, "comprovado"
    if pdf:
        return pdf, "comprovado pelo RREO do portal"
    if inscricao_sic is None or not e7:
        return v1, "inconclusivo"
    r_exc, r_inc = inscricao_sic - sem, inscricao_sic - sem - e7
    melhor, resto = ("exclui", r_exc) if abs(r_exc) < abs(r_inc) else ("inclui", r_inc)
    if Decimal(abs(resto)) < LIMIAR_PROVAVEL * e7:
        return melhor, "provavel"
    return v1, "inconclusivo"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--banco", required=True)
    ap.add_argument("--derivacao", type=int, required=True)
    ap.add_argument("--saida-json", required=True)
    ap.add_argument("--saida-md", required=True)
    a = ap.parse_args()
    con = sqlite3.connect(f"file:{a.banco}?mode=ro", uri=True)
    nid = con.execute("SELECT normalizacao_id FROM derivacao_execucao WHERE id=?", (a.derivacao,)).fetchone()[0]
    ate_v1 = json.loads(con.execute(
        "SELECT p.valor_json FROM regra_parametro p JOIN regra r ON r.id=p.regra_id WHERE r.codigo='ESCOPO-MUN' AND "
        "r.versao=1 AND p.nome='ate_exercicio'").fetchone()[0])
    pasta = leitura_siconfi()
    linhas = []
    for ano in range(2016, 2027):
        for bim in range(1, 7):
            df = f"{ano}-{2 * bim:02d}-{calendar.monthrange(ano, 2 * bim)[1]:02d}"
            e7 = visao(con, a.derivacao, ENTIDADE, ano, df)
            pub = (visao(con, a.derivacao, None, ano, df, "analitico", ("CONS-PAR", 4)) if ano >= PRIMEIRO_ANO_PARES
                   else visao(con, a.derivacao, None, ano, df, "publicado"))
            if e7 is None or pub is None:
                continue
            sem = pub - e7 if ano <= ate_v1 else pub
            insc_sic, arq = siconfi(pasta, ano, bim)
            r_sic = None if insc_sic is None else insc_sic - sem
            c_sic = None if r_sic is None else classificar(r_sic, e7)
            docs = [(uid, v - sem) for uid, v in pdfs(con, nid, ano, df)]
            c_pdfs = {classificar(r, e7) for _, r in docs} - {None}
            c_pdf = c_pdfs.pop() if len(c_pdfs) == 1 else None
            trat, sit = decidir(c_sic, c_pdf, e7, sem, insc_sic, ate_v1, ano)
            linhas.append({"exercicio": ano, "bimestre": bim, "data_final": df, "inscricao_entidade_7_c": e7,
                           "siconfi": {"arquivo": arq, "residual_c": r_sic, "classe": c_sic},
                           "rreo_portal": [{"snapshot": u[:8], "residual_c": r, "classe": classificar(r, e7)}
                                           for u, r in docs],
                           "tratamento": trat, "situacao": sit, "v1": "inclui" if ano <= ate_v1 else "exclui"})
    Path(a.saida_json).write_text(json.dumps({"derivacao": a.derivacao, "normalizacao": nid,
                                              "siconfi": str(pasta.relative_to(RAIZ).as_posix()), "periodos": linhas},
                                             ensure_ascii=False, indent=1), encoding="utf-8")
    br = lambda c: "—" if c is None else f"{c / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    md = ["# Entidade 7 (ARAS) em cada demonstrativo oficial", "",
          f"Gerado por `docs/audits/escopo/escopo_entidade7.py` sobre a derivação {a.derivacao} (normalização {nid}) e "
          f"a leitura do Siconfi `{pasta.relative_to(RAIZ).as_posix()}`. Teste pelas colunas de inscrição (a+b+f+g): "
          "resíduo = demonstrativo − Município da fonte Elotech sem a entidade 7.", "",
          "| Exercício | Bim. | Inscrição ent. 7 | Resíduo Siconfi | Siconfi | RREO do portal | v1 | Tratamento (v2) | Situação |",
          "|---|---|---:|---:|---|---|---|---|---|"]
    for x in linhas:
        portal = "; ".join(f"{d['snapshot']}: {d['classe'] or 'indeterminado (' + br(d['residual_c']) + ')'}"
                           for d in x["rreo_portal"]) or "sem PDF transcrito"
        md.append(f"| {x['exercicio']} | {x['bimestre']}º | {br(x['inscricao_entidade_7_c'])} | "
                  f"{br(x['siconfi']['residual_c'])} | {x['siconfi']['classe'] or 'indeterminado'} | {portal} | "
                  f"{x['v1']} | {x['tratamento']} | {x['situacao']} |")
    Path(a.saida_md).write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
