"""Camada 2: derivação (interpretações, sempre com a versão da regra).

VALIDAÇÃO DO MODELO — Etapa 03. Não é código de produção.

Uma chamada a `derivar` cria uma derivacao_execucao nova sobre uma
normalização; nada de execuções anteriores é alterado. O mesmo bruto com as
mesmas regras tem de produzir o mesmo `hash_resultado`.
"""
import hashlib
import json
from collections import defaultdict

from . import regras
from .bruto import agora

VERSAO = "derivador-1"
COPIA_BASE = 2_400_000
ENT_COPIA, ENT_ORIGINAL = 1, 15
COMPONENTES = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "L", "S1", "S2", "S3"]


def derivar(con, nid):
    R = {c: regras.regra_id(con, c) for c in (
        "CAT", "FAIXA", "S1", "S2", "S3", "CANC", "RREO-COL", "MOV-REF", "PAR-24", "CONS-PAR",
        "CONC-RREO", "ANOM-REG", "ANOM-CONT")}
    R["CONS-PAR-2"] = regras.regra_id(con, "CONS-PAR", 2)
    R["RREO-COL-2"] = regras.regra_id(con, "RREO-COL", 2)
    with con:
        did = con.execute("INSERT INTO derivacao_execucao (normalizacao_id, derivador_versao, regras_json, executada_em) "
                          "VALUES (?,?,?,?)", (nid, VERSAO, json.dumps(sorted(R.values())), agora())).lastrowid
        _registros(con, did, nid, R)
        _movimentacao(con, did, nid)
        vig = coletas_vigentes(con)
        _continuidade(con, did, R, vig)
        pares = _pareamento(con, did, R, vig)
        _visoes(con, did, R, vig, pares)
        _conciliacao(con, did, nid, R)
        con.execute("UPDATE derivacao_execucao SET hash_resultado=? WHERE id=?", (hash_resultado(con, did), did))
    return did


# ---------------------------------------------------------------------------
def coletas_vigentes(con, em=None):
    """Snapshot vigente de cada corte (listagem sem tipo, completa): o mais recente,
    ou o mais recente até `em`. Chave: (entidade, exercicio, data_inicial, data_final)."""
    sql = ("SELECT id, entidade, exercicio, data_inicial, data_final, coletada_em FROM coleta "
           "WHERE tipo='rp_listagem' AND status='completa' AND tipo_pesquisa IS NULL"
           + (" AND coletada_em <= ?" if em else "") + " ORDER BY coletada_em, id")
    vig = {}
    for cid, e, ex, di, df, _ in con.execute(sql, (em,) if em else ()):
        vig[(e, ex, di, df)] = cid  # o último na ordem vence
    return vig


def _linhas(con, did, cid):
    """Registros normalizados + derivados de uma coleta, como dicts."""
    q = ("SELECT r.*, d.categoria, d.faixa_processado, d.faixa_nao_processado, d.s1_saldo_total_c, "
         "d.s2_a_liquidar_c, d.s3_liquidado_a_pagar_c, d.cancel_processado_c, d.cancel_nao_processado_c "
         "FROM rp_registro r JOIN rp_derivado d ON d.resposta_id=r.resposta_id AND d.indice=r.indice "
         "WHERE d.derivacao_id=? AND r.coleta_id=? AND r.normalizacao_id=(SELECT normalizacao_id FROM derivacao_execucao WHERE id=?)")
    cur = con.execute(q, (did, cid, did))
    nomes = [c[0] for c in cur.description]
    return [dict(zip(nomes, row)) for row in cur]


def _anomalia(con, did, regra, tipo, cid=None, e=None, ano=None, emp=None, **det):
    con.execute("INSERT INTO anomalia VALUES (?,?,?,?,?,?,?,?)",
                (did, regra, tipo, cid, e, ano, emp, json.dumps(det, sort_keys=True, ensure_ascii=False) if det else None))


def _verif(con, did, regra, descricao, escopo, verificados, falhas):
    con.execute("INSERT INTO verificacao VALUES (?,?,?,?,?,?)",
                (did, regra, descricao, json.dumps(escopo, sort_keys=True), verificados, falhas))


# ---------------------------------------------------------------------------
def _registros(con, did, nid, R):
    cur = con.execute(
        "SELECT r.resposta_id, r.indice, r.coleta_id, r.entidade, r.anoempenho, r.empenho, c.exercicio, "
        "r.proc_c, r.aproc_c, r.cancelado_proc_c, r.pago_proc_c, r.cancelado_aproc_c, r.pago_aproc_c, r.liquidado_c "
        "FROM rp_registro r JOIN coleta c ON c.id=r.coleta_id WHERE r.normalizacao_id=? AND c.status='completa'", (nid,))
    vistos = defaultdict(int)
    for rid, i, cid, e, ano, emp, ex, proc, aproc, cproc, pproc, caproc, paproc, liq in cur.fetchall():
        cat = ("ambos" if proc > 0 and aproc > 0 else "processado" if proc > 0
               else "nao_processado" if aproc > 0 else "sem_saldo_abertura")
        fp = ("b" if ano == ex - 1 else "a") if proc > 0 else None
        fn = ("g" if ano == ex - 1 else "f") if aproc > 0 else None
        s1 = proc + aproc - pproc - paproc - caproc
        s2 = aproc - liq - caproc
        s3 = proc - pproc + liq - paproc
        cp = caproc if proc > 0 and aproc == 0 else 0
        cn = caproc if aproc > 0 else 0
        con.execute("INSERT INTO rp_derivado VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (did, rid, i, cid, e, ano, emp, cat, fp, fn, s1, s2, s3, cp, cn))
        a = lambda tipo, **k: _anomalia(con, did, R["ANOM-REG"], tipo, cid, e, ano, emp, **k)
        if liq < 0:
            a("LIQ-NEG", liquidado_c=liq)
        if proc == 0 and pproc != 0:
            a("PAGOPROC-SEM-PROC", pago_proc_c=pproc)
        if cproc != 0:
            a("CANCPROC-NZ", cancelado_proc_c=cproc)
        if e == ENT_COPIA and emp >= COPIA_BASE:
            a("COPIA-24")
        if ano >= ex:
            a("ANOEMP-FUTURO", exercicio=ex)
        if proc == 0 and aproc == 0:
            a("SEM-SALDO-ABERTURA")
        vistos[(cid, e, ano, emp)] += 1
    for (cid, e, ano, emp), n in vistos.items():
        if n > 1:
            _anomalia(con, did, R["ANOM-REG"], "CHAVE-DUP", cid, e, ano, emp, ocorrencias=n)


EFEITO = {20: ("empenho", 1), 21: ("cancelamento", -1), 22: ("estorno_cancelamento", 1),
          30: ("liquidacao", 1), 31: ("estorno_liquidacao", -1), 40: ("pagamento", 1),
          41: ("estorno_pagamento", -1), 50: ("retencao", 1), 51: ("estorno_retencao", -1)}


def _movimentacao(con, did, nid):
    cur = con.execute("SELECT resposta_id, indice, tipo_lancamento, valor_c, exercicio_liquidacao_rotulo, "
                      "no_liquidacao_rotulo, exercicio_pagamento_rotulo, no_pagamento_rotulo "
                      "FROM movimentacao_lancamento WHERE normalizacao_id=?", (nid,))
    for rid, i, t, v, exl, nol, exp, nop in cur.fetchall():
        if t in (40, 41):          # rótulos trocados (MOV-REF v1)
            ref = (exp, nop)
        elif t in (30, 31, 50, 51):
            ref = (exl, nol)
        else:
            ref = (None, None)
        efeito, sinal = EFEITO.get(t, ("desconhecido", 0))
        con.execute("INSERT INTO movimentacao_interpretada VALUES (?,?,?,?,?,?,?)",
                    (did, rid, i, ref[0], ref[1], efeito, sinal * v))


# ---------------------------------------------------------------------------
def _continuidade(con, did, R, vig):
    """Fechamento de A (01/01–31/12) × abertura de A+1 (01/01–qualquer)."""
    fech = {(e, ex): cid for (e, ex, di, df), cid in vig.items() if di == f"{ex}-01-01" and df == f"{ex}-12-31"}
    aber = {}
    for (e, ex, di, df), cid in sorted(vig.items(), key=lambda kv: kv[1]):
        if di == f"{ex}-01-01":
            aber[(e, ex)] = cid
    for (e, ex), cA in sorted(fech.items()):
        cB = aber.get((e, ex + 1))
        if not cB:
            continue
        A = {(r["anoempenho"], r["empenho"]): r for r in _linhas(con, did, cA)}
        B = {(r["anoempenho"], r["empenho"]): r for r in _linhas(con, did, cB)}
        falhas = 0
        for k, r in A.items():
            s = B.get(k)
            if s is None:
                if r["s1_saldo_total_c"] != 0:
                    falhas += 1
                    _anomalia(con, did, R["ANOM-CONT"], "SALDO-SEM-CONTINUIDADE", cB, e, *k, s1_final_c=r["s1_saldo_total_c"])
                continue
            if s["proc_c"] != r["s3_liquidado_a_pagar_c"] or s["aproc_c"] != r["s2_a_liquidar_c"]:
                falhas += 1
                _anomalia(con, did, R["ANOM-CONT"], "DESCONTINUIDADE", cB, e, *k,
                          fechamento=[r["s3_liquidado_a_pagar_c"], r["s2_a_liquidar_c"]], abertura=[s["proc_c"], s["aproc_c"]])
        _verif(con, did, R["ANOM-CONT"], "continuidade fechamento→abertura",
               {"entidade": e, "de": ex, "para": ex + 1, "coletas": [cA, cB]}, len(A), falhas)


# ---------------------------------------------------------------------------
def _execucao(r):
    return abs(r["pago_proc_c"]) + abs(r["pago_aproc_c"]) + abs(r["cancelado_aproc_c"]) + abs(r["liquidado_c"])


def _pareamento(con, did, R, vig):
    """PAR-24 v1. Devolve {(exercicio, di, df): [pares]} para a visão analítica."""
    saida = {}
    cortes = {(ex, di, df) for (e, ex, di, df) in vig if e == ENT_COPIA} & {(ex, di, df) for (e, ex, di, df) in vig if e == ENT_ORIGINAL}
    for ex, di, df in sorted(cortes):
        cA, cB = vig[(ENT_COPIA, ex, di, df)], vig[(ENT_ORIGINAL, ex, di, df)]
        copias = [r for r in _linhas(con, did, cA) if r["empenho"] >= COPIA_BASE]
        B = {(r["anoempenho"], r["empenho"]): r for r in _linhas(con, did, cB)}
        pares, sem_par = [], 0
        for a in copias:
            b = B.get((a["anoempenho"], a["empenho"] - COPIA_BASE))
            if not b or b["cnpj"] != a["cnpj"] or b["data_emissao"] != a["data_emissao"]:
                sem_par += 1
                _anomalia(con, did, R["PAR-24"], "COPIA-SEM-PAR", cA, a["entidade"], a["anoempenho"], a["empenho"])
                continue
            mesma = int(a["proc_c"] == b["proc_c"] and a["aproc_c"] == b["aproc_c"])
            insc_a = a["proc_c"] + a["aproc_c"]
            relacao = ("igual" if mesma else
                       "a_e_saldo_final_de_b" if insc_a == b["s1_saldo_total_c"] else "outra")
            xa, xb = _execucao(a), _execucao(b)
            lado = "ambos" if xa and xb else "A" if xa else "B" if xb else "nenhum"
            con.execute("INSERT INTO espelhamento_par VALUES (" + ",".join("?" * 24) + ")",
                        (did, R["PAR-24"], ex, di, df,
                         cA, a["resposta_id"], a["indice"], a["entidade"], a["anoempenho"], a["empenho"],
                         cB, b["resposta_id"], b["indice"], b["entidade"], b["anoempenho"], b["empenho"],
                         insc_a, b["proc_c"] + b["aproc_c"], mesma, relacao, xa, xb, lado))
            if not mesma:
                _anomalia(con, did, R["PAR-24"], "PAR-INSCRICAO-DIVERGENTE", cA, a["entidade"], a["anoempenho"], a["empenho"],
                          par=[b["entidade"], b["anoempenho"], b["empenho"]], relacao=relacao,
                          inscricao_a=[a["proc_c"], a["aproc_c"]], inscricao_b=[b["proc_c"], b["aproc_c"]])
            if lado == "ambos":
                _anomalia(con, did, R["PAR-24"], "PAR-EXECUCAO-DOIS-LADOS", cA, a["entidade"], a["anoempenho"], a["empenho"])
            pares.append({"a": a, "b": b, "mesma": mesma, "relacao": relacao, "lado": lado})
        _verif(con, did, R["PAR-24"], "pareamento de cópias 24xxxxx",
               {"exercicio": ex, "data_inicial": di, "data_final": df, "coletas": [cA, cB]}, len(copias), sem_par)
        saida[(ex, di, df)] = pares
    return saida


# ---------------------------------------------------------------------------
def _componentes(linhas, versao_agregacao):
    """RREO-COL v1: pagamento segue o CAMPO. v2: pagamento segue a CATEGORIA do registro."""
    v = dict.fromkeys(COMPONENTES, 0)
    for r in linhas:
        so_p = r["proc_c"] > 0 and r["aproc_c"] == 0
        so_n = r["aproc_c"] > 0 and r["proc_c"] == 0
        if r["proc_c"] > 0:
            v[r["faixa_processado"]] += r["proc_c"]
            v["c"] += r["pago_proc_c"]
        v["d"] += r["cancel_processado_c"]
        if r["aproc_c"] > 0:
            v[r["faixa_nao_processado"]] += r["aproc_c"]
            v["h"] += r["liquidado_c"]
            v["i"] += r["pago_aproc_c"]
            v["j"] += r["cancelado_aproc_c"]
        if versao_agregacao == 2:
            if so_p:
                v["c"] += r["pago_aproc_c"]
            if so_n:
                v["i"] += r["pago_proc_c"]
        v["S1"] += r["s1_saldo_total_c"]
        v["S2"] += r["s2_a_liquidar_c"]
        v["S3"] += r["s3_liquidado_a_pagar_c"]
    return _fechar(v)


def _fechar(v):
    v["e"] = v["a"] + v["b"] - v["c"] - v["d"]
    v["k"] = v["f"] + v["g"] - v["i"] - v["j"]
    v["L"] = v["e"] + v["k"]
    return v


def _gravar_visao(con, did, visao, ragg, regra, ent, ex, df, coletas, v):
    for comp in COMPONENTES:
        con.execute("INSERT INTO visao_valor (derivacao_id, visao, regra_agregacao_id, regra_consolidacao_id, entidade, "
                    "exercicio, data_final, coletas_json, componente, valor_c) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (did, visao, ragg, regra, ent, ex, df, json.dumps(sorted(coletas)), comp, v[comp]))


def _visoes(con, did, R, vig, pares):
    for ragg, versao in ((R["RREO-COL"], 1), (R["RREO-COL-2"], 2)):
        _visoes_agregacao(con, did, R, vig, pares, ragg, versao)


def _visoes_agregacao(con, did, R, vig, pares, ragg, versao):
    entidades = {row[0] for row in con.execute("SELECT DISTINCT entidade FROM entidade_ref")}
    por_corte = defaultdict(dict)
    for (e, ex, di, df), cid in vig.items():
        if di != f"{ex}-01-01":
            continue  # RREO-COL só vale com dataInicial = 01/01
        v = _componentes(_linhas(con, did, cid), versao)
        _gravar_visao(con, did, "entidade", ragg, None, e, ex, df, [cid], v)
        por_corte[(ex, df)][e] = (cid, v)
    for (ex, df), ents in sorted(por_corte.items()):
        if not entidades or set(ents) != entidades:
            continue  # visão do Município só com TODAS as entidades no mesmo corte
        pub = dict.fromkeys(COMPONENTES, 0)
        for cid, v in ents.values():
            for comp in COMPONENTES:
                pub[comp] += v[comp]
        coletas = [cid for cid, _ in ents.values()]
        _gravar_visao(con, did, "publicado", ragg, None, None, ex, df, coletas, pub)
        # visões analíticas: uma por regra de consolidação (EXPERIMENTAIS), lado a lado
        for regra, lado_excluido in ((R["CONS-PAR"], CONS_PAR_V1), (R["CONS-PAR-2"], CONS_PAR_V2)):
            ana = dict(pub)
            for p in pares.get((ex, f"{ex}-01-01", df), []):
                lado = lado_excluido(p)
                if lado is None:
                    continue  # não consolidado: os dois lados contam (anomalia já registrada)
                x = p[lado]   # só a INSCRIÇÃO desse lado sai; fluxos dos dois lados ficam
                if x["proc_c"] > 0:
                    ana[x["faixa_processado"]] -= x["proc_c"]
                if x["aproc_c"] > 0:
                    ana[x["faixa_nao_processado"]] -= x["aproc_c"]
                ana["S1"] -= x["proc_c"] + x["aproc_c"]
                ana["S2"] -= x["aproc_c"]
                ana["S3"] -= x["proc_c"]
            _gravar_visao(con, did, "analitico", ragg, regra, None, ex, df, coletas, _fechar(ana))


def CONS_PAR_V1(p):
    """v1: inscrições iguais e execução em no máximo um lado → a inscrição de B sai."""
    return "b" if p["mesma"] and p["lado"] != "ambos" else None


def CONS_PAR_V2(p):
    """v2: inscrição de A = inscrição de B ou = saldo final de B → A é remanescente; a inscrição de A sai."""
    return "a" if p["relacao"] in ("igual", "a_e_saldo_final_de_b") and p["lado"] != "ambos" else None


# ---------------------------------------------------------------------------
def _conciliacao(con, did, nid, R):
    docs = con.execute("SELECT DISTINCT coleta_id, escopo, exercicio, data_final FROM rreo_valor "
                       "WHERE normalizacao_id=? AND linha='TOTAL (III)'", (nid,)).fetchall()
    for ragg, versao in ((R["RREO-COL"], 1), (R["RREO-COL-2"], 2)):
        for rcid, escopo, ex, df in docs:
            rv = dict(con.execute("SELECT coluna, valor_c FROM rreo_valor WHERE normalizacao_id=? AND coleta_id=? "
                                  "AND linha='TOTAL (III)'", (nid, rcid)).fetchall())
            filtro = "visao='entidade' AND entidade=1" if escopo == "entidade" else "visao='publicado'"
            api = con.execute("SELECT componente, valor_c, coletas_json FROM visao_valor WHERE derivacao_id=? AND "
                              f"{filtro} AND regra_agregacao_id=? AND exercicio=? AND data_final=?",
                              (did, ragg, ex, df)).fetchall()
            escopo_v = {"rreo_coleta": rcid, "escopo": escopo, "exercicio": ex, "data_final": df, "rreo_col": versao}
            if not api:
                _verif(con, did, R["CONC-RREO"], "RREO sem snapshot da API no mesmo corte", escopo_v, 0, 0)
                continue
            av = {c: v for c, v, _ in api}
            coletas = api[0][2]
            dif = 0
            for col, vr in sorted(rv.items()):
                d = av[col] - vr
                dif += d != 0
                con.execute("INSERT INTO conciliacao_rreo VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                            (did, rcid, ragg, escopo, 1 if escopo == "entidade" else None, ex, df, coletas, col, vr, av[col], d))
            _verif(con, did, R["CONC-RREO"], "conciliação RREO × API (colunas com diferença)", escopo_v, len(rv), dif)


# ---------------------------------------------------------------------------
TABELAS_HASH = ["rp_derivado", "movimentacao_interpretada", "anomalia", "espelhamento_par",
                "visao_valor", "conciliacao_rreo", "verificacao"]


def hash_resultado(con, did):
    """Hash de todo o resultado da derivação, sem colunas que identificam a execução."""
    h = hashlib.sha256()
    for t in TABELAS_HASH:
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({t})") if r[1] not in ("derivacao_id", "id")]
        linhas = con.execute(f"SELECT {','.join(cols)} FROM {t} WHERE derivacao_id=? ORDER BY {','.join(cols)}", (did,))
        h.update(t.encode())
        for row in linhas:
            h.update(json.dumps(row, default=str).encode())
    return h.hexdigest()
