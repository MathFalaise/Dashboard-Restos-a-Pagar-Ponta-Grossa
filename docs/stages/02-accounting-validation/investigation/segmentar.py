"""INVESTIGAÇÃO — Etapa 02. NÃO é código de produção.

Compara, registro a registro, as três consultas (Processados, NaoProcessados,
SemTipo) do mesmo período: quem está em cada aba, se os valores de um mesmo
empenho coincidem entre as abas, qual regra separa as abas, e as somas por
segmento. Nada é inferido: só contagens e somas.
"""
import sys
from collections import Counter
from decimal import Decimal

from conciliar_rreo import CAMPOS, br, carregar

CHAVE = lambda r: (r["entidade"], r["anoempenho"], r["empenho"])


def main(ent, ex, di, df):
    P = {CHAVE(r): r for r in carregar(ent, ex, di, df, "Processados")}
    N = {CHAVE(r): r for r in carregar(ent, ex, di, df, "NaoProcessados")}
    S = {CHAVE(r): r for r in carregar(ent, ex, di, df, "SemTipo")}
    print(f"== ent={ent} ex={ex} {di}..{df}: P={len(P)} N={len(N)} S={len(S)}")
    so_p, so_n, ambos = P.keys() - N.keys(), N.keys() - P.keys(), P.keys() & N.keys()
    print(f"   so P={len(so_p)} so N={len(so_n)} ambos={len(ambos)} | uniao={len(P.keys() | N.keys())}"
          f" | S - uniao={len(S.keys() - (P.keys() | N.keys()))} | uniao - S={len((P.keys() | N.keys()) - S.keys())}")

    # o mesmo empenho traz os mesmos valores nas três consultas?
    dif = Counter()
    for k in S:
        for fonte, D in (("P", P), ("N", N)):
            if k in D:
                for c in CAMPOS:
                    if Decimal(D[k][c]) != Decimal(S[k][c]):
                        dif[(fonte, c)] += 1
    print("   campos que diferem entre a aba e SemTipo para o mesmo empenho:", dict(dif) or "nenhum")

    # regra de pertinência às abas
    def cond(r):
        return ("proc>0" if Decimal(r["proc"]) > 0 else "proc=0" if Decimal(r["proc"]) == 0 else "proc<0",
                "aproc>0" if Decimal(r["aproc"]) > 0 else "aproc=0" if Decimal(r["aproc"]) == 0 else "aproc<0")
    for nome, ks in (("so P", so_p), ("so N", so_n), ("ambos", ambos)):
        print(f"   {nome:6s} condicoes:", dict(Counter(cond(S.get(k) or P.get(k) or N.get(k)) for k in ks)))

    print(f"\n   {'campo':20s} {'so P':>16s} {'so N':>16s} {'ambos':>16s} {'SemTipo':>16s}")
    for c in CAMPOS:
        soma = lambda ks: sum((Decimal(S.get(k, P.get(k, N.get(k)))[c]) for k in ks), Decimal(0))
        print(f"   {c:20s} {br(soma(so_p)):>16s} {br(soma(so_n)):>16s} {br(soma(ambos)):>16s} {br(soma(S.keys())):>16s}")

    # sinais: valores negativos por campo
    neg = Counter(c for r in S.values() for c in CAMPOS if Decimal(r[c]) < 0)
    print("   registros com valor negativo por campo (SemTipo):", dict(neg))


if __name__ == "__main__":
    a = sys.argv[1:] or ["1", "2026", "2026-01-01", "2026-08-31"]
    main(int(a[0]), int(a[1]), a[2], a[3])
