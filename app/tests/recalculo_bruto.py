"""Recalculo INDEPENDENTE a partir do JSON bruto do armazem (Subetapa 05.1; etapa05/CONTRATO_ANALITICO.md).

Oraculo de validacao das metricas numericas da Etapa 05 (regime "bruto", contrato secao 4.1):
  * le os valores so do armazem (manifesto -> objetos -> JSON da API, Decimal -> centavos);
  * do banco usa apenas a camada 0 (tabela `coleta`, para achar os snapshots) e o limite de processamento
    (`normalizacao_execucao.ultima_coleta_id` da normalizacao da derivacao atual);
  * NAO importa rp.painel, rp.derivar nem rp.normalizar: nada aqui reaproveita a implementacao de producao, que e
    justamente o que se valida.
Generaliza registros_brutos / recalcular de test_homologacao_real.py (04.6) para pontos de serie com a situacao do
dado (contrato secao 2), diferencas (posterior - anterior), composicao por dimensao (contrato M-05 a M-08),
contribuicoes por empenho (contrato M-09 a M-11) e o historico de um empenho nos cortes (M-12).
Anomalias e verificacoes NAO sao recalculadas aqui (regime "derivacao"): seria uma segunda implementacao das regras.
A unica excecao e a elegibilidade do retrato (revisao critica, item 1): retrato com a mesma chave (entidade,
anoempenho, empenho) mais de uma vez nunca e o vigente. Aqui ela e decidida lendo o bruto, nao a anomalia CHAVE-DUP
gravada - e o que permite conferir a regra do painel em vez de repeti-la.
So suporta o retrato atual (sem "como estava em").
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
    """Valor da API (lido como Decimal) -> centavos inteiros. Ausente = 0 (o registro existe, o campo nao veio)."""
    if v is None:
        return 0
    c = Decimal(str(v)) * 100
    if c != c.to_integral_value():
        raise ValueError(f"valor com mais de 2 casas decimais: {v!r}")
    return int(c)


def valores_do_item(r):
    """Campos monetarios de um item da API, em centavos, com as formulas documentadas (Etapa 02)."""
    v = {nome: centavos(r.get(api)) for api, nome in CAMPOS.items()}
    v["s1"] = v["proc"] + v["aproc"] - v["pago_proc"] - v["pago_aproc"] - v["cancelado_aproc"]
    v["s2"] = v["aproc"] - v["liquidado"] - v["cancelado_aproc"]
    v["s3"] = v["proc"] - v["pago_proc"] + v["liquidado"] - v["pago_aproc"]
    v["pagamentos"] = v["pago_proc"] + v["pago_aproc"]
    return v


def indicadores(itens):
    """Os 14 indicadores de `SOMAS` (consulta.py), recalculados de itens brutos."""
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
    """CAT v1 pela definicao documentada (contrato M-05), sobre os centavos do item."""
    if v["proc"] > 0 and v["aproc"] > 0:
        return "ambos"
    return "processado" if v["proc"] > 0 else "nao_processado" if v["aproc"] > 0 else "sem_saldo_abertura"


def tipo_credor(cnpj):
    """Tipo do credor pela definicao documentada (contrato M-07): CNPJ completo -> pessoa juridica; CPF mascarado
    pela API ou 11 digitos -> pessoa fisica; resto -> nao identificado."""
    s = str(cnpj or "")
    if re.fullmatch(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", s):
        return "pessoa jurídica"
    if re.fullmatch(r"\*+\d{3}\*+", s) or len(re.sub(r"\D", "", s)) == 11:
        return "pessoa física"
    return "não identificado"


# dimensoes orcamentarias da composicao (contrato M-08): chave do grupo a partir do item da API (chave ausente = None)
CHAVES_ORCAMENTARIAS = {"fonte_recurso": ("fonteRecurso", "descricaoFonte"), "orgao": ("orgao",), "funcao": ("funcao",),
                        "programa": ("programa",), "elemento": ("elemento",)}


def composicao(itens, exercicio):
    """Composicao de um conjunto de itens brutos (contrato M-05 a M-08): por dimensao, {chave: somas}; faixa so com o
    valor inscrito de cada parte positiva (R3). Chaves: categoria e tipo como texto; faixa 'a'/'b'/'f'/'g';
    orcamentarias como tupla dos valores do item (fonte: codigo e descricao)."""
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
        anterior = r["anoempenho"] == exercicio - 1          # FAIXA v1: b/g para exercicio-1, a/f para os demais
        if v["proc"] > 0:
            somar("faixa", "b" if anterior else "a", 1, v["proc"])
        if v["aproc"] > 0:
            somar("faixa", "g" if anterior else "f", 1, v["aproc"])
    return {"total": total, "dimensoes": saida}


def diferenca(anterior, posterior):
    """Contrato secao 1.5: posterior - anterior; ausencia em qualquer lado = None (nunca zero)."""
    if anterior is None or posterior is None:
        return None
    for x in (anterior, posterior):
        if isinstance(x, bool) or not isinstance(x, int):
            raise TypeError(f"diferenca exige centavos inteiros: {x!r}")
    return posterior - anterior


def fechamento(total_c, componentes):
    """Contrato secao 4.2: diferenca = soma dos componentes - total; aprova so se 0. Sem tolerancia, sem ajuste.
    `componentes`: lista de (rotulo, centavos)."""
    for rotulo, v in [("total", total_c)] + list(componentes):
        if isinstance(v, bool) or not isinstance(v, int):
            raise TypeError(f"fechamento exige centavos inteiros: {rotulo} = {v!r}")
    soma = sum(v for _, v in componentes)
    return {"fecha": soma == total_c, "total_c": total_c, "soma_componentes_c": soma, "diferenca_c": soma - total_c,
            "componentes": len(componentes)}


class Bruto:
    """Leitura independente de um banco do projeto + armazem. `con` pode ser somente leitura."""

    def __init__(self, con, armazem):
        self.con, self.armazem, self._cache = con, armazem, {}
        row = con.execute("SELECT n.ultima_coleta_id FROM derivacao_execucao d JOIN normalizacao_execucao n "
                          "ON n.id = d.normalizacao_id WHERE d.vigencia_em IS NULL ORDER BY d.id DESC LIMIT 1").fetchone()
        if not row or row[0] is None:
            raise ValueError("banco sem derivacao atual sobre normalizacao v4 (ultima_coleta_id)")
        self.limite = row[0]

    # ---------------------------------------------------------------- leitura do bruto
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
        """O retrato tem a mesma chave (entidade, anoempenho, empenho) mais de uma vez no bruto?"""
        chaves = [(r["entidade"], r["anoempenho"], r["empenho"]) for r in self.itens(coleta_id)]
        return len(chaves) != len(set(chaves))

    def uid(self, coleta_id):
        return self.con.execute("SELECT snapshot_uid FROM coleta WHERE id=?", (coleta_id,)).fetchone()[0]

    # ---------------------------------------------------------------- catalogos (do bruto)
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
        """Exercicios do catalogo oficial da entidade, ou None se nao ha catalogo dela."""
        cid = self._ultima("exercicios", entidade)
        if not cid:
            return None
        anos = {x["id"]["exercicio"] for corpo in self._json(cid) for x in corpo}
        return anos or None

    # ---------------------------------------------------------------- cortes e situacao (contrato secao 2)
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
        """Coleta completa e processada mais recente do corte sem chave repetida (ou None)."""
        ok = [cid for cid, st, _, _ in self._listagens(entidade, exercicio, data_final)
              if st == "completa" and cid <= self.limite and not self.repetida(cid)]
        return ok[-1] if ok else None

    def cortes_do_exercicio(self, exercicio):
        """Universo da serie (contrato secao 2.4): cortes com snapshot processado de QUALQUER entidade."""
        return sorted({df for cid, st, _, df in self._listagens(None, exercicio)
                       if st == "completa" and cid <= self.limite})

    def situacao(self, entidade, exercicio, data_final):
        """Situacao de uma entidade num corte, com a precedencia do contrato (secao 2.2)."""
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
        if any(st == "completa" for _, st, _, _ in linhas):      # processada, mas toda com chave repetida
            return "ambiguo"
        if any(st != "completa" for _, st, _, _ in linhas):
            return "incompleto"
        return "sem_coleta"

    def ponto(self, exercicio, data_final, entidade=None):
        """Ponto de serie (contrato secao 2.3): situacao, valores (None sem valor) e snapshots usados."""
        if entidade is not None:
            sit = self.situacao(entidade, exercicio, data_final)
            cid = self.vigente(entidade, exercicio, data_final) if sit in TEM_VALOR else None
            return {"situacao": sit, "tem_valor": sit in TEM_VALOR, "entidades": {entidade: sit},
                    "valores": indicadores(self.itens(cid)) if cid else None,
                    "coletas": [cid] if cid else []}
        if not self._listagens(None, exercicio):
            return {"situacao": "exercicio_sem_cobertura", "tem_valor": False, "entidades": {}, "valores": None,
                    "coletas": []}
        # catalogo de entidades + entidades com snapshot processado no corte (contrato secao 2.1)
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
        """Todos os pontos do universo do exercicio, com a diferenca para o ponto adjacente anterior (secao 2.6)."""
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

    # ---------------------------------------------------------------- serie entre exercicios (contrato M-03, M-04)
    def sem_cobertura(self, exercicio):
        return not self._listagens(None, exercicio)

    def corte_representativo(self, exercicio):
        """(data_final, aberto): 31/12 com Municipio disponivel; senao o ultimo corte com Municipio disponivel."""
        disp = [df for df in self.cortes_do_exercicio(exercicio) if self.ponto(exercicio, df)["tem_valor"]]
        if f"{exercicio}-12-31" in disp:
            return f"{exercicio}-12-31", False
        return (disp[-1], True) if disp else (None, None)

    def a_mais_f(self, exercicio, coletas):
        """Abertura de RP de exercicios anteriores a exercicio-1: proc e aproc dos itens com anoempenho diferente de
        exercicio-1 (faixas 'a' e 'f'; so a parte positiva entra em faixa), recalculado do bruto."""
        total = 0
        for c in coletas:
            for r in self.itens(c):
                v = valores_do_item(r)
                if r["anoempenho"] != exercicio - 1:
                    total += (v["proc"] if v["proc"] > 0 else 0) + (v["aproc"] if v["aproc"] > 0 else 0)
        return total

    # ---------------------------------------------------------------- composicao (contrato M-05 a M-08)
    def composicao(self, exercicio, data_final, entidade=None):
        """Composicao do ponto (situacao do contrato secao 2): None sem valor; senao `composicao()` dos itens."""
        pt = self.ponto(exercicio, data_final, entidade)
        if not pt["tem_valor"]:
            return {"situacao": pt["situacao"], "composicao": None}
        itens = [r for c in pt["coletas"] for r in self.itens(c)]
        return {"situacao": pt["situacao"], "composicao": composicao(itens, exercicio)}

    # ---------------------------------------------------------------- historico de um empenho (contrato M-12)
    def empenho_nos_cortes(self, entidade, anoempenho, empenho, exercicio):
        """Para cada corte do universo do exercicio: situacao da entidade e os valores (valores_do_item) de cada
        ocorrencia da chave no snapshot vigente (lista vazia = empenho ausente do corte)."""
        saida = []
        for df in self.cortes_do_exercicio(exercicio):
            sit = self.situacao(entidade, exercicio, df)
            ocorrencias = None
            if sit in TEM_VALOR:
                ocorrencias = [valores_do_item(r) for r in self.itens(self.vigente(entidade, exercicio, df))
                               if (r["entidade"], r["anoempenho"], r["empenho"]) == (entidade, anoempenho, empenho)]
            saida.append({"data_final": df, "situacao": sit, "ocorrencias": ocorrencias})
        return saida

    # ---------------------------------------------------------------- contribuicoes (contrato M-09 a M-11)
    def contribuicoes(self, exercicio, df_anterior, df_posterior, entidade=None, metrica="s1", top=10):
        """Contribuicao de cada empenho para a variacao de `metrica` ('s1' ou 'pagamentos') entre dois cortes do
        mesmo exercicio. Bloqueia o par se faltar valor num lado, se o Municipio tiver conjuntos de entidades
        diferentes ou se houver chave repetida num lado."""
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
        linhas.sort(key=lambda x: (-x["contribuicao_c"], x["chave"]))       # ordem do contrato (M-10)
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
