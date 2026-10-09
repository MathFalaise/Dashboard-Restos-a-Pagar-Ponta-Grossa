"""STABLE fingerprints of a database, to prove that two databases have the same content (READ-ONLY).

`execucoes.hash_camada0` still exists (it is the value in the homologated reports), but it only proves the integrity
of the SAME file over time: it includes internal ids and recording timestamps (coletor_versao.registrado_em,
esquema_versao.aplicada_em), which change in a database rebuilt from the store (audit DET-02).

Here each layer is reduced to identifiers that do not depend on the database: snapshot_uid, response order, record
index, SHA-256 of the bytes, rule code and version. So "active database" x "database rebuilt from the store" can be
compared layer by layer:
  * layer 0: collections (parameters, date, status, collector), responses (order, URL, headers, hash, size) and
    evidence;
  * normalization (the most recent): each layer 1 table, with the stable source position;
  * derivation: the hash_resultado (already stable) of the last derivation of each validity, recomputed.
Fields that record WHEN processing ran (executada_em, extraida_em) stay out: they are not content.
"""
import hashlib
import json

from . import derivar

_TABELAS_1 = {
    "rp_registro": ("resposta_id", "indice", None),
    # schema v6: a database without the table (v5) has no refusal - same content as the table empty
    "valor_recusado": ("resposta_id", "indice", None),
    "movimentacao_lancamento": ("resposta_id", "indice", None),
    "rreo_extracao": ("resposta_id", None, ("extraida_em",)),
    "rreo_valor": (None, None, None),
    "entidade_ref": (None, None, None),
    "exercicio_ref": (None, None, None),
}


def _h():
    return hashlib.sha256()


def _atualizar(h, linha):
    h.update(json.dumps(linha, ensure_ascii=False, sort_keys=True, default=str).encode())
    h.update(b"\n")


def camada0(con):
    """Fingerprint of the raw layer by store identifiers."""
    h, n = _h(), {"coletas": 0, "respostas": 0, "objetos": 0, "evidencias": 0}
    for row in con.execute(
            "SELECT c.snapshot_uid, c.tipo, c.endpoint, c.parametros_json, c.coletada_em, c.origem_carimbo, c.status, "
            "c.observacao, v.nome, v.versao, v.sha256_codigo FROM coleta c JOIN coletor_versao v ON v.id = c.coletor_versao_id "
            "ORDER BY c.snapshot_uid"):
        _atualizar(h, ["coleta", *row[:3], json.loads(row[3]), *row[4:]])
        n["coletas"] += 1
    for row in con.execute(
            "SELECT c.snapshot_uid, r.ordem, r.url, r.http_status, r.cabecalhos_json, r.recebida_em, r.sha256, r.tamanho "
            "FROM resposta_bruta r JOIN coleta c ON c.id = r.coleta_id ORDER BY c.snapshot_uid, r.ordem"):
        _atualizar(h, ["resposta", *row[:4], json.loads(row[4] or "{}"), *row[5:]])
        n["respostas"] += 1
    for row in con.execute("SELECT sha256, tamanho FROM objeto_bruto ORDER BY sha256"):
        _atualizar(h, ["objeto", *row])
        n["objetos"] += 1
    for row in con.execute("SELECT evidencia_uid, tipo, descricao, data_documento, caminho_arquivo, sha256, registrada_em, "
                           "origem, observacao FROM evidencia_externa ORDER BY evidencia_uid, id"):
        _atualizar(h, ["evidencia", *row])
        n["evidencias"] += 1
    return {**n, "hash": h.hexdigest()}


def normalizacao(con, nid=None):
    """Fingerprint of each layer 1 table of a normalization (default: the most recent)."""
    if nid is None:
        nid = con.execute("SELECT MAX(id) FROM normalizacao_execucao").fetchone()[0]
    if nid is None:
        return None
    versao = con.execute("SELECT normalizador_versao FROM normalizacao_execucao WHERE id=?", (nid,)).fetchone()[0]
    saida = {"normalizacao": nid, "normalizador_versao": versao, "tabelas": {}}
    for tabela, (col_resp, col_ind, fora) in _TABELAS_1.items():
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({tabela})")
                if r[1] not in ("normalizacao_id", "coleta_id", col_resp, *(fora or ()))]
        if not cols:              # table that does not exist in this schema version: no row
            saida["tabelas"][tabela] = {"linhas": 0, "hash": _h().hexdigest()}
            continue
        sel = ", ".join(f"t.{c}" for c in cols)
        if col_resp:
            sql = (f"SELECT c.snapshot_uid, rb.ordem, {sel} FROM {tabela} t JOIN resposta_bruta rb ON rb.id = t.{col_resp} "
                   f"JOIN coleta c ON c.id = t.coleta_id WHERE t.normalizacao_id=? ORDER BY c.snapshot_uid, rb.ordem"
                   + (f", t.{col_ind}" if col_ind else ""))
        else:
            sql = (f"SELECT c.snapshot_uid, {sel} FROM {tabela} t JOIN coleta c ON c.id = t.coleta_id "
                   f"WHERE t.normalizacao_id=? ORDER BY c.snapshot_uid, {sel}")
        h, n = _h(), 0
        for row in con.execute(sql, (nid,)):
            _atualizar(h, list(row))
            n += 1
        saida["tabelas"][tabela] = {"linhas": n, "hash": h.hexdigest()}
    return saida


def derivacoes(con):
    """Last derivation of each validity: recorded and recomputed hash_resultado (already stable by construction) and the
    semantic hash (values and relations only, without anomaly/check; critical review, item 25)."""
    saida = {}
    for did, vig in con.execute("SELECT MAX(id), vigencia_em FROM derivacao_execucao GROUP BY IFNULL(vigencia_em, '')"):
        gravado, versao = con.execute("SELECT hash_resultado, derivador_versao FROM derivacao_execucao WHERE id=?",
                                      (did,)).fetchone()
        saida[vig or "atual"] = {"derivacao": did, "derivador_versao": versao, "hash_gravado": gravado,
                                 "hash_recalculado": derivar.hash_resultado(con, did),
                                 "hash_semantico": derivar.hash_semantico(con, did)}
    return saida


def resumo(con):
    return {"camada0": camada0(con), "normalizacao": normalizacao(con), "derivacoes": derivacoes(con)}


def comparar(con_a, con_b):
    """Compares two databases layer by layer. `equivalentes` is only True if everything is equal."""
    a, b = resumo(con_a), resumo(con_b)
    c0 = a["camada0"] == b["camada0"]
    na, nb = a["normalizacao"] or {}, b["normalizacao"] or {}
    tabelas = {t: (na.get("tabelas", {}).get(t) == nb.get("tabelas", {}).get(t)) for t in _TABELAS_1}
    norm = na.get("normalizador_versao") == nb.get("normalizador_versao") and all(tabelas.values())
    vigs = sorted(set(a["derivacoes"]) | set(b["derivacoes"]))
    der = {v: (a["derivacoes"].get(v, {}).get("hash_recalculado") == b["derivacoes"].get(v, {}).get("hash_recalculado")
               and a["derivacoes"].get(v, {}).get("hash_recalculado") is not None) for v in vigs}
    integras = all(d["hash_gravado"] == d["hash_recalculado"] for x in (a, b) for d in x["derivacoes"].values())
    # same financial result even when only the diagnostics differ (check text, anomaly detail)
    semantica = {v: (a["derivacoes"].get(v, {}).get("hash_semantico") == b["derivacoes"].get(v, {}).get("hash_semantico")
                     and a["derivacoes"].get(v, {}).get("hash_semantico") is not None) for v in vigs}
    return {"equivalentes": c0 and norm and all(der.values()) and integras,
            "camada0_igual": c0, "normalizacao_igual": norm, "normalizacao_por_tabela": tabelas,
            "derivacao_igual_por_vigencia": der, "resultado_semantico_igual_por_vigencia": semantica,
            "hash_gravado_confere_nos_dois": integras, "a": a, "b": b}
