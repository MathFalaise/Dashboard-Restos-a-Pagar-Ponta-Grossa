"""Portoes de qualidade antes de disponibilizar uma carga nova no painel (SOMENTE LEITURA).

Fluxo de atualizacao: COLETAR -> VALIDAR -> PROCESSAR -> TESTAR -> VERIFICAR -> DISPONIBILIZAR NO PAINEL.
Este modulo e o VERIFICAR: le o banco (URI mode=ro + PRAGMA query_only) e o armazem e diz, portao a portao, se
o retrato novo pode ser tratado como valido. Nao coleta, nao processa, nao corrige nada.

A referencia (`gravar_referencia`) e um retrato da camada bruta ANTES da carga nova: hashes das linhas de coleta
e resposta_bruta existentes. Depois da carga, `avaliar(..., referencia)` confere que essas linhas continuam
identicas (a carga so acrescenta; nada anterior muda).
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


def _hash(con, sql, params=()):
    h = hashlib.sha256()
    n = 0
    for row in con.execute(sql, params):
        h.update(repr(row).encode())
        n += 1
    return n, h.hexdigest()


def _referencia(con):
    ultima = con.execute("SELECT IFNULL(MAX(id), 0) FROM coleta").fetchone()[0]
    nc, hc = _hash(con, "SELECT * FROM coleta WHERE id <= ? ORDER BY id", (ultima,))
    nr, hr = _hash(con, "SELECT * FROM resposta_bruta WHERE coleta_id <= ? ORDER BY id", (ultima,))
    nv, hv = _hash(con, "SELECT * FROM coletor_versao ORDER BY 1")
    return {"max_coleta_id": ultima, "coletas": nc, "hash_coletas": hc, "respostas": nr, "hash_respostas": hr,
            "coletor_versoes": nv, "hash_coletor_versoes": hv}


def gravar_referencia(caminho_banco, arquivo):
    """Grava (modo 'x': nunca sobrescreve) o retrato da camada bruta para conferir depois da carga nova."""
    con = _abrir(caminho_banco)
    try:
        ref = _referencia(con)
    finally:
        con.close()
    with open(arquivo, "x", encoding="utf-8") as f:
        f.write(json.dumps(ref, ensure_ascii=False, indent=1))
    return ref


def avaliar(caminho_banco, armazem, referencia=None):
    """Lista de portoes {id, descricao, ok, detalhe}; `apto` = todos os verificaveis ok. `referencia` = dict de
    gravar_referencia (ou None: o portao da camada bruta anterior fica 'nao verificado')."""
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

        # coleta completa: o retrato mais recente de cada corte/consulta precisa estar 'completa'
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
            _, hc = _hash(con, "SELECT * FROM coleta WHERE id <= ? ORDER BY id", (n,))
            _, hr = _hash(con, "SELECT * FROM resposta_bruta WHERE coleta_id <= ? ORDER BY id", (n,))
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


# Campos monetarios da API: ausencia vira 0 na normalizacao (registrada em chaves_ausentes). Enquanto a regra nao for
# revista, uma carga com campo monetario ausente nao pode ser disponibilizada sem decisao (auditoria NORM-01).
_MONETARIOS = ("proc", "aproc", "canceladoProc", "pagoProc", "pagoProcEstornado", "canceladoAProc", "pagoAProc",
               "pagoAProcEstornado", "liquidado", "retencao")


def _vigentes_por_vigencia(con):
    """Ultima derivacao de cada vigencia (atual e cada 'como estava em'): as que a camada painel usa."""
    return [r for r in con.execute(
        "SELECT MAX(id), vigencia_em FROM derivacao_execucao GROUP BY IFNULL(vigencia_em, '') ORDER BY 1")]


def _orfaos(con):
    """Relacoes logicas que o esquema nao protege com FOREIGN KEY (auditoria DB-02): contagem de linhas sem par."""
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
    """Portoes acrescentados pela auditoria tecnica (DB-01, DB-02, NORM-01, DER-02). Todos so leem."""
    from . import derivar
    conferidos = []
    for did, vig in _vigentes_por_vigencia(con):
        gravado = con.execute("SELECT hash_resultado FROM derivacao_execucao WHERE id=?", (did,)).fetchone()[0]
        try:
            confere, erro = gravado is not None and derivar.hash_resultado(con, did) == gravado, None
        except (KeyError, TypeError) as e:   # linha derivada que aponta para coleta/resposta/regra inexistente
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

    cond = " OR ".join(f"chaves_ausentes LIKE '%\"{c}\"%'" for c in _MONETARIOS)
    ausentes = con.execute(f"SELECT COUNT(*) FROM rp_registro WHERE normalizacao_id=? AND ({cond})", (nid,)).fetchone()[0]
    portao("campos_monetarios_ausentes", "nenhum registro sem campo monetário (a normalização grava ausência como 0)",
           ausentes == 0, {"registros": ausentes, "normalizacao": nid})

    desconhecidos = con.execute("SELECT COUNT(*) FROM movimentacao_interpretada WHERE derivacao_id=? AND "
                                "efeito='desconhecido'", (did_atual,)).fetchone()[0]
    portao("lancamento_desconhecido", "nenhum tipo de lançamento sem efeito conhecido (MOV-REF: valeria 0)",
           desconhecidos == 0, {"lancamentos": desconhecidos, "derivacao": did_atual})
