"""INVESTIGAÇÃO — Etapa 02. NÃO é código de produção.

Seleciona empenhos representativos (casos A–I da Etapa 02) na base de 2026
(entidade 1, SemTipo, 01/01–31/12), baixa a movimentação bruta de cada um e
imprime, lado a lado, a cronologia e os valores da listagem em cada período.

A seleção é determinística (primeiro empenho, em ordem de chave, que atende à
condição) para que o resultado seja reproduzível.
"""
import json
import sys
import time
from decimal import Decimal
from pathlib import Path

import requests

from analisar_periodo import PER, dados

BASE = "https://servicos.pontagrossa.pr.gov.br/portaltransparencia-api/empenhos/detalhe/movimentacao"
DIR = Path(__file__).resolve().parent.parent / "dados_brutos" / "movimentacao"
Z = Decimal(0)
A = dados["A"]  # 01/01-31/12


def mov(ano, emp, ent=1):
    arq = DIR / f"mov_ent{ent}_ex{ano}_emp{emp}.json"
    if not arq.exists():
        DIR.mkdir(parents=True, exist_ok=True)
        r = requests.get(BASE, params={"entidade": ent, "exercicio": ano, "empenho": emp, "size": 500}, timeout=60)
        r.raise_for_status()
        arq.write_bytes(r.content)
        time.sleep(1.2)
    d = json.loads(arq.read_text(encoding="utf-8"), parse_float=Decimal)
    assert d["last"], f"movimentação paginada: {arq}"
    return d["content"]


def primeiro(cond, excluir=()):
    for k in sorted(A):
        if k not in excluir and cond(A[k]):
            return k
    return None


def v(r, c):
    return r[c]


SELECAO = {
    "A  processado sem pagamento": lambda r: r["proc"] > 0 and r["aproc"] == 0 and all(r[c] == 0 for c in
                                   ("pagoProc", "canceladoAProc", "liquidado", "pagoAProc", "pagoProcEstornado")),
    "B1 processado pago integralmente": lambda r: r["proc"] > 0 and r["aproc"] == 0 and r["pagoProc"] == r["proc"],
    "B2 processado pago parcialmente": lambda r: r["proc"] > 0 and r["aproc"] == 0 and 0 < r["pagoProc"] < r["proc"],
    "C  processado com cancelamento": lambda r: r["proc"] > 0 and r["aproc"] == 0 and r["canceladoAProc"] > 0,
    "D1 processado com pagamento estornado": lambda r: r["proc"] > 0 and r["pagoProcEstornado"] > 0,
    "D2 processado com estorno de liquidação sem cancelamento": lambda r: r["proc"] > 0 and r["aproc"] == 0
                                   and r["liquidado"] < 0 and r["canceladoAProc"] == 0,
    "E  não processado sem liquidação": lambda r: r["aproc"] > 0 and r["proc"] == 0 and all(r[c] == 0 for c in
                                   ("liquidado", "pagoAProc", "canceladoAProc")),
    "F  não processado parcialmente liquidado": lambda r: r["aproc"] > 0 and r["proc"] == 0 and 0 < r["liquidado"] < r["aproc"]
                                   and r["canceladoAProc"] == 0,
    "G  não processado liquidado e pago": lambda r: r["aproc"] > 0 and r["proc"] == 0 and r["pagoAProc"] > 0
                                   and r["pagoAProc"] == r["liquidado"] == r["aproc"],
    "G2 não processado liquidado, pago em parte": lambda r: r["aproc"] > 0 and r["proc"] == 0 and 0 < r["pagoAProc"] < r["liquidado"],
    "G3 não processado com pagamento estornado": lambda r: r["aproc"] > 0 and r["pagoAProcEstornado"] > 0,
    "H1 nas duas abas": lambda r: r["proc"] > 0 and r["aproc"] > 0,
    "H2 nas duas abas, com pagamento dos dois tipos": lambda r: r["proc"] > 0 and r["aproc"] > 0 and r["pagoProc"] > 0 and r["pagoAProc"] > 0,
    "I1 não processado cancelado em parte e liquidado": lambda r: r["aproc"] > 0 and r["canceladoAProc"] > 0 and r["liquidado"] > 0,
    "I2 pagoProc sem proc (valor em aba NaoProc)": lambda r: r["proc"] == 0 and r["pagoProc"] != 0,
    "I3 retenção": lambda r: r["retencao"] > 0 and r["proc"] == 0,
}
FIXOS = {"C0 caso 11963/2016 (Etapa 01)": (2016, 11963), "B0 caso 5659/2025 (Etapa 01)": (2025, 5659)}
NAO_ADITIVOS = [(2025, 20738), (2025, 20744)]

TIPOS = {}


def cronologia(ano, emp):
    linhas = []
    for m in mov(ano, emp):
        TIPOS[m["tipoLancamento"]] = m["descricaoTipoLancamento"].strip()
        linhas.append(f"      {m['data']} {m['tipoLancamento']:>3} {m['descricaoTipoLancamento'].strip():28s}"
                      f" {m['valor']:>14,.2f}  aLiq={m['valorALiquidar']:>13,.2f} aPag={m['valorAPagar']:>13,.2f}"
                      f"  {m['nroDocumento']} [liqEx={m['exercicioLiquidacao']} liqNo={m['noLiquidacao']}"
                      f" pagEx={m['exercicioPagamento']} pagNo={m['noPagamento']}]")
    return linhas


def listagem(k):
    out = []
    for p in "BCDEFA":
        r = dados[p].get(k)
        if r is None:
            out.append(f"      {p} {PER[p][0]}..{PER[p][1]}: (fora do universo)")
            continue
        nz = {c: f"{x:,.2f}" for c, x in r.items() if x != 0}
        out.append(f"      {p} {PER[p][0]}..{PER[p][1]}: {nz}")
    return out


def main():
    casos = dict(FIXOS)
    usados = set(casos.values())
    for nome, cond in SELECAO.items():
        k = primeiro(cond, usados)
        casos[nome] = k
        if k:
            usados.add(k)
    for i, k in enumerate(NAO_ADITIVOS):
        casos[f"I4 pagoAProcEstornado não aditivo #{i + 1}"] = k
    for nome, k in casos.items():
        print(f"\n=== {nome}: {k[1]}/{k[0]}" if k else f"\n=== {nome}: NENHUM EMPENHO ATENDE")
        if not k:
            continue
        print("   movimentação:")
        print("\n".join(cronologia(*k)))
        print("   listagem restos-a-pagar (exercicio 2026, só campos != 0):")
        print("\n".join(listagem(k)))
    print("\nTipos de lançamento vistos:", dict(sorted(TIPOS.items())))


if __name__ == "__main__":
    main()
