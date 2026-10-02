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

        portao("testes", "suítes de teste", None, f"não verificado por este comando: {TESTES}")
        verif = con.execute("SELECT descricao, COUNT(*), SUM(verificados), SUM(falhas) FROM verificacao "
                            "WHERE derivacao_id=? GROUP BY descricao ORDER BY descricao", (der and der[0],)).fetchall()
    finally:
        con.close()
    verificaveis = [p for p in portoes if p["ok"] is not None]
    return {"apto": all(p["ok"] for p in verificaveis), "portoes": portoes,
            "verificacoes_da_derivacao": [{"descricao": d, "itens": n, "verificados": v, "falhas": f}
                                          for d, n, v, f in verif],
            "nota": ("'falhas' nas verificações da derivação incluem diferenças já conhecidas com o RREO (informativo, "
                     "não é portão). Portão com ok = null não é verificável por este comando e fica sob responsabilidade "
                     "de quem disponibiliza a carga.")}
