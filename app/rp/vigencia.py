"""The SINGLE rule for the current snapshot of each listing cut-off (critical review, items 1 and 15). READ-ONLY.

Derivation, queries and panel pick the current snapshot through these functions. They live outside `derivar`
because the interface uses the panel and must not load the deriver (test_homologacao: the interface cannot
process); `derivar` re-exports the names.

Rule (v2, 09/10/2026): the current snapshot of (entidade, exercicio, data_inicial, data_final) is the most recent
COMPLETE snapshot AVAILABLE at `em` that has NO repeated business key and NO refused money field.
  * available at `em` = CONCLUDED up to `em` (coleta_tempo.concluida_em, schema v7). Until v1 the START
    (coletada_em) was compared: a collection started before `em` and finished after it counted as available at `em`,
    when part of its pages did not exist yet. A snapshot without evidence of its conclusion is never available to a
    query with a date (it is to the current one, without a date);
  * most recent = order by start, then conclusion, then snapshot_uid - all in canonical form (rp.instante), so two
    equivalent time zones compare equal and two collections with the same start are ordered by which ended last;
  * every instant compared as text is canonical (Brasilia offset): `em` goes through rp.instante, and coleta_tempo
    refuses a non-canonical instant by trigger.
The selection SQL lives in filtro_disponivel/ordem below: derivation and panel layer use the same text. A
snapshot with a repetition (CHAVE-DUP anomaly) or with a money field missing, null or invalid (VALOR-RECUSADO anomaly,
since 09/10/2026) stays in the database and in the store, it is just not used: the previous valid snapshot of the
same cut-off applies, or none. Summing it would either count a key twice or leave a record out of the total.
"""

from . import instante

VERSAO = "rp-vigencia/2"
VERIF_RETRATO_AMBIGUO = "retrato com chave repetida fora da vigência"
VERIF_RETRATO_VALOR_RECUSADO = "retrato com valor monetário recusado fora da vigência"
# Anomaly types that keep a snapshot from being the current one, in order of precedence for the reason shown.
TIPOS_QUE_RECUSAM_O_RETRATO = ("CHAVE-DUP", "VALOR-RECUSADO")


def filtro_disponivel(em, alias="c"):
    """(SQL, params): the collection `alias` is available at `em` - it was CONCLUDED up to `em`. Empty without `em`
    (the current state: every recorded collection is concluded, since its manifest is written at the end)."""
    if not em:
        return "", ()
    # canonical here too (idempotent): a date without time or another offset is never compared as raw text
    return (f" AND EXISTS (SELECT 1 FROM coleta_tempo t WHERE t.coleta_id = {alias}.id AND t.concluida_em IS NOT NULL "
            "AND t.concluida_em <= ?)", (instante(em),))


def ordem(alias="c", desc=False):
    """ORDER BY terms for "most recent": canonical start, then conclusion, then snapshot_uid (deterministic)."""
    d = " DESC" if desc else ""
    sub = f"(SELECT t.{{}} FROM coleta_tempo t WHERE t.coleta_id = {alias}.id)"
    return (f"COALESCE({sub.format('inicio_em')}, {alias}.coletada_em){d}, {sub.format('concluida_em')}{d}, "
            f"{alias}.snapshot_uid{d}")


def coletas_recusadas(con, did=None):
    """{collection: anomaly type} of the collections that can never be current in derivation `did` (default: the
    most recent current derivation). A collection with both types gets CHAVE-DUP (TIPOS_QUE_RECUSAM_O_RETRATO order)."""
    if did is None:
        did = con.execute("SELECT MAX(id) FROM derivacao_execucao WHERE vigencia_em IS NULL").fetchone()[0]
    if did is None:
        return {}
    saida = {}
    for tipo in TIPOS_QUE_RECUSAM_O_RETRATO:
        for (c,) in con.execute("SELECT DISTINCT coleta_id FROM anomalia WHERE derivacao_id=? AND tipo=? AND "
                                "coleta_id IS NOT NULL", (did, tipo)):
            saida.setdefault(c, tipo)
    return saida


def coletas_ambiguas(con, did=None):
    """Collections that are never current (repeated business key or refused money field: coletas_recusadas) in
    derivation `did`; default: the most recent current derivation. The derivation in progress passes the set it just
    computed; the panel and later readers use what was recorded - so everyone picks the same current snapshot."""
    return frozenset(coletas_recusadas(con, did))


def coletas_vigentes(con, em=None, excluir=None, limite_coleta=None):
    """Current snapshot of each listing cut-off (untyped, complete, no repeated key): the most recent up to `em`.
    Key (entidade, exercicio, data_inicial, data_final). Stable tie-break by snapshot_uid.
    `excluir`: ambiguous collections, never current; default: the recorded ones (coletas_ambiguas).
    `limite_coleta`: only collections with id up to it (the panel only considers what the normalization processed)."""
    excluir = coletas_ambiguas(con) if excluir is None else excluir
    filtros, params = [], []
    if limite_coleta is not None:
        filtros.append(" AND c.id <= ?")
        params.append(limite_coleta)
    if em:                                      # the same rule as filtro_disponivel, through the join below
        filtros.append(" AND t.concluida_em IS NOT NULL AND t.concluida_em <= ?")
        params.append(instante(em))
    # hot path of the panel (called once per cut-off and series point): a join instead of ordem()'s correlated
    # subqueries - same order (canonical start, conclusion, snapshot_uid); measured 09/10/2026 in item 10 of the
    # correction request (docs/audits/CORRECOES_20261009.md, phase D)
    sql = ("SELECT c.id, c.entidade, c.exercicio, c.data_inicial, c.data_final FROM coleta c LEFT JOIN coleta_tempo t "
           "ON t.coleta_id = c.id WHERE c.tipo='rp_listagem' AND c.status='completa' AND c.tipo_pesquisa IS NULL" +
           "".join(filtros) + " ORDER BY COALESCE(t.inicio_em, c.coletada_em), t.concluida_em, c.snapshot_uid")
    vig = {}
    for cid, e, ex, di, df in con.execute(sql, params):
        if cid not in excluir:
            vig[(e, ex, di, df)] = cid
    return vig
