"""Walks through every screen of the interface at http://127.0.0.1:8051 (no proxy) and measures the time of each one."""
import json, re, sys, time, urllib.request
from urllib.parse import urlencode
sys.stdout.reconfigure(errors="backslashreplace")
abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))
BASE = "http://127.0.0.1:8051"
for _ in range(60):
    try:
        abridor.open(BASE + "/estilo.css", timeout=2).close(); break
    except OSError:
        time.sleep(0.5)
visitas = [
 ("inicializacao/resumo padrao", "/", {}),
 ("resumo Municipio 2025", "/", dict(exercicio=2025, data_final="2025-12-31")),
 ("resumo entidade 1 2024", "/", dict(exercicio=2024, data_final="2024-12-31", entidade=1)),
 ("resumo como estava em 29/09", "/", dict(exercicio=2025, data_final="2025-12-31", entidade=1, em="2026-09-29")),
 ("entidades 2016", "/entidades", dict(exercicio=2016, data_final="2016-12-31")),
 ("empenhos Municipio 2025", "/empenhos", dict(exercicio=2025, data_final="2025-12-31")),
 ("empenhos filtrados", "/empenhos", dict(exercicio=2025, data_final="2025-12-31", entidade=1, categoria="ambos",
                                          tipo_credor="pessoa jurídica", programatica="09", ordem="empenho")),
 ("empenhos pagina 20", "/empenhos", dict(exercicio=2025, data_final="2025-12-31", pagina=20)),
 ("detalhe 5659/2025", "/empenho", dict(entidade=1, anoempenho=2025, empenho=5659, exercicio=2026)),
 ("detalhe 2401751/2023", "/empenho", dict(entidade=1, anoempenho=2023, empenho=2401751, exercicio=2024, data_final="2024-12-31")),
 ("retratos (indice)", "/retratos", {}),
 ("retratos 1/2025/31-12", "/retratos", dict(entidade=1, exercicio=2025, data_final="2025-12-31")),
 ("reconciliacao (indice + coerencia)", "/reconciliacao", {}),
 ("reconciliacao 2024 entidade", "/reconciliacao", dict(exercicio=2024, data_final="2024-12-31", escopo="entidade")),
 ("pares 2026", "/pares", dict(exercicio=2026, data_final="2026-08-31")),
 ("metodologia", "/metodologia", {}),
]
saida = []
for nome, caminho, params in visitas:
    url = BASE + caminho + ("?" + urlencode(params) if params else "")
    t = time.perf_counter()
    with abridor.open(url, timeout=60) as r:
        corpo = r.read(); status = r.status
    dt = time.perf_counter() - t
    html = corpo.decode("utf-8")
    saida.append({"tela": nome, "status": status, "segundos": round(dt, 3), "bytes": len(corpo),
                  "tem_proveniencia": "Origem do dado" in html or "<code>" in html,
                  "fonte_visivel": "API do sistema Elotech/Oxy Transparência" in html})
# comparison of snapshots from a link on the snapshots screen
ret = abridor.open(BASE + "/retratos?" + urlencode(dict(entidade=1, exercicio=2025, data_final="2025-12-31")), timeout=60).read().decode()
link = re.search(r'href="(/comparar\?[^"]+)"', ret).group(1).replace("&amp;", "&")
t = time.perf_counter(); r = abridor.open(BASE + link, timeout=60); dt = time.perf_counter() - t
saida.append({"tela": "comparar retratos (link)", "status": r.status, "segundos": round(dt, 3), "bytes": len(r.read())})
for s in saida:
    print(s)
json.dump(saida, open("percurso_sem_rede.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("todas 200:", all(s["status"] == 200 for s in saida), "| mais lenta:", max(s["segundos"] for s in saida))
