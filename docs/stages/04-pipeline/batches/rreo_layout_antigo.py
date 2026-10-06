"""INVESTIGACAO (nao e extrator de producao): le a linha TOTAL (III) dos PDFs de RREO que o extrator
`rp-rreo-coordenadas/1` nao reconhece (layouts de 2016, 2018 e 2019) e compara com a API.

Metodo: texto do PDF (pymupdf), a partir do rotulo "TOTAL (III)", os 12 primeiros valores numericos
("-" = 0) na ordem a..L, conferidos pelas identidades do proprio demonstrativo (e = a+b-c-d;
k = f+g-i-j; L = e+k). Se as identidades nao fecharem, a leitura e recusada, nunca ajustada.
O escopo (entidade 1 ou consolidado) e decidido pelo conteudo: se lista fundacoes/autarquias como
orgaos, e o Municipio. Somente leitura: nada e gravado no banco.
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "app"))
import pymupdf  # noqa: E402

from rp import banco  # noqa: E402
from rp.config import carregar  # noqa: E402

COLS = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "L"]
NUM = re.compile(r"^-?[\d.]+,\d{2}$|^-$")


def br(c):
    return f"{c / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def ler(texto):
    i = texto.find("TOTAL (III)")
    if i < 0:
        return None, "rótulo TOTAL (III) ausente"
    vals = []
    for tok in texto[i:].split("\n")[1:]:
        tok = tok.strip()
        if NUM.match(tok):
            vals.append(0 if tok == "-" else int(tok.replace(".", "").replace(",", "")))
            if len(vals) == 12:
                break
    if len(vals) < 12:
        return None, f"só {len(vals)} valores após TOTAL (III)"
    v = dict(zip(COLS, vals))
    ok = (v["e"] == v["a"] + v["b"] - v["c"] - v["d"] and v["k"] == v["f"] + v["g"] - v["i"] - v["j"]
          and v["L"] == v["e"] + v["k"])
    return (v if ok else None), ("identidades e/k/L conferem" if ok else f"identidades NÃO conferem: {v}")


def main():
    con = sqlite3.connect(f"file:{carregar().banco}?mode=ro", uri=True)
    nid = con.execute("SELECT MAX(id) FROM normalizacao_execucao").fetchone()[0]
    did = con.execute("SELECT MAX(id) FROM derivacao_execucao WHERE vigencia_em IS NULL").fetchone()[0]
    rg = {(c, v): i for i, c, v in con.execute("SELECT id, codigo, versao FROM regra")}
    falhos = con.execute("SELECT c.id, c.exercicio, c.parametros_json FROM coleta c WHERE c.tipo='rreo_pdf' AND c.status='completa' "
                         "AND NOT EXISTS (SELECT 1 FROM rreo_valor v WHERE v.normalizacao_id=? AND v.coleta_id=c.id) ORDER BY 2", (nid,)).fetchall()
    for cid, ex, pj in falhos:
        p = json.loads(pj)
        (sha,) = con.execute("SELECT sha256 FROM resposta_bruta WHERE coleta_id=? ORDER BY ordem LIMIT 1", (cid,)).fetchone()
        doc = pymupdf.open(stream=banco.corpo(con, sha), filetype="pdf")
        texto = "\n".join(pg.get_text() for pg in doc)
        municipio = bool(re.search(r"Funda[cç][aã]o|Autarquia|Instituto", texto, re.I))
        emitido = re.search(r"(\d{2}/\d{2}/\d{4} \d{2}:\d{2})", texto)
        periodo = re.search(r"JANEIRO\s+[AÁ]\s+([A-ZÇ]+)\s+([\d.]+)", texto)
        v, nota = ler(texto)
        print(f"\n### {ex} — {p['rotulo']} (coleta {cid}, arquivo {p['id_arquivo']}, páginas {len(doc)})")
        print(f"- período impresso: {periodo.group(0) if periodo else '—'}; emitido: {emitido.group(1) if emitido else '—'}; "
              f"escopo pelo conteúdo: {'consolidado (lista fundações/autarquias)' if municipio else 'entidade 1'}")
        print(f"- leitura: {nota}")
        if not v:
            continue
        df = f"{ex}-12-31"
        for vagg in (1, 2):
            q = "visao='publicado'" if municipio else "visao='entidade' AND entidade=1"
            api = dict(con.execute(f"SELECT componente, valor_c FROM visao_valor WHERE derivacao_id=? AND {q} AND regra_agregacao_id=? "
                                   "AND exercicio=? AND data_final=?", (did, rg[("RREO-COL", vagg)], ex, df)))
            if not api:
                print(f"- RREO-COL v{vagg}: sem visão da API para o corte"); continue
            difs = [(c, api[c] - v[c]) for c in COLS if api[c] != v[c]]
            print(f"- RREO-COL v{vagg}: {12 - len(difs)}/12 iguais; " + ("; ".join(f"({c}) {br(d)}" for c, d in difs) or "**todas iguais**"))
        print("- valores lidos: " + "; ".join(f"({c}) {br(v[c])}" for c in COLS))


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="backslashreplace")   # saida em cp1252 (arquivo) nao derruba o script
    main()
