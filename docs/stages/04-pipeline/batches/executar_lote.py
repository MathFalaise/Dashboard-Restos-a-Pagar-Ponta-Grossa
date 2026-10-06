"""Executor de lotes da Etapa 04.4 - artefato operacional/validacao (nao e codigo de producao).

Fluxo obrigatorio de cada lote:
    COLETA -> SNAPSHOT -> NORMALIZACAO -> DERIVACAO -> TESTES -> INTEGRIDADE -> VALIDACAO -> proximo lote
Portoes (definidos ANTES de coletar; qualquer falha PARA o lote, com relatorio):
    G1 coleta completa - G2 integridade armazemxbanco - G3 fidelidade/esquema do bruto normalizado
    G4 continuidade fechamento->abertura - G5 regressao temporal ("como estava em 29/09" com o mesmo hash)
    G6 sem efeito colateral em cortes nao tocados - G7 testes (producao + investigacao)
    G8 anomalias estruturais (CHAVE-DUP, ANOEMP-FUTURO) - as demais sao relatadas, nao bloqueiam

Uso: python executar_lote.py LOTE        (LOTE em A, R, B, C, D, E, F, T)
"""
import json
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ / "app"))

from rp import banco, comparador, derivar, execucoes, normalizar  # noqa: E402
from rp.armazem import Armazem  # noqa: E402
from rp.coletor import Coletor  # noqa: E402
from rp.config import carregar  # noqa: E402
from rp.http import Cliente  # noqa: E402

TODAS = [1, 15, 4, 5, 8, 3, 6, 9, 10, 11]          # as 5 da carga + as 5 que completam o Municipio (catalogo de entidades)
EM_29 = "2026-09-29T23:59:59-03:00"
OPCIONAIS = {"orgao", "unidade", "funcao", "subFuncao", "programa", "projeto", "elemento"}
ESTRUTURAIS = {"CHAVE-DUP", "ANOEMP-FUTURO"}


def anos(a, b, ents=TODAS):
    return [(e, ex, f"{ex}-12-31") for ex in range(a, b + 1) for e in ents]


LOTES = {
    "A": {"titulo": "2024 — entidades 1 e 15 (teste das regras experimentais)",
          "listagens": anos(2024, 2024, [1, 15]), "rreo": [(2024, {6})]},
    "R": {"titulo": "Cortes que faltam para conciliar TODOS os RREOs armazenados (2025 e 2026)",
          "listagens": "faltantes_rreo"},
    "B": {"titulo": "2024 — demais entidades (fecha o exercício)", "catalogos": [3, 6, 9, 10, 11],
          "listagens": anos(2024, 2024, [4, 5, 8, 3, 6, 9, 10, 11])},
    "C": {"titulo": "2022–2023", "catalogos": [3, 6, 9, 10, 11],
          "listagens": anos(2022, 2023), "rreo": [(2022, {6}), (2023, {6})]},
    "D": {"titulo": "2020–2021", "listagens": anos(2020, 2021), "rreo": [(2020, {6}), (2021, {6})]},
    "E": {"titulo": "2018–2019", "listagens": anos(2018, 2019), "rreo": [(2018, {6}), (2019, {6})]},
    "F": {"titulo": "2016–2017 (+ RREO 2019, que o filtro sensível a maiúsculas pulou no Lote E)",
          "listagens": anos(2016, 2017), "rreo": [(2016, {6}), (2017, {6}), (2019, {6})]},
    "M": {"titulo": "Movimentação dos registros localizados nas conciliações (datas dos lançamentos)",
          "movimentacao": [(1, 2023, 9459), (1, 2011, 21040), (1, 2023, 2401751), (15, 2023, 1751),
                           (1, 2023, 22383), (6, 2019, 1684), (5, 2025, 1485)]},
    "T": {"titulo": "Teste temporal — recoleta, com os MESMOS parâmetros, dos cortes coletados em 29/09", "recoleta": True},
}


def br(c):
    return f"{c / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def catalogo_exercicios(con):
    """{entidade: {exercicios}} do snapshot de catalogo de exercicios mais recente de cada entidade (lido do bruto)."""
    cat = {}
    for e, cid in con.execute("SELECT entidade, id FROM coleta WHERE tipo='exercicios' AND status='completa' "
                              "ORDER BY coletada_em, snapshot_uid"):
        (sha,) = con.execute("SELECT sha256 FROM resposta_bruta WHERE coleta_id=? ORDER BY ordem LIMIT 1", (cid,)).fetchone()
        cat[e] = {x["id"]["exercicio"] for x in json.loads(banco.corpo(con, sha))}
    return cat


def faltantes_rreo(con):
    """(entidade, exercicio, data_final) sem snapshot completo, para cada periodo de RREO armazenado.
    Entidade 1 basta para o RREO por entidade; o consolidado exige as 10 do catalogo."""
    periodos = con.execute("SELECT DISTINCT v.escopo, v.exercicio, v.data_final FROM rreo_valor v "
                           "WHERE v.normalizacao_id=(SELECT MAX(id) FROM normalizacao_execucao) ORDER BY 2,3,1").fetchall()
    tem = {(e, ex, df) for e, ex, df in con.execute(
        "SELECT entidade, exercicio, data_final FROM coleta WHERE tipo='rp_listagem' AND status='completa' "
        "AND tipo_pesquisa IS NULL AND data_inicial = exercicio || '-01-01'")}
    falta = []
    for escopo, ex, df in periodos:
        for e in ([1] if escopo == "entidade" else TODAS):
            if (e, ex, df) not in tem and (e, ex, df) not in falta:
                falta.append((e, ex, df))
    return falta


def ultima_derivacao(con, vigencia):
    q = "SELECT id, hash_resultado FROM derivacao_execucao WHERE vigencia_em " + ("IS NULL" if vigencia is None else "=?") + " ORDER BY id DESC LIMIT 1"
    return con.execute(q, () if vigencia is None else (vigencia,)).fetchone()


def visoes(con, did):
    return {r[:-1]: r[-1] for r in con.execute(
        "SELECT v.visao, g.versao, IFNULL(c.versao,0), IFNULL(v.entidade,0), v.exercicio, v.data_final, v.componente, v.valor_c "
        "FROM visao_valor v JOIN regra g ON g.id=v.regra_agregacao_id LEFT JOIN regra c ON c.id=v.regra_consolidacao_id "
        "WHERE v.derivacao_id=?", (did,))}


def pytest(pasta):
    t = time.time()
    r = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"],
                       cwd=pasta, capture_output=True, text=True, encoding="utf-8", errors="replace")
    ultima = [l for l in r.stdout.splitlines() if "passed" in l or "failed" in l or "error" in l.lower()]
    return {"ok": r.returncode == 0, "resumo": ultima[-1].strip("= ") if ultima else r.stdout[-300:], "segundos": round(time.time() - t)}


def executar(nome):
    L = LOTES[nome]
    cfg = carregar()
    con = banco.abrir(cfg)
    armazem = Armazem(cfg.snapshots)
    rel = {"lote": nome, "titulo": L["titulo"], "inicio": time.strftime("%Y-%m-%dT%H:%M:%S"), "gates": {}, "parou_em": None}
    antes_atual = ultima_derivacao(con, None)
    ref_29 = con.execute("SELECT hash_resultado FROM derivacao_execucao WHERE vigencia_em=? ORDER BY id LIMIT 1", (EM_29,)).fetchone()[0]
    rel["backup"] = str(banco.backup(con, cfg, f"antes-lote-{nome}", operacional=True))

    def gate(g, ok, detalhe):
        rel["gates"][g] = {"ok": bool(ok), "detalhe": detalhe}
        if not ok and not rel["parou_em"]:
            rel["parou_em"] = g
        return ok

    # ---------------- COLETA -> SNAPSHOT
    coletor = Coletor(cfg, con, armazem, Cliente(cfg))
    snaps = []
    if L.get("catalogos"):
        snaps += coletor.catalogos(L["catalogos"])
    listagens = faltantes_rreo(con) if L.get("listagens") == "faltantes_rreo" else L.get("listagens", [])
    rel["cortes_planejados"] = listagens
    for e, ex, df in listagens:
        snaps.append(coletor.listagem(e, ex, df))
    for e, ano, emp in L.get("movimentacao", []):
        snaps.append(coletor.movimentacao(e, ano, emp))
    for ex, bims in L.get("rreo", []):
        snaps += coletor.rreo(ex, 1, None, True, bims)
    comparacoes = []
    if L.get("recoleta"):
        cortes = con.execute(
            "SELECT entidade, exercicio, data_final, MIN(coletada_em) FROM coleta WHERE tipo='rp_listagem' AND status='completa' "
            "AND tipo_pesquisa IS NULL AND data_inicial = exercicio || '-01-01' GROUP BY 1,2,3 "
            "HAVING MIN(coletada_em) < ? ORDER BY 2,3,1", (CORTE_T,)).fetchall()
        for e, ex, df, quando in cortes:
            uid = con.execute("SELECT snapshot_uid FROM coleta WHERE tipo='rp_listagem' AND tipo_pesquisa IS NULL AND entidade=? "
                              "AND exercicio=? AND data_inicial=? AND data_final=? AND coletada_em=?",
                              (e, ex, f"{ex}-01-01", df, quando)).fetchone()[0]
            s = coletor.recoletar(uid)
            s["recoleta_de"] = uid
            snaps.append(s)
    rel["requisicoes"] = coletor.cliente.requisicoes
    lote_ids = [s["coleta_id"] for s in snaps]
    # Regra fixada antes dos Lotes C-F: combinacao entidadexexercicio FORA do catalogo oficial de exercicios
    # e consultada e relatada a parte; nao entra no G1. Dentro do catalogo (ou entidade sem catalogo), tudo e exigido.
    cat = catalogo_exercicios(con)
    fora = {}
    for s_ in snaps:
        t, pj = con.execute("SELECT tipo, parametros_json FROM coleta WHERE id=?", (s_["coleta_id"],)).fetchone()
        pr = json.loads(pj)
        if t == "rp_listagem" and pr["entidade"] in cat and pr["exercicio"] not in cat[pr["entidade"]]:
            n = sum(len(json.loads(banco.corpo(con, sha))["content"]) for (sha,) in con.execute(
                "SELECT sha256 FROM resposta_bruta WHERE coleta_id=?", (s_["coleta_id"],))) if s_["status"] == "completa" else None
            fora[s_["snapshot_uid"]] = {"entidade": pr["entidade"], "exercicio": pr["exercicio"], "status": s_["status"], "registros": n}
    rel["fora_do_catalogo"] = list(fora.values())
    status = Counter(s["status"] for s in snaps if s["snapshot_uid"] not in fora)
    gate("G1 coleta completa", status.get("completa", 0) == len(snaps) - len(fora),
         dict(status) | ({"fora_do_catalogo (não exigido)": len(fora)} if fora else {}))
    rel["snapshots"] = []
    for s in snaps:
        tipo, params, quando = con.execute("SELECT tipo, parametros_json, coletada_em FROM coleta WHERE id=?", (s["coleta_id"],)).fetchone()
        resp = con.execute("SELECT r.sha256, r.tamanho, LENGTH(o.dados) FROM resposta_bruta r JOIN objeto_bruto o ON o.sha256=r.sha256 "
                           "WHERE r.coleta_id=? ORDER BY r.ordem", (s["coleta_id"],)).fetchall()
        rel["snapshots"].append({"uid": s["snapshot_uid"], "tipo": tipo, "parametros": json.loads(params), "coletada_em": quando,
                                 "status": s["status"], "sha256": [r[0] for r in resp], "bytes": sum(r[1] for r in resp),
                                 "bytes_comprimidos": sum(r[2] for r in resp), "recoleta_de": s.get("recoleta_de")})
    rel["bytes_brutos"] = sum(x["bytes"] for x in rel["snapshots"])
    rel["bytes_comprimidos"] = sum(x["bytes_comprimidos"] for x in rel["snapshots"])
    gate("G2 integridade armazém×banco (após coleta)", not banco.verificar(con, armazem), banco.verificar(con, armazem)[:5])
    if rel["parou_em"]:
        return finalizar(rel, con)

    # ---------------- NORMALIZACAO
    nid, resumo = normalizar.normalizar(con)
    rel["normalizacao"] = {"id": nid, **{k: v for k, v in resumo.items() if k != "problemas"}, "problemas": resumo["problemas"]}
    ph = ",".join("?" * len(lote_ids))
    esperado = 0
    for cid in [c for c in lote_ids if con.execute("SELECT tipo FROM coleta WHERE id=?", (c,)).fetchone()[0] == "rp_listagem"]:
        for (sha,) in con.execute("SELECT sha256 FROM resposta_bruta WHERE coleta_id=?", (cid,)):
            pag = normalizar._pagina(banco.corpo(con, sha))   # mesma leitura do normalizador: pagina invalida nao conta
            esperado += len(pag) if pag is not None else 0
    obtidos = con.execute(f"SELECT COUNT(*) FROM rp_registro WHERE normalizacao_id=? AND coleta_id IN ({ph})", (nid, *lote_ids)).fetchone()[0]
    extras = con.execute(f"SELECT COUNT(*) FROM rp_registro WHERE normalizacao_id=? AND coleta_id IN ({ph}) AND chaves_extras<>'[]'", (nid, *lote_ids)).fetchone()[0]
    ausentes = Counter()
    for (a,) in con.execute(f"SELECT chaves_ausentes FROM rp_registro WHERE normalizacao_id=? AND coleta_id IN ({ph})", (nid, *lote_ids)):
        ausentes.update(json.loads(a))
    base_faltando = sorted(set(ausentes) - OPCIONAIS)
    rel["registros_do_lote"] = obtidos
    gate("G3 fidelidade (registros = bruto; sem chave desconhecida; chaves-base presentes)",
         obtidos == esperado and extras == 0 and not base_faltando,
         {"esperado": esperado, "obtido": obtidos, "com_chaves_extras": extras, "chaves_base_faltando": base_faltando})

    # ---------------- DERIVACAO
    d_atual = derivar.derivar(con, nid)
    d_29 = derivar.derivar(con, nid, EM_29)
    h_atual, = con.execute("SELECT hash_resultado FROM derivacao_execucao WHERE id=?", (d_atual,)).fetchone()
    h_29, = con.execute("SELECT hash_resultado FROM derivacao_execucao WHERE id=?", (d_29,)).fetchone()
    rel["derivacoes"] = {"atual": {"id": d_atual, "hash": h_atual}, "como_estava_29_09": {"id": d_29, "hash": h_29}}
    cont = con.execute("SELECT escopo_json, verificados, falhas FROM verificacao WHERE derivacao_id=? AND descricao LIKE 'continuidade%'",
                       (d_atual,)).fetchall()
    falhas_cont = [(json.loads(e), v, f) for e, v, f in cont if f]
    rel["continuidade"] = [{k: json.loads(e)[k] for k in ("entidade", "de", "para")} | {"verificados": v, "falhas": f} for e, v, f in cont]
    gate("G4 continuidade fechamento→abertura", not falhas_cont, falhas_cont[:5] or f"{len(cont)} pares entidade×ano, 0 falhas")
    gate("G5 regressão temporal ('como estava em 29/09' inalterado)", h_29 == ref_29, {"referencia": ref_29[:16], "obtido": h_29[:16]})
    va, vn = visoes(con, antes_atual[0]), visoes(con, d_atual)
    tocados = {(ex, df) for e, ex, df in [tuple(x["parametros"].get(k) for k in ("entidade", "exercicio", "dataFinal"))
                                          for x in rel["snapshots"] if x["tipo"] == "rp_listagem"]}
    diffs = {k: (va[k], vn[k]) for k in va.keys() & vn.keys() if va[k] != vn[k]}
    colaterais = {k: v for k, v in diffs.items() if (k[4], k[5]) not in tocados}
    rel["visoes"] = {"comuns": len(va.keys() & vn.keys()), "novas": len(vn.keys() - va.keys()), "sumidas": len(va.keys() - vn.keys()),
                     "alteradas_em_cortes_do_lote": len(diffs) - len(colaterais)}
    gate("G6 sem efeito colateral em cortes não tocados pelo lote", not colaterais and not (va.keys() - vn.keys()),
         {"alteradas_fora_do_lote": len(colaterais), "sumidas": len(va.keys() - vn.keys())})

    # ---------------- TESTES
    t_prod, t_inv = pytest(RAIZ / "app"), pytest(RAIZ / "docs/stages/03-data-model/validation")
    rel["testes"] = {"producao": t_prod, "investigacao": t_inv}
    gate("G7 testes (produção + investigação)", t_prod["ok"] and t_inv["ok"], f"{t_prod['resumo']} | {t_inv['resumo']}")

    # ---------------- INTEGRIDADE
    gate("G2b integridade armazém×banco (após processamento)", not banco.verificar(con, armazem), "")

    # ---------------- VALIDACAO
    anom = Counter(t for (t,) in con.execute(f"SELECT tipo FROM anomalia WHERE derivacao_id=? AND coleta_id IN ({ph})", (d_atual, *lote_ids)))
    rel["anomalias_do_lote"] = dict(anom)
    gate("G8 sem anomalia estrutural", not (set(anom) & ESTRUTURAIS), {t: anom[t] for t in set(anom) & ESTRUTURAIS})
    # comportamento x 2025/2026: presenca de chaves, tamanho da programatica, fontes
    perfil = defaultdict(Counter)
    for ex, prog, aus, fonte in con.execute(
            f"SELECT c.exercicio, LENGTH(r.programatica), r.chaves_ausentes, r.fonte_recurso FROM rp_registro r JOIN coleta c ON c.id=r.coleta_id "
            f"WHERE r.normalizacao_id=? AND r.coleta_id IN ({ph})", (nid, *lote_ids)):
        perfil[ex]["registros"] += 1
        perfil[ex][f"programatica_{prog}_dig"] += 1
        perfil[ex]["sem_programatica_detalhada"] += aus != "[]"
        perfil[ex][f"fonte_{len(str(fonte))}_dig"] += 1
    rel["perfil_por_exercicio"] = {ex: dict(c) for ex, c in sorted(perfil.items())}
    rel["pares"] = [dict(zip(("exercicio", "data_final", "relacao", "lado", "pares", "inscrito_a", "inscrito_b", "exec_a", "exec_b"), r))
                    for r in con.execute("SELECT exercicio, data_final, relacao_inscricao, lado_com_execucao, COUNT(*), SUM(inscrito_a_c), "
                                         "SUM(inscrito_b_c), SUM(execucao_a_c), SUM(execucao_b_c) FROM espelhamento_par WHERE derivacao_id=? "
                                         f"AND coleta_a_id IN ({ph}) GROUP BY 1,2,3,4 ORDER BY 1,2,3,4", (d_atual, *lote_ids))]
    exercicios = sorted({x["parametros"].get("exercicio") for x in rel["snapshots"] if x["parametros"].get("exercicio")})
    rel["conciliacao"] = [dict(zip(("exercicio", "data_final", "escopo", "rreo_col", "coluna", "rreo", "api", "diferenca"), r)) for r in con.execute(
        f"SELECT c.exercicio, c.data_final, c.escopo, g.versao, c.coluna, c.valor_rreo_c, c.valor_api_c, c.diferenca_c FROM conciliacao_rreo c "
        f"JOIN regra g ON g.id=c.regra_agregacao_id WHERE c.derivacao_id=? AND c.exercicio IN ({','.join('?' * len(exercicios))}) "
        "ORDER BY 1,2,3,4,5", (d_atual, *exercicios))] if exercicios else []
    rel["rreo_sem_extracao"] = [json.loads(e) for (e,) in con.execute(
        "SELECT escopo_json FROM verificacao WHERE derivacao_id=? AND descricao LIKE 'RREO sem valores%'", (d_atual,))]
    if L.get("recoleta"):
        for s in snaps:
            r = comparador.comparar(con, s["recoleta_de"], s["snapshot_uid"], nid, d_atual)
            comparacoes.append({k: r[k] for k in ("corte", "anterior", "posterior", "bytes_identicos", "contagens",
                                                  "impacto_financeiro_por_grupo", "saldo_s1")} | {"alterados": r["alterados"][:20],
                                                                                                  "novos": r["novos"][:20], "removidos": r["removidos"][:20]})
        rel["comparacoes_temporais"] = comparacoes

    # ---------------- limpeza: so a execucao anterior (reprocessavel); as do lote ficam
    if not rel["parou_em"]:
        # execucao que a protecao considera "em uso" (ex.: ultima de outra vigencia) fica e vai para o relatorio
        rel["execucoes_mantidas"] = []
        antigas = [d for (d,) in con.execute("SELECT id FROM derivacao_execucao WHERE id NOT IN (?,?) ORDER BY id", (d_atual, d_29))]
        for d in antigas:
            try:
                execucoes.apagar(con, cfg, "derivacao", d, d)
            except execucoes.ExclusaoRecusada as e:
                rel["execucoes_mantidas"].append({"derivacao": d, "motivo": str(e)})
        for (n,) in con.execute("SELECT id FROM normalizacao_execucao WHERE id<>? ORDER BY id", (nid,)).fetchall():
            try:
                execucoes.apagar(con, cfg, "normalizacao", n, n)
            except execucoes.ExclusaoRecusada as e:
                rel["execucoes_mantidas"].append({"normalizacao": n, "motivo": str(e)})
        rel["compactacao"] = banco.compactar(con, cfg.banco)
        gate("G2c integridade após limpeza", not banco.verificar(con, armazem), "")
    return finalizar(rel, con)


def finalizar(rel, con):
    rel["fim"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    pasta = RAIZ / "docs/stages/04-pipeline/batches"
    nome = f"LOTE_{rel['lote']}"
    if (pasta / f"{nome}.md").exists():   # relatorio de lote nunca e sobrescrito (ex.: Lote T rodado de novo dias depois)
        nome += "_" + rel["inicio"].replace(":", "").replace("-", "")
    (pasta / f"{nome}.json").write_text(json.dumps(rel, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (pasta / f"{nome}.md").write_text(markdown(rel), encoding="utf-8")
    print(markdown(rel))
    return 0 if not rel["parou_em"] else 1


def markdown(r):
    m = [f"# Lote {r['lote']} — {r['titulo']}", "",
         f"Início {r['inicio']} · fim {r.get('fim', '')} · requisições {r.get('requisicoes', '?')} · "
         f"**{'CONCLUÍDO' if not r['parou_em'] else 'PARADO EM ' + r['parou_em']}**", ""]
    listas = [x for x in r.get("snapshots", []) if x["tipo"] == "rp_listagem"]
    exs = sorted({x["parametros"]["exercicio"] for x in listas})
    ents = sorted({x["parametros"]["entidade"] for x in listas})
    m += [f"- **Exercícios:** {exs}  ·  **Entidades:** {ents}",
          f"- **Snapshots:** {len(r.get('snapshots', []))} ({Counter(x['tipo'] for x in r.get('snapshots', []))})",
          f"- **Registros normalizados do lote:** {r.get('registros_do_lote', '—')}",
          f"- **Tamanho bruto:** {r.get('bytes_brutos', 0):,} bytes ({r.get('bytes_comprimidos', 0):,} comprimidos)".replace(",", "."),
          f"- **Hashes de resultado:** atual `{r.get('derivacoes', {}).get('atual', {}).get('hash', '')[:16]}` · "
          f"como estava em 29/09 `{r.get('derivacoes', {}).get('como_estava_29_09', {}).get('hash', '')[:16]}`", "",
          "## Portões", "", "| Portão | Resultado | Detalhe |", "|---|---|---|"]
    for g, v in r["gates"].items():
        m.append(f"| {g} | {'OK' if v['ok'] else '**FALHOU**'} | {str(v['detalhe'])[:220]} |")
    if r.get("testes"):
        m += ["", f"Testes: produção `{r['testes']['producao']['resumo']}`; investigação `{r['testes']['investigacao']['resumo']}`."]
    m += ["", "## Anomalias do lote", "", f"{r.get('anomalias_do_lote', {})}", "",
          "## Perfil por exercício (comparar com 2025/2026: programática de 28 dígitos, fontes de 3–4 dígitos)", ""]
    for ex, p in r.get("perfil_por_exercicio", {}).items():
        m.append(f"- {ex}: {p}")
    if r.get("fora_do_catalogo"):
        m += ["", "## Consultas fora do catálogo oficial de exercícios (relatadas, não exigidas no G1)", ""]
        m += [f"- entidade {x['entidade']}, {x['exercicio']}: status {x['status']}, registros {x['registros']}" for x in r["fora_do_catalogo"]]
    if r.get("pares"):
        m += ["", "## Pares espelhados nos cortes do lote", "", "| Corte | Relação | Execução | Pares | Inscrito A | Inscrito B | Exec. A | Exec. B |",
              "|---|---|---|--:|--:|--:|--:|--:|"]
        for p in r["pares"]:
            m.append(f"| {p['exercicio']} até {p['data_final']} | {p['relacao']} | {p['lado']} | {p['pares']} | {br(p['inscrito_a'])} | "
                     f"{br(p['inscrito_b'])} | {br(p['exec_a'])} | {br(p['exec_b'])} |")
    if r.get("conciliacao"):
        m += ["", "## Conciliação com o RREO (colunas com diferença ≠ 0)", "", "| Exercício | Corte | Escopo | RREO-COL | Coluna | RREO | API | Diferença |",
              "|---|---|---|---|---|--:|--:|--:|"]
        docs = {(c["exercicio"], c["data_final"], c["escopo"], c["rreo_col"]) for c in r["conciliacao"]}
        for c in r["conciliacao"]:
            if c["diferenca"]:
                m.append(f"| {c['exercicio']} | {c['data_final']} | {c['escopo']} | v{c['rreo_col']} | ({c['coluna']}) | {br(c['rreo'])} | {br(c['api'])} | {br(c['diferenca'])} |")
        zerados = sorted(d for d in docs if not any(c["diferenca"] for c in r["conciliacao"] if (c["exercicio"], c["data_final"], c["escopo"], c["rreo_col"]) == d))
        m += ["", f"Conciliações com TODAS as colunas iguais: {zerados or 'nenhuma'}"]
    if r.get("rreo_sem_extracao"):
        m += ["", f"PDFs de RREO sem valores extraídos (layout): {len(r['rreo_sem_extracao'])}; problemas da normalização: "
              f"{[p['erro'][:80] for p in r.get('normalizacao', {}).get('problemas', [])][:4]}"]
    if r.get("comparacoes_temporais"):
        m += ["", "## Comparações temporais (retrato anterior × recoleta)", "", "| Corte | Anterior | Posterior | Bytes iguais | Novos | Removidos | Alterados | ΔS1 |",
              "|---|---|---|---|--:|--:|--:|--:|"]
        for c in r["comparacoes_temporais"]:
            k = c["corte"]
            m.append(f"| ent {k['entidade']} {k['exercicio']} até {k['data_final']} | {c['anterior']['coletada_em'][5:16]} | {c['posterior']['coletada_em'][5:16]} | "
                     f"{c['bytes_identicos']} | {c['contagens']['novos']} | {c['contagens']['removidos']} | {c['contagens']['alterados']} | {br(c['saldo_s1']['diferenca'])} |")
    return "\n".join(m) + "\n"


CORTE_T = "2026-09-30T00:00:00-03:00"   # Lote T: recoleta os cortes cuja 1a coleta e anterior a isto

if __name__ == "__main__":
    sys.stdout.reconfigure(errors="backslashreplace")   # saida em cp1252 (arquivo) nao derruba o script
    if len(sys.argv) > 2:   # ex.: python executar_lote.py T 2026-10-07T00:00:00-03:00
        CORTE_T = sys.argv[2]
    sys.exit(executar(sys.argv[1]))
