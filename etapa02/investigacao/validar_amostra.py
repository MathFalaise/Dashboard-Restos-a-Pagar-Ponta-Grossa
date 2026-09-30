"""INVESTIGAÇÃO — Etapa 02. NÃO é código de produção.

Valida o modelo de reconstrução (reconstruir.modelo) numa amostra aleatória
estratificada (semente fixa) do exercício 2026, entidade 1, em todos os
períodos baixados. Baixa a movimentação de cada empenho da amostra (1 req/emp.).
"""
import random
from collections import Counter

from analisar_periodo import dados
from reconstruir import comparar

A = dados["A"]
random.seed(20260929)


def estrato(r):
    if r["proc"] > 0 and r["aproc"] > 0:
        return "ambos"
    tem_fluxo = any(r[c] != 0 for c in ("pagoProc", "pagoAProc", "liquidado", "canceladoAProc", "retencao"))
    return ("P" if r["proc"] > 0 else "N") + ("_com_fluxo" if tem_fluxo else "_sem_fluxo")


grupos = {}
for k in sorted(A):
    grupos.setdefault(estrato(A[k]), []).append(k)
TAMANHO = {"P_com_fluxo": 30, "P_sem_fluxo": 10, "N_com_fluxo": 50, "N_sem_fluxo": 10, "ambos": 20}
amostra = [(g, k) for g, n in TAMANHO.items() for k in random.sample(grupos[g], min(n, len(grupos[g])))]
print("população por estrato:", {g: len(v) for g, v in grupos.items()})

falhas = Counter()
por_estrato = Counter()
lista = []
for g, k in amostra:
    e = comparar(k, verbose=False)
    if e:
        falhas.update(e)
        por_estrato[g] += 1
        lista.append((g, k, dict(e)))
print(f"amostra: {len(amostra)} empenhos x 7 períodos x 10 campos")
print("empenhos com alguma divergência, por estrato:", dict(por_estrato) or "nenhum")
print("divergências por campo:", dict(falhas) or "nenhuma")
for x in lista:
    print("  ", x)
