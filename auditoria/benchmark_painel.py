"""Medicao das consultas da camada painel (auditoria tecnica; SOMENTE LEITURA, fora da execucao normal).

Uso (dentro de app/):  python ../auditoria/benchmark_painel.py SAIDA.json [--banco CAMINHO] [--repeticoes N]

Para cada chamada tipica da interface: tempo (mediana de N repeticoes), numero de comandos SQL executados e os
planos (EXPLAIN QUERY PLAN) que fazem SCAN de tabela inteira. Nao altera nada: o banco e aberto pela camada painel
(URI mode=ro + query_only).
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "app"))

from rp.config import carregar  # noqa: E402
from rp.painel import Painel  # noqa: E402


def chamadas(p):
    cortes = p.cortes()["cortes"]
    ult = [c for c in cortes if c["municipio_disponivel"]][-1]
    ex, df = ult["exercicio"], ult["data_final"]
    do_ex = [c["data_final"] for c in cortes if c["exercicio"] == ex]
    return [
        ("contexto", lambda: p.contexto()),
        ("cortes", lambda: p.cortes()),
        ("indicadores Municipio", lambda: p.indicadores(ex, df)),
        ("indicadores entidade 1", lambda: p.indicadores(ex, df, 1)),
        ("evolucao Municipio", lambda: p.evolucao(ex)),
        ("serie entre exercicios", lambda: p.serie_entre_exercicios()),
        ("composicao Municipio", lambda: p.composicao(ex, df)),
        ("variacao s1 (ultimo par)", lambda: p.variacao(ex, do_ex[-2], do_ex[-1])),
        ("empenhos pagina 1", lambda: p.empenhos(ex, df, None, None, 50, 0)),
        ("empenhos busca por numero", lambda: p.empenhos(ex, df, None, None, 50, 0, empenho=5659)),
        ("detalhe de empenho", lambda: p.detalhe_empenho(1, 2025, 5659, ex)),
        ("historico de empenho", lambda: p.historico_empenho(1, 2025, 5659, ex)),
        ("qualidade", lambda: p.qualidade()),
        ("anomalias COPIA-24 pagina 1", lambda: p.anomalias("COPIA-24", 50, 0)),
        ("anomalias COPIA-24 filtradas", lambda: p.anomalias("COPIA-24", 50, 0, ex, 1, df)),
        ("reconciliacao (todas as linhas)", lambda: p.reconciliacao()),
        ("coerencia entre publicacoes", lambda: p.coerencia_entre_publicacoes()),
        ("entidades do corte", lambda: p.entidades_do_corte(ex, df)),
        ("pares", lambda: p.pares(ex, df)),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("saida")
    ap.add_argument("--banco")
    ap.add_argument("--repeticoes", type=int, default=3)
    a = ap.parse_args()
    banco = a.banco or carregar().banco
    out = []
    with Painel.abrir(banco) as p:
        sqls = []
        p.con.set_trace_callback(sqls.append)
        for nome, f in chamadas(p):
            tempos = []
            for _ in range(a.repeticoes):
                sqls.clear()
                t = time.perf_counter()
                f()
                tempos.append(time.perf_counter() - t)
            n = len(sqls)
            unicos = list(dict.fromkeys(s for s in sqls if s.lstrip().upper().startswith("SELECT")))
            p.con.set_trace_callback(None)
            scans = set()
            for s in unicos[:200]:
                try:
                    for linha in p.con.execute("EXPLAIN QUERY PLAN " + s):
                        det = linha[-1]
                        if det.startswith("SCAN ") and " USING " not in det:
                            scans.add(det)
                except Exception as e:  # consulta com parametro ja substituido pelo trace: plano nao disponivel
                    scans.add(f"(plano indisponivel: {type(e).__name__})")
            p.con.set_trace_callback(sqls.append)
            out.append({"chamada": nome, "mediana_s": round(statistics.median(tempos), 3), "max_s": round(max(tempos), 3),
                        "comandos_sql": n, "scans_de_tabela": sorted(scans)})
            print(f"{nome:34} {out[-1]['mediana_s']:7.3f}s  sql={n:5}  scans={sorted(scans)}")
    Path(a.saida).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
