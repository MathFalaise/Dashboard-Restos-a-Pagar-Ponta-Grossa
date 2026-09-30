"""INVESTIGAÇÃO — Etapa 02. NÃO é código de produção.

Baixa TODAS as páginas de uma consulta a /empenhos/restos-a-pagar e grava cada
página exatamente como recebida (bytes), mais uma linha de manifesto com URL,
data/hora, status HTTP e SHA-256. Uma requisição por vez, com pausa.

Uso:
  python coletar.py ENTIDADE EXERCICIO DATA_INICIAL DATA_FINAL TIPO
  TIPO = Processados | NaoProcessados | SemTipo
"""
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

BASE = "https://servicos.pontagrossa.pr.gov.br/portaltransparencia-api/empenhos/restos-a-pagar"
RAIZ = Path(__file__).resolve().parent.parent / "dados_brutos" / "api"
MANIFESTO = RAIZ / "MANIFESTO.jsonl"
SIZE = 2000
PAUSA = 1.5


def nome_base(ent, ex, di, df, tipo):
    return f"rp_ent{ent}_ex{ex}_{di}_a_{df}_{tipo}"


def coletar(ent, ex, di, df, tipo, sessao=None):
    """Devolve a lista de registros (content de todas as páginas)."""
    sessao = sessao or requests.Session()
    RAIZ.mkdir(parents=True, exist_ok=True)
    base = nome_base(ent, ex, di, df, tipo)
    params = {"entidade": ent, "exercicio": ex, "dataInicial": di, "dataFinal": df, "size": SIZE}
    if tipo != "SemTipo":
        params["tipoPesquisa"] = tipo
    registros, page = [], 0
    while True:
        arq = RAIZ / f"{base}_p{page}.json"
        if arq.exists():  # não baixa de novo o que já está no disco
            corpo = arq.read_bytes()
        else:
            r = sessao.get(BASE, params={**params, "page": page}, timeout=120)
            corpo = r.content
            arq.write_bytes(corpo)
            with MANIFESTO.open("a", encoding="utf-8") as m:
                m.write(json.dumps({
                    "arquivo": arq.name, "url": r.url, "status": r.status_code,
                    "coletado_em": datetime.now().isoformat(timespec="seconds"),
                    "sha256": hashlib.sha256(corpo).hexdigest(), "bytes": len(corpo),
                }, ensure_ascii=False) + "\n")
            r.raise_for_status()
            time.sleep(PAUSA)
        d = json.loads(corpo)
        registros += d["content"]
        if d["last"] or not d["content"]:
            assert len(registros) == d["totalElements"], (base, len(registros), d["totalElements"])
            return registros
        page += 1


if __name__ == "__main__":
    ent, ex, di, df, tipo = sys.argv[1:6]
    regs = coletar(int(ent), int(ex), di, df, tipo)
    print(nome_base(ent, ex, di, df, tipo), len(regs), "registros")
