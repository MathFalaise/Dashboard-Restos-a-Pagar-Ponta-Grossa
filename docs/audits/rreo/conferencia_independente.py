"""Independent check of the RREO Annex VII transcription and coverage matrix (correction request of 09/10/2026, item 6).

READ-ONLY on the database. It does not use the production extractor: each collected PDF is read again by ANOTHER
engine - xpdf's `pdftotext -table` (production uses PyMuPDF/MuPDF word coordinates) - and every transcribed cell is
compared with this second reading. The document's own identities (e = a + b - c - d, k = f + g - i - j, L = e + k,
TOTAL = (I) + (II)) are checked on the second reading too. What it is NOT: a check of the accounting itself - it only
says the numbers in the database are the numbers printed in the PDF.

Usage (from the repository root):
    python docs/audits/rreo/conferencia_independente.py --banco DB --saida-json OUT.json --saida-md OUT.md
    [--pdftotext PATH]   (default: `pdftotext` on PATH; xpdf 4.06 was used on 09/10/2026)
"""
import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "app"))
from rp import rreo_cobertura  # noqa: E402

COLUNAS = "abcdefghijkL"
LINHAS = (("RESTOS A PAGAR (EXCETO", "RESTOS A PAGAR (EXCETO"), ("PODER EXECUTIVO", "PODER EXECUTIVO"),
          ("RESTOS A PAGAR (INTRA", "RESTOS A PAGAR (INTRA"), ("TOTAL (III)", "TOTAL (III)"))
NUM = re.compile(r"-?\d{1,3}(?:\.\d{3})*,\d{2}")


def _centavos(w):
    """'-1.234,56' -> -123456 (the sign stays in front)."""
    return int(w.replace(".", "").replace(",", ""))


def ler(pdftotext, pdf_bytes):
    """Second reading: {line: {column: cents}} of the rows with exactly 12 numbers, + period text and problems."""
    with tempfile.TemporaryDirectory() as d:
        arq = Path(d) / "rreo.pdf"
        arq.write_bytes(pdf_bytes)
        r = subprocess.run([pdftotext, "-table", "-enc", "UTF-8", str(arq), "-"], capture_output=True, timeout=120)
    texto = r.stdout.decode("utf-8", "replace")
    linhas, problemas = {}, []
    for bruta in texto.splitlines():
        s = bruta.strip()
        nome = next((n for p, n in LINHAS if s.startswith(p)), None)
        if not nome:
            continue
        nums = NUM.findall(s)
        if not nums:            # a title or header with the same words (e.g. "PODER EXECUTIVO" on top of the page)
            continue
        if len(nums) != 12:
            problemas.append(f"{nome}: {len(nums)} número(s) na segunda leitura")
            continue
        valores = {c: _centavos(w) for c, w in zip(COLUNAS, nums)}
        if nome in linhas and linhas[nome] != valores:
            problemas.append(f"{nome}: impressa duas vezes com valores diferentes")
        linhas.setdefault(nome, valores)
    m = re.search(r"JANEIRO A ([A-ZÇ]+) (\d)\.(\d{3})", texto)
    return linhas, (f"{m.group(1)} {m.group(2)}{m.group(3)}" if m else None), problemas, r.returncode


def identidades(linhas):
    falhas = []
    for nome, v in linhas.items():
        for rotulo, ok in (("e = a + b - c - d", v["e"] == v["a"] + v["b"] - v["c"] - v["d"]),
                           ("k = f + g - i - j", v["k"] == v["f"] + v["g"] - v["i"] - v["j"]),
                           ("L = e + k", v["L"] == v["e"] + v["k"])):
            if not ok:
                falhas.append(f"{nome}: {rotulo}")
    if "TOTAL (III)" in linhas and "RESTOS A PAGAR (EXCETO" in linhas:
        intra = linhas.get("RESTOS A PAGAR (INTRA", {})
        if any(linhas["TOTAL (III)"][c] != linhas["RESTOS A PAGAR (EXCETO"][c] + intra.get(c, 0) for c in COLUNAS):
            falhas.append("TOTAL (III) diferente de (I) + (II)")
    return falhas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--banco", required=True)
    ap.add_argument("--saida-json", required=True)
    ap.add_argument("--saida-md", required=True)
    ap.add_argument("--pdftotext", default=shutil.which("pdftotext"))
    a = ap.parse_args()
    if not a.pdftotext:
        sys.exit("pdftotext não encontrado: informe --pdftotext")
    versao = subprocess.run([a.pdftotext, "-v"], capture_output=True, text=True)
    versao = (versao.stdout + versao.stderr).strip().splitlines()[0]
    con = sqlite3.connect(f"file:{Path(a.banco).resolve()}?mode=ro", uri=True)
    nid = con.execute("SELECT MAX(id) FROM normalizacao_execucao").fetchone()[0]
    cob = rreo_cobertura.matriz(con, nid)
    for d in cob["documentos"]:
        d["conferencia"] = None
        if d["snapshot"] is None:
            continue
        cid, sha = con.execute("SELECT k.id, r.sha256 FROM coleta k JOIN resposta_bruta r ON r.coleta_id = k.id WHERE "
                               "k.snapshot_uid=?", (d["snapshot"],)).fetchone()
        pdf = zlib.decompress(con.execute("SELECT dados FROM objeto_bruto WHERE sha256=?", (sha,)).fetchone()[0])
        assert hashlib.sha256(pdf).hexdigest() == sha
        linhas, periodo, problemas, rc = ler(a.pdftotext, pdf)
        conf = {"pdf_sha256": sha, "periodo_impresso": periodo, "linhas_lidas": sorted(linhas),
                "identidades_que_falham": identidades(linhas), "problemas_da_leitura": problemas}
        producao = {(l, c): v for l, c, v in con.execute("SELECT linha, coluna, valor_c FROM rreo_valor WHERE "
                                                         "normalizacao_id=? AND coleta_id=?", (nid, cid))}
        if d["situacao"] == "transcrito":
            difs = [f"{l} ({c}): produção {producao.get((l, c))} x leitura independente {v}"
                    for l, vs in linhas.items() for c, v in vs.items() if producao.get((l, c)) != v]
            so_producao = [f"{l} ({c})" for (l, c) in producao if c not in linhas.get(l, {})]
            conf.update({"celulas_da_producao": len(producao), "celulas_comparadas": len(producao) - len(so_producao),
                         "diferencas": difs, "so_na_producao": so_producao})
            ok = (not difs and not so_producao and not conf["identidades_que_falham"] and not problemas and
                  "TOTAL (III)" in linhas)
            conf["resultado"] = "conferido" if ok else "divergente"
        else:
            conf["resultado"] = "lido_so_pela_conferencia" if linhas else "nao_legivel_pela_conferencia"
            conf["linhas"] = {l: v for l, v in linhas.items() if l in ("TOTAL (III)", "RESTOS A PAGAR (EXCETO")}
        d["conferencia"] = conf
    resumo = dict(cob["resumo"])
    resumo["conferidos"] = sum(1 for d in cob["documentos"] if (d["conferencia"] or {}).get("resultado") == "conferido")
    resumo["divergentes"] = sum(1 for d in cob["documentos"] if (d["conferencia"] or {}).get("resultado") == "divergente")
    # file name only: no local path in the repository
    saida = {"gerado_com": versao, "banco": Path(a.banco).name, "normalizacao": nid, "resumo": resumo,
             "por_exercicio": cob["por_exercicio"], "documentos": cob["documentos"]}
    Path(a.saida_json).write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
    Path(a.saida_md).write_text(_markdown(saida), encoding="utf-8")
    print(json.dumps(resumo, ensure_ascii=False))


def _markdown(s):
    r = s["resumo"]
    out = ["# Matriz de cobertura e conferência independente do RREO Anexo VII", "",
           f"Gerada por `docs/audits/rreo/conferencia_independente.py` (segunda leitura: {s['gerado_com']}; "
           f"normalização {s['normalizacao']}).", "",
           f"Esperados {r['esperados']} · transcritos {r['transcrito']} (conferidos {r['conferidos']}, divergentes "
           f"{r['divergentes']}) · recusados pelo extrator {r['recusado_layout']} · não coletados {r['nao_coletado']}"
           f" · coletados sem extração {r['coletado_sem_extracao']}", "",
           "| Exercício | Documento | Escopo | Situação | Conferência independente | Observação |", "|---|---|---|---|---|---|"]
    for d in sorted(s["documentos"], key=lambda d: (d["exercicio"], d["bimestre"] or 0, d["escopo"], str(d["rotulo"]))):
        c = d["conferencia"] or {}
        obs = ""
        if d["situacao"] == "recusado_layout":
            obs = f"{d['motivo']}; segunda leitura: identidades {'ok' if not c.get('identidades_que_falham') else 'falham'}" \
                  f", período impresso: {c.get('periodo_impresso') or 'não impresso'}"
        elif c.get("resultado") == "divergente":
            obs = "; ".join((c.get("diferencas") or []) + (c.get("so_na_producao") or []) + (c.get("problemas_da_leitura") or []))[:300]
        out.append(f"| {d['exercicio']} | {d['rotulo']} | {d['escopo']} | {d['situacao']} | {c.get('resultado', '—')} | {obs} |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    main()
