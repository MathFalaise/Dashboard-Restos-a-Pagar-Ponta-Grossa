"""Provenance of every computed value and the root manifest (correction request of 09/10/2026, item 7). READ-ONLY.

The chain of a value (`cadeia`), walked through relations with FOREIGN KEYs (schema v8), never through text:

    visao_valor -> derivation (hash, code hash, rule hash, environment) -> declared rules (derivacao_regra)
                -> snapshots (visao_valor_coleta) -> normalized records of the derivation's normalization
                -> HTTP responses (resposta_bruta) -> raw object (objeto_bruto, SHA-256 re-checked)
                -> manifest in the store (SHA-256 recorded in coleta_manifesto x file today)

`conferir` checks the whole current derivation in bulk (the 'proveniencia_completa' gate).

Root manifest (`gerar_raiz` / `conferir_raiz`): a JSON with the SHA-256 of every manifest and object and the result
hashes of the derivations. On its own it proves nothing against whoever administers the database AND the store:
both are under the same control. It is worth something only when kept OUTSIDE them - another disk, an e-mail, a
signed commit, a timestamping service - and compared later. The Git history of data/snapshots (manifests versioned
byte by byte, -text) is one such external reference for the manifests; it is not one for the database.
"""
import hashlib
import json

from . import agora, banco, hash_do_codigo, regras

FORMATO_RAIZ = "rp-raiz/1"


def cadeia(con, armazem, visao_valor_id):
    """The whole chain of one view value, with a check at each link (`ok` = every link present and every hash equal)."""
    v = con.execute("SELECT id, derivacao_id, visao, regra_agregacao_id, regra_consolidacao_id, entidade, exercicio, "
                    "data_final, componente, valor_c, coletas_json FROM visao_valor WHERE id=?", (visao_valor_id,)).fetchone()
    if v is None:
        raise KeyError(f"visao_valor {visao_valor_id} nao existe")
    vid, did, visao, ragg, rcons, ent, ex, df, comp, valor, coletas_json = v
    d = con.execute("SELECT normalizacao_id, derivador_versao, vigencia_em, hash_resultado, sha256_codigo, sha256_regras, "
                    "ambiente_json, regras_json FROM derivacao_execucao WHERE id=?", (did,)).fetchone()
    nid = d[0]
    n = con.execute("SELECT normalizador_versao, sha256_codigo, ambiente_json FROM normalizacao_execucao WHERE id=?",
                    (nid,)).fetchone()
    declaradas = {r for (r,) in con.execute("SELECT regra_id FROM derivacao_regra WHERE derivacao_id=?", (did,))}
    nome = dict(((i, f"{c} v{ver}") for i, c, ver in con.execute("SELECT id, codigo, versao FROM regra")))
    problemas = []
    regras_do_valor = [r for r in (ragg, rcons) if r is not None]
    for r in regras_do_valor:
        if r not in declaradas:
            problemas.append(f"regra {nome.get(r, r)} não declarada pela derivação {did}")
    if d[5] is not None and d[5] != regras.impressao(con, json.loads(d[7])):
        problemas.append("hash das regras da derivação diferente do recalculado")
    snapshots = []
    ligados = con.execute("SELECT k.id, k.snapshot_uid, k.manifesto, k.tipo, k.status FROM visao_valor_coleta l JOIN "
                          "coleta k ON k.id = l.coleta_id WHERE l.visao_valor_id=? ORDER BY k.snapshot_uid", (vid,)).fetchall()
    if sorted(u for _, u, *_ in ligados) != sorted(json.loads(coletas_json)):
        problemas.append("snapshots ligados ao valor diferentes do coletas_json")
    for cid, uid, rel, tipo, status in ligados:
        gravado = con.execute("SELECT sha256, tamanho FROM coleta_manifesto WHERE coleta_id=?", (cid,)).fetchone()
        try:
            no_armazem = banco.hash_do_manifesto(armazem, rel)
        except (OSError, ValueError) as e:
            no_armazem = None
            problemas.append(f"snapshot {uid[:8]}: manifesto ilegível ({type(e).__name__})")
        if gravado is None or no_armazem is None or tuple(gravado) != no_armazem:
            problemas.append(f"snapshot {uid[:8]}: hash do manifesto gravado diferente do arquivo")
        respostas = []
        for ordem, url, sha in con.execute("SELECT ordem, url, sha256 FROM resposta_bruta WHERE coleta_id=? ORDER BY ordem",
                                           (cid,)):
            try:
                ok = hashlib.sha256(banco.corpo(con, sha)).hexdigest() == sha
            except (ValueError, TypeError) as e:
                ok = False
                problemas.append(f"snapshot {uid[:8]} resposta {ordem}: objeto {sha[:12]} ilegível ({e})")
            if not ok:
                problemas.append(f"snapshot {uid[:8]} resposta {ordem}: objeto {sha[:12]} não confere")
            respostas.append({"ordem": ordem, "url": url, "objeto_sha256": sha, "objeto_confere": ok})
        if not respostas:
            problemas.append(f"snapshot {uid[:8]} sem resposta HTTP")
        registros = con.execute("SELECT COUNT(*) FROM rp_registro WHERE normalizacao_id=? AND coleta_id=?",
                                (nid, cid)).fetchone()[0]
        snapshots.append({"snapshot_uid": uid, "tipo": tipo, "status": status, "manifesto": rel,
                          "manifesto_sha256": gravado[0] if gravado else None,
                          "manifesto_confere": gravado is not None and no_armazem is not None and tuple(gravado) == no_armazem,
                          "registros_normalizados": registros, "respostas": respostas})
    if not ligados:
        problemas.append("valor sem snapshot ligado")
    return {"valor": {"id": vid, "visao": visao, "entidade": ent, "exercicio": ex, "data_final": df,
                      "componente": comp, "valor_c": valor},
            "regras": [nome.get(r, r) for r in regras_do_valor],
            "derivacao": {"id": did, "versao": d[1], "vigencia_em": d[2], "hash_resultado": d[3], "sha256_codigo": d[4],
                          "sha256_regras": d[5], "ambiente": json.loads(d[6]) if d[6] else None},
            "normalizacao": {"id": nid, "versao": n[0], "sha256_codigo": n[1],
                             "ambiente": json.loads(n[2]) if n[2] else None},
            "snapshots": snapshots, "ok": not problemas, "problemas": problemas}


def conferir(con, did):
    """Bulk check of the provenance of derivation `did` (counts of broken links; all zero = complete)."""
    q = lambda sql, *p: con.execute(sql, (did, *p)).fetchone()[0]
    return {
        "valores": q("SELECT COUNT(*) FROM visao_valor WHERE derivacao_id=?"),
        "valor_sem_snapshot": q("SELECT COUNT(*) FROM visao_valor v WHERE v.derivacao_id=? AND NOT EXISTS (SELECT 1 FROM "
                                "visao_valor_coleta l WHERE l.visao_valor_id = v.id)"),
        "ligacao_diferente_do_json": q("SELECT COUNT(*) FROM visao_valor v WHERE v.derivacao_id=? AND (SELECT COUNT(*) "
                                       "FROM json_each(v.coletas_json)) <> (SELECT COUNT(*) FROM visao_valor_coleta l "
                                       "WHERE l.visao_valor_id = v.id)"),
        "conciliacao_diferente_do_json": q("SELECT COUNT(*) FROM conciliacao_rreo c WHERE c.derivacao_id=? AND (SELECT "
                                           "COUNT(*) FROM json_each(c.coletas_api_json)) <> (SELECT COUNT(*) FROM "
                                           "conciliacao_rreo_coleta l WHERE l.derivacao_id = c.derivacao_id AND "
                                           "l.rreo_coleta_id = c.rreo_coleta_id AND l.regra_agregacao_id = "
                                           "c.regra_agregacao_id AND l.coluna = c.coluna)"),
        "regras_diferentes_do_json": q("SELECT (SELECT COUNT(*) FROM derivacao_execucao e, json_each(e.regras_json) WHERE "
                                       "e.id = ?1) <> (SELECT COUNT(*) FROM derivacao_regra WHERE derivacao_id = ?1)"),
        "snapshot_sem_resposta": q("SELECT COUNT(DISTINCT l.coleta_id) FROM visao_valor_coleta l WHERE l.derivacao_id=? "
                                   "AND NOT EXISTS (SELECT 1 FROM resposta_bruta b WHERE b.coleta_id = l.coleta_id)"),
        "resposta_sem_objeto": q("SELECT COUNT(*) FROM resposta_bruta b WHERE b.coleta_id IN (SELECT coleta_id FROM "
                                 "visao_valor_coleta WHERE derivacao_id=?) AND NOT EXISTS (SELECT 1 FROM objeto_bruto o "
                                 "WHERE o.sha256 = b.sha256)"),
        "snapshot_sem_hash_de_manifesto": q("SELECT COUNT(DISTINCT l.coleta_id) FROM visao_valor_coleta l WHERE "
                                            "l.derivacao_id=? AND NOT EXISTS (SELECT 1 FROM coleta_manifesto m WHERE "
                                            "m.coleta_id = l.coleta_id)"),
    }


def identificacao(con, did):
    """Is the run identified? Code hash recorded (and equal to today's code or not), rule hash recorded and equal to the
    recomputed one, environment recorded - for derivation `did` and its normalization."""
    d = con.execute("SELECT normalizacao_id, sha256_codigo, sha256_regras, ambiente_json, regras_json FROM "
                    "derivacao_execucao WHERE id=?", (did,)).fetchone()
    n = con.execute("SELECT sha256_codigo, ambiente_json FROM normalizacao_execucao WHERE id=?", (d[0],)).fetchone()
    atual = hash_do_codigo()
    return {"derivacao": did, "normalizacao": d[0],
            "derivacao_sha256_codigo": d[1], "normalizacao_sha256_codigo": n[0],
            "codigo_atual": atual,
            "derivacao_feita_com_o_codigo_atual": d[1] == atual if d[1] else None,
            "sha256_regras_gravado": d[2],
            "sha256_regras_confere": (d[2] == regras.impressao(con, json.loads(d[4]))) if d[2] else None,
            "ambiente_registrado": bool(d[3]) and bool(n[1]),
            "nota": None if d[1] and n[0] else ("execução anterior ao esquema v8 (sem hash de código): rode 'python -m "
                                               "rp processar' para uma normalização e uma derivação identificadas; os "
                                               "hashes antigos não são preenchidos depois")}


# ------------------------------------------------------------------ root manifest
def _raiz(linhas):
    h = hashlib.sha256()
    for linha in linhas:
        h.update((" ".join(str(x) for x in linha) + "\n").encode())
    return h.hexdigest()


def gerar_raiz(con):
    """Root manifest of the database's raw layer and current results. Keep it OUTSIDE the database and the store."""
    snaps = [list(r) for r in con.execute("SELECT c.snapshot_uid, m.sha256, c.status FROM coleta c JOIN coleta_manifesto m "
                                          "ON m.coleta_id = c.id ORDER BY c.snapshot_uid")]
    sem_hash = con.execute("SELECT COUNT(*) FROM coleta c LEFT JOIN coleta_manifesto m ON m.coleta_id = c.id WHERE "
                           "m.coleta_id IS NULL").fetchone()[0]
    objetos = [o for (o,) in con.execute("SELECT sha256 FROM objeto_bruto ORDER BY sha256")]
    derivacoes = {vig or "atual": {"derivacao": did, "hash_resultado": h} for did, vig, h in con.execute(
        "SELECT id, vigencia_em, hash_resultado FROM derivacao_execucao WHERE id IN (SELECT MAX(id) FROM "
        "derivacao_execucao GROUP BY IFNULL(vigencia_em, ''))")}
    return {"formato": FORMATO_RAIZ, "gerada_em": agora(), "esquema": banco.versao_esquema(con),
            "coletas": len(snaps), "coletas_sem_hash_de_manifesto": sem_hash,
            "raiz_manifestos": _raiz(snaps), "objetos": len(objetos), "raiz_objetos": _raiz([[o] for o in objetos]),
            "derivacoes": derivacoes, "snapshots": snaps, "lista_objetos": objetos,
            "nota": "Guarde este arquivo FORA do banco e do armazém (outro disco, e-mail, commit assinado, carimbo de "
                    "tempo): só assim ele serve de referência contra uma alteração feita por quem administra os dois."}


def conferir_raiz(con, raiz):
    """Problems (empty list = everything in the root is still in the database exactly as it was). New snapshots and
    objects after the root are allowed (the raw layer only grows); missing or different ones are not."""
    if raiz.get("formato") != FORMATO_RAIZ:
        return [f"formato de raiz desconhecido: {raiz.get('formato')!r}"]
    problemas = []
    if _raiz(raiz["snapshots"]) != raiz["raiz_manifestos"]:
        problemas.append("a lista de snapshots do arquivo não bate com a sua própria raiz (arquivo alterado)")
    if _raiz([[o] for o in raiz["lista_objetos"]]) != raiz["raiz_objetos"]:
        problemas.append("a lista de objetos do arquivo não bate com a sua própria raiz (arquivo alterado)")
    atuais = {uid: (h, st) for uid, h, st in con.execute(
        "SELECT c.snapshot_uid, m.sha256, c.status FROM coleta c LEFT JOIN coleta_manifesto m ON m.coleta_id = c.id")}
    for uid, h, st in raiz["snapshots"]:
        if uid not in atuais:
            problemas.append(f"snapshot {uid[:8]} da raiz não está no banco")
        elif atuais[uid] != (h, st):
            problemas.append(f"snapshot {uid[:8]}: manifesto ou status diferente do da raiz")
    objetos = {o for (o,) in con.execute("SELECT sha256 FROM objeto_bruto")}
    faltam = [o for o in raiz["lista_objetos"] if o not in objetos]
    if faltam:
        problemas.append(f"{len(faltam)} objeto(s) da raiz fora do banco (ex.: {faltam[0][:12]})")
    for vig, x in raiz.get("derivacoes", {}).items():
        h = con.execute("SELECT hash_resultado FROM derivacao_execucao WHERE id=?", (x["derivacao"],)).fetchone()
        if h is None:
            problemas.append(f"derivação {x['derivacao']} ({vig}) da raiz não está no banco")
        elif h[0] != x["hash_resultado"]:
            problemas.append(f"derivação {x['derivacao']} ({vig}): hash_resultado diferente do da raiz")
    return problemas
