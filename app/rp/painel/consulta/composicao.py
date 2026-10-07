"""Painel mixin: Balance composition by dimension (05.4)."""
from .. import fontes, publico
from .comum import (CATEGORIAS, COMPOSICOES, DIMENSOES, DIMENSOES_ORCAMENTARIAS, ErroDoPainel, EXPR_CANCELAMENTOS,
                    EXPR_PAGAMENTOS, FAIXAS, fechamento, instante, MEDIDAS_DA_COMPOSICAO, REGRAS_DO_INDICADOR,
                    ROTULO_CATEGORIA, ROTULO_COMPOSICAO, SEM_CLASSIFICACAO, SITUACOES_DO_PONTO, TEM_VALOR, TEXTO_FAIXA)


class Composicao:
    """Balance composition by dimension (05.4)."""

    def por_dimensao(self, dimensao, exercicio, data_final, entidade=None, em=None):
        """Totals by funding source, budget program, agency, category etc. (closed list of dimensions)."""
        if dimensao not in DIMENSOES:
            raise ErroDoPainel(f"dimensao precisa ser uma de {sorted(DIMENSOES)}")
        ctx, em = self.contexto(), instante(em)
        corte = self._corte(ctx, exercicio, data_final, entidade, em)
        regras_usadas = self._regras_publicaveis(REGRAS_DO_INDICADOR)
        if not corte["disponivel"]:
            return {"dimensao": dimensao, "disponivel": False, "motivo_indisponivel": corte["motivo"], "linhas": []}
        uids = self._uids(corte["somar"])
        regs = [r for r in regras_usadas if r["codigo"] in ("S1",) + (("CAT",) if dimensao == "categoria" else ())]
        nomes = [c.split(".")[1] for c in DIMENSOES[dimensao]]
        linhas = [{**dict(zip(nomes, g.pop("chave"))), **g, "natureza": "derivado",
                   "proveniencia": self._prov_curta(ctx, uids, f"somas agrupadas por {dimensao}", regs)}
                  for g in self._por_grupo(ctx, corte["somar"], DIMENSOES[dimensao])]
        return {"dimensao": dimensao, "disponivel": True, "retrato": corte["retrato"], "fonte": fontes.ELOTECH["rotulo"],
                "linhas": linhas, "proveniencia": self._proveniencia(ctx, corte["somar"], f"somas agrupadas por {dimensao}")}

    def _por_grupo(self, ctx, coletas, colunas):
        """Single grouping query (por_dimensao, indicator categories and composition): records and sums per value of
        `colunas` (fixed SQL expressions of this module), INCLUDING the null group, in descending S1 order."""
        grupo = ", ".join(colunas)
        filtro, p = self._de_coletas(coletas)
        k = len(colunas)
        return [{"chave": row[:k], "registros": row[k], "inscricao_total_c": row[k + 1] or 0,
                 "pagamentos_c": row[k + 2] or 0, "liquidacoes_c": row[k + 3] or 0, "cancelamentos_c": row[k + 4] or 0,
                 "saldo_total_c": row[k + 5] or 0}
                for row in self.con.execute(
                    f"SELECT {grupo}, COUNT(*), SUM(r.proc_c + r.aproc_c), SUM({EXPR_PAGAMENTOS}), "
                    f"SUM(r.liquidado_c), SUM({EXPR_CANCELAMENTOS}), SUM(d.s1_saldo_total_c) "
                    f"FROM rp_registro r JOIN rp_derivado d ON d.derivacao_id=? AND d.resposta_id=r.resposta_id "
                    f"AND d.indice=r.indice WHERE r.normalizacao_id=? AND {filtro} GROUP BY {grupo} "
                    f"ORDER BY SUM(d.s1_saldo_total_c) DESC, {grupo}",
                    (ctx["derivacao"]["id"], ctx["normalizacao"]["id"], *p))]

    def _por_faixa(self, ctx, coletas):
        """Inscribed value by band (FAIXA v1; R3): proc by the processed band and aproc by the not processed band. A record
        with both parts goes into two groups, so only the VALUES add up; the count is per part."""
        filtro, p = self._de_coletas(coletas)
        saida = {}
        for coluna, valor in (("d.faixa_processado", "r.proc_c"), ("d.faixa_nao_processado", "r.aproc_c")):
            for faixa, n, v in self.con.execute(
                    f"SELECT {coluna}, COUNT(*), SUM({valor}) FROM rp_registro r JOIN rp_derivado d ON d.derivacao_id=? "
                    f"AND d.resposta_id=r.resposta_id AND d.indice=r.indice WHERE r.normalizacao_id=? AND {filtro} "
                    f"AND {coluna} IS NOT NULL GROUP BY {coluna}",
                    (ctx["derivacao"]["id"], ctx["normalizacao"]["id"], *p)):
                saida[faixa] = {"registros": n, "inscricao_total_c": v or 0}
        return saida

    def composicao(self, exercicio, data_final, entidade=None, em=None):
        """Composition of a cut-off's inscription and balance (sub-stage 05.4; contract M-05 to M-08), by category, band,
        creditor type and budget dimension.
        * Each dimension adds up ON ITS OWN to the cut-off total, per measure (section 4.2: sum of the groups - total =
          0, with no tolerance or adjustment). A dimension that does not add up is not shown: it comes out without
          groups, with the reason and the closing.
        * Fixed groups (category, band, creditor type) all appear, with 0 when they have no records (the group's zero);
          in the budget dimensions the 'sem classificacao' group (field missing in the API) always appears.
        * Band (R3): only the inscribed value adds up; the record count per band is per part and is not summed.
        * Each group carries the commitment list filter whose total is the group itself.
        * A cut-off without a value for the scope: unavailable, with the situation (never groups with zero)."""
        ctx, em = self.contexto(), instante(em)
        corte = self._corte(ctx, exercicio, data_final, entidade, em)
        codigo = self._situacao_do_ponto(corte, entidade)
        saida = {"consulta": {"exercicio": exercicio, "data_final": data_final, "entidade": entidade, "como_estava_em": em},
                 "escopo": f"entidade {entidade}" if entidade is not None else "Município (entidades do catálogo oficial do exercício)",
                 "situacao": {"codigo": codigo, "texto": SITUACOES_DO_PONTO[codigo]}, "disponivel": codigo in TEM_VALOR,
                 "motivo_indisponivel": None if codigo in TEM_VALOR else corte["motivo"], "retrato": corte["retrato"],
                 "fonte": fontes.ELOTECH["rotulo"], "total": None, "dimensoes": {},
                 "pares_espelhados_no_corte": 0, "proveniencia": None, "nota": fontes.METODOLOGIA["importante"]}
        if codigo not in TEM_VALOR:
            return saida
        regras_usadas = self._regras_publicaveis(REGRAS_DO_INDICADOR | {("FAIXA", 1)})
        uids = self._uids(corte["somar"])
        s = self._somas(ctx, corte["somar"])
        total = {"registros": s["registros"], "inscricao_total_c": s["inscricao_total"], "saldo_total_c": s["saldo_total"]}
        saida.update(total=total, proveniencia=self._proveniencia(ctx, corte["somar"], "composição por dimensão sobre "
                                                                                      "rp_registro + rp_derivado"))
        for d in COMPOSICOES:
            saida["dimensoes"][d] = self._dimensao(ctx, corte["somar"], uids, regras_usadas, d, total, exercicio)
        saida["pares_espelhados_no_corte"] = self._pares_no_corte(ctx, exercicio, data_final, entidade)
        return saida

    def _dimensao(self, ctx, coletas, uids, regras_usadas, d, total, exercicio):
        """Groups and closing of ONE composition dimension (see `composicao`)."""
        codigos = {"categoria": ("S1", "CAT"), "faixa": ("FAIXA",)}.get(d, ("S1",))
        regs = [r for r in regras_usadas if r["codigo"] in codigos]
        medidas = ("inscricao_total_c",) if d == "faixa" else MEDIDAS_DA_COMPOSICAO
        por = {"categoria": "categoria (CAT v1)", "tipo_credor": "tipo de credor",
               "fonte_recurso": "fonte de recurso (código e descrição)", "orgao": "órgão", "funcao": "função",
               "programa": "programa", "elemento": "elemento de despesa"}
        consulta = (f"{TEXTO_FAIXA}: soma de proc por faixa do processado e de aproc por faixa do não processado"
                    if d == "faixa" else f"registros, soma de proc + aproc e soma de S1 por {por.get(d)}")
        grupos = []
        if d == "faixa":
            achadas = self._por_faixa(ctx, coletas)
            anterior = exercicio - 1
            textos = {"a": ("processada", f"empenhos de anos anteriores a {anterior}", "inscricao_processada"),
                      "b": ("processada", f"empenhos de {anterior}", "inscricao_processada"),
                      "f": ("não processada", f"empenhos de anos anteriores a {anterior}", "inscricao_nao_processada"),
                      "g": ("não processada", f"empenhos de {anterior}", "inscricao_nao_processada")}
            for f in list(FAIXAS) + sorted(set(achadas) - set(FAIXAS)):
                parte, origem, na_lista = textos.get(f, ("?", "valor de faixa não previsto pela regra", None))
                v = achadas.get(f, {"registros": 0, "inscricao_total_c": 0})
                grupos.append({"ident": f, "chave": f, "rotulo": f"faixa {f} — parte {parte} de {origem}", "parte": parte,
                               "registros": v["registros"], "inscricao_total_c": v["inscricao_total_c"],
                               "filtro": {"faixa": f} if f in FAIXAS else None, "total_na_lista": na_lista})
        else:
            colunas = {"categoria": ["d.categoria"], "tipo_credor": ["tipo_credor(r.cnpj)"]}.get(d, DIMENSOES.get(d))
            achados = {g["chave"]: g for g in self._por_grupo(ctx, coletas, colunas)}
            fixos = {"categoria": CATEGORIAS, "tipo_credor": publico.TIPOS_CREDOR}.get(d)
            if fixos:
                chaves = [(k,) for k in fixos] + [k for k in achados if k[0] not in fixos]
            else:
                nulo = (None,) * len(colunas)
                chaves = [k for k in achados if k != nulo] + [nulo]
            descricoes = {}
            for k in chaves:
                if d == "fonte_recurso" and k[0] is not None:
                    descricoes.setdefault(k[0], set()).add(k[1])
            for i, k in enumerate(chaves):
                g = achados.get(k, {"registros": 0, "inscricao_total_c": 0, "saldo_total_c": 0})
                grupos.append({**self._rotulo_do_grupo(d, k, i, descricoes), "registros": g["registros"],
                               "inscricao_total_c": g["inscricao_total_c"], "saldo_total_c": g["saldo_total_c"]})
        for g in grupos:
            g.update(natureza="derivado", proveniencia=self._prov_curta(ctx, uids, consulta, regs))
        fech = {m: fechamento(total[m], [g[m] for g in grupos]) for m in medidas}
        abertas = [m for m in medidas if not fech[m]["fecha"]]
        motivo = None
        if abertas:
            motivo = ("a soma dos grupos não fecha com o total do corte ("
                      + "; ".join(f"{m}: diferença {fech[m]['diferenca']}" for m in abertas)
                      + "): a dimensão não é exibida até a causa ser explicada")
        return {"dimensao": d, "rotulo": ROTULO_COMPOSICAO[d], "medidas": list(medidas), "regras": regs,
                "consulta": consulta, "fechamento": fech, "fecha": not abertas, "exibida": not abertas,
                "motivo_nao_exibida": motivo, "grupos": [] if abertas else grupos,
                "contagem_aditiva": d != "faixa"}

    @staticmethod
    def _rotulo_do_grupo(d, k, i, descricoes):
        """Identifier, label and commitment list filter of a group (see `composicao`). A group without an exact filter
        (unexpected value, a code with more than one description) comes out with filter None and the reason, never
        with a wrong list."""
        v = k[0]
        if d in DIMENSOES_ORCAMENTARIAS and all(x is None for x in k):
            return {"ident": "sem", "chave": None, "rotulo": SEM_CLASSIFICACAO, "filtro": {"sem_classificacao": d}}
        if d == "categoria":
            return {"ident": str(v), "chave": v, "rotulo": ROTULO_CATEGORIA.get(v, f"valor não previsto: {v}"),
                    "filtro": {"categoria": v} if v in CATEGORIAS else None}
        if d == "tipo_credor":
            ident = {"pessoa jurídica": "pj", "pessoa física": "pf", "não identificado": "ni"}.get(v, f"tipo{i}")
            return {"ident": ident, "chave": v, "rotulo": v,
                    "filtro": {"tipo_credor": v} if v in publico.TIPOS_CREDOR else None}
        if d == "fonte_recurso":
            item = {"ident": str(v), "chave": {"fonte_recurso": v, "descricao_fonte": k[1]},
                    "rotulo": k[1] or f"fonte {v}", "filtro": {"fonte_recurso": v}}
            if v is None:
                item.update(ident="sem-codigo", filtro=None, motivo_sem_lista="registro sem o código da fonte")
            elif len(descricoes.get(v, ())) > 1:
                item.update(filtro=None, motivo_sem_lista=f"o código {v} aparece com mais de uma descrição neste "
                                                          "corte; a lista por código juntaria esses grupos")
            return item
        nome = {"orgao": "órgão", "funcao": "função", "programa": "programa", "elemento": "elemento"}[d]
        return {"ident": str(v), "chave": v, "rotulo": f"{nome} {v}", "filtro": {d: v}}
