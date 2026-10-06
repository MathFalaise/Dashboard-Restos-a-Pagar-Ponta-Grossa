"""Walks over HTTP through the interface screens, including the stage 05 ones, and records status, size and time
(sub-stage 05.7).

Usage:  python 05_7_percorrer_telas.py http://127.0.0.1:PORTA SAIDA.json

It only accesses the given local server (no proxy). Used with the 04.6 offline server
(docs/stages/04-pipeline/results/04_6_servidor_sem_rede.py), which logs every outgoing connection attempt.
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
    ("resumo de um corte", "/", dict(exercicio=2025, data_final="2025-12-31")),
    ("evolução no exercício", "/evolucao", dict(exercicio=2026)),
    ("evolução de uma entidade", "/evolucao", dict(exercicio=2026, entidade=15)),
    ("série entre exercícios", "/historico", {}),
    ("série de uma entidade", "/historico", dict(entidade=1)),
    ("composição por categoria", "/composicao", dict(exercicio=2025, data_final="2025-12-31")),
    ("composição por faixa", "/composicao", dict(exercicio=2025, data_final="2025-12-31", dimensao="faixa")),
    ("composição por fonte", "/composicao", dict(exercicio=2025, data_final="2025-12-31", dimensao="fonte_recurso")),
    ("composição indisponível", "/composicao", dict(exercicio=2026, data_final="2026-03-31")),
    ("lista de um grupo da composição", "/empenhos", dict(exercicio=2025, data_final="2025-12-31", faixa="a")),
    ("variação entre cortes", "/variacao", dict(exercicio=2025, anterior="2025-10-31", data_final="2025-12-31")),
    ("variação que salta lacuna", "/variacao", dict(exercicio=2026, anterior="2026-02-28", data_final="2026-04-30")),
    ("variação: última página", "/variacao", dict(exercicio=2026, anterior="2026-02-28", data_final="2026-04-30", pagina=20)),
    ("variação indisponível", "/variacao", dict(exercicio=2026, anterior="2026-01-31", data_final="2026-02-28")),
    ("empenho nos cortes", "/empenho/cortes", dict(entidade=1, anoempenho=2025, empenho=5659, exercicio=2026)),
    ("qualidade dos dados", "/qualidade", {}),
    ("ocorrências de anomalia", "/qualidade", dict(tipo="LIQ-NEG", exercicio=2026)),
    ("entidades", "/entidades", dict(exercicio=2026, data_final="2026-08-31")),
    ("consulta detalhada", "/empenho", dict(entidade=1, anoempenho=2025, empenho=5659, exercicio=2026)),
    ("reconciliação", "/reconciliacao", {}),
    ("metodologia", "/metodologia", {}),
    ("folha de estilo", "/estilo.css", {}),
    ("parâmetro inválido", "/variacao", dict(metrica="liquidacoes")),
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
