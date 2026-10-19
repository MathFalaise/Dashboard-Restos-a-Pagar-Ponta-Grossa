"""Figures of NOTA_RP_2025.md: why the RP inscribed at the opening of 2025 grew 53.2% over 2024.

Read-only. Sources:
  * the active database (API listings, normalization given by --normalizacao): the latest complete listing of each
    entity at 31/12 of each exercise; entity 7 (ARAS, outside the Municipality since 2021) and the 24xxxxx copies of
    entity 1 (COPIA-ORIGEM v1, outside the indicator before 2026) are left out, as in the published panel;
  * the public RGF Annex 5 files (3rd four-month period, Executive) in docs/audits/rreo/rgf/raw_20261015, each checked
    against the SHA-256 of its manifest.

Usage (from the repository root):
  python docs/audits/rreo/nota_rp_2025.py --banco DB [--normalizacao 18] [--saida-json OUT.json]
"""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

RGF = Path(__file__).resolve().parent / "rgf" / "raw_20261015"
FONTE_FINISA_IV = "632"


def br(c):
    return f"{c / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class Base:
    def __init__(self, banco, nid):
        self.con = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
        self.nid = nid

    def coletas(self, ex, df):
        return [r[0] for r in self.con.execute(
            "SELECT MAX(id) FROM coleta WHERE tipo='rp_listagem' AND tipo_pesquisa IS NULL AND status='completa' "
            "AND exercicio=? AND data_final=? AND entidade<>7 GROUP BY entidade", (ex, df))]

    def soma(self, ex, df, expr, filtro="", params=()):
        ids = self.coletas(ex, df)
        q = ",".join("?" * len(ids))
        return self.con.execute(
            f"SELECT COALESCE(SUM({expr}), 0) FROM rp_registro WHERE normalizacao_id=? AND coleta_id IN ({q}) "
            f"AND NOT (entidade=1 AND empenho>=2400000 AND ?<2026) {filtro}",
            [self.nid, *ids, ex, *params]).fetchone()[0]


def rgf(ano):
    man = json.loads((RGF / "manifest.json").read_text(encoding="utf-8"))["arquivos"]
    nome = f"rgf05_{ano}_Q3.json"
    corpo = (RGF / nome).read_bytes()
    if hashlib.sha256(corpo).hexdigest() != man[nome]["sha256"]:
        raise ValueError(f"{nome}: SHA-256 differs from the manifest")
    linhas = {}
    for i in json.loads(corpo)["items"]:
        col = i["coluna"]
        chave = ("caixa_bruta" if col.startswith("DISPONIBILIDADE DE CAIXA BRUTA") else
                 "processados_do_exercicio" if col.startswith("Do Exercício") else
                 "rpnp_do_exercicio" if col.startswith("RESTOS A PAGAR EMPENHADOS E N") else
                 "liquida_apos_rpnp" if "APÓS A INSCRIÇÃO" in col else None)
        if chave:
            linhas.setdefault(i["conta"], {})[chave] = round(i["valor"] * 100)
    return linhas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--banco", required=True)
    ap.add_argument("--normalizacao", type=int, default=18)
    ap.add_argument("--saida-json")
    a = ap.parse_args()
    b = Base(a.banco, a.normalizacao)
    insc = "proc_c + aproc_c"
    out = {"series": {}, "novos": {}}
    for ex in range(2017, 2026):
        df = f"{ex}-12-31"
        novos = b.soma(ex, df, insc, "AND anoempenho=?", (ex - 1,))
        mai_dez = b.soma(ex, df, insc, "AND anoempenho=? AND substr(data_emissao,6,2)>='05'", (ex - 1,))
        out["series"][ex] = {"inscricao": b.soma(ex, df, insc), "novos": novos, "novos_emitidos_mai_dez": mai_dez}
    for ex in (2024, 2025):
        df, ano = f"{ex}-12-31", ("AND anoempenho=?", (ex - 1,))
        f632 = b.soma(ex, df, insc, ano[0] + " AND fonte_recurso=?", ano[1] + (FONTE_FINISA_IV,))
        pessoal = b.soma(ex, df, insc, ano[0] + " AND elemento LIKE '31%'", ano[1])
        out["novos"][ex] = {"total": out["series"][ex]["novos"], "finisa_iv_fonte_632": f632, "pessoal_31": pessoal,
                            "processados": b.soma(ex, df, "proc_c", *ano),
                            "nao_processados": b.soma(ex, df, "aproc_c", *ano)}
    fundeb = ("AND anoempenho=2024 AND elemento='3190110000' AND fonte_recurso='101' "
              "AND substr(data_emissao,1,7)='2024-12'")
    out["folha_fundeb_dez_2024"] = {
        "inscricao": b.soma(2025, "2025-12-31", insc, fundeb),
        "processados": b.soma(2025, "2025-12-31", "proc_c", fundeb),
        "pago_ate": {df: b.soma(2025, df, "pago_proc_c + pago_aproc_c", fundeb)
                     for df in ("2025-02-28", "2025-08-31", "2025-10-31", "2025-12-31")}}
    out["finisa_iv_em_2025"] = {
        "pago": b.soma(2025, "2025-12-31", "pago_proc_c + pago_aproc_c", "AND anoempenho=2024 AND fonte_recurso=?",
                       (FONTE_FINISA_IV,)),
        "cancelado": b.soma(2025, "2025-12-31", "cancelado_proc_c + cancelado_aproc_c",
                            "AND anoempenho=2024 AND fonte_recurso=?", (FONTE_FINISA_IV,))}
    out["rgf"] = {ano: rgf(ano) for ano in (2020, 2023, 2024)}

    s = out["series"]
    print("inscricao na abertura, sem a entidade 7:", {ex: br(v["inscricao"]) for ex, v in s.items()})
    print("RP novos emitidos mai-dez:", {ex - 1: f"{v['novos_emitidos_mai_dez'] / v['novos']:.1%}" for ex, v in s.items()})
    for ex, v in out["novos"].items():
        print(f"novos {ex}:", {k: br(x) for k, x in v.items()})
    print("folha Fundeb dez/2024:", br(out["folha_fundeb_dez_2024"]["inscricao"]),
          {k: br(x) for k, x in out["folha_fundeb_dez_2024"]["pago_ate"].items()})
    print("FINISA IV em 2025:", {k: br(x) for k, x in out["finisa_iv_em_2025"].items()})
    for ano, linhas in out["rgf"].items():
        tot = next(v for k, v in linhas.items() if k.startswith("TOTAL (I"))
        print(f"RGF {ano} total:", {k: br(x) for k, x in tot.items()})
    if a.saida_json:
        Path(a.saida_json).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
