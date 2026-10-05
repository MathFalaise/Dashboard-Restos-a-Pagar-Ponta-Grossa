"""Impressoes digitais ESTAVEIS de um banco, para provar que dois bancos tem o mesmo conteudo (SOMENTE LEITURA).

`execucoes.hash_camada0` continua existindo (e o valor dos relatorios homologados), mas so prova a integridade do MESMO
arquivo ao longo do tempo: ele inclui ids internos e carimbos de registro (coletor_versao.registrado_em,
esquema_versao.aplicada_em), que mudam num banco reconstruido a partir do armazem (auditoria DET-02).

Aqui cada camada e reduzida a identificadores que nao dependem do banco: snapshot_uid, ordem da resposta, indice do
registro, SHA-256 dos bytes, codigo e versao da regra. Assim "banco ativo" x "banco reconstruido do armazem" pode ser
comparado camada a camada:
  * camada 0: coletas (parametros, data, status, coletor), respostas (ordem, URL, cabecalhos, hash, tamanho) e evidencias;
  * normalizacao (a mais recente): cada tabela da camada 1, com a posicao de origem estavel;
  * derivacao: o hash_resultado (ja estavel) da ultima derivacao de cada vigencia, recalculado.
Campos que registram QUANDO o processamento rodou (executada_em, extraida_em) ficam fora: nao sao conteudo.
"""
import hashlib
import json

from . import derivar

_TABELAS_1 = {
    "rp_registro": ("resposta_id", "indice", None),
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
    """Impressao da camada bruta por identificadores do armazem."""
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
    """Impressao de cada tabela da camada 1 de uma normalizacao (padrao: a mais recente)."""
    if nid is None:
        nid = con.execute("SELECT MAX(id) FROM normalizacao_execucao").fetchone()[0]
    if nid is None:
        return None
    versao = con.execute("SELECT normalizador_versao FROM normalizacao_execucao WHERE id=?", (nid,)).fetchone()[0]
    saida = {"normalizacao": nid, "normalizador_versao": versao, "tabelas": {}}
    for tabela, (col_resp, col_ind, fora) in _TABELAS_1.items():
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({tabela})")
                if r[1] not in ("normalizacao_id", "coleta_id", col_resp, *(fora or ()))]
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
    """Ultima derivacao de cada vigencia: hash_resultado gravado e recalculado (ja e estavel por construcao) e o hash
    semantico (so valores e relacoes, sem anomalia/verificacao; revisao critica, item 25)."""
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
    """Compara dois bancos camada a camada. `equivalentes` so e True se tudo for igual."""
    a, b = resumo(con_a), resumo(con_b)
    c0 = a["camada0"] == b["camada0"]
    na, nb = a["normalizacao"] or {}, b["normalizacao"] or {}
    tabelas = {t: (na.get("tabelas", {}).get(t) == nb.get("tabelas", {}).get(t)) for t in _TABELAS_1}
    norm = na.get("normalizador_versao") == nb.get("normalizador_versao") and all(tabelas.values())
    vigs = sorted(set(a["derivacoes"]) | set(b["derivacoes"]))
    der = {v: (a["derivacoes"].get(v, {}).get("hash_recalculado") == b["derivacoes"].get(v, {}).get("hash_recalculado")
               and a["derivacoes"].get(v, {}).get("hash_recalculado") is not None) for v in vigs}
    integras = all(d["hash_gravado"] == d["hash_recalculado"] for x in (a, b) for d in x["derivacoes"].values())
    # resultado financeiro igual mesmo quando so o diagnostico difere (texto de verificacao, detalhe de anomalia)
    semantica = {v: (a["derivacoes"].get(v, {}).get("hash_semantico") == b["derivacoes"].get(v, {}).get("hash_semantico")
                     and a["derivacoes"].get(v, {}).get("hash_semantico") is not None) for v in vigs}
    return {"equivalentes": c0 and norm and all(der.values()) and integras,
            "camada0_igual": c0, "normalizacao_igual": norm, "normalizacao_por_tabela": tabelas,
            "derivacao_igual_por_vigencia": der, "resultado_semantico_igual_por_vigencia": semantica,
            "hash_gravado_confere_nos_dois": integras, "a": a, "b": b}
