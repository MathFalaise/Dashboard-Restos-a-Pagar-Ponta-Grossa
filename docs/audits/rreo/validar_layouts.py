"""Validation of the versioned layout rules (app/rp/rreo_layouts.py) on every RREO PDF the production extractor refuses
(corrective audit of 13/10/2026, item 6.5). READ-ONLY on the database and the store.

Each refused PDF is read by the layout rule (PyMuPDF word coordinates) and compared, cell by cell, with:
  1. the independent second reading by ANOTHER engine (xpdf pdftotext -table, conferencia_independente.ler);
  2. for the SICONFI prints, the structured SICONFI declaration of the same period (rows I, PODER EXECUTIVO, III).
The TRANSCRIPTION is validated by the second reading of the same document: 'validado' only when every cell read by the
rule equals the xpdf reading and xpdf covers every row the rule read. The SICONFI comparison is a CONTENT check (the
current declaration may be another version of the printed one): its differences are reported apart, as differences
between official documents, never as an extraction failure and never corrected. Anything else keeps the document
refused.

Usage (from the repository root):
    python docs/audits/rreo/validar_layouts.py --banco DB --saida-json OUT.json --saida-md OUT.md
"""
import argparse
import json
import shutil
import sqlite3
import sys
import zlib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "app"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from conferencia_independente import ler  # noqa: E402
from rp import siconfi  # noqa: E402
from rp.config import carregar  # noqa: E402
from rp.normalizar import LayoutDesconhecido  # noqa: E402
from rp import rreo_layouts  # noqa: E402

LINHA_SICONFI = {"RESTOS A PAGAR (EXCETO": "I", "PODER EXECUTIVO": "executivo", "TOTAL (III)": "III"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--banco", required=True)
    ap.add_argument("--saida-json", required=True)
    ap.add_argument("--saida-md", required=True)
    ap.add_argument("--pdftotext", default=shutil.which("pdftotext"))
    a = ap.parse_args()
    con = sqlite3.connect(f"file:{a.banco}?mode=ro", uri=True)
    armazem = carregar().snapshots
    nid = con.execute("SELECT MAX(id) FROM normalizacao_execucao").fetchone()[0]
    leitura = siconfi.leituras()[-1]
    docs = con.execute(
        "SELECT c.id, c.snapshot_uid, c.exercicio, c.parametros_json, r.sha256 FROM coleta c JOIN resposta_bruta r ON "
        "r.coleta_id = c.id WHERE c.tipo='rreo_pdf' AND c.status='completa' AND NOT EXISTS (SELECT 1 FROM rreo_valor v "
        "WHERE v.normalizacao_id=? AND v.coleta_id=c.id) ORDER BY c.exercicio, c.id", (nid,)).fetchall()
    saida = []
    for cid, uid, ex, params, sha in docs:
        corpo = zlib.decompress((armazem / "objetos" / sha[:2] / f"{sha}.zlib").read_bytes())
        item = {"snapshot": uid[:8], "exercicio": ex, "rotulo": json.loads(params).get("rotulo"), "sha256_pdf": sha}
        try:
            versao, escopo, ano, df, emitido, celulas = rreo_layouts.extrair(corpo, json.loads(params))
        except LayoutDesconhecido as e:
            item.update(situacao="continua_recusado", motivo=str(e))
            saida.append(item)
            continue
        segunda, periodo2, problemas2, _ = ler(a.pdftotext, corpo)
        bim = int(df[5:7]) // 2
        dec = siconfi.declaracao(leitura, ano, bim) if versao == rreo_layouts.VERSAO_SICONFI else None
        conferidas, divergentes, sem_fonte, conteudo = 0, [], [], []
        for (linha, col), v in sorted(celulas.items()):
            if linha not in segunda:
                sem_fonte.append(f"{linha} ({col})")
            else:
                conferidas += 1
                if segunda[linha][col] != v:
                    divergentes.append({"linha": linha, "coluna": col, "regra": v, "xpdf": segunda[linha][col]})
            if dec and linha in LINHA_SICONFI and LINHA_SICONFI[linha] in dec["linhas"]:
                w = dec["linhas"][LINHA_SICONFI[linha]].get(col)
                if w != v:
                    conteudo.append({"linha": linha, "coluna": col, "pdf": v, "siconfi": w})
        linhas_sem_fonte = sorted({x.split(" (")[0] for x in sem_fonte})
        ok = not divergentes and not sem_fonte and conferidas > 0
        item.update(versao=versao, escopo=escopo, data_final=df, emitido_em=emitido, celulas=len(celulas),
                    conferidas=conferidas, divergentes=divergentes, linhas_sem_fonte_independente=linhas_sem_fonte,
                    segunda_leitura_problemas=problemas2, siconfi=(dec or {}).get("arquivo"),
                    diferencas_de_conteudo_com_o_siconfi=conteudo,
                    situacao="validado" if ok else "divergente")
        saida.append(item)
    Path(a.saida_json).write_text(json.dumps({"normalizacao": nid, "documentos": saida}, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
    md = ["# Validação das regras de layout do RREO (2016 e impressões do Siconfi)", "",
          "Gerada por `docs/audits/rreo/validar_layouts.py`: cada PDF recusado pelo extrator de produção é lido pela regra "
          "de layout versionada (PyMuPDF) e comparado, célula a célula, com a segunda leitura (xpdf `pdftotext -table`) e, "
          "nas impressões do Siconfi, com a declaração estruturada do mesmo período.", "",
          "| Exercício | Documento | Snapshot | Regra | Escopo | Corte | Células | Conferidas (xpdf) | Divergentes (xpdf) | Linhas sem segunda leitura | Diferenças de conteúdo com o Siconfi | Situação |",
          "|---|---|---|---|---|---|---:|---:|---:|---|---:|---|"]
    for x in saida:
        md.append(f"| {x['exercicio']} | {x['rotulo']} | {x['snapshot']} | {x.get('versao', '—')} | {x.get('escopo', '—')} | "
                  f"{x.get('data_final', '—')} | {x.get('celulas', '—')} | {x.get('conferidas', '—')} | "
                  f"{len(x.get('divergentes', []))} | {', '.join(x.get('linhas_sem_fonte_independente', [])) or '—'} | "
                  f"{len(x.get('diferencas_de_conteudo_com_o_siconfi', []))} | "
                  f"{x['situacao']}{(': ' + x['motivo']) if x.get('motivo') else ''} |")
    Path(a.saida_md).write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({s: sum(1 for x in saida if x["situacao"] == s) for s in ("validado", "divergente",
                                                                            "continua_recusado")}))


if __name__ == "__main__":
    main()
