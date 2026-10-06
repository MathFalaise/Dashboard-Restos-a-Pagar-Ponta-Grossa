"""INDEPENDENT recalculation from the store's raw JSON (sub-stage 05.1; docs/stages/05-analysis/ANALYTICAL_CONTRACT.md).

Validation oracle for the numeric metrics of stage 05 ("bruto" regime, contract section 4.1):
  * reads values only from the store (manifest -> objects -> API JSON, Decimal -> cents);
  * from the database it only uses layer 0 (the `coleta` table, to find the snapshots) and the processing limit
    (`normalizacao_execucao.ultima_coleta_id` of the current derivation's normalization);
  * it does NOT import rp.painel, rp.derivar or rp.normalizar: nothing here reuses the production implementation,
    which is exactly what is being validated.
It generalizes registros_brutos / recalcular from test_homologacao_real.py (04.6) to series points with the data
situation (contract section 2), differences (later - earlier), composition by dimension (contract M-05 to M-08),
contributions per commitment (contract M-09 to M-11) and a commitment's history across cut-offs (M-12).
Anomalies and checks are NOT recalculated here ("derivacao" regime): that would be a second implementation of the
rules. The only exception is snapshot eligibility (critical review, item 1): a snapshot with the same key (entidade,
anoempenho, empenho) more than once is never the current one. Here it is decided by reading the raw data, not the
recorded CHAVE-DUP anomaly - which is what lets us check the panel's rule instead of repeating it.
It only supports the current snapshot (no "as it was on").
"""
import json
import re
from decimal import Decimal

CAMPOS = {"proc": "proc", "aproc": "aproc", "pagoProc": "pago_proc", "pagoAProc": "pago_aproc",
          "liquidado": "liquidado", "canceladoAProc": "cancelado_aproc", "canceladoProc": "cancelado_proc",
          "retencao": "retencao", "pagoProcEstornado": "pago_proc_estornado",
          "pagoAProcEstornado": "pago_aproc_estornado"}
TEM_VALOR = ("com_dados", "sem_rp")
SEM_SNAPSHOT = ("nao_processado", "ambiguo", "incompleto", "sem_coleta")


def centavos(v):
    """API value (read as Decimal) -> integer cents. Missing = 0 (the record exists, the field did not come)."""
    if v is None:
        return 0
    c = Decimal(str(v)) * 100
    if c != c.to_integral_value():
        raise ValueError(f"valor com mais de 2 casas decimais: {v!r}")
    return int(c)


def valores_do_item(r):
    """Monetary fields of an API item, in cents, with the documented formulas (stage 02)."""
    v = {nome: centavos(r.get(api)) for api, nome in CAMPOS.items()}
    v["s1"] = v["proc"] + v["aproc"] - v["pago_proc"] - v["pago_aproc"] - v["cancelado_aproc"]
    v["s2"] = v["aproc"] - v["liquidado"] - v["cancelado_aproc"]
    v["s3"] = v["proc"] - v["pago_proc"] + v["liquidado"] - v["pago_aproc"]
    v["pagamentos"] = v["pago_proc"] + v["pago_aproc"]
    return v


def indicadores(itens):
    """The 14 indicators of `SOMAS` (consulta.py), recalculated from raw items."""
    s = dict.fromkeys(("registros", "inscricao_processada", "inscricao_nao_processada", "inscricao_total",
                       "pago_processado", "pago_nao_processado", "pagamentos", "estornos_de_pagamento", "liquidacoes",
                       "cancelamentos", "retencoes", "saldo_total", "saldo_a_liquidar", "saldo_liquidado_a_pagar"), 0)
    for r in itens:
        v = valores_do_item(r)
        s["registros"] += 1
        s["inscricao_processada"] += v["proc"]
        s["inscricao_nao_processada"] += v["aproc"]
        s["inscricao_total"] += v["proc"] + v["aproc"]
        s["pago_processado"] += v["pago_proc"]
        s["pago_nao_processado"] += v["pago_aproc"]
        s["pagamentos"] += v["pagamentos"]
        s["estornos_de_pagamento"] += v["pago_proc_estornado"] + v["pago_aproc_estornado"]
        s["liquidacoes"] += v["liquidado"]
        s["cancelamentos"] += v["cancelado_aproc"] + v["cancelado_proc"]
        s["retencoes"] += v["retencao"]
        s["saldo_total"] += v["s1"]
        s["saldo_a_liquidar"] += v["s2"]
        s["saldo_liquidado_a_pagar"] += v["s3"]
    return s


def categoria(v):
    """CAT v1 by the documented definition (contract M-05), over the item's cents."""
    if v["proc"] > 0 and v["aproc"] > 0:
        return "ambos"
    return "processado" if v["proc"] > 0 else "nao_processado" if v["aproc"] > 0 else "sem_saldo_abertura"


def tipo_credor(cnpj):
    """Creditor type by the documented definition (contract M-07): complete CNPJ -> legal entity; CPF masked by the
    API or 11 digits -> individual; anything else -> not identified."""
    s = str(cnpj or "")
    if re.fullmatch(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", s):
        return "pessoa jurídica"
    if re.fullmatch(r"\*+\d{3}\*+", s) or len(re.sub(r"\D", "", s)) == 11:
        return "pessoa física"
    return "não identificado"


# budget dimensions of the composition (contract M-08): group key from the API item (missing key = None)
CHAVES_ORCAMENTARIAS = {"fonte_recurso": ("fonteRecurso", "descricaoFonte"), "orgao": ("orgao",), "funcao": ("funcao",),
                        "programa": ("programa",), "elemento": ("elemento",)}


def composicao(itens, exercicio):
    """Composition of a set of raw items (contract M-05 to M-08): per dimension, {key: sums}; band only with the
    inscribed value of each positive part (R3). Keys: category and type as text; band 'a'/'b'/'f'/'g'; budget ones as
    a tuple of the item's values (source: code and description)."""
    saida = {d: {} for d in ("categoria", "faixa", "tipo_credor", *CHAVES_ORCAMENTARIAS)}

    def somar(d, chave, registros, insc, s1=None):
        g = saida[d].setdefault(chave, {"registros": 0, "inscricao_total_c": 0, "saldo_total_c": 0})
        g["registros"] += registros
        g["inscricao_total_c"] += insc
        g["saldo_total_c"] += s1 or 0

    total = {"registros": 0, "inscricao_total_c": 0, "saldo_total_c": 0}
    for r in itens:
        v = valores_do_item(r)
        insc = v["proc"] + v["aproc"]
        total["registros"] += 1
        total["inscricao_total_c"] += insc
        total["saldo_total_c"] += v["s1"]
        somar("categoria", categoria(v), 1, insc, v["s1"])
        somar("tipo_credor", tipo_credor(r.get("cnpj")), 1, insc, v["s1"])
        for d, chaves in CHAVES_ORCAMENTARIAS.items():
            somar(d, tuple(r.get(k) for k in chaves), 1, insc, v["s1"])
        anterior = r["anoempenho"] == exercicio - 1          # FAIXA v1: b/g for exercicio-1, a/f for the others
        if v["proc"] > 0:
            somar("faixa", "b" if anterior else "a", 1, v["proc"])
        if v["aproc"] > 0:
            somar("faixa", "g" if anterior else "f", 1, v["aproc"])
    return {"total": total, "dimensoes": saida}


def diferenca(anterior, posterior):
    """Contract section 1.5: later - earlier; absence on either side = None (never zero)."""
    if anterior is None or posterior is None:
        return None
    for x in (anterior, posterior):
        if isinstance(x, bool) or not isinstance(x, int):
            raise TypeError(f"diferenca exige centavos inteiros: {x!r}")
    return posterior - anterior


def fechamento(total_c, componentes):
    """Contract section 4.2: difference = sum of the components - total; passes only if 0. No tolerance, no adjustment.
    `componentes`: list of (label, cents)."""
    for rotulo, v in [("total", total_c)] + list(componentes):
        if isinstance(v, bool) or not isinstance(v, int):
            raise TypeError(f"fechamento exige centavos inteiros: {rotulo} = {v!r}")
    soma = sum(v for _, v in componentes)
    return {"fecha": soma == total_c, "total_c": total_c, "soma_componentes_c": soma, "diferenca_c": soma - total_c,
            "componentes": len(componentes)}


class Bruto:
    """Independent reading of a project database + store. `con` may be read-only."""

    def __init__(self, con, armazem):
        self.con, self.armazem, self._cache = con, armazem, {}
        row = con.execute("SELECT n.ultima_coleta_id FROM derivacao_execucao d JOIN normalizacao_execucao n "
                          "ON n.id = d.normalizacao_id WHERE d.vigencia_em IS NULL ORDER BY d.id DESC LIMIT 1").fetchone()
        if not row or row[0] is None:
            raise ValueError("banco sem derivacao atual sobre normalizacao v4 (ultima_coleta_id)")
        self.limite = row[0]

    # ---------------------------------------------------------------- reading the raw data
    def _json(self, coleta_id):
        if coleta_id not in self._cache:
            rel = self.con.execute("SELECT manifesto FROM coleta WHERE id=?", (coleta_id,)).fetchone()[0]
            m = self.armazem.ler_manifesto(rel)
            self._cache[coleta_id] = [json.loads(self.armazem.ler_objeto(r["sha256"]), parse_float=Decimal)
                                      for r in m["respostas"]]
        return self._cache[coleta_id]

    def itens(self, coleta_id):
        return [r for corpo in self._json(coleta_id) for r in corpo["content"]]

    def repetida(self, coleta_id):
        """Does the snapshot have the same key (entidade, anoempenho, empenho) more than once in the raw data?"""
        chaves = [(r["entidade"], r["anoempenho"], r["empenho"]) for r in self.itens(coleta_id)]
        return len(chaves) != len(set(chaves))

    def uid(self, coleta_id):
        return self.con.execute("SELECT snapshot_uid FROM coleta WHERE id=?", (coleta_id,)).fetchone()[0]

    # ---------------------------------------------------------------- catalogs (from the raw data)
    def _ultima(self, tipo, entidade=None):
        sql = "SELECT id FROM coleta WHERE tipo=? AND status='completa' AND id <= ?"
        p = [tipo, self.limite]
        if entidade is not None:
            sql, p = sql + " AND entidade=?", p + [entidade]
        row = self.con.execute(sql + " ORDER BY coletada_em DESC, snapshot_uid DESC LIMIT 1", p).fetchone()
        return row and row[0]

    def entidades_do_catalogo(self):
        cid = self._ultima("entidades")
        return set() if not cid else {x["id"] for corpo in self._json(cid) for x in corpo}

    def exercicios_oficiais(self, entidade):
        """Fiscal years in the entity's official catalog, or None if there is no catalog for it."""
        cid = self._ultima("exercicios", entidade)
        if not cid:
            return None
        anos = {x["id"]["exercicio"] for corpo in self._json(cid) for x in corpo}
        return anos or None

    # ---------------------------------------------------------------- cut-offs and situation (contract section 2)
    def _listagens(self, entidade, exercicio, data_final=None):
        sql = ("SELECT id, status, entidade, data_final FROM coleta WHERE tipo='rp_listagem' AND tipo_pesquisa IS NULL "
               "AND exercicio=? AND data_inicial=?")
        p = [exercicio, f"{exercicio}-01-01"]
        if entidade is not None:
            sql, p = sql + " AND entidade=?", p + [entidade]
        if data_final is not None:
            sql, p = sql + " AND data_final=?", p + [data_final]
        return self.con.execute(sql + " ORDER BY coletada_em, snapshot_uid", p).fetchall()

    def vigente(self, entidade, exercicio, data_final):
        """Most recent complete and processed collection of the cut-off without a repeated key (or None)."""
        ok = [cid for cid, st, _, _ in self._listagens(entidade, exercicio, data_final)
              if st == "completa" and cid <= self.limite and not self.repetida(cid)]
        return ok[-1] if ok else None

    def cortes_do_exercicio(self, exercicio):
        """Series universe (contract section 2.4): cut-offs with a processed snapshot of ANY entity."""
        return sorted({df for cid, st, _, df in self._listagens(None, exercicio)
                       if st == "completa" and cid <= self.limite})

    def situacao(self, entidade, exercicio, data_final):
        """Situation of an entity at a cut-off, with the contract's precedence (section 2.2)."""
        anos = self.exercicios_oficiais(entidade)
        if anos is not None and exercicio not in anos:
            return "inexistente"
        if not self._listagens(None, exercicio):
            return "exercicio_sem_cobertura"
        cid = self.vigente(entidade, exercicio, data_final)
        if cid is not None:
            return "sem_rp" if not self.itens(cid) else "com_dados"
        linhas = self._listagens(entidade, exercicio, data_final)
        if any(st == "completa" and c > self.limite for c, st, _, _ in linhas):
            return "nao_processado"
        if any(st == "completa" for _, st, _, _ in linhas):      # processed, but all with a repeated key
            return "ambiguo"
        if any(st != "completa" for _, st, _, _ in linhas):
            return "incompleto"
        return "sem_coleta"

    def ponto(self, exercicio, data_final, entidade=None):
        """Series point (contract section 2.3): situation, values (None without a value) and snapshots used."""
        if entidade is not None:
            sit = self.situacao(entidade, exercicio, data_final)
            cid = self.vigente(entidade, exercicio, data_final) if sit in TEM_VALOR else None
            return {"situacao": sit, "tem_valor": sit in TEM_VALOR, "entidades": {entidade: sit},
                    "valores": indicadores(self.itens(cid)) if cid else None,
                    "coletas": [cid] if cid else []}
        if not self._listagens(None, exercicio):
            return {"situacao": "exercicio_sem_cobertura", "tem_valor": False, "entidades": {}, "valores": None,
                    "coletas": []}
        # entity catalog + entities with a processed snapshot at the cut-off (contract section 2.1)
        universo = self.entidades_do_catalogo() | {e for c, st, e, _ in self._listagens(None, exercicio, data_final)
                                                   if st == "completa" and c <= self.limite}
        sits = {e: self.situacao(e, exercicio, data_final) for e in sorted(universo)}
        somar = [e for e, s in sits.items() if s in TEM_VALOR]
        if any(s in SEM_SNAPSHOT for s in sits.values()) or not somar:
            return {"situacao": "municipio_indisponivel", "tem_valor": False, "entidades": sits, "valores": None,
                    "coletas": []}
        coletas = [self.vigente(e, exercicio, data_final) for e in somar]
        itens = [r for c in coletas for r in self.itens(c)]
        sit = "sem_rp" if not itens else "com_dados"
        return {"situacao": sit, "tem_valor": True, "entidades": sits, "valores": indicadores(itens), "coletas": coletas}

    def serie(self, exercicio, entidade=None):
        """All points of the fiscal year's universe, with the difference to the previous adjacent point (section 2.6)."""
        pontos, anterior = [], None
        for df in self.cortes_do_exercicio(exercicio):
            pt = {"data_final": df, **self.ponto(exercicio, df, entidade)}
            if anterior is None:
                pt["diferenca_saldo"] = None
            else:
                pt["diferenca_saldo"] = diferenca(anterior["valores"] and anterior["valores"]["saldo_total"],
                                                  pt["valores"] and pt["valores"]["saldo_total"])
            pontos.append(pt)
            anterior = pt
        return pontos

    # ---------------------------------------------------------------- series across fiscal years (contract M-03, M-04)
    def sem_cobertura(self, exercicio):
        return not self._listagens(None, exercicio)

    def corte_representativo(self, exercicio):
        """(data_final, open): 31/12 with the Municipality available; otherwise the last cut-off with the Municipality available."""
        disp = [df for df in self.cortes_do_exercicio(exercicio) if self.ponto(exercicio, df)["tem_valor"]]
        if f"{exercicio}-12-31" in disp:
            return f"{exercicio}-12-31", False
        return (disp[-1], True) if disp else (None, None)

    def a_mais_f(self, exercicio, coletas):
        """Opening RP of years before exercicio-1: proc and aproc of the items with anoempenho other than exercicio-1
        (bands 'a' and 'f'; only the positive part goes into a band), recalculated from the raw data."""
        total = 0
        for c in coletas:
            for r in self.itens(c):
                v = valores_do_item(r)
                if r["anoempenho"] != exercicio - 1:
                    total += (v["proc"] if v["proc"] > 0 else 0) + (v["aproc"] if v["aproc"] > 0 else 0)
        return total

    # ---------------------------------------------------------------- composition (contract M-05 to M-08)
    def composicao(self, exercicio, data_final, entidade=None):
        """Composition of the point (contract section 2 situation): None without a value; otherwise `composicao()` of the items."""
        pt = self.ponto(exercicio, data_final, entidade)
        if not pt["tem_valor"]:
            return {"situacao": pt["situacao"], "composicao": None}
        itens = [r for c in pt["coletas"] for r in self.itens(c)]
        return {"situacao": pt["situacao"], "composicao": composicao(itens, exercicio)}

    # ---------------------------------------------------------------- history of a commitment (contract M-12)
    def empenho_nos_cortes(self, entidade, anoempenho, empenho, exercicio):
        """For each cut-off of the fiscal year's universe: the entity's situation and the values (valores_do_item) of each
        occurrence of the key in the current snapshot (empty list = commitment missing from the cut-off)."""
        saida = []
        for df in self.cortes_do_exercicio(exercicio):
            sit = self.situacao(entidade, exercicio, df)
            ocorrencias = None
            if sit in TEM_VALOR:
                ocorrencias = [valores_do_item(r) for r in self.itens(self.vigente(entidade, exercicio, df))
                               if (r["entidade"], r["anoempenho"], r["empenho"]) == (entidade, anoempenho, empenho)]
            saida.append({"data_final": df, "situacao": sit, "ocorrencias": ocorrencias})
        return saida

    # ---------------------------------------------------------------- contributions (contract M-09 to M-11)
    def contribuicoes(self, exercicio, df_anterior, df_posterior, entidade=None, metrica="s1", top=10):
        """Contribution of each commitment to the variation of `metrica` ('s1' or 'pagamentos') between two cut-offs of the
        same fiscal year. Blocks the pair if a value is missing on one side, if the Municipality has different sets
        of entities or if there is a repeated key on one side."""
        if metrica not in ("s1", "pagamentos"):
            raise ValueError("metrica do contrato: 's1' ou 'pagamentos'")
        a, b = self.ponto(exercicio, df_anterior, entidade), self.ponto(exercicio, df_posterior, entidade)
        if not (a["tem_valor"] and b["tem_valor"]):
            return {"disponivel": False, "motivo": f"ponto sem valor: {a['situacao']} / {b['situacao']}"}
        def somadas(p):
            return {e for e, s in p["entidades"].items() if s in TEM_VALOR}
        if somadas(a) != somadas(b):
            return {"disponivel": False, "motivo": "conjunto de entidades diferente nos dois cortes (R6)"}
        lados, repetidas = [], set()
        for p in (a, b):
            mapa = {}
            for r in (r for c in p["coletas"] for r in self.itens(c)):
                k = (r["entidade"], r["anoempenho"], r["empenho"])
                if k in mapa:
                    repetidas.add(k)
                mapa[k] = valores_do_item(r)[metrica]
            lados.append(mapa)
        if repetidas:
            return {"disponivel": False, "motivo": "chave duplicada", "chaves_repetidas": sorted(repetidas)}
        ant, post = lados
        linhas = []
        for k in sorted(set(ant) | set(post)):
            if k in ant and k in post:
                classe, c = "nos_dois", post[k] - ant[k]
            elif k in post:
                classe, c = "so_posterior", post[k]
            else:
                classe, c = "so_anterior", 0 - ant[k]
            linhas.append({"chave": k, "classe": classe, "contribuicao_c": c})
        variacao = sum(post.values()) - sum(ant.values())
        linhas.sort(key=lambda x: (-x["contribuicao_c"], x["chave"]))       # contract order (M-10)
        aum = [x for x in linhas if x["contribuicao_c"] > 0]
        red = sorted((x for x in linhas if x["contribuicao_c"] < 0), key=lambda x: (x["contribuicao_c"], x["chave"]))
        grupos = [("top_aumentos", sum(x["contribuicao_c"] for x in aum[:top])),
                  ("outros_aumentos", sum(x["contribuicao_c"] for x in aum[top:])),
                  ("top_reducoes", sum(x["contribuicao_c"] for x in red[:top])),
                  ("outras_reducoes", sum(x["contribuicao_c"] for x in red[top:])),
                  ("sem_variacao", 0)]
        classes = [(cl, sum(x["contribuicao_c"] for x in linhas if x["classe"] == cl))
                   for cl in ("nos_dois", "so_posterior", "so_anterior")]
        return {"disponivel": True, "variacao_c": variacao, "linhas": linhas, "grupos": grupos, "classes": classes,
                "sem_variacao": sum(1 for x in linhas if x["contribuicao_c"] == 0),
                "fechamento_grupos": fechamento(variacao, grupos), "fechamento_classes": fechamento(variacao, classes),
                "fechamento_linhas": fechamento(variacao, [(str(x["chave"]), x["contribuicao_c"]) for x in linhas])}
