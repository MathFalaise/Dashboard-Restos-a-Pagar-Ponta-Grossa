"""Comparador de dois snapshots do MESMO corte. Somente leitura: nunca escreve no banco nem no armazem.

Relata fatos, nao causas:
  * registros novos, removidos, comuns e alterados, pela chave (entidade, anoempenho, empenho);
  * cada campo alterado com valor ANTERIOR e POSTERIOR (e a diferenca, se monetario);
  * impacto financeiro por campo e por grupo (inscricao, pagamentos, cancelamentos, liquidacoes...);
  * mudancas de classificacao e de saldos derivados (categoria, faixas, S1-S3), se houver derivacao;
  * registros ligados a pares espelhados (entidade 1 <-> 15).
Nenhuma alteracao e chamada de "cancelamento", "correcao" ou "erro": isso exige evidencia adicional.

Chave repetida no mesmo snapshot nao e descartada: da segunda ocorrencia em diante, a chave ganha um
quarto elemento com o numero da ocorrencia.
Os valores derivados sao ligados a cada registro pela posicao de origem (resposta, indice), nunca
pela chave de negocio - assim duas ocorrencias da mesma chave nao se confundem.
"""
from collections import defaultdict

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
COPIA_BASE, ENT_COPIA, ENT_ORIGINAL = 2_400_000, 1, 15
# respostas da coleta como lista: a consulta usa a chave primaria (id da execucao, resposta_id, indice)
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
        chave = k if dup[k] == 1 else (*k, f"ocorrência {dup[k]}")  # chave repetida nao e descartada
        por_chave[chave] = {"posicao": tuple(row[0:2]), **dict(zip(DINHEIRO + OUTROS, row[5:]))}
    return por_chave, sorted(k for k, n in dup.items() if n > 1)


def _derivados(con, did, cid):
    """{(resposta_id, indice): valores derivados} da coleta na derivacao `did`."""
    if not did:
        return {}
    cur = con.execute(f"SELECT resposta_id, indice, {', '.join(DERIVADOS)} FROM rp_derivado "
                      f"WHERE derivacao_id=? AND {_DA_COLETA}", (did, cid, cid))
    return {tuple(r[:2]): dict(zip(DERIVADOS, r[2:])) for r in cur}


def _em_par(con, did, cids):
    """Chaves de registros que participam de um par espelhado na derivacao `did` (qualquer lado)."""
    if not did:
        return set()
    out = set()
    q = ("SELECT entidade_a, anoempenho_a, empenho_a, entidade_b, anoempenho_b, empenho_b FROM espelhamento_par "
         "WHERE derivacao_id=? AND (coleta_a_id IN ({0}) OR coleta_b_id IN ({0}))").format(",".join("?" * len(cids)))
    for ea, aa, pa, eb, ab, pb in con.execute(q, (did, *cids, *cids)):
        out |= {(ea, aa, pa), (eb, ab, pb)}
    return out


def _espelhamento(chave, pares):
    e, ano, emp = chave[:3]
    if chave[:3] in pares:
        return "em par espelhado"
    if e == ENT_COPIA and emp >= COPIA_BASE:
        return "cópia 24xxxxx (sem par nesta derivação)"
    return None


def comparar(con, ref_a, ref_b, nid=None, did=None):
    """Compara o snapshot A (anterior) com o B (posterior). Nao escreve nada."""
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
    da, db = _derivados(con, did, a["id"]), _derivados(con, did, b["id"])
    pares = _em_par(con, did, [a["id"], b["id"]])

    novos = sorted(rb.keys() - ra.keys(), key=str)
    removidos = sorted(ra.keys() - rb.keys(), key=str)
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
                              "campos": campos, "classificacao_e_saldos": deriv, "espelhamento": _espelhamento(k, pares)})

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
    registro = lambda regs, k: {"chave": k, "posicao": regs[k]["posicao"], "espelhamento": _espelhamento(k, pares),
                                **{c: regs[k][c] for c in DINHEIRO}}
    return {
        "corte": dict(zip(CORTE, a["corte"])),
        "anterior": {"snapshot_uid": a["snapshot_uid"], "coletada_em": a["coletada_em"], "registros": len(ra)},
        "posterior": {"snapshot_uid": b["snapshot_uid"], "coletada_em": b["coletada_em"], "registros": len(rb)},
        "normalizacao": nid, "derivacao": did,
        "bytes_identicos": shas(a["id"]) == shas(b["id"]),
        "chaves_duplicadas": {"anterior": dup_a, "posterior": dup_b},
        "contagens": {"novos": len(novos), "removidos": len(removidos), "comuns": len(comuns), "alterados": len(alterados),
                      "alterados_em_espelhamento": sum(1 for x in alterados if x["espelhamento"]),
                      "novos_ou_removidos_em_espelhamento": sum(1 for k in novos + removidos if _espelhamento(k, pares))},
        "novos": [registro(rb, k) for k in novos],
        "removidos": [registro(ra, k) for k in removidos],
        "alterados": alterados,
        "impacto_financeiro_por_campo": impacto,
        "impacto_financeiro_por_grupo": grupos,
        "saldo_s1": s1,
    }
