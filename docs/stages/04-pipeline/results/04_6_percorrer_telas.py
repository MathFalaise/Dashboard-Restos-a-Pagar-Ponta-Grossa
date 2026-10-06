"""Walks through the interface screens over HTTP (local server already started) and records status, size and time.

Usage:  python 04_6_percorrer_telas.py http://127.0.0.1:PORTA SAIDA.json

It only accesses the given local server (no proxy). Covers the operations of section 14 of the 04.6 specification:
opening, change of fiscal year, entity filter, detailed query, search, navigation and reconciliation.
"""
import json
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode

BASE, SAIDA = sys.argv[1].rstrip("/"), sys.argv[2]
VISITAS = [
    ("abertura", "/", {}),
    ("troca de exercício", "/", dict(exercicio=2019, data_final="2019-12-31")),
    ("troca de exercício", "/", dict(exercicio=2024, data_final="2024-12-31")),
    ("filtro de entidade", "/", dict(exercicio=2025, data_final="2025-12-31", entidade=15)),
    ("como estava em", "/", dict(exercicio=2026, data_final="2026-08-31", em="2026-09-29")),
    ("entidades", "/entidades", dict(exercicio=2026, data_final="2026-08-31")),
    ("lista de empenhos", "/empenhos", dict(exercicio=2026, data_final="2026-08-31")),
    ("filtros combinados", "/empenhos", dict(exercicio=2026, data_final="2026-08-31", entidade=1, categoria="ambos",
                                             programatica="09")),
    ("busca", "/empenhos", dict(exercicio=2026, data_final="2026-08-31", anoempenho=2025, empenho=5659)),
    ("filtro sem resultado", "/empenhos", dict(exercicio=2026, data_final="2026-08-31", empenho=999999999)),
    ("navegação", "/empenhos", dict(exercicio=2016, data_final="2016-12-31", pagina=40)),
    ("consulta detalhada", "/empenho", dict(entidade=1, anoempenho=2025, empenho=5659, exercicio=2026)),
    ("consulta detalhada", "/empenho", dict(entidade=1, anoempenho=2023, empenho=2401751, exercicio=2024)),
    ("retratos", "/retratos", {}),
    ("retratos do corte", "/retratos", dict(entidade=1, exercicio=2026, data_final="2026-08-31")),
    ("reconciliação", "/reconciliacao", {}),
    ("reconciliação do documento", "/reconciliacao", dict(exercicio=2026, data_final="2026-08-31", escopo="entidade")),
    ("pares", "/pares", dict(exercicio=2026, data_final="2026-08-31")),
    ("metodologia", "/metodologia", {}),
    ("folha de estilo", "/estilo.css", {}),
    ("parâmetro inválido", "/empenhos", dict(empenho="abc")),
    ("rota inexistente", "/nao-existe", {}),
]
abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))
saida = []
for nome, caminho, params in VISITAS:
    url = BASE + caminho + ("?" + urlencode(params) if params else "")
    t = time.perf_counter()
    try:
        with abridor.open(url, timeout=60) as r:
            status, corpo = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, corpo = e.code, e.read()
    saida.append({"operacao": nome, "url": caminho + ("?" + urlencode(params) if params else ""), "status": status,
                  "bytes": len(corpo), "ms": round((time.perf_counter() - t) * 1000)})
with open(SAIDA, "w", encoding="utf-8") as f:
    json.dump(saida, f, ensure_ascii=False, indent=1)
for s in saida:
    print(f"{s['status']} {s['ms']:6d} ms {s['bytes']:8d} B  {s['operacao']}: {s['url']}")
