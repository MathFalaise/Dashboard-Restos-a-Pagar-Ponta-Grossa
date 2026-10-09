"""Comparison of two snapshots of the SAME cut-off. Read-only: never writes to the database or the store.

It reports facts, not causes:
  * new, removed, common and changed records, by the key (entidade, anoempenho, empenho);
  * each changed field with its PREVIOUS and LATER value (and the difference, if monetary);
  * financial impact per field and per group (inscription, payments, cancellations, liquidations...);
  * changes in classification and in derived balances (category, bands, S1-S3), if there is a derivation;
  * records linked to mirrored pairs (entity 1 <-> 15).
No change is called "cancellation", "correction" or "error": that requires additional evidence.

A key repeated within the same snapshot is not discarded: from the second occurrence on, the key gets a fourth
element with the occurrence number.
A record whose money field was refused by the normalization (valor_recusado, schema v6) has no value: it is listed
in `recusados` and never counted as new, removed or changed, and `impacto_completo` becomes False - the financial
impact then covers only the records with known values.
Derived values are linked to each record by its source position (response, index), never by the business key -
so two occurrences of the same key are never mixed up.
"""
import sqlite3
from collections import defaultdict

from . import regras

DINHEIRO = ["proc_c", "aproc_c", "cancelado_proc_c", "pago_proc_c", "pago_proc_estornado_c", "cancelado_aproc_c",
            "pago_aproc_c", "pago_aproc_estornado_c", "liquidado_c", "retencao_c"]
OUTROS = ["empenho_exercicio", "data_emissao", "programatica", "fonte_recurso", "descricao_fonte", "fornecedor", "nome",
          "cnpj", "cnpj_nome", "orgao", "unidade", "funcao", "sub_funcao", "programa", "projeto", "elemento",
          "desdobra_desp", "sub_desdobramento", "chaves_ausentes", "chaves_extras"]
GRUPOS = {"inscricao_processada": ["proc_c"], "inscricao_nao_processada": ["aproc_c"],
          "pagamentos": ["pago_proc_c", "pago_aproc_c"], "estornos_de_pagamento": ["pago_proc_estornado_c", "pago_aproc_estornado_c"],
          "cancelamentos": ["cancelado_proc_c", "cancelado_aproc_c"], "liquidacoes": ["liquidado_c"], "retencoes": ["retencao_c"]}
DERIVADOS = ["categoria", "faixa_processado", "faixa_nao_processado", "s1_saldo_total_c", "s2_a_liquidar_c",
             "s3_liquidado_a_pagar_c", "cancel_processado_c", "cancel_nao_processado_c"]
CORTE = ["tipo", "entidade", "exercicio", "data_inicial", "data_final", "tipo_pesquisa"]
# Identifying a 24xxxxx copy uses the parameters of rule PAR-24 v1 (regra_parametro table), not constants.
# the collection's responses as a list: the query uses the primary key (run id, resposta_id, indice)
_DA_COLETA = "resposta_id IN (SELECT id FROM resposta_bruta WHERE coleta_id=?) AND coleta_id=?"


class CorteDiferente(ValueError):
    pass


def _coleta(con, ref):
    col = "snapshot_uid" if isinstance(ref, str) and not ref.isdigit() else "id"
    r = con.execute(f"SELECT id, snapshot_uid, coletada_em, {', '.join(CORTE)} FROM coleta WHERE {col}=?", (ref,)).fetchone()
    if not r:
        raise KeyError(f"snapshot {ref} não existe")
    return {"id": r[0], "snapshot_uid": r[1], "coletada_em": r[2], "corte": r[3:]}


def _registros(con, nid, cid):
    cur = con.execute(f"SELECT resposta_id, indice, entidade, anoempenho, empenho, {', '.join(DINHEIRO + OUTROS)} "
                      f"FROM rp_registro WHERE normalizacao_id=? AND {_DA_COLETA} ORDER BY resposta_id, indice",
                      (nid, cid, cid))
    por_chave, dup = {}, defaultdict(int)
    for row in cur:
        k = tuple(row[2:5])
        dup[k] += 1
        chave = k if dup[k] == 1 else (*k, f"ocorrência {dup[k]}")  # a repeated key is not discarded
        por_chave[chave] = {"posicao": tuple(row[0:2]), **dict(zip(DINHEIRO + OUTROS, row[5:]))}
    return por_chave, sorted(k for k, n in dup.items() if n > 1)


def _recusados(con, nid, cid):
    """{key: {"posicao", "campos": {field: nature}}} of the collection's records refused by the normalization."""
    try:
        linhas = con.execute(f"SELECT resposta_id, indice, entidade, anoempenho, empenho, campo, natureza FROM "
                             f"valor_recusado WHERE normalizacao_id=? AND {_DA_COLETA} ORDER BY resposta_id, indice, "
                             "campo", (nid, cid, cid)).fetchall()
    except sqlite3.OperationalError as e:          # schema before v6: there is no refusal
        if "no such table" not in str(e):
            raise
        return {}
    saida = {}
    for rid, i, e, ano, emp, campo, natureza in linhas:
        saida.setdefault((e, ano, emp), {"posicao": (rid, i), "campos": {}})["campos"][campo] = natureza
    return saida


def _derivados(con, did, cid):
    """{(resposta_id, indice): derived values} of the collection in derivation `did`."""
    if not did:
        return {}
    cur = con.execute(f"SELECT resposta_id, indice, {', '.join(DERIVADOS)} FROM rp_derivado "
                      f"WHERE derivacao_id=? AND {_DA_COLETA}", (did, cid, cid))
    return {tuple(r[:2]): dict(zip(DERIVADOS, r[2:])) for r in cur}


def _em_par(con, did, cids):
    """Keys of records that take part in a mirrored pair in derivation `did` (either side)."""
    if not did:
        return set()
    out = set()
    q = ("SELECT entidade_a, anoempenho_a, empenho_a, entidade_b, anoempenho_b, empenho_b FROM espelhamento_par "
         "WHERE derivacao_id=? AND (coleta_a_id IN ({0}) OR coleta_b_id IN ({0}))").format(",".join("?" * len(cids)))
    for ea, aa, pa, eb, ab, pb in con.execute(q, (did, *cids, *cids)):
        out |= {(ea, aa, pa), (eb, ab, pb)}
    return out


def _espelhamento(chave, pares, par):
    e, ano, emp = chave[:3]
    if chave[:3] in pares:
        return "em par espelhado"
    if e == par["entidade_copia"] and emp >= par["base_empenho_copia"]:
        return "cópia 24xxxxx (sem par nesta derivação)"
    return None


def comparar(con, ref_a, ref_b, nid=None, did=None):
    """Compares snapshot A (previous) with B (later). Writes nothing."""
    a, b = _coleta(con, ref_a), _coleta(con, ref_b)
    if a["corte"] != b["corte"]:
        raise CorteDiferente(f"cortes diferentes: {a['corte']} × {b['corte']}")
    if nid is None:
        nid = con.execute("SELECT MAX(normalizacao_id) FROM rp_registro WHERE coleta_id IN (?,?)", (a["id"], b["id"])).fetchone()[0]
    if did is None:
        did = con.execute("SELECT MAX(d.id) FROM derivacao_execucao d WHERE d.normalizacao_id=? AND "
                          "(SELECT COUNT(DISTINCT coleta_id) FROM rp_derivado WHERE derivacao_id=d.id AND coleta_id IN (?,?))=2",
                          (nid, a["id"], b["id"])).fetchone()[0]
    shas = lambda c: [s for (s,) in con.execute("SELECT sha256 FROM resposta_bruta WHERE coleta_id=? ORDER BY ordem", (c,))]
    ra, dup_a = _registros(con, nid, a["id"])
    rb, dup_b = _registros(con, nid, b["id"])
    xa, xb = _recusados(con, nid, a["id"]), _recusados(con, nid, b["id"])
    da, db = _derivados(con, did, a["id"]), _derivados(con, did, b["id"])
    pares = _em_par(con, did, [a["id"], b["id"]])
    par = regras.parametros(con, "PAR-24", 1)

    novos = sorted(rb.keys() - ra.keys() - xa.keys(), key=str)       # refused on the other side: not new
    removidos = sorted(ra.keys() - rb.keys() - xb.keys(), key=str)   # refused on the other side: not removed
    comuns = sorted(ra.keys() & rb.keys(), key=str)
    alterados = []
    for k in comuns:
        x, y = ra[k], rb[k]
        dx, dy = da.get(x["posicao"], {}), db.get(y["posicao"], {})
        campos = [{"campo": c, "antes": x[c], "depois": y[c], **({"diferenca": y[c] - x[c]} if c in DINHEIRO else {})}
                  for c in DINHEIRO + OUTROS if x[c] != y[c]]
        deriv = [{"campo": c, "antes": dx.get(c), "depois": dy.get(c)} for c in DERIVADOS if dx.get(c) != dy.get(c)]
        if campos or deriv:
            alterados.append({"chave": k, "posicao_antes": x["posicao"], "posicao_depois": y["posicao"],
                              "campos": campos, "classificacao_e_saldos": deriv, "espelhamento": _espelhamento(k, pares, par)})

    impacto = {}
    for c in DINHEIRO:
        de_novos = sum(rb[k][c] for k in novos)
        de_removidos = -sum(ra[k][c] for k in removidos)
        de_alterados = sum(rb[k][c] - ra[k][c] for k in comuns)
        impacto[c] = {"antes": sum(v[c] for v in ra.values()), "depois": sum(v[c] for v in rb.values()),
                      "diferenca": de_novos + de_removidos + de_alterados,
                      "de_registros_novos": de_novos, "de_registros_removidos": de_removidos, "de_registros_alterados": de_alterados}
    grupos = {g: {"antes": sum(impacto[c]["antes"] for c in cs), "depois": sum(impacto[c]["depois"] for c in cs),
                  "diferenca": sum(impacto[c]["diferenca"] for c in cs)} for g, cs in GRUPOS.items()}
    s1 = {"antes": sum(v["s1_saldo_total_c"] for v in da.values()), "depois": sum(v["s1_saldo_total_c"] for v in db.values())}
    s1["diferenca"] = s1["depois"] - s1["antes"]
    registro = lambda regs, k: {"chave": k, "posicao": regs[k]["posicao"], "espelhamento": _espelhamento(k, pares, par),
                                **{c: regs[k][c] for c in DINHEIRO}}
    return {
        "corte": dict(zip(CORTE, a["corte"])),
        "anterior": {"snapshot_uid": a["snapshot_uid"], "coletada_em": a["coletada_em"], "registros": len(ra)},
        "posterior": {"snapshot_uid": b["snapshot_uid"], "coletada_em": b["coletada_em"], "registros": len(rb)},
        "normalizacao": nid, "derivacao": did,
        "bytes_identicos": shas(a["id"]) == shas(b["id"]),
        "chaves_duplicadas": {"anterior": dup_a, "posterior": dup_b},
        "recusados": {"anterior": [{"chave": k, **v} for k, v in sorted(xa.items(), key=lambda x: str(x[0]))],
                      "posterior": [{"chave": k, **v} for k, v in sorted(xb.items(), key=lambda x: str(x[0]))]},
        "impacto_completo": not (xa or xb),
        "contagens": {"novos": len(novos), "removidos": len(removidos), "comuns": len(comuns), "alterados": len(alterados),
                      "alterados_em_espelhamento": sum(1 for x in alterados if x["espelhamento"]),
                      "novos_ou_removidos_em_espelhamento": sum(1 for k in novos + removidos if _espelhamento(k, pares, par))},
        "novos": [registro(rb, k) for k in novos],
        "removidos": [registro(ra, k) for k in removidos],
        "alterados": alterados,
        "impacto_financeiro_por_campo": impacto,
        "impacto_financeiro_por_grupo": grupos,
        "saldo_s1": s1,
    }
