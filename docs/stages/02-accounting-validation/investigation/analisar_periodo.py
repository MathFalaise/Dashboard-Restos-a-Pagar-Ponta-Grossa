"""INVESTIGATION - stage 02. NOT production code.

Controlled tests of dataInicial/dataFinal (fiscal year 2026, entity 1,
SemTipo query). For each commitment, compares the fields across periods and
counts in how many records each candidate relation holds. A relation that fails in
any record is reported with examples: it is not silently discarded.

Periods (all already downloaded by coletar.py):
  A 01/01-31/12   B 01/01-31/01   C 01/02-31/03   D 01/01-31/03
  E 01/01-30/06   F 01/01-31/08   X 01/02-31/12
"""
from decimal import Decimal

from conciliar_rreo import CAMPOS, br, carregar

PER = {"A": ("2026-01-01", "2026-12-31"), "B": ("2026-01-01", "2026-01-31"),
       "C": ("2026-02-01", "2026-03-31"), "D": ("2026-01-01", "2026-03-31"),
       "E": ("2026-01-01", "2026-06-30"), "F": ("2026-01-01", "2026-08-31"),
       "X": ("2026-02-01", "2026-12-31")}
FLUXOS = ["canceladoProc", "pagoProc", "pagoProcEstornado", "canceladoAProc", "pagoAProc",
          "pagoAProcEstornado", "liquidado", "retencao"]
ZERO = Decimal(0)

K = lambda r: (r["anoempenho"], r["empenho"])
dados = {p: {K(r): {c: Decimal(r[c]) for c in CAMPOS} for r in carregar(1, 2026, di, df, "SemTipo")}
         for p, (di, df) in PER.items()}
for p in PER:
    print(f"periodo {p} {PER[p]}: {len(dados[p])} registros")


def val(p, k, c):
    return dados[p].get(k, {}).get(c, ZERO)


def testar(nome, cond, universo):
    falhas = [k for k in universo if not cond(k)]
    print(f"  [{'OK ' if not falhas else 'FALHA'}] {nome}: vale em {len(universo) - len(falhas)}/{len(universo)}"
          + (f"  ex.: {falhas[:4]}" if falhas else ""))
    return falhas


print("\n1) Universo")
print("   B,D,E,F,A tem as mesmas chaves?", len({frozenset(dados[p]) for p in "ABDEF"}) == 1)
print("   C == X (mesmo dataInicial)?", set(dados["C"]) == set(dados["X"]))
print("   C contido em A?", set(dados["C"]) <= set(dados["A"]))
saiu = set(dados["A"]) - set(dados["C"])
print(f"   saíram ao mudar dataInicial para 01/02: {len(saiu)}")

print("\n2) Campos que variam só com dataFinal (mesmo dataInicial=01/01): B x D x E x F x A")
for c in CAMPOS:
    n = sum(1 for k in dados["A"] if len({val(p, k, c) for p in "BDEFA"}) > 1)
    print(f"   {c:20s} varia em {n} registros")

print("\n3) Aditividade dos fluxos: X[D] == X[B] + X[C]  (C=0 para quem não está em C)")
for c in FLUXOS:
    testar(c, lambda k, c=c: val("D", k, c) == val("B", k, c) + val("C", k, c), list(dados["D"]))

print("\n4) Estoque no início do período (dataInicial=01/02) a partir de janeiro")
U = list(dados["C"])
testar("proc[C] == proc[B] - pagoProc[B]", lambda k: val("C", k, "proc") == val("B", k, "proc") - val("B", k, "pagoProc"), U)
testar("proc[C] == proc[B] - pagoProc[B] + pagoProcEstornado[B]",
       lambda k: val("C", k, "proc") == val("B", k, "proc") - val("B", k, "pagoProc") + val("B", k, "pagoProcEstornado"), U)
testar("proc[C] == proc[B] - pagoProc[B] - canceladoProc[B]",
       lambda k: val("C", k, "proc") == val("B", k, "proc") - val("B", k, "pagoProc") - val("B", k, "canceladoProc"), U)
testar("aproc[C] == aproc[B]", lambda k: val("C", k, "aproc") == val("B", k, "aproc"), U)
testar("aproc[C] == aproc[B] - pagoAProc[B] - canceladoAProc[B]",
       lambda k: val("C", k, "aproc") == val("B", k, "aproc") - val("B", k, "pagoAProc") - val("B", k, "canceladoAProc"), U)
testar("aproc[C] == aproc[B] - liquidado[B] - canceladoAProc[B]",
       lambda k: val("C", k, "aproc") == val("B", k, "aproc") - val("B", k, "liquidado") - val("B", k, "canceladoAProc"), U)
testar("proc[C]+aproc[C] == proc[B]+aproc[B] - pagoProc[B] - pagoAProc[B] - canceladoAProc[B]",
       lambda k: val("C", k, "proc") + val("C", k, "aproc") == val("B", k, "proc") + val("B", k, "aproc")
       - val("B", k, "pagoProc") - val("B", k, "pagoAProc") - val("B", k, "canceladoAProc"), U)

print("\n5) Quem saiu do universo em 01/02 zerou o saldo em janeiro?")
testar("proc[B]+aproc[B] - pagoProc[B] - pagoAProc[B] - canceladoAProc[B] == 0",
       lambda k: val("B", k, "proc") + val("B", k, "aproc") - val("B", k, "pagoProc") - val("B", k, "pagoAProc")
       - val("B", k, "canceladoAProc") == 0, list(saiu))

print("\n6) Totais dos fluxos por período (todos os registros)")
for c in FLUXOS:
    print(f"   {c:20s} " + " ".join(f"{p}={br(sum((v[c] for v in dados[p].values()), ZERO)):>15s}" for p in "BCDEFA"))
