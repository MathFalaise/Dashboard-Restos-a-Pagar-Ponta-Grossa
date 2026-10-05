"""Regra UNICA do retrato vigente de cada corte de listagem (revisao critica, itens 1 e 15). SOMENTE LEITURA.

Derivacao, consultas e painel escolhem o vigente por estas funcoes. Moram fora de `derivar` porque a interface usa o
painel e nao pode carregar o derivador (test_homologacao: a interface nao tem como processar); `derivar` reexporta os
nomes.

Regra: o vigente de (entidade, exercicio, data_inicial, data_final) e o snapshot COMPLETO mais recente ate `em`
(desempate estavel por snapshot_uid) que NAO tenha chave de negocio repetida. O retrato com repeticao (anomalia
CHAVE-DUP) continua no banco e no armazem, so nao e usado: vale o retrato valido anterior do mesmo corte, ou nenhum.
"""

VERIF_RETRATO_AMBIGUO = "retrato com chave repetida fora da vigência"


def coletas_ambiguas(con, did=None):
    """Coletas com chave de negocio repetida (anomalia CHAVE-DUP) na derivacao `did`; padrao: a derivacao atual mais
    recente. A derivacao em curso passa o conjunto que acabou de calcular; o painel e quem consulta depois leem o
    registrado - assim todos escolhem o mesmo retrato vigente."""
    if did is None:
        did = con.execute("SELECT MAX(id) FROM derivacao_execucao WHERE vigencia_em IS NULL").fetchone()[0]
    if did is None:
        return frozenset()
    return frozenset(c for (c,) in con.execute(
        "SELECT DISTINCT coleta_id FROM anomalia WHERE derivacao_id=? AND tipo='CHAVE-DUP' AND coleta_id IS NOT NULL",
        (did,)))


def coletas_vigentes(con, em=None, excluir=None, limite_coleta=None):
    """Snapshot vigente de cada corte de listagem (sem tipo, completo, sem chave repetida): o mais recente ate `em`.
    Chave (entidade, exercicio, data_inicial, data_final). Desempate estavel por snapshot_uid.
    `excluir`: coletas ambiguas, que nunca sao vigentes; padrao: as registradas (coletas_ambiguas).
    `limite_coleta`: so coletas com id ate ele (o painel considera so o que a normalizacao processou)."""
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
