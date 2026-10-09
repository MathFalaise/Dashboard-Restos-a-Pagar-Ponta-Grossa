"""Mirrored pairs between entities 1 (Prefeitura) and 15 (Fundação Municipal de Saúde) - documentation of the pairs,
the values involved, the rules and the effect of each consolidation decision (correction request of 09/10/2026,
item 5). READ-ONLY.

It never decides the nature of the pairs (duplication or transfer): that is NOT DETERMINED by the evidence and stays
pending the answer of the Prefeitura/Fundação (e-SIC draft, docs/foi-requests/FOI_REQUEST_DRAFT.md, block A).
Every number comes from the current derivation of the database given; nothing is recomputed outside the rules.

Usage (from the repository root):
    python docs/audits/pares/pares_1_15.py --banco DB --saida-json OUT.json --saida-md OUT.md
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "app"))
from rp import governanca, regras  # noqa: E402

COMPONENTES = ("a", "b", "f", "g", "L", "S1")


def _reais(c):
    return None if c is None else f"{c / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def coletar(con):
    did = con.execute("SELECT MAX(id) FROM derivacao_execucao WHERE vigencia_em IS NULL").fetchone()[0]
    h = con.execute("SELECT hash_resultado FROM derivacao_execucao WHERE id=?", (did,)).fetchone()[0]
    governo = governanca.situacao_atual(con)
    regras_ = {}
    for cod, ver, tipo, uso, status, definicao, fonte in con.execute(
            "SELECT codigo, versao, tipo, uso, status_evidencia, definicao, fonte FROM regra WHERE codigo IN "
            "('PAR-24', 'CONS-PAR') ORDER BY codigo, versao"):
        g = governo.get((cod, ver), {})
        regras_[f"{cod} v{ver}"] = {"tipo": tipo, "uso_original": uso, "status_evidencia": g.get("status_evidencia", status),
                                    "situacao": g.get("situacao"), "compoe_indicador_publicado":
                                    g.get("compoe_indicador_publicado"), "definicao": definicao, "fonte": fonte,
                                    "parametros": regras.parametros(con, cod, ver) if (cod, ver) == ("PAR-24", 1) else {}}
    cortes = []
    for ex, df, n, iguais, ia, ib, xa, xb in con.execute(
            "SELECT exercicio, data_final, COUNT(*), SUM(mesma_inscricao), SUM(inscrito_a_c), SUM(inscrito_b_c), "
            "SUM(execucao_a_c), SUM(execucao_b_c) FROM espelhamento_par WHERE derivacao_id=? GROUP BY 1, 2 ORDER BY 1, 2",
            (did,)):
        rel = dict(con.execute("SELECT relacao_inscricao, COUNT(*) FROM espelhamento_par WHERE derivacao_id=? AND "
                               "exercicio=? AND data_final=? GROUP BY 1", (did, ex, df)).fetchall())
        lado = dict(con.execute("SELECT lado_com_execucao, COUNT(*) FROM espelhamento_par WHERE derivacao_id=? AND "
                                "exercicio=? AND data_final=? GROUP BY 1", (did, ex, df)).fetchall())
        anos = dict(con.execute("SELECT anoempenho_a, COUNT(*) FROM espelhamento_par WHERE derivacao_id=? AND exercicio=? "
                                "AND data_final=? GROUP BY 1", (did, ex, df)).fetchall())
        efeito = {}
        for visao, cons in (("publicado", None), ("analitico", 1), ("analitico", 2)):
            filtro = "v.regra_consolidacao_id IS NULL" if cons is None else "gc.versao = ?"
            p = (did, ex, df, visao) + (() if cons is None else (cons,))
            valores = dict(con.execute(
                "SELECT v.componente, v.valor_c FROM visao_valor v JOIN regra ga ON ga.id = v.regra_agregacao_id "
                "LEFT JOIN regra gc ON gc.id = v.regra_consolidacao_id WHERE v.derivacao_id=? AND v.exercicio=? AND "
                f"v.data_final=? AND v.visao=? AND ga.codigo='RREO-COL' AND ga.versao=1 AND {filtro}", p).fetchall())
            efeito["oficial (dois lados)" if cons is None else f"CONS-PAR v{cons} (experimental)"] = \
                {k: valores.get(k) for k in COMPONENTES}
        rreo = con.execute(
            "SELECT c.valor_rreo_c, k.snapshot_uid FROM conciliacao_rreo c JOIN regra g ON g.id = c.regra_agregacao_id "
            "JOIN coleta k ON k.id = c.rreo_coleta_id WHERE c.derivacao_id=? AND c.exercicio=? AND c.data_final=? AND "
            "c.escopo='consolidado' AND c.coluna='L' AND g.codigo='RREO-COL' AND g.versao=1", (did, ex, df)).fetchone()
        cortes.append({"exercicio": ex, "data_final": df, "pares": n, "mesma_inscricao": iguais,
                       "inscricao_lado_a_entidade_1": ia, "inscricao_lado_b_entidade_15": ib,
                       "execucao_lado_a": xa, "execucao_lado_b": xb, "relacao_inscricao": rel,
                       "lado_com_execucao": lado, "pares_por_anoempenho": anos, "efeito_no_municipio": efeito,
                       "rreo_consolidado_L": rreo[0] if rreo else None,
                       "rreo_consolidado_snapshot": rreo[1] if rreo else None})
    return {"derivacao": did, "hash_resultado": h, "regras": regras_, "cortes": cortes}


def markdown(d):
    out = ["# Pares espelhados entre as entidades 1 e 15", "",
           f"Gerado por `docs/audits/pares/pares_1_15.py` sobre a derivação {d['derivacao']} "
           f"(hash `{d['hash_resultado'][:16]}…`). Somente leitura; nenhuma regra recalculada fora do código.", "",
           "**Natureza dos pares: NÃO DETERMINADA.** Duplicidade ou transferência dependem de resposta oficial "
           "(e-SIC, bloco A de `docs/foi-requests/FOI_REQUEST_DRAFT.md`). Os dois lados continuam no bruto, na "
           "normalização e nos indicadores oficiais; a consolidação existe só como visão experimental.", "",
           "## Regras", "", "| Regra | Situação | Evidência | Compõe indicador publicado | Definição |", "|---|---|---|---|---|"]
    for nome, r in d["regras"].items():
        out.append(f"| {nome} | {r['situacao']} | {r['status_evidencia']} | {'sim' if r['compoe_indicador_publicado'] else 'não'} | "
                   f"{r['definicao']} |")
    out += ["", f"Parâmetros de PAR-24 v1: `{json.dumps(d['regras'].get('PAR-24 v1', {}).get('parametros'), ensure_ascii=False)}`",
            "", "## Pares por corte", "",
            "| Exercício | Corte | Pares | Mesma inscrição | Inscrição lado A (ent. 1) | Inscrição lado B (ent. 15) | Execução A | "
            "Execução B | Lado com execução | Anos de empenho |", "|---|---|---|---|---|---|---|---|---|---|"]
    for c in d["cortes"]:
        out.append(f"| {c['exercicio']} | {c['data_final']} | {c['pares']} | {c['mesma_inscricao']} | "
                   f"{_reais(c['inscricao_lado_a_entidade_1'])} | {_reais(c['inscricao_lado_b_entidade_15'])} | "
                   f"{_reais(c['execucao_lado_a'])} | {_reais(c['execucao_lado_b'])} | "
                   f"{json.dumps(c['lado_com_execucao'], ensure_ascii=False)} | {json.dumps(c['pares_por_anoempenho'])} |")
    out += ["", "## Efeito de cada decisão no Município (agregação RREO-COL v1)", "",
            "Oficial = os dois lados somados (como a API e o RREO consolidado de 2026 publicam). CONS-PAR v1 retira a "
            "inscrição de B em par igual; CONS-PAR v2 retira a de A. Diferença = visão − oficial.", "",
            "| Exercício | Corte | Componente | Oficial | CONS-PAR v1 | dif. v1 | CONS-PAR v2 | dif. v2 | RREO consolidado (L) |",
            "|---|---|---|---|---|---|---|---|---|"]
    for c in d["cortes"]:
        e = c["efeito_no_municipio"]
        of, v1, v2 = e["oficial (dois lados)"], e["CONS-PAR v1 (experimental)"], e["CONS-PAR v2 (experimental)"]
        for k in COMPONENTES:
            if of.get(k) is None:
                continue
            dif = lambda x: None if x.get(k) is None else x[k] - of[k]
            out.append(f"| {c['exercicio']} | {c['data_final']} | {k} | {_reais(of[k])} | {_reais(v1.get(k))} | "
                       f"{_reais(dif(v1))} | {_reais(v2.get(k))} | {_reais(dif(v2))} | "
                       f"{(_reais(c['rreo_consolidado_L']) or 'sem RREO do corte') if k == 'L' else ''} |")
    out += ["", "## Pendências", "",
            "- Natureza contábil dos pares: depende de resposta oficial (e-SIC, bloco A). Nenhuma conclusão aqui.",
            "- Promover CONS-PAR a operacional exige evidência independente registrada (decisão D7: `decidir-regra` com "
            "evidência externa ou ressalva escrita). Hoje: experimental, HIPÓTESE.",
            "- Os indicadores oficiais continuam com os dois lados, como a fonte publica.", ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--banco", required=True)
    ap.add_argument("--saida-json", required=True)
    ap.add_argument("--saida-md", required=True)
    a = ap.parse_args()
    con = sqlite3.connect(f"file:{Path(a.banco).resolve()}?mode=ro", uri=True)
    d = coletar(con)
    Path(a.saida_json).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    Path(a.saida_md).write_text(markdown(d), encoding="utf-8")
    print(json.dumps({"derivacao": d["derivacao"], "cortes": len(d["cortes"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
