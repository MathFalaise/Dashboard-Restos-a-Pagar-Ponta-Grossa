"""Valores das telas novas da Etapa 05 conferidos com a camada painel (Subetapa 05.7; somente leitura).

Uso (dentro de app/):  python ../docs/stages/05-analysis/results/05_7_telas_novas.py SAIDA.json [--banco CAMINHO]

Percorre por WSGI (sem servidor) as telas das subetapas 05.2 a 05.6 em todos os escopos e grava todo
<data id value> de cada pagina. Para cada pagina, monta o valor esperado de cada id a partir da camada painel (a mesma
consulta que a tela usa) e registra: ids esperados ausentes, valores diferentes e ids exibidos que nao foram
conferidos. Criterio: os tres vazios.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ / "app"))

from rp.config import carregar  # noqa: E402
from rp.interface import paginas  # noqa: E402
from rp.interface.aplicacao import Aplicacao  # noqa: E402
from rp.painel import Painel  # noqa: E402
from rp.painel.consulta import COMPOSICOES  # noqa: E402

_DATA = re.compile(r'<data class="[^"]*" id="([^"]+)" value="(-?\d+)">')


def pagina(app, caminho, **q):
    status = []
    corpo = b"".join(app({"REQUEST_METHOD": "GET", "PATH_INFO": caminho,
                          "QUERY_STRING": urlencode({k: v for k, v in q.items() if v is not None})},
                         lambda s, h: status.append(s)))
    return status[0], corpo.decode("utf-8")


def esperado_evolucao(p, ex, ent):
    e = {}
    for x in p.evolucao(ex, ent)["serie"]:
        df = x["data_final"]
        if x["tem_valor"]:
            e.update({f"ser-{df}-{k}": x["valores"][k]["valor_c"] for k, _, _ in paginas.SERIE_COLUNAS})
        d = x["diferenca_para_o_anterior"]
        if d and not d["motivo_indisponivel"]:
            e.update({f"dif-{df}-{k}": d["valores"][k] for k, _, _ in paginas.SERIE_COLUNAS})
    return e


def esperado_historico(p, ent):
    r, e = p.serie_entre_exercicios(ent), {}
    for x in r["exercicios"]:
        if x["tem_valor"]:
            e.update({f"hist-{x['exercicio']}-{k}": x["valores"][k]["valor_c"] for k, _, _ in paginas.HISTORICO_COLUNAS})
    for f in r["fechamento_abertura"]:
        if not f["motivo_indisponivel"]:
            e.update({f"fa-{f['de']}-s1": f["s1_de_c"], f"fa-{f['de']}-af": f["a_mais_f_para_c"],
                      f"fa-{f['de']}-dif": f["diferenca_c"]})
    return e


def esperado_composicao(r, dim):
    t = r["total"]
    e = {"comp-total-reg": t["registros"], "comp-total-insc": t["inscricao_total_c"], "comp-total-s1": t["saldo_total_c"]}
    curto = {"registros": "reg", "inscricao_total_c": "insc", "saldo_total_c": "s1"}
    for d, x in r["dimensoes"].items():
        for m, f in x["fechamento"].items():
            e[f"fech-{d}-{curto[m]}"] = f["diferenca"]
    x = r["dimensoes"][dim]
    if x["exibida"]:
        medidas = ("registros", "inscricao_total_c") + (() if dim == "faixa" else ("saldo_total_c",))
        for g in x["grupos"]:
            e.update({f"comp-{dim}-{g['ident']}-{curto[m]}": g[m] for m in medidas})
        for m in x["medidas"]:
            e[f"comp-{dim}-total-{curto[m]}"] = t[m]
            e[f"comp-{dim}-fech-{curto[m]}"] = x["fechamento"][m]["diferenca"]
    return e


def esperado_variacao(r):
    e = {f"var-{lado}": r[lado]["total_c"] for lado in ("anterior", "posterior") if r[lado] and r[lado]["total_c"] is not None}
    if not r["disponivel"]:
        return e
    e["var-total"] = r["variacao_c"]
    for g in r["resumo"]["grupos"]:
        e[f"grp-{g['id']}"], e[f"grp-{g['id']}-n"] = g["soma_c"], g["quantidade"]
    f = r["fechamentos"]
    e.update({"grp-soma": f["grupos"]["soma_dos_grupos"], "grp-total": f["grupos"]["total"],
              "fech-grupos": f["grupos"]["diferenca"], "cls-soma": f["classes"]["soma_dos_grupos"],
              "fech-classes": f["classes"]["diferenca"], "fech-lista": f["lista"]["diferenca"],
              "lst-subtotal": r["lista"]["subtotal_c"], "lst-acumulado": r["lista"]["acumulado_c"]})
    for c in r["classes"]:
        e[f"cls-{c['id']}"], e[f"cls-{c['id']}-n"] = c["soma_c"], c["quantidade"]
    grupos = {g["id"]: g for g in r["resumo"]["grupos"]}
    for gid, prefixo in (("top_aumentos", "top-aum"), ("top_reducoes", "top-red")):
        for i, x in enumerate(grupos[gid]["itens"], 1):
            e[f"{prefixo}-{i}"] = x["contribuicao_c"]
    for x in r["lista"]["itens"]:
        e[f"lst-{x['posicao']}"] = x["contribuicao_c"]
    return e


def esperado_empenho(h):
    e = {}
    for x in h["cortes"]:
        for i, o in enumerate(x["ocorrencias"], 1):
            e.update({f"emp-{x['data_final']}-{i}-{c['coluna']}": o["valores"][c["coluna"]] for c in h["campos"]})
    return e


def esperado_qualidade(q, o=None):
    e = {}
    for x in q["anomalias"]["por_tipo"]:
        e[f"anom-{x['tipo']}"], e[f"anom-{x['tipo']}-vig"] = x["ocorrencias"], x["em_snapshots_vigentes"]
    for i, v in enumerate(q["verificacoes"], 1):
        e[f"verif-{i}-v"], e[f"verif-{i}-f"] = v["verificados"], v["falhas"]
    dr = q["diferencas_rreo"]
    colunas = [(r.split()[-1], dr["por_regra"][r], dr["total_por_regra"][r]) for r in dr["por_regra"]]
    colunas += [("coe", dr["coerencia"]["exibida"], dr["total_coerencia"]["exibida"]),
                ("coe-todas", dr["coerencia"]["todas"], dr["total_coerencia"]["todas"])]
    for ident, contagem, total in colunas:
        e.update({f"sit-{ident}-{paginas.SITUACAO_CURTA[s]}": contagem[s] for s in dr["situacoes"]})
        e[f"sit-{ident}-total"] = total
    if o and o["sem_chave"]:
        e["ocorr-sem-chave"] = o["sem_chave"]
    return e


def conferir(saida, chave, html, esperado):
    tela = {k: int(v) for k, v in _DATA.findall(html)}
    saida["paginas"][chave] = tela
    ausentes = sorted(set(esperado) - set(tela))
    diferentes = sorted(k for k in set(esperado) & set(tela) if esperado[k] != tela[k])
    nao_conferidos = sorted(set(tela) - set(esperado))
    if ausentes or diferentes or nao_conferidos:
        saida["problemas"][chave] = {"ausentes": ausentes[:20], "diferentes": diferentes[:20],
                                     "nao_conferidos": nao_conferidos[:20]}
    saida["valores_conferidos"] += len(set(esperado) & set(tela)) - len(diferentes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("saida")
    ap.add_argument("--banco")
    a = ap.parse_args()
    banco = Path(a.banco) if a.banco else carregar().banco
    app = Aplicacao(banco)
    saida = {"paginas": {}, "problemas": {}, "status_diferente_de_200": [], "valores_conferidos": 0}
    t0 = time.perf_counter()
    with Painel.abrir(banco) as p:
        cortes = p.cortes()["cortes"]
        escopos = [None] + [e["entidade"] for e in p.entidades()["entidades"]]

        def visitar(chave, caminho, esperado, **q):
            status, html = pagina(app, caminho, **q)
            if status != "200 OK":
                saida["status_diferente_de_200"].append([chave, status])
                return
            conferir(saida, chave, html, esperado)

        for ex in (2025, 2026):
            for ent in escopos:
                visitar(f"evolucao|{ex}|{ent}", "/evolucao", esperado_evolucao(p, ex, ent), exercicio=ex, entidade=ent)
        for ent in escopos:
            visitar(f"historico|{ent}", "/historico", esperado_historico(p, ent), entidade=ent)
        for c in cortes:
            ex, df = c["exercicio"], c["data_final"]
            for ent in escopos:
                r = p.composicao(ex, df, ent)
                if not r["disponivel"]:
                    visitar(f"composicao|{ex}|{df}|{ent}|indisponivel", "/composicao", {}, exercicio=ex, data_final=df,
                            entidade=ent)
                    continue
                for dim in COMPOSICOES:
                    visitar(f"composicao|{ex}|{df}|{ent}|{dim}", "/composicao", esperado_composicao(r, dim), exercicio=ex,
                            data_final=df, entidade=ent, dimensao=dim)
        for ex in (2025, 2026):
            dfs = [c["data_final"] for c in cortes if c["exercicio"] == ex]
            pares = list(zip(dfs, dfs[1:])) + ([("2026-02-28", "2026-04-30")] if ex == 2026 else [])
            for ant, post in pares:
                for ent in escopos:
                    for metrica in ("s1", "pagamentos"):
                        r = p.variacao(ex, ant, post, ent, metrica, limite=paginas.TAMANHO_PAGINA)
                        visitar(f"variacao|{ex}|{ant}|{post}|{ent}|{metrica}", "/variacao", esperado_variacao(r),
                                exercicio=ex, anterior=ant, data_final=post, entidade=ent, metrica=metrica)
        for ent, ano, emp, ex in ((1, 2025, 5659, 2026), (1, 2023, 2401751, 2025), (1, 2023, 2401751, 2026),
                                  (15, 2023, 1751, 2026)):
            visitar(f"empenho_cortes|{ent}|{ano}|{emp}|{ex}", "/empenho/cortes", esperado_empenho(
                p.historico_empenho(ent, ano, emp, ex)), entidade=ent, anoempenho=ano, empenho=emp, exercicio=ex)
        q = p.qualidade()
        visitar("qualidade", "/qualidade", esperado_qualidade(q))
        for x in q["anomalias"]["por_tipo"]:
            o = p.anomalias(x["tipo"], paginas.TAMANHO_PAGINA, 0)
            visitar(f"qualidade|{x['tipo']}", "/qualidade", esperado_qualidade(q, o), tipo=x["tipo"])
    saida["resumo"] = {"paginas": len(saida["paginas"]), "valores_conferidos": saida["valores_conferidos"],
                       "paginas_com_problema": len(saida["problemas"]),
                       "status_diferente_de_200": len(saida["status_diferente_de_200"]),
                       "segundos": round(time.perf_counter() - t0, 1)}
    Path(a.saida).write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({k: saida[k] for k in ("resumo", "status_diferente_de_200")}, ensure_ascii=False, indent=1))
    print(json.dumps(dict(list(saida["problemas"].items())[:5]), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
