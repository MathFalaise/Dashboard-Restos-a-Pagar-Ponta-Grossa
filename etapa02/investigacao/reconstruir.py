"""INVESTIGAÇÃO — Etapa 02. NÃO é código de produção.

Modelo de reconstrução (HIPÓTESE sob teste) dos campos da listagem de Restos a
Pagar a partir da movimentação de cada empenho. Para cada caso e cada período
já baixado, calcula o valor previsto e compara com o que a API devolveu.
Só imprime divergências, mais um resumo por campo.

Rótulos da movimentação, conforme observado (ver relatório):
  20 Empenho, 21 Cancelamento Empenho, 22 Estorno Cancelamento Empenho,
  30 Liquidação, 31 Estorno Liquidação, 40 Pagamento, 41 Estorno Pagamento,
  50 Retenção, 51 Est Retenção.
  Em 40/41 a liquidação paga está em (exercicioPagamento, noPagamento) — os
  rótulos vêm trocados; em 30/31/50/51 está em (exercicioLiquidacao, noLiquidacao).
"""
from collections import Counter
from datetime import date
from decimal import Decimal

from analisar_periodo import PER, dados
from casos import FIXOS, NAO_ADITIVOS, SELECAO, mov, primeiro

Z = Decimal(0)
EX = 2026
SINAL_EMP = {20: 1, 21: -1, 22: 1}
SINAL_LIQ = {30: 1, 31: -1}
SINAL_PAG = {40: 1, 41: -1}
SINAL_RET = {50: 1, 51: -1}


def ex_liq(m):
    """Exercício da liquidação a que o lançamento se refere."""
    if m["tipoLancamento"] in (40, 41):
        return m["exercicioPagamento"]
    return m["exercicioLiquidacao"]


def modelo(movs, di, df):
    di, df = date.fromisoformat(di), date.fromisoformat(df)
    emp = liq = pag = ret = Z  # acumulados antes de di
    o = Counter()
    for m in movs:
        t, d, v = m["tipoLancamento"], date.fromisoformat(m["data"]), Decimal(m["valor"])
        antes, dentro = d < di, di <= d <= df
        if antes:
            emp += SINAL_EMP.get(t, 0) * v
            liq += SINAL_LIQ.get(t, 0) * v
            pag += SINAL_PAG.get(t, 0) * v
            ret += SINAL_RET.get(t, 0) * v
        elif dentro:
            corrente = ex_liq(m) == EX
            if t in (21, 22):
                o["canceladoAProc"] += -SINAL_EMP[t] * v
            elif t in SINAL_LIQ:
                o["liquidado"] += SINAL_LIQ[t] * v
            elif t in SINAL_PAG:
                o["pagoAProc" if corrente else "pagoProc"] += SINAL_PAG[t] * v
                if t == 41:
                    o["pagoAProcEstornado" if corrente else "pagoProcEstornado"] += v
            elif t in SINAL_RET:
                o["retencao"] += SINAL_RET[t] * v
                if corrente:
                    o["pagoAProc"] += SINAL_RET[t] * v
    o["aproc"] = emp - liq
    o["proc"] = liq - pag - ret
    return o


CAMPOS = ["proc", "aproc", "canceladoProc", "pagoProc", "pagoProcEstornado", "canceladoAProc",
          "pagoAProc", "pagoAProcEstornado", "liquidado", "retencao"]


def comparar(k, verbose=True):
    movs = mov(*k)
    erros = Counter()
    for p, (di, df) in PER.items():
        api = dados[p].get(k)
        prev = modelo(movs, di, df)
        if api is None:
            saldo = prev["proc"] + prev["aproc"]
            if saldo != 0:
                erros["universo"] += 1
                if verbose:
                    print(f"      {p}: fora do universo na API, mas modelo tem saldo {saldo}")
            continue
        for c in CAMPOS:
            if prev[c] != api[c]:
                erros[c] += 1
                if verbose:
                    print(f"      {p} {di}..{df} {c}: API={api[c]:,.2f} modelo={prev[c]:,.2f}")
    return erros


def casos_selecionados():
    casos = dict(FIXOS)
    usados = set(casos.values())
    for nome, cond in SELECAO.items():
        k = primeiro(cond, usados)
        if k:
            casos[nome] = k
            usados.add(k)
    for i, k in enumerate(NAO_ADITIVOS):
        casos[f"I4 pagoAProcEstornado não aditivo #{i + 1}"] = k
    return casos


if __name__ == "__main__":
    total = Counter()
    for nome, k in casos_selecionados().items():
        print(f"=== {nome}: {k[1]}/{k[0]}")
        e = comparar(k)
        print("      OK em todos os períodos e campos" if not e else f"      divergências: {dict(e)}")
        total.update(e)
    print("\nDivergências por campo (somando casos x períodos):", dict(total) or "nenhuma")
