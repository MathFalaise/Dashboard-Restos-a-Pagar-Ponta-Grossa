"""Camada 2 - derivacao: toda interpretacao, sempre com a versao da regra.

* Todas as versoes de regra do catalogo sao calculadas LADO A LADO (RREO-COL v1/v2 x
  CONS-PAR v1/v2). Nenhuma experimental vira padrao.
* Determinismo: o resultado depende so do conjunto de snapshots e do catalogo de
  regras - nao da hora, da ordem de insercao nem de ids internos. O `hash_resultado`
  e calculado sobre identificadores estaveis (snapshot_uid, ordem da resposta,
  indice), entao e o mesmo num banco reconstruido a partir do armazem.
* Nenhum registro e removido: espelhamento e consolidacao existem so aqui.

Desempenho: as linhas (registro + derivado) de cada coleta sao lidas com as colunas que as
regras usam, por um leitor com cache LRU pequeno (o fechamento de um ano e a abertura do
seguinte costumam ser a mesma coleta), e as visoes guardam so os componentes calculados,
nao as linhas. Nada disso muda o resultado: a ordem de leitura e a mesma e o hash e conferido.
"""
import hashlib
import json
import logging
from collections import OrderedDict, defaultdict

from . import DataInvalida, agora, instante, regras

log = logging.getLogger("rp.derivar")

VERSAO = "rp-derivador/1"
# Entidades do par, base das copias e entidade do RREO por entidade NAO ficam aqui: sao parametros das regras
# PAR-24 v1 e CONC-RREO v1 (regras.PARAMETROS -> tabela regra_parametro), lidos a cada derivacao.
COMPONENTES = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "L", "S1", "S2", "S3"]
AGREGACOES = (("RREO-COL", 1), ("RREO-COL", 2))
CONSOLIDACOES = (("CONS-PAR", 1), ("CONS-PAR", 2))

# Colunas que as regras leem de cada linha (continuidade, pareamento, componentes das visoes).
CAMPOS_REGISTRO = ["resposta_id", "indice", "coleta_id", "entidade", "anoempenho", "empenho", "data_emissao", "cnpj",
                   "proc_c", "aproc_c", "cancelado_proc_c", "pago_proc_c", "cancelado_aproc_c", "pago_aproc_c",
                   "liquidado_c"]
CAMPOS_DERIVADO = ["categoria", "faixa_processado", "faixa_nao_processado", "s1_saldo_total_c", "s2_a_liquidar_c",
                   "s3_liquidado_a_pagar_c", "cancel_processado_c", "cancel_nao_processado_c"]
# As respostas da coleta entram como lista (resposta_id IN ...): assim o SQLite percorre a chave primaria
# (normalizacao_id, resposta_id, indice) so nas respostas da coleta, ja na ordem pedida, em vez de varrer
# todos os registros da normalizacao a cada consulta. O filtro por coleta_id continua, redundante de proposito.
SQL_LINHAS = ("SELECT " + ", ".join([f"r.{c}" for c in CAMPOS_REGISTRO] + [f"d.{c}" for c in CAMPOS_DERIVADO]) +
              " FROM rp_registro r JOIN rp_derivado d ON d.resposta_id = r.resposta_id AND d.indice = r.indice "
              "AND d.derivacao_id = ? WHERE r.normalizacao_id = ? "
              "AND r.resposta_id IN (SELECT id FROM resposta_bruta WHERE coleta_id = ?) AND r.coleta_id = ? "
              "ORDER BY r.resposta_id, r.indice")
NOMES_LINHA = CAMPOS_REGISTRO + CAMPOS_DERIVADO


def derivar(con, nid, em=None):
    """Nova derivacao sobre a normalizacao `nid`. `em` (ISO com fuso): considera so snapshots coletados
    ate essa data - 'como estava em'. Sem `em`, usa todos (o mais recente de cada corte e o vigente).
    `em` precisa estar na forma canonica de rp.instante (a comparacao com coletada_em e textual e a camada painel
    procura a derivacao por esse texto): outra forma do mesmo instante e recusada, nunca comparada (auditoria CLI-01)."""
    if em is not None and instante(em) != em:
        raise DataInvalida(f"vigencia {em!r} fora da forma canonica {instante(em)!r}: use rp.instante")
    regras.semear(con)
    R = regras.ids(con)
    par = regras.parametros(con, "PAR-24", 1)
    conc = regras.parametros(con, "CONC-RREO", 1)
    with con:
        did = con.execute("INSERT INTO derivacao_execucao (normalizacao_id, derivador_versao, regras_json, executada_em, "
                          "vigencia_em) VALUES (?,?,?,?,?)",
                          (nid, VERSAO, json.dumps(sorted(R.values())), agora(), em)).lastrowid
        uid = dict(con.execute("SELECT id, snapshot_uid FROM coleta"))
        _registros(con, did, nid, R, par, em)
        _movimentacao(con, did, nid, em)
        vig = coletas_vigentes(con, em)
        ler = _Leitor(con, did, nid)
        _continuidade(con, did, nid, R, vig, uid, ler)
        pares = _pareamento(con, did, nid, R, vig, uid, par, ler)
        _visoes(con, did, nid, R, vig, pares, uid, em, ler)
        _conciliacao(con, did, nid, R, uid, conc, em)
        h = hash_resultado(con, did)
        con.execute("UPDATE derivacao_execucao SET hash_resultado=? WHERE id=?", (h, did))
    log.info("derivação %d sobre normalização %d (vigência %s): hash %s", did, nid, em or "atual", h[:16])
    return did


def _ate(em, alias="c"):
    """Filtro SQL de vigencia sobre coleta.coletada_em."""
    return (f" AND {alias}.coletada_em <= ?", (em,)) if em else ("", ())


# --------------------------------------------------------------------------- selecao de snapshots
def coletas_vigentes(con, em=None):
    """Snapshot vigente de cada corte de listagem (sem tipo, completo): o mais recente ate `em`.
    Chave (entidade, exercicio, data_inicial, data_final). Desempate estavel por snapshot_uid."""
    sql = ("SELECT id, entidade, exercicio, data_inicial, data_final FROM coleta WHERE tipo='rp_listagem' "
           "AND status='completa' AND tipo_pesquisa IS NULL" + (" AND coletada_em <= ?" if em else "")
           + " ORDER BY coletada_em, snapshot_uid")
    vig = {}
    for cid, e, ex, di, df in con.execute(sql, (em,) if em else ()):
        vig[(e, ex, di, df)] = cid
    return vig


def _linhas(con, did, nid, cid):
    """Linhas (registro + derivado) de uma coleta, na ordem de origem (resposta, indice)."""
    return [dict(zip(NOMES_LINHA, row)) for row in con.execute(SQL_LINHAS, (did, nid, cid, cid))]


class _Leitor:
    """`_linhas` com cache LRU de poucas coletas. As linhas sao so lidas pelas regras, nunca alteradas."""

    def __init__(self, con, did, nid, capacidade=4):
        self.con, self.did, self.nid, self.capacidade = con, did, nid, capacidade
        self._cache = OrderedDict()

    def __call__(self, cid):
        if cid in self._cache:
            self._cache.move_to_end(cid)
            return self._cache[cid]
        linhas = _linhas(self.con, self.did, self.nid, cid)
        self._cache[cid] = linhas
        if len(self._cache) > self.capacidade:
            self._cache.popitem(last=False)
        return linhas


def _detalhe(det):
    return json.dumps(det, sort_keys=True, ensure_ascii=False) if det else None


def _anomalia(con, did, regra, tipo, cid=None, e=None, ano=None, emp=None, **det):
    con.execute("INSERT INTO anomalia VALUES (?,?,?,?,?,?,?,?)", (did, regra, tipo, cid, e, ano, emp, _detalhe(det)))


def _verif(con, did, regra, descricao, escopo, verificados, falhas):
    con.execute("INSERT INTO verificacao VALUES (?,?,?,?,?,?)",
                (did, regra, descricao, json.dumps(escopo, sort_keys=True, ensure_ascii=False), verificados, falhas))


# --------------------------------------------------------------------------- por registro
def _registros(con, did, nid, R, par, em=None):
    filtro, p = _ate(em)
    fonte = con.execute(
        "SELECT r.resposta_id, r.indice, r.coleta_id, r.entidade, r.anoempenho, r.empenho, c.exercicio, r.proc_c, "
        "r.aproc_c, r.cancelado_proc_c, r.pago_proc_c, r.cancelado_aproc_c, r.pago_aproc_c, r.liquidado_c "
        "FROM rp_registro r JOIN coleta c ON c.id = r.coleta_id WHERE r.normalizacao_id = ? AND c.status = 'completa' "
        + filtro + " ORDER BY r.resposta_id, r.indice", (nid, *p)).fetchall()
    ocorrencias = defaultdict(int)
    anom = R[("ANOM-REG", 1)]
    anomalias = []

    def linha(tipo, cid, e, ano, emp, **det):
        anomalias.append((did, anom, tipo, cid, e, ano, emp, _detalhe(det)))

    def derivados():
        for rid, i, cid, e, ano, emp, ex, proc, aproc, cproc, pproc, caproc, paproc, liq in fonte:
            categoria = ("ambos" if proc > 0 and aproc > 0 else "processado" if proc > 0
                         else "nao_processado" if aproc > 0 else "sem_saldo_abertura")
            fp = ("b" if ano == ex - 1 else "a") if proc > 0 else None
            fn = ("g" if ano == ex - 1 else "f") if aproc > 0 else None
            yield (did, rid, i, cid, e, ano, emp, categoria, fp, fn,
                   proc + aproc - pproc - paproc - caproc,        # S1
                   aproc - liq - caproc,                          # S2
                   proc - pproc + liq - paproc,                   # S3
                   caproc if proc > 0 and aproc == 0 else 0,      # CANC processado
                   caproc if aproc > 0 else 0)                    # CANC nao processado
            if liq < 0:
                linha("LIQ-NEG", cid, e, ano, emp, liquidado_c=liq)
            if proc == 0 and pproc != 0:
                linha("PAGOPROC-SEM-PROC", cid, e, ano, emp, pago_proc_c=pproc)
            if cproc != 0:
                linha("CANCPROC-NZ", cid, e, ano, emp, cancelado_proc_c=cproc)
            if e == par["entidade_copia"] and emp >= par["base_empenho_copia"]:
                linha("COPIA-24", cid, e, ano, emp)
            if ano >= ex:
                linha("ANOEMP-FUTURO", cid, e, ano, emp, exercicio=ex)
            if proc == 0 and aproc == 0:
                linha("SEM-SALDO-ABERTURA", cid, e, ano, emp)
            ocorrencias[(cid, e, ano, emp)] += 1

    con.executemany("INSERT INTO rp_derivado VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", derivados())
    for (cid, e, ano, emp), n in sorted(ocorrencias.items()):
        if n > 1:
            linha("CHAVE-DUP", cid, e, ano, emp, ocorrencias=n)
    con.executemany("INSERT INTO anomalia VALUES (?,?,?,?,?,?,?,?)", anomalias)


EFEITO = {20: ("empenho", 1), 21: ("cancelamento", -1), 22: ("estorno_cancelamento", 1), 30: ("liquidacao", 1),
          31: ("estorno_liquidacao", -1), 40: ("pagamento", 1), 41: ("estorno_pagamento", -1), 50: ("retencao", 1),
          51: ("estorno_retencao", -1)}


def _movimentacao(con, did, nid, em=None):
    """Lancamentos so de snapshot completo, como os registros (_registros): snapshot incompleto nunca vira retrato
    valido (auditoria DER-01)."""
    filtro, p = _ate(em)
    fonte = con.execute(
        "SELECT m.resposta_id, m.indice, m.tipo_lancamento, m.valor_c, m.exercicio_liquidacao_rotulo, "
        "m.no_liquidacao_rotulo, m.exercicio_pagamento_rotulo, m.no_pagamento_rotulo FROM movimentacao_lancamento m "
        "JOIN coleta c ON c.id = m.coleta_id WHERE m.normalizacao_id = ? AND c.status = 'completa'" + filtro +
        " ORDER BY m.resposta_id, m.indice", (nid, *p)).fetchall()

    def interpretados():
        for rid, i, t, v, exl, nol, exp, nop in fonte:
            ref = (exp, nop) if t in (40, 41) else (exl, nol) if t in (30, 31, 50, 51) else (None, None)  # MOV-REF v1
            efeito, sinal = EFEITO.get(t, ("desconhecido", 0))
            yield (did, rid, i, ref[0], ref[1], efeito, sinal * v)

    con.executemany("INSERT INTO movimentacao_interpretada VALUES (?,?,?,?,?,?,?)", interpretados())


# --------------------------------------------------------------------------- continuidade
def _continuidade(con, did, nid, R, vig, uid, ler=None):
    """Fechamento de A (01/01-31/12) x abertura de A+1 (snapshot que comeca em 01/01 de A+1;
    a abertura nao depende de dataFinal - escolhe-se o de maior dataFinal, depois o mais recente)."""
    ler = ler or _Leitor(con, did, nid)
    regra = R[("ANOM-CONT", 1)]
    fech = {(e, ex): c for (e, ex, di, df), c in vig.items() if di == f"{ex}-01-01" and df == f"{ex}-12-31"}
    aber = {}
    for (e, ex, di, df), c in sorted(vig.items(), key=lambda kv: (kv[0][3], kv[0])):
        if di == f"{ex}-01-01":
            aber[(e, ex)] = c
    for (e, ex), ca in sorted(fech.items()):
        cb = aber.get((e, ex + 1))
        if not cb:
            continue
        A = {(r["anoempenho"], r["empenho"]): r for r in ler(ca)}
        B = {(r["anoempenho"], r["empenho"]): r for r in ler(cb)}
        falhas = 0
        for k in sorted(A):
            r, s = A[k], B.get(k)
            if s is None:
                if r["s1_saldo_total_c"] != 0:
                    falhas += 1
                    _anomalia(con, did, regra, "SALDO-SEM-CONTINUIDADE", cb, e, *k, s1_final_c=r["s1_saldo_total_c"])
            elif s["proc_c"] != r["s3_liquidado_a_pagar_c"] or s["aproc_c"] != r["s2_a_liquidar_c"]:
                falhas += 1
                _anomalia(con, did, regra, "DESCONTINUIDADE", cb, e, *k,
                          fechamento=[r["s3_liquidado_a_pagar_c"], r["s2_a_liquidar_c"]], abertura=[s["proc_c"], s["aproc_c"]])
        _verif(con, did, regra, "continuidade fechamento→abertura",
               {"entidade": e, "de": ex, "para": ex + 1, "snapshots": [uid[ca], uid[cb]]}, len(A), falhas)


# --------------------------------------------------------------------------- espelhamento
def _execucao(r):
    return abs(r["pago_proc_c"]) + abs(r["pago_aproc_c"]) + abs(r["cancelado_aproc_c"]) + abs(r["liquidado_c"])


def _pareamento(con, did, nid, R, vig, uid, par, ler=None):
    """Pares copia <-> original segundo os parametros da regra PAR-24 (entidades, base, campos de conferencia)."""
    ler = ler or _Leitor(con, did, nid)
    regra = R[("PAR-24", 1)]
    ent_a, ent_b, base = par["entidade_copia"], par["entidade_original"], par["base_empenho_copia"]
    conferir = par["campos_de_conferencia"]
    saida = {}
    cortes = ({(ex, di, df) for (e, ex, di, df) in vig if e == ent_a}
              & {(ex, di, df) for (e, ex, di, df) in vig if e == ent_b})
    for ex, di, df in sorted(cortes):
        ca, cb = vig[(ent_a, ex, di, df)], vig[(ent_b, ex, di, df)]
        copias = [r for r in ler(ca) if r["empenho"] >= base]
        B = {(r["anoempenho"], r["empenho"]): r for r in ler(cb)}
        pares, sem_par = [], 0
        for a in copias:
            b = B.get((a["anoempenho"], a["empenho"] - base))
            if not b or any(b[c] != a[c] for c in conferir):
                sem_par += 1
                _anomalia(con, did, regra, "COPIA-SEM-PAR", ca, a["entidade"], a["anoempenho"], a["empenho"])
                continue
            mesma = int(a["proc_c"] == b["proc_c"] and a["aproc_c"] == b["aproc_c"])
            insc_a = a["proc_c"] + a["aproc_c"]
            relacao = "igual" if mesma else "a_e_saldo_final_de_b" if insc_a == b["s1_saldo_total_c"] else "outra"
            xa, xb = _execucao(a), _execucao(b)
            lado = "ambos" if xa and xb else "A" if xa else "B" if xb else "nenhum"
            con.execute("INSERT INTO espelhamento_par VALUES (" + ",".join("?" * 24) + ")",
                        (did, regra, ex, di, df, ca, a["resposta_id"], a["indice"], a["entidade"], a["anoempenho"],
                         a["empenho"], cb, b["resposta_id"], b["indice"], b["entidade"], b["anoempenho"], b["empenho"],
                         insc_a, b["proc_c"] + b["aproc_c"], mesma, relacao, xa, xb, lado))
            if not mesma:
                _anomalia(con, did, regra, "PAR-INSCRICAO-DIVERGENTE", ca, a["entidade"], a["anoempenho"], a["empenho"],
                          par=[b["entidade"], b["anoempenho"], b["empenho"]], relacao=relacao,
                          inscricao_a=[a["proc_c"], a["aproc_c"]], inscricao_b=[b["proc_c"], b["aproc_c"]])
            if lado == "ambos":
                _anomalia(con, did, regra, "PAR-EXECUCAO-DOIS-LADOS", ca, a["entidade"], a["anoempenho"], a["empenho"])
            pares.append({"a": a, "b": b, "mesma": mesma, "relacao": relacao, "lado": lado})
        _verif(con, did, regra, "pareamento de cópias 24xxxxx",
               {"exercicio": ex, "data_inicial": di, "data_final": df, "snapshots": [uid[ca], uid[cb]]}, len(copias), sem_par)
        saida[(ex, di, df)] = pares
    return saida


# --------------------------------------------------------------------------- visoes
def _componentes(linhas, versao_agregacao):
    v = dict.fromkeys(COMPONENTES, 0)
    for r in linhas:
        if r["proc_c"] > 0:
            v[r["faixa_processado"]] += r["proc_c"]
            v["c"] += r["pago_proc_c"]
        v["d"] += r["cancel_processado_c"]
        if r["aproc_c"] > 0:
            v[r["faixa_nao_processado"]] += r["aproc_c"]
            v["h"] += r["liquidado_c"]
            v["i"] += r["pago_aproc_c"]
            v["j"] += r["cancelado_aproc_c"]
        if versao_agregacao == 2:  # pagamento segue a categoria do registro
            if r["proc_c"] > 0 and r["aproc_c"] == 0:
                v["c"] += r["pago_aproc_c"]
            if r["aproc_c"] > 0 and r["proc_c"] == 0:
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


def _gravar_visao(con, did, visao, ragg, rcons, ent, ex, df, snapshots, v):
    coletas = json.dumps(sorted(snapshots))
    con.executemany("INSERT INTO visao_valor (derivacao_id, visao, regra_agregacao_id, regra_consolidacao_id, entidade, "
                    "exercicio, data_final, coletas_json, componente, valor_c) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    [(did, visao, ragg, rcons, ent, ex, df, coletas, comp, v[comp]) for comp in COMPONENTES])


def _lado_excluido(versao, p):
    """CONS-PAR: qual lado tem a INSCRICAO retirada (None = par nao consolidado)."""
    if p["lado"] == "ambos":
        return None
    if versao == 1:
        return "b" if p["mesma"] else None
    return "a" if p["relacao"] in ("igual", "a_e_saldo_final_de_b") else None


def _entidades_do_catalogo(con, nid, em=None):
    """Entidades do snapshot de catalogo vigente (o mais recente ate `em`)."""
    filtro, p = _ate(em, "coleta")
    ult = con.execute("SELECT id FROM coleta WHERE tipo='entidades' AND status='completa'" + filtro +
                      " ORDER BY coletada_em DESC, snapshot_uid DESC LIMIT 1", p).fetchone()
    if not ult:
        return set()
    return {e for (e,) in con.execute("SELECT entidade FROM entidade_ref WHERE normalizacao_id=? AND coleta_id=?", (nid, ult[0]))}


def _visoes(con, did, nid, R, vig, pares, uid, em=None, ler=None):
    ler = ler or _Leitor(con, did, nid)
    entidades = _entidades_do_catalogo(con, nid, em)
    alvos = [(k, c) for k, c in sorted(vig.items()) if k[2] == f"{k[1]}-01-01"]  # colunas do RREO so com dataInicial = 01/01
    componentes = {}
    for _, c in alvos:   # cada coleta e lida uma vez; so os componentes ficam na memoria
        if (AGREGACOES[0][1], c) not in componentes:
            linhas = ler(c)
            for _, versao in AGREGACOES:
                componentes[(versao, c)] = _componentes(linhas, versao)
    for (codigo, versao) in AGREGACOES:
        ragg = R[(codigo, versao)]
        por_corte = defaultdict(dict)
        for (e, ex, di, df), c in alvos:
            v = componentes[(versao, c)]
            _gravar_visao(con, did, "entidade", ragg, None, e, ex, df, [uid[c]], v)
            por_corte[(ex, df)][e] = (c, v)
        for (ex, df), ents in sorted(por_corte.items()):
            if not entidades or set(ents) != entidades:
                continue  # visao do Municipio so com TODAS as entidades no mesmo corte
            pub = dict.fromkeys(COMPONENTES, 0)
            for _, v in ents.values():
                for comp in COMPONENTES:
                    pub[comp] += v[comp]
            snaps = [uid[c] for c, _ in ents.values()]
            _gravar_visao(con, did, "publicado", ragg, None, None, ex, df, snaps, pub)
            for cons in CONSOLIDACOES:
                ana = dict(pub)
                for p in pares.get((ex, f"{ex}-01-01", df), []):
                    lado = _lado_excluido(cons[1], p)
                    if lado is None:
                        continue
                    x = p[lado]  # so a INSCRICAO deste lado sai; fluxos dos dois lados ficam
                    if x["proc_c"] > 0:
                        ana[x["faixa_processado"]] -= x["proc_c"]
                    if x["aproc_c"] > 0:
                        ana[x["faixa_nao_processado"]] -= x["aproc_c"]
                    ana["S1"] -= x["proc_c"] + x["aproc_c"]
                    ana["S2"] -= x["aproc_c"]
                    ana["S3"] -= x["proc_c"]
                _gravar_visao(con, did, "analitico", ragg, R[cons], None, ex, df, snaps, _fechar(ana))


# --------------------------------------------------------------------------- conciliacao
def _conciliacao(con, did, nid, R, uid, conc, em=None):
    regra = R[("CONC-RREO", 1)]
    ent_rreo = conc["entidade_do_rreo_por_entidade"]   # o RREO "por entidade" e o desta entidade
    filtro, p = _ate(em)
    # PDF de RREO sem nenhum valor extraido nesta normalizacao (ex.: layout desconhecido): registrado, nunca ignorado
    for (cid,) in con.execute("SELECT c.id FROM coleta c WHERE c.tipo='rreo_pdf' AND c.status='completa'" + filtro +
                              " AND NOT EXISTS (SELECT 1 FROM rreo_valor v WHERE v.normalizacao_id=? AND v.coleta_id=c.id) "
                              "ORDER BY c.coletada_em, c.snapshot_uid", (*p, nid)).fetchall():
        _verif(con, did, regra, "RREO sem valores extraídos (ver problemas da normalização)", {"rreo_snapshot": uid[cid]}, 1, 1)
    docs = con.execute("SELECT DISTINCT v.coleta_id, v.escopo, v.exercicio, v.data_final FROM rreo_valor v "
                       "JOIN coleta c ON c.id = v.coleta_id WHERE v.normalizacao_id=? AND v.linha='TOTAL (III)'" + filtro +
                       " ORDER BY v.coleta_id", (nid, *p)).fetchall()
    for codigo, versao in AGREGACOES:
        ragg = R[(codigo, versao)]
        for rc, escopo, ex, df in docs:
            rv = dict(con.execute("SELECT coluna, valor_c FROM rreo_valor WHERE normalizacao_id=? AND coleta_id=? "
                                  "AND linha='TOTAL (III)'", (nid, rc)).fetchall())
            if escopo == "entidade":
                api = con.execute("SELECT componente, valor_c, coletas_json FROM visao_valor WHERE derivacao_id=? AND "
                                  "visao='entidade' AND entidade=? AND regra_agregacao_id=? AND exercicio=? AND data_final=?",
                                  (did, ent_rreo, ragg, ex, df)).fetchall()
            else:
                api = con.execute("SELECT componente, valor_c, coletas_json FROM visao_valor WHERE derivacao_id=? AND "
                                  "visao='publicado' AND regra_agregacao_id=? AND exercicio=? AND data_final=?",
                                  (did, ragg, ex, df)).fetchall()
            escopo_v = {"rreo_snapshot": uid[rc], "escopo": escopo, "exercicio": ex, "data_final": df, "rreo_col": versao}
            if not api:
                _verif(con, did, regra, "RREO sem snapshot da API no mesmo corte", escopo_v, 0, 0)
                continue
            av = {c: v for c, v, _ in api}
            dif = 0
            for col, vr in sorted(rv.items()):
                d = av[col] - vr
                dif += d != 0
                con.execute("INSERT INTO conciliacao_rreo VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                            (did, rc, ragg, escopo, ent_rreo if escopo == "entidade" else None, ex, df, api[0][2], col, vr,
                             av[col], d))
            _verif(con, did, regra, "conciliação RREO × API (colunas com diferença)", escopo_v, len(rv), dif)


# --------------------------------------------------------------------------- hash estavel
def resultado_estavel(con, did):
    """Todo o resultado da derivacao com ids internos trocados por identificadores estaveis."""
    uid = dict(con.execute("SELECT id, snapshot_uid FROM coleta"))
    resp = {i: (uid[c], o) for i, c, o in con.execute("SELECT id, coleta_id, ordem FROM resposta_bruta")}
    rg = {i: f"{c} v{v}" for i, c, v in con.execute("SELECT id, codigo, versao FROM regra")}
    q = lambda sql: con.execute(sql, (did,)).fetchall()
    return {
        "rp_derivado": sorted((resp[r[0]], r[1], uid[r[2]], *r[3:]) for r in q(
            "SELECT resposta_id, indice, coleta_id, entidade, anoempenho, empenho, categoria, faixa_processado, "
            "faixa_nao_processado, s1_saldo_total_c, s2_a_liquidar_c, s3_liquidado_a_pagar_c, cancel_processado_c, "
            "cancel_nao_processado_c FROM rp_derivado WHERE derivacao_id=?")),
        "movimentacao_interpretada": sorted((resp[r[0]], *r[1:]) for r in q(
            "SELECT resposta_id, indice, liquidacao_exercicio, liquidacao_numero, efeito, valor_com_sinal_c "
            "FROM movimentacao_interpretada WHERE derivacao_id=?")),
        "anomalia": sorted((rg[r[0]], r[1], uid.get(r[2]), *r[3:]) for r in q(
            "SELECT regra_id, tipo, coleta_id, entidade, anoempenho, empenho, IFNULL(detalhe_json,'') FROM anomalia "
            "WHERE derivacao_id=?")),
        "espelhamento_par": sorted((rg[r[0]], *r[1:4], resp[r[4]], *r[5:9], resp[r[9]], *r[10:]) for r in q(
            "SELECT regra_pareamento_id, exercicio, data_inicial, data_final, resposta_a_id, indice_a, entidade_a, "
            "anoempenho_a, empenho_a, resposta_b_id, indice_b, entidade_b, anoempenho_b, empenho_b, inscrito_a_c, "
            "inscrito_b_c, mesma_inscricao, relacao_inscricao, execucao_a_c, execucao_b_c, lado_com_execucao "
            "FROM espelhamento_par WHERE derivacao_id=?")),
        "visao_valor": sorted((r[0], rg[r[1]], rg.get(r[2], ""), *r[3:]) for r in q(
            "SELECT visao, regra_agregacao_id, IFNULL(regra_consolidacao_id,0), IFNULL(entidade,0), exercicio, "
            "data_final, coletas_json, componente, valor_c FROM visao_valor WHERE derivacao_id=?")),
        "conciliacao_rreo": sorted((uid[r[0]], rg[r[1]], *r[2:]) for r in q(
            "SELECT rreo_coleta_id, regra_agregacao_id, escopo, IFNULL(entidade,0), exercicio, data_final, "
            "coletas_api_json, coluna, valor_rreo_c, valor_api_c, diferenca_c FROM conciliacao_rreo WHERE derivacao_id=?")),
        "verificacao": sorted((rg[r[0]], *r[1:]) for r in q(
            "SELECT regra_id, descricao, escopo_json, verificados, falhas FROM verificacao WHERE derivacao_id=?")),
    }


def hash_resultado(con, did):
    h = hashlib.sha256()
    for tabela, linhas in resultado_estavel(con, did).items():
        h.update(tabela.encode())
        for linha in linhas:
            h.update(json.dumps(linha, ensure_ascii=False, default=str).encode())
    return h.hexdigest()
