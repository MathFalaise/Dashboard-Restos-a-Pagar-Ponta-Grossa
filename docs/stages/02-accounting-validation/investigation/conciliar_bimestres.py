"""INVESTIGATION - stage 02. NOT production code.

Difference (API - RREO) of each column of Annex VII, bimester by bimester.
The tabs are derived from the SemTipo query by the confirmed rule
(Processados = proc>0; NaoProcessados = aproc>0), which matches 100% the
per-tab queries in the periods where all three were downloaded.
"""
from decimal import Decimal

from conciliar_rreo import D, br, carregar

RREO = {  # entity 1 (Prefeitura), extracted with extrair_rreo.py
    (2025, "2025-06-30", "3º bim, emit. 29/07/2025"): ("2.661.515,65", "24.993.694,85", "7.782.824,73", "-1.829,50", "15.861.840,64", "159.165.530,25", "122.855.255,76", "122.057.925,81", "1.829,50"),
    (2025, "2025-10-31", "5º bim, emit. 27/11/2025"): ("2.661.515,65", "24.993.694,85", "26.202.972,44", "50.874,75", "15.861.840,64", "159.165.530,25", "134.011.459,46", "132.855.286,20", "16.060.588,86"),
    (2025, "2025-12-31", "6º bim, emit. 30/01/2026"): ("2.661.515,65", "24.993.694,85", "26.203.738,11", "51.906,63", "15.861.840,64", "159.165.530,25", "136.380.158,67", "136.288.900,26", "20.763.209,97"),
    (2026, "2026-02-28", "1º bim, emit. 27/03/2026"): ("1.488.994,67", "16.227.940,86", "10.327.211,97", "72.595,82", "18.811.534,37", "121.593.126,88", "51.211.031,20", "46.909.034,63", "2.922.832,94"),
    (2026, "2026-04-30", "2º bim, emit. 29/05/2026"): ("1.490.824,17", "27.386.680,16", "22.302.820,20", "74.497,32", "18.809.704,87", "118.302.373,90", "71.354.135,05", "69.213.577,46", "3.424.282,51"),
    (2026, "2026-06-30", "3º bim, emit. 29/07/2026"): ("1.490.824,17", "27.386.680,16", "24.506.510,29", "78.361,84", "18.809.704,87", "118.302.373,90", "80.097.138,94", "77.764.383,26", "4.183.870,38"),
    (2026, "2026-08-31", "4º bim, emit. 29/09/2026"): ("1.490.824,17", "27.386.680,16", "25.557.330,59", "78.570,99", "18.809.704,87", "118.302.373,90", "85.599.108,05", "83.893.145,91", "8.015.744,44"),
}
COLS = "abcdfghij"


def api(ex, df):
    S = carregar(1, ex, f"{ex}-01-01", df, "SemTipo")
    P = [r for r in S if Decimal(r["proc"]) > 0]
    N = [r for r in S if Decimal(r["aproc"]) > 0]
    soP = [r for r in P if Decimal(r["aproc"]) == 0]
    s = lambda regs, c, f=lambda r: True: sum((Decimal(r[c]) for r in regs if f(r)), Decimal(0))
    return {
        "a": s(P, "proc", lambda r: r["anoempenho"] < ex - 1), "b": s(P, "proc", lambda r: r["anoempenho"] == ex - 1),
        "c": s(P, "pagoProc"), "d": s(soP, "canceladoAProc"),
        "f": s(N, "aproc", lambda r: r["anoempenho"] < ex - 1), "g": s(N, "aproc", lambda r: r["anoempenho"] == ex - 1),
        "h": s(N, "liquidado"), "i": s(N, "pagoAProc"), "j": s(N, "canceladoAProc"),
    }


print(f"{'período':34s} " + " ".join(f"{'dif (' + c + ')':>14s}" for c in COLS))
for (ex, df, rot), vals in RREO.items():
    a = api(ex, df)
    r = dict(zip(COLS, map(D, vals)))
    print(f"{ex} até {df} {rot:24s}"[:34].ljust(34) + " " + " ".join(f"{br(a[c] - r[c]):>14s}" for c in COLS))
