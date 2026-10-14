"""Source freshness and retrospective changes (corrective audit of 13/10/2026, item 7). READ-ONLY.

The Elotech API is not immutable: a cut-off already closed can come back with other values (cancellations recorded
after the first collection, payments and liquidations changed backwards). The store keeps every snapshot; this module
compares, for every cut-off with more than one complete snapshot, each snapshot with the previous one (rp.comparador)
and reports:
  * per cut-off: counts of new, removed and changed records and the financial impact per group;
  * per commitment: each money field that changed, before -> after, and the difference (impact by commitment);
  * an ALERT when the change is retrospective: the cut-off had already ended when the previous snapshot was collected,
    so the change rewrote a closed period.
Dates are kept apart, as the evidence allows: the cut-off end (data_final, the accounting period), the collection
instant of each snapshot (coletada_em) and, for a changed commitment, the dates of its movement entries when the
movement was collected (the date the entry carries in the API). The date the entry was RECORDED in the municipal
system is not in the API: it is reported as unavailable, never assumed equal to the document date.

`atualidade` measures freshness: last collection per type, days since then, cut-offs whose newest snapshot is not
processed yet (collected and stored, not yet published) and cut-offs with retrospective changes.
"""
from datetime import datetime

from . import comparador, instante
from .comparador import DINHEIRO

CAMPOS_DE_IMPACTO = DINHEIRO


def _cortes_com_varios(con, limite):
    return con.execute(
        "SELECT entidade, exercicio, data_inicial, data_final FROM coleta WHERE tipo='rp_listagem' AND "
        "tipo_pesquisa IS NULL AND status='completa' AND id <= ? GROUP BY entidade, exercicio, data_inicial, data_final "
        "HAVING COUNT(*) > 1 ORDER BY exercicio, data_final, entidade", (limite,)).fetchall()


def _movimentos(con, nid, entidade, anoempenho, empenho):
    """Movement entries collected for the commitment (date of the entry in the API, type, value), newest normalization."""
    try:
        return [{"data": d, "tipo": t, "valor_c": v} for d, t, v in con.execute(
            "SELECT data, tipo_lancamento, valor_c FROM movimentacao_lancamento WHERE normalizacao_id=? AND entidade=? "
            "AND anoempenho=? AND empenho=? ORDER BY data", (nid, entidade, anoempenho, empenho))]
    except Exception:       # older schema without these columns: no movement detail, never a guess
        return None


def alteracoes_retrospectivas(con, nid=None, did=None, limite_empenhos=None):
    """Every pair of consecutive complete snapshots of the same cut-off, with the impact per group and per commitment."""
    if nid is None:
        nid = con.execute("SELECT MAX(id) FROM normalizacao_execucao").fetchone()[0]
    if nid is None:
        return {"normalizacao": None, "cortes": [], "alertas": 0}
    limite = con.execute("SELECT ultima_coleta_id FROM normalizacao_execucao WHERE id=?", (nid,)).fetchone()[0]
    limite = limite if limite is not None else con.execute("SELECT MAX(id) FROM coleta").fetchone()[0]
    cortes, alertas = [], 0
    for e, ex, di, df in _cortes_com_varios(con, limite):
        snaps = con.execute(
            "SELECT id, snapshot_uid, coletada_em FROM coleta WHERE tipo='rp_listagem' AND tipo_pesquisa IS NULL AND "
            "status='completa' AND id <= ? AND entidade=? AND exercicio=? AND data_inicial=? AND data_final=? "
            "ORDER BY coletada_em, id", (limite, e, ex, di, df)).fetchall()
        for (ia, ua, ta), (ib, ub, tb) in zip(snaps, snaps[1:]):
            r = comparador.comparar(con, ia, ib, nid=nid, did=did)
            mudou = r["contagens"]["novos"] or r["contagens"]["removidos"] or r["contagens"]["alterados"]
            if not mudou:
                continue
            retro = df < ta[:10]          # the period had ended when the previous snapshot was taken
            alertas += retro
            empenhos = []
            for x in r["alterados"]:
                dif = {c["campo"]: c["diferenca"] for c in x["campos"] if c["campo"] in CAMPOS_DE_IMPACTO}
                if not dif:
                    continue
                ent, ano, emp = x["chave"][:3]
                empenhos.append({"chave": list(x["chave"]), "diferencas_c": dif,
                                 "movimentacao": _movimentos(con, nid, ent, ano, emp),
                                 "data_de_registro_no_sistema": "não disponível na API",
                                 "em_par_espelhado": bool(x["espelhamento"])})
            empenhos.sort(key=lambda y: -sum(abs(v) for v in y["diferencas_c"].values()))
            cortes.append({"entidade": e, "exercicio": ex, "data_final": df,
                           "anterior": {"snapshot_uid": ua, "coletada_em": ta},
                           "posterior": {"snapshot_uid": ub, "coletada_em": tb},
                           "retrospectiva": retro, "contagens": r["contagens"],
                           "impacto_por_grupo": r["impacto_financeiro_por_grupo"], "saldo_s1": r["saldo_s1"],
                           "impacto_completo": r["impacto_completo"],
                           "empenhos": empenhos[:limite_empenhos] if limite_empenhos else empenhos,
                           "empenhos_alterados_com_valor": len(empenhos)})
    return {"normalizacao": nid, "cortes": cortes, "alertas": alertas,
            "nota": ("Alerta = alteração retrospectiva: o corte já tinha terminado quando o retrato anterior foi "
                     "coletado. Datas: data_final = fim do período contábil; coletada_em = consulta à API; data de "
                     "registro do lançamento no sistema municipal = não disponível na API.")}


def atualidade(con, agora=None):
    """Freshness of the base: last collection per type, days since the last listing, snapshots stored but not yet
    processed (not published) and the number of retrospective alerts."""
    agora = datetime.fromisoformat(instante(agora) or datetime.now().astimezone().isoformat(timespec="seconds"))
    por_tipo = {t: q for t, q in con.execute("SELECT tipo, MAX(coletada_em) FROM coleta WHERE status='completa' "
                                             "GROUP BY tipo")}
    ultima = por_tipo.get("rp_listagem")
    nid = con.execute("SELECT MAX(id) FROM normalizacao_execucao").fetchone()[0]
    lim = con.execute("SELECT ultima_coleta_id FROM normalizacao_execucao WHERE id=?", (nid,)).fetchone()[0] if nid else 0
    pendentes = con.execute("SELECT COUNT(*) FROM coleta WHERE tipo='rp_listagem' AND id > ?", (lim or 0,)).fetchone()[0]
    retro = alteracoes_retrospectivas(con, nid) if nid else {"alertas": 0, "cortes": []}
    return {"agora": agora.isoformat(timespec="seconds"), "ultima_coleta_por_tipo": por_tipo,
            "dias_desde_a_ultima_listagem": (agora - datetime.fromisoformat(ultima)).days if ultima else None,
            "retratos_armazenados_nao_processados": pendentes,
            "cortes_com_alteracao": len(retro["cortes"]), "alertas_retrospectivos": retro["alertas"]}
