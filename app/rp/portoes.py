"""Quality gates before a new load is made available on the panel (READ-ONLY).

Update flow: COLLECT -> VALIDATE -> PROCESS -> TEST -> VERIFY -> MAKE AVAILABLE ON THE PANEL.
This module is the VERIFY step: it reads the database (URI mode=ro + PRAGMA query_only) and the store and says, gate
by gate, whether the new snapshot can be treated as valid. It does not collect, process or fix anything.

The reference (`gravar_referencia`) is a picture of the raw layer BEFORE the new load: hashes of the existing coleta
and resposta_bruta rows. After the load, `avaliar(..., referencia)` checks that these rows are still identical (the
load only adds; nothing earlier changes).
"""
import hashlib
import json
import sqlite3
from pathlib import Path

from . import banco

TESTES = "rodar 'python -m pytest tests' (e os 26 testes de etapa03/validacao) e conferir que todos passam"


def _abrir(caminho):
    p = Path(caminho).expanduser()
    if not p.is_file():
        raise FileNotFoundError(f"banco nao encontrado: {p}")
    con = sqlite3.connect(f"{p.resolve().as_uri()}?mode=ro", uri=True)
    con.execute("PRAGMA query_only = ON")
    return con


# Reference format (critical review, item 44): v2 serializes each row as canonical JSON (specified: UTF-8, fixed
# separators, bytes in hexadecimal), instead of Python's repr(). A reference without "formato" is v1 (repr) and
# is still checked the way it was recorded.
FORMATO_REFERENCIA = "rp-referencia/2"


def _valor_canonico(v):
    if isinstance(v, bytes):
        return v.hex()
    raise TypeError(f"tipo sem serialização canônica: {type(v).__name__}")


def _hash(con, sql, params=(), canonico=False):
    h = hashlib.sha256()
    n = 0
    for row in con.execute(sql, params):
        if canonico:
            h.update(json.dumps(list(row), ensure_ascii=False, separators=(",", ":"), default=_valor_canonico).encode()
                     + b"\n")
        else:
            h.update(repr(row).encode())
        n += 1
    return n, h.hexdigest()


def _referencia(con, canonico=True):
    ultima = con.execute("SELECT IFNULL(MAX(id), 0) FROM coleta").fetchone()[0]
    nc, hc = _hash(con, "SELECT * FROM coleta WHERE id <= ? ORDER BY id", (ultima,), canonico)
    nr, hr = _hash(con, "SELECT * FROM resposta_bruta WHERE coleta_id <= ? ORDER BY id", (ultima,), canonico)
    nv, hv = _hash(con, "SELECT * FROM coletor_versao ORDER BY 1", (), canonico)
    return {**({"formato": FORMATO_REFERENCIA} if canonico else {}), "max_coleta_id": ultima, "coletas": nc,
            "hash_coletas": hc, "respostas": nr, "hash_respostas": hr, "coletor_versoes": nv, "hash_coletor_versoes": hv}


def gravar_referencia(caminho_banco, arquivo):
    """Writes (mode 'x': never overwrites) the picture of the raw layer, to be checked after the new load."""
    con = _abrir(caminho_banco)
    try:
        ref = _referencia(con)
    finally:
        con.close()
    with open(arquivo, "x", encoding="utf-8") as f:
        f.write(json.dumps(ref, ensure_ascii=False, indent=1))
    return ref


def avaliar(caminho_banco, armazem, referencia=None):
    """List of gates {id, descricao, ok, detalhe}; `apto` = all verifiable ones ok. `referencia` = dict from
    gravar_referencia (or None: the gate for the earlier raw layer stays 'not verified')."""
    con = _abrir(caminho_banco)
    portoes = []

    def portao(ident, descricao, ok, detalhe):
        portoes.append({"id": ident, "descricao": descricao, "ok": ok, "detalhe": detalhe})

    try:
        integ = [r[0] for r in con.execute("PRAGMA integrity_check")]
        portao("integridade_sqlite", "PRAGMA integrity_check do banco", integ == ["ok"], integ[:5])

        problemas = banco.verificar(con, armazem)
        portao("snapshots_validos", "armazém × banco: manifestos, objetos e SHA-256 conferidos (verificar)",
               not problemas, problemas[:10])

        # complete collection: the most recent snapshot of each cut-off/query must be 'completa'
        ultimas = {}
        for cid, tipo, ent, ex, di, df, emp, ano, pesq, par, st in con.execute(
                "SELECT id, tipo, entidade, exercicio, data_inicial, data_final, empenho, anoempenho, tipo_pesquisa, "
                "parametros_json, status FROM coleta ORDER BY coletada_em, snapshot_uid"):
            chave = (tipo, ent, ex, di, df, emp, ano, pesq) if tipo in ("rp_listagem", "movimentacao") else (tipo, par)
            ultimas[chave] = (cid, st)
        ruins = sorted([{"coleta_id": c, "status": s, "consulta": [str(x) for x in k]}
                        for k, (c, s) in ultimas.items() if s != "completa"], key=lambda x: x["coleta_id"])
        portao("coleta_completa", "o snapshot mais recente de cada corte está completo", not ruins, ruins[:10])

        norm = con.execute("SELECT id, ultima_coleta_id FROM normalizacao_execucao ORDER BY id DESC LIMIT 1").fetchone()
        maior = con.execute("SELECT IFNULL(MAX(id), 0) FROM coleta").fetchone()[0]
        pend = None if not norm or norm[1] is None else maior - norm[1]
        portao("normalizacao", "a normalização mais recente leu todos os snapshots do banco",
               norm is not None and norm[1] is not None and norm[1] >= maior,
               {"normalizacao": norm and norm[0], "ultima_coleta_lida": norm and norm[1], "maior_coleta": maior,
                "snapshots_sem_processar": pend})

        der = con.execute("SELECT id, normalizacao_id, hash_resultado FROM derivacao_execucao WHERE vigencia_em IS NULL "
                          "ORDER BY id DESC LIMIT 1").fetchone()
        regs = con.execute("SELECT COUNT(*) FROM rp_registro WHERE normalizacao_id=?", (norm and norm[0],)).fetchone()[0]
        derivs = con.execute("SELECT COUNT(*) FROM rp_derivado WHERE derivacao_id=?", (der and der[0],)).fetchone()[0]
        portao("derivacao", "a derivação atual é da normalização mais recente e cobre todo registro",
               bool(der and norm and der[1] == norm[0] and regs == derivs),
               {"derivacao": der and der[0], "normalizacao_da_derivacao": der and der[1],
                "hash_resultado": der and der[2], "registros": regs, "registros_derivados": derivs})

        orfaos = {
            "registro_sem_resposta": con.execute(
                "SELECT COUNT(*) FROM rp_registro r LEFT JOIN resposta_bruta b ON b.id = r.resposta_id "
                "WHERE b.id IS NULL").fetchone()[0],
            "resposta_sem_objeto": con.execute(
                "SELECT COUNT(*) FROM resposta_bruta b LEFT JOIN objeto_bruto o ON o.sha256 = b.sha256 "
                "WHERE o.sha256 IS NULL").fetchone()[0],
            "registro_de_outra_coleta": con.execute(
                "SELECT COUNT(*) FROM rp_registro r JOIN resposta_bruta b ON b.id = r.resposta_id "
                "WHERE b.coleta_id <> r.coleta_id").fetchone()[0],
        }
        portao("proveniencia", "todo registro aponta para resposta HTTP e objeto bruto existentes",
               not any(orfaos.values()), orfaos)

        if referencia is None:
            portao("camada_bruta_preservada", "linhas do bruto anteriores à carga continuam idênticas", None,
                   "não verificado: informe --referencia (gravada antes da carga com --gravar-referencia)")
        else:
            n = referencia["max_coleta_id"]
            canonico = referencia.get("formato") == FORMATO_REFERENCIA    # no format: v1 reference (repr)
            _, hc = _hash(con, "SELECT * FROM coleta WHERE id <= ? ORDER BY id", (n,), canonico)
            _, hr = _hash(con, "SELECT * FROM resposta_bruta WHERE coleta_id <= ? ORDER BY id", (n,), canonico)
            iguais = {"coletas": hc == referencia["hash_coletas"], "respostas": hr == referencia["hash_respostas"]}
            portao("camada_bruta_preservada", "linhas do bruto anteriores à carga continuam idênticas",
                   all(iguais.values()), {"ate_coleta_id": n, **iguais})

        _portoes_da_auditoria(con, portao, norm and norm[0], der and der[0])
        portao("testes", "suítes de teste", None, f"não verificado por este comando: {TESTES}")
        verif = con.execute("SELECT descricao, COUNT(*), SUM(verificados), SUM(falhas) FROM verificacao "
                            "WHERE derivacao_id=? GROUP BY descricao ORDER BY descricao", (der and der[0],)).fetchall()
    finally:
        con.close()
    verificaveis = [p for p in portoes if p["ok"] is not None]
    nao_verificados = [p["id"] for p in portoes if p["ok"] is None]
    apto = all(p["ok"] for p in verificaveis)
    return {"apto": apto, "apto_sem_ressalvas": apto and not nao_verificados, "nao_verificados": nao_verificados,
            "portoes": portoes,
            "verificacoes_da_derivacao": [{"descricao": d, "itens": n, "verificados": v, "falhas": f}
                                          for d, n, v, f in verif],
            "nota": ("'falhas' nas verificações da derivação incluem diferenças já conhecidas com o RREO (informativo, "
                     "não é portão). Portão com ok = null não é verificável por este comando e fica sob responsabilidade "
                     "de quem disponibiliza a carga: 'apto' considera só os verificáveis; 'apto_sem_ressalvas' exige "
                     "também que nenhum tenha ficado sem verificação (lista em 'nao_verificados').")}


# API monetary fields. Normalizer v1 typed a missing one as 0 (recorded in chaves_ausentes; audit NORM-01); since v2
# (09/10/2026) it is refused in valor_recusado. The gate 'campos_monetarios_ausentes' flags both.
_MONETARIOS = ("proc", "aproc", "canceladoProc", "pagoProc", "pagoProcEstornado", "canceladoAProc", "pagoAProc",
               "pagoAProcEstornado", "liquidado", "retencao")


def _vigentes_por_vigencia(con):
    """Last derivation of each validity (current and each 'as it was on'): the ones the panel layer uses."""
    return [r for r in con.execute(
        "SELECT MAX(id), vigencia_em FROM derivacao_execucao GROUP BY IFNULL(vigencia_em, '') ORDER BY 1")]


def _orfaos(con):
    """Logical relations the schema does not protect with a FOREIGN KEY (audit DB-02): count of rows without a match."""
    q = lambda sql: con.execute(sql).fetchone()[0]
    o = {
        "rp_derivado_sem_registro_da_normalizacao": q(
            "SELECT COUNT(*) FROM rp_derivado d JOIN derivacao_execucao e ON e.id = d.derivacao_id "
            "LEFT JOIN rp_registro r ON r.normalizacao_id = e.normalizacao_id AND r.resposta_id = d.resposta_id "
            "AND r.indice = d.indice WHERE r.resposta_id IS NULL OR r.coleta_id <> d.coleta_id"),
        "movimentacao_sem_lancamento_da_normalizacao": q(
            "SELECT COUNT(*) FROM movimentacao_interpretada m JOIN derivacao_execucao e ON e.id = m.derivacao_id "
            "LEFT JOIN movimentacao_lancamento l ON l.normalizacao_id = e.normalizacao_id AND l.resposta_id = m.resposta_id "
            "AND l.indice = m.indice WHERE l.resposta_id IS NULL"),
        "anomalia_sem_coleta": q("SELECT COUNT(*) FROM anomalia a LEFT JOIN coleta c ON c.id = a.coleta_id "
                                 "WHERE a.coleta_id IS NOT NULL AND c.id IS NULL"),
        "par_sem_registro": q(
            "SELECT COUNT(*) FROM espelhamento_par p JOIN derivacao_execucao e ON e.id = p.derivacao_id "
            "LEFT JOIN rp_registro a ON a.normalizacao_id = e.normalizacao_id AND a.resposta_id = p.resposta_a_id "
            "AND a.indice = p.indice_a AND a.coleta_id = p.coleta_a_id "
            "LEFT JOIN rp_registro b ON b.normalizacao_id = e.normalizacao_id AND b.resposta_id = p.resposta_b_id "
            "AND b.indice = p.indice_b AND b.coleta_id = p.coleta_b_id WHERE a.resposta_id IS NULL OR b.resposta_id IS NULL"),
        "conciliacao_sem_pdf": q("SELECT COUNT(*) FROM conciliacao_rreo x LEFT JOIN coleta c ON c.id = x.rreo_coleta_id "
                                 "AND c.tipo = 'rreo_pdf' WHERE c.id IS NULL"),
        "normalizacao_com_ultima_coleta_inexistente": q(
            "SELECT COUNT(*) FROM normalizacao_execucao n LEFT JOIN coleta c ON c.id = n.ultima_coleta_id "
            "WHERE n.ultima_coleta_id IS NOT NULL AND n.ultima_coleta_id > 0 AND c.id IS NULL"),
    }
    uids = {u for (u,) in con.execute("SELECT snapshot_uid FROM coleta")}
    sem = 0
    for (texto,) in con.execute("SELECT DISTINCT coletas_json FROM visao_valor UNION "
                                "SELECT DISTINCT coletas_api_json FROM conciliacao_rreo"):
        try:
            sem += sum(1 for u in json.loads(texto) if u not in uids)
        except (ValueError, TypeError):
            sem += 1
    o["snapshot_em_coletas_json_inexistente"] = sem
    regras = {i for (i,) in con.execute("SELECT id FROM regra")}
    o["derivacao_com_regra_inexistente"] = sum(
        1 for (texto,) in con.execute("SELECT regras_json FROM derivacao_execucao")
        if not set(json.loads(texto)) <= regras)
    return o


def _portoes_da_auditoria(con, portao, nid, did_atual):
    """Gates added by the technical audit (DB-01, DB-02, NORM-01, DER-02). All of them only read."""
    from . import derivar
    conferidos = []
    for did, vig in _vigentes_por_vigencia(con):
        gravado = con.execute("SELECT hash_resultado FROM derivacao_execucao WHERE id=?", (did,)).fetchone()[0]
        try:
            confere, erro = gravado is not None and derivar.hash_resultado(con, did) == gravado, None
        except (KeyError, TypeError) as e:   # a derived row pointing to a non-existent collection/response/rule
            confere, erro = False, f"hash nao recalculavel: {type(e).__name__} {e}"
        conferidos.append({"derivacao": did, "vigencia": vig or "atual", "gravado": gravado, "confere": confere,
                           **({"erro": erro} if erro else {})})
    portao("hash_resultado_confere", "o hash_resultado gravado é o do conteúdo atual das tabelas derivadas "
           "(recalculado; a última derivação de cada vigência)", bool(conferidos) and all(c["confere"] for c in conferidos),
           conferidos)

    fk = con.execute("PRAGMA foreign_key_check").fetchall()
    orfaos = _orfaos(con)
    portao("integridade_relacional", "FOREIGN KEY do esquema (foreign_key_check) e relações sem FK (órfãos)",
           not fk and not any(orfaos.values()), {"foreign_key_check": [list(r) for r in fk[:10]], **orfaos})

    # Normalizer v1 typed a missing money field as 0 (the key stays in chaves_ausentes); v2 (09/10/2026) refuses it in
    # valor_recusado and the record composes no indicator. Both fail the gate: an absence is never approved silently.
    cond = " OR ".join(f"chaves_ausentes LIKE '%\"{c}\"%'" for c in _MONETARIOS)
    ausentes = con.execute(f"SELECT COUNT(*) FROM rp_registro WHERE normalizacao_id=? AND ({cond})", (nid,)).fetchone()[0]
    recusas = con.execute("SELECT campo, natureza, COUNT(*) FROM valor_recusado WHERE normalizacao_id=? GROUP BY 1, 2 "
                          "ORDER BY 1, 2", (nid,)).fetchall()
    recusados = con.execute("SELECT COUNT(*) FROM (SELECT DISTINCT resposta_id, indice FROM valor_recusado WHERE "
                            "normalizacao_id=?)", (nid,)).fetchone()[0]
    portao("campos_monetarios_ausentes", "nenhum registro com campo monetário ausente, nulo ou inválido (recusado na "
           "normalização v2; na v1, gravado como 0)", ausentes == 0 and recusados == 0,
           {"registros": ausentes + recusados, "gravados_como_zero_v1": ausentes, "recusados_v2": recusados,
            "campos_recusados": {f"{c}:{n}": q for c, n, q in recusas}, "normalizacao": nid,
            "nota": "um retrato com valor recusado nunca é o vigente (VALOR-RECUSADO): vale o retrato válido anterior "
                    "do corte, ou o dado fica indisponível. Analise a resposta da API antes de recoletar"})

    desconhecidos = con.execute("SELECT COUNT(*) FROM movimentacao_interpretada WHERE derivacao_id=? AND "
                                "efeito='desconhecido'", (did_atual,)).fetchone()[0]
    portao("lancamento_desconhecido", "nenhum tipo de lançamento sem efeito conhecido (MOV-REF: valeria 0)",
           desconhecidos == 0, {"lancamentos": desconhecidos, "derivacao": did_atual})

    _portoes_da_revisao(con, portao, did_atual)


def _portoes_da_revisao(con, portao, did_atual):
    """Gates from the critical review of 05/10/2026 (items 14 and 28). They only read."""
    # item 14: a repeated key is a gate, not just a note. The ambiguous snapshot is no longer current
    # (vigencia.coletas_vigentes), but the load is not made available without a decision: the panel would show the
    # previous snapshot of the cut-off.
    naturezas, snapshots = {"exata": 0, "conflitante": 0, "não classificada": 0}, set()
    for uid, detalhe in con.execute(
            "SELECT c.snapshot_uid, a.detalhe_json FROM anomalia a LEFT JOIN coleta c ON c.id = a.coleta_id "
            "WHERE a.derivacao_id=? AND a.tipo='CHAVE-DUP'", (did_atual,)):
        try:
            natureza = json.loads(detalhe or "{}").get("natureza", "não classificada")
        except ValueError:
            natureza = "não classificada"
        naturezas[natureza if natureza in naturezas else "não classificada"] += 1
        snapshots.add(uid)
    portao("retrato_sem_chave_repetida", "nenhum retrato com a mesma chave (entidade, anoempenho, empenho) mais de uma "
           "vez (CHAVE-DUP): exata = cópias idênticas; conflitante = conteúdo diferente",
           sum(naturezas.values()) == 0,
           {"chaves": sum(naturezas.values()), **naturezas, "snapshots": sorted(s for s in snapshots if s)[:10],
            "derivacao": did_atual,
            # decision D1 (06/10/2026): block and say what to do. No automatic re-collection: the collection's own second
            # read already re-read the pages right away; re-collecting is worth it LATER, when the API may have changed
            "recoletar": [f"python -m rp recoletar --snapshot {s}" for s in sorted(s for s in snapshots if s)[:10]],
            "nota": "retrato com chave repetida nunca é o vigente (vale o retrato válido anterior do corte). "
                    "A segunda leitura da coleta já releu as páginas na hora: recolete o corte MAIS TARDE com o "
                    "comando em 'recoletar', confira com 'python -m rp verificar' e processe de novo "
                    "('python -m rp processar')"})

    # correction request of 09/10/2026, item 4: every collection has its start and conclusion (coleta_tempo, v7).
    # Approximate or unknown conclusions are not a failure: they are the documented limitation of old snapshots
    tem_tempo = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='coleta_tempo'").fetchone()
    if tem_tempo:
        sem = con.execute("SELECT COUNT(*) FROM coleta c LEFT JOIN coleta_tempo t ON t.coleta_id = c.id WHERE "
                          "t.coleta_id IS NULL").fetchone()[0]
        precisao = dict(con.execute("SELECT precisao, COUNT(*) FROM coleta_tempo GROUP BY 1 ORDER BY 1").fetchall())
        fontes_ = dict(con.execute("SELECT fonte_conclusao, COUNT(*) FROM coleta_tempo GROUP BY 1 ORDER BY 1").fetchall())
        portao("tempos_das_coletas", "toda coleta tem início e conclusão registrados (coleta_tempo): retrato só vale "
               "'como estava em' a partir da conclusão", sem == 0,
               {"coletas_sem_tempo": sem, "por_precisao": precisao, "por_fonte_da_conclusao": fontes_,
                "limitacao": "'aproximada' = conclusão pela data do arquivo (Etapas 01/02); 'desconhecida' = sem "
                             "evidência de conclusão: o retrato nunca vale numa consulta com data"})
    else:
        portao("tempos_das_coletas", "toda coleta tem início e conclusão registrados (coleta_tempo)", None,
               "não verificado: banco antes da v7")

    # correction request of 09/10/2026, items 1 and 7: every value walks to its snapshots, responses, objects and
    # manifest hashes through relations (v8), and the current derivation says which code, rules and environment
    if banco._tem_tabela(con, "derivacao_regra") and did_atual:
        from . import proveniencia
        prov = proveniencia.conferir(con, did_atual)
        portao("proveniencia_completa", "todo valor calculado chega, por relações (v8), aos snapshots, às respostas "
               "HTTP, aos objetos brutos e ao hash do manifesto; as relações batem com o JSON",
               all(v == 0 for k, v in prov.items() if k != "valores"), {"derivacao": did_atual, **prov})
        ident = proveniencia.identificacao(con, did_atual)
        portao("execucao_identificada", "a derivação atual e a sua normalização registram o hash do código e o "
               "ambiente; o hash das regras gravado é o recalculado do catálogo",
               bool(ident["derivacao_sha256_codigo"] and ident["normalizacao_sha256_codigo"] and
                    ident["sha256_regras_confere"] and ident["ambiente_registrado"]), ident)
    else:
        portao("proveniencia_completa", "todo valor calculado chega aos snapshots, respostas, objetos e manifestos",
               None, "não verificado: banco antes da v8 ou sem derivação")

    # item 28: the database schema is the one of its version in the code (structure, without comments or whitespace)
    versao = banco.versao_esquema(con)
    esperado = banco.IMPRESSAO_ESQUEMA.get(versao)
    atual = banco.impressao_esquema(con)
    portao("esquema_confere", "o esquema do banco (tabelas, colunas, restrições, índices, gatilhos) é o da versão "
           "registrada em esquema_versao", None if esperado is None else atual == esperado,
           {"versao": versao, "impressao_banco": atual, "impressao_do_codigo": esperado}
           if esperado is not None else f"não verificado: o código não tem a impressão do esquema v{versao}")
