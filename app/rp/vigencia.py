"""The SINGLE rule for the current snapshot of each listing cut-off (critical review, items 1 and 15). READ-ONLY.

Derivation, queries and panel pick the current snapshot through these functions. They live outside `derivar`
because the interface uses the panel and must not load the deriver (test_homologacao: the interface cannot
process); `derivar` re-exports the names.

Rule: the current snapshot of (entidade, exercicio, data_inicial, data_final) is the most recent COMPLETE snapshot
up to `em` (stable tie-break by snapshot_uid) that has NO repeated business key and NO refused money field. A
snapshot with a repetition (CHAVE-DUP anomaly) or with a money field missing, null or invalid (VALOR-RECUSADO anomaly,
since 09/10/2026) stays in the database and in the store, it is just not used: the previous valid snapshot of the
same cut-off applies, or none. Summing it would either count a key twice or leave a record out of the total.
"""

VERIF_RETRATO_AMBIGUO = "retrato com chave repetida fora da vigência"
VERIF_RETRATO_VALOR_RECUSADO = "retrato com valor monetário recusado fora da vigência"
# Anomaly types that keep a snapshot from being the current one, in order of precedence for the reason shown.
TIPOS_QUE_RECUSAM_O_RETRATO = ("CHAVE-DUP", "VALOR-RECUSADO")


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
        filtros.append(" AND id <= ?")
        params.append(limite_coleta)
    if em:
        filtros.append(" AND coletada_em <= ?")
        params.append(em)
    sql = ("SELECT id, entidade, exercicio, data_inicial, data_final FROM coleta WHERE tipo='rp_listagem' "
           "AND status='completa' AND tipo_pesquisa IS NULL" + "".join(filtros) + " ORDER BY coletada_em, snapshot_uid")
    vig = {}
    for cid, e, ex, di, df in con.execute(sql, params):
        if cid not in excluir:
            vig[(e, ex, di, df)] = cid
    return vig
