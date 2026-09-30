"""INVESTIGAÇÃO — Etapa 02. NÃO é código de produção.

Soma os campos da listagem de Restos a Pagar (páginas brutas já baixadas por
coletar.py) e compara com as colunas do RREO Anexo VII. Não assume
correspondência: imprime as somas candidatas ao lado do valor do RREO e a
diferença, para inspeção.
"""
import json
import sys
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / "dados_brutos" / "api"
CAMPOS = ["proc", "aproc", "canceladoProc", "pagoProc", "pagoProcEstornado", "canceladoAProc",
          "pagoAProc", "pagoAProcEstornado", "liquidado", "retencao"]


def carregar(ent, ex, di, df, tipo):
    regs, p = [], 0
    while True:
        arq = RAIZ / f"rp_ent{ent}_ex{ex}_{di}_a_{df}_{tipo}_p{p}.json"
        if not arq.exists():
            break
        # Decimal: soma exata dos valores como vieram no JSON
        regs += json.loads(arq.read_text(encoding="utf-8"), parse_float=Decimal)["content"]
        p += 1
    return regs


def somar(regs, filtro=lambda r: True):
    s = {c: Decimal(0) for c in CAMPOS}
    for r in regs:
        if filtro(r):
            for c in CAMPOS:
                s[c] += Decimal(r[c])
    return s


def br(v):
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def relatorio(ent, ex, di, df, rreo):
    anterior = ex - 1
    for tipo in ("Processados", "NaoProcessados"):
        regs = carregar(ent, ex, di, df, tipo)
        print(f"\n### ent={ent} ex={ex} {di}..{df} {tipo}: {len(regs)} registros")
        total = somar(regs)
        ult = somar(regs, lambda r: r["anoempenho"] == anterior)
        ant = somar(regs, lambda r: r["anoempenho"] < anterior)
        outros = [r for r in regs if r["anoempenho"] >= ex]
        print(f"   registros com anoempenho >= exercicio: {len(outros)}")
        print(f"   {'campo':20s} {'total':>18s} {'anoemp=' + str(anterior):>18s} {'anoemp<' + str(anterior):>18s}")
        for c in CAMPOS:
            print(f"   {c:20s} {br(total[c]):>18s} {br(ult[c]):>18s} {br(ant[c]):>18s}")
    print("\n   RREO:", {k: br(v) for k, v in rreo.items()})


def D(s):
    return Decimal(s.replace(".", "").replace(",", "."))


def comparar(ent, ex, di, df, rreo, rotulo):
    """Cada coluna do RREO contra a soma candidata da API. A regra de cada
    candidata está escrita ao lado; o resultado (diferença) é que diz se vale."""
    P = carregar(ent, ex, di, df, "Processados")
    N = carregar(ent, ex, di, df, "NaoProcessados")
    ant = ex - 1
    soP = [r for r in P if Decimal(r["aproc"]) == 0]
    cand = {
        "a": ("soma proc, aba Processados, anoempenho < ex-1", somar(P, lambda r: r["anoempenho"] < ant)["proc"]),
        "b": ("soma proc, aba Processados, anoempenho = ex-1", somar(P, lambda r: r["anoempenho"] == ant)["proc"]),
        "c": ("soma pagoProc, aba Processados", somar(P)["pagoProc"]),
        "d": ("soma canceladoAProc dos registros so-Processados (aproc=0)", somar(soP)["canceladoAProc"]),
        "f": ("soma aproc, aba NaoProcessados, anoempenho < ex-1", somar(N, lambda r: r["anoempenho"] < ant)["aproc"]),
        "g": ("soma aproc, aba NaoProcessados, anoempenho = ex-1", somar(N, lambda r: r["anoempenho"] == ant)["aproc"]),
        "h": ("soma liquidado, aba NaoProcessados", somar(N)["liquidado"]),
        "i": ("soma pagoAProc, aba NaoProcessados", somar(N)["pagoAProc"]),
        "j": ("soma canceladoAProc, aba NaoProcessados", somar(N)["canceladoAProc"]),
    }
    print(f"\n### {rotulo}  (API ent={ent} ex={ex} {di}..{df})")
    for col, (regra, v) in cand.items():
        dif = v - rreo[col]
        print(f"   ({col}) RREO {br(rreo[col]):>16s} | API {br(v):>16s} | dif {br(dif):>13s} {'OK' if dif == 0 else '  '} | {regra}")
    e = cand["a"][1] + cand["b"][1] - cand["c"][1] - cand["d"][1]
    k = cand["f"][1] + cand["g"][1] - cand["i"][1] - cand["j"][1]
    print(f"   (e) RREO {br(rreo['e']):>16s} | API (a+b)-(c+d) {br(e):>16s} | dif {br(e - rreo['e'])}")
    print(f"   (k) RREO {br(rreo['k']):>16s} | API (f+g)-(i+j) {br(k):>16s} | dif {br(k - rreo['k'])}")


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "todos":
    def R(*v):
        return dict(zip("abcdefghijk", map(D, v)))
    comparar(1, 2025, "2025-01-01", "2025-12-31",
             R("2.661.515,65", "24.993.694,85", "26.203.738,11", "51.906,63", "1.399.565,76", "15.861.840,64",
               "159.165.530,25", "136.380.158,67", "136.288.900,26", "20.763.209,97", "17.975.260,66"),
             "RREO 2025 6º bim (emitido 30/01/2026)")
    comparar(1, 2026, "2026-01-01", "2026-06-30",
             R("1.490.824,17", "27.386.680,16", "24.506.510,29", "78.361,84", "4.292.632,20", "18.809.704,87",
               "118.302.373,90", "80.097.138,94", "77.764.383,26", "4.183.870,38", "55.163.825,13"),
             "RREO 2026 3º bim (emitido 29/07/2026)")
    comparar(1, 2026, "2026-01-01", "2026-08-31",
             R("1.490.824,17", "27.386.680,16", "25.557.330,59", "78.570,99", "3.241.602,75", "18.809.704,87",
               "118.302.373,90", "85.599.108,05", "83.893.145,91", "8.015.744,44", "45.203.188,42"),
             "RREO 2026 4º bim (emitido 29/09/2026 12h33)")
    sys.exit()

if __name__ == "__main__":
    RREO_2025_ENT = dict(a=D("2.661.515,65"), b=D("24.993.694,85"), c=D("26.203.738,11"), d=D("51.906,63"),
                         e=D("1.399.565,76"), f=D("15.861.840,64"), g=D("159.165.530,25"),
                         h=D("136.380.158,67"), i=D("136.288.900,26"), j=D("20.763.209,97"),
                         k=D("17.975.260,66"))
    RREO_2026_4B_ENT = dict(a=D("1.490.824,17"), b=D("27.386.680,16"), c=D("25.557.330,59"), d=D("78.570,99"),
                            e=D("3.241.602,75"), f=D("18.809.704,87"), g=D("118.302.373,90"),
                            h=D("85.599.108,05"), i=D("83.893.145,91"), j=D("8.015.744,44"),
                            k=D("45.203.188,42"))
    alvo = sys.argv[1] if len(sys.argv) > 1 else "2025"
    if alvo == "2025":
        relatorio(1, 2025, "2025-01-01", "2025-12-31", RREO_2025_ENT)
    else:
        relatorio(1, 2026, "2026-01-01", "2026-08-31", RREO_2026_4B_ENT)
