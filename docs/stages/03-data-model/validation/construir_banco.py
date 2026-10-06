"""Constrói o banco DESCARTÁVEL de validação com os dados brutos das Etapas 01 e 02.

VALIDAÇÃO DO MODELO — Etapa 03. Não é código de produção. Não faz nenhuma requisição.

Uso: python construir_banco.py CAMINHO_DO_BANCO.sqlite
"""
import sys
import time
from pathlib import Path

from rpval import bruto, derivar, normalizar

RAIZ = Path(__file__).resolve().parents[4]


def construir(caminho):
    caminho = Path(caminho)
    if caminho.exists():
        caminho.unlink()  # descartável por definição
    t = time.time()
    con = bruto.criar_banco(caminho)
    resumo = bruto.carregar_etapas_anteriores(con, RAIZ)
    nid = normalizar.normalizar(con)
    did = derivar.derivar(con, nid)
    return con, nid, did, resumo, time.time() - t


if __name__ == "__main__":
    con, nid, did, resumo, seg = construir(sys.argv[1])
    print("carga bruta:", resumo)
    for t in ("coleta", "resposta_bruta", "rp_registro", "movimentacao_lancamento", "rreo_valor", "rp_derivado",
              "anomalia", "espelhamento_par", "visao_valor", "conciliacao_rreo", "verificacao"):
        print(f"  {t:25s} {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:>8}")
    print(f"normalização {nid}, derivação {did}, {seg:.1f}s, banco {Path(sys.argv[1]).stat().st_size/1e6:.1f} MB")
