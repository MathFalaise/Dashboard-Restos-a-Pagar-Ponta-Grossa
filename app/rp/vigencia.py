"""The SINGLE rule for the current snapshot of each listing cut-off (critical review, items 1 and 15). READ-ONLY.

Derivation, queries and panel pick the current snapshot through these functions. They live outside `derivar`
because the interface uses the panel and must not load the deriver (test_homologacao: the interface cannot
process); `derivar` re-exports the names.

Rule: the current snapshot of (entidade, exercicio, data_inicial, data_final) is the most recent COMPLETE snapshot
up to `em` (stable tie-break by snapshot_uid) that has NO repeated business key. A snapshot with a repetition
(CHAVE-DUP anomaly) stays in the database and in the store, it is just not used: the previous valid snapshot of the
same cut-off applies, or none.
"""

VERIF_RETRATO_AMBIGUO = "retrato com chave repetida fora da vigência"


def coletas_ambiguas(con, did=None):
    """Collections with a repeated business key (CHAVE-DUP anomaly) in derivation `did`; default: the most recent
    current derivation. The derivation in progress passes the set it just computed; the panel and later readers use
    what was recorded - so everyone picks the same current snapshot."""
    if did is None:
        did = con.execute("SELECT MAX(id) FROM derivacao_execucao WHERE vigencia_em IS NULL").fetchone()[0]
    if did is None:
        return frozenset()
    return frozenset(c for (c,) in con.execute(
        "SELECT DISTINCT coleta_id FROM anomalia WHERE derivacao_id=? AND tipo='CHAVE-DUP' AND coleta_id IS NOT NULL",
        (did,)))


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
