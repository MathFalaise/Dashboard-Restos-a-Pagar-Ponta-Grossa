"""Painel mixin: Variation between two cut-offs and the history of a commitment (05.5)."""
from .. import fontes
from .comum import (CAMPOS_DO_HISTORICO, CLASSES_DA_CHAVE, _data_br, diferenca, ErroDoPainel, fechamento, instante,
                    LIMITE_LISTA, METRICAS_DA_VARIACAO, ROTULO_POSTERIOR_A_COLETA, SITUACOES_DO_PONTO, TEM_VALOR,
                    TOP_DA_VARIACAO)


class Variacao:
    """Variation between two cut-offs and the history of a commitment (05.5)."""

    def _valores_por_chave(self, ctx, coletas, expr):
        """{(entidade, anoempenho, empenho): [occurrences]} with the value of `expr` (a fixed expression of this module)
        and the origin of each record (snapshot, HTTP response, position in content[] and SHA-256 of the raw object)."""
        filtro, p = self._de_coletas(coletas)
        mapa = {}
        for e, ano, emp, v, uid, ordem, sha, indice, rid in self.con.execute(
                f"SELECT r.entidade, r.anoempenho, r.empenho, {expr}, c.snapshot_uid, rb.ordem, rb.sha256, r.indice, "
                f"r.resposta_id FROM rp_registro r JOIN rp_derivado d ON d.derivacao_id=? AND d.resposta_id=r.resposta_id "
                f"AND d.indice=r.indice JOIN coleta c ON c.id=r.coleta_id JOIN resposta_bruta rb ON rb.id=r.resposta_id "
                f"WHERE r.normalizacao_id=? AND {filtro}", (ctx["derivacao"]["id"], ctx["normalizacao"]["id"], *p)):
            mapa.setdefault((e, ano, emp), []).append(
                {"valor_c": v, "proveniencia": {"snapshot_uid": uid, "resposta_ordem": ordem, "indice_no_content": indice,
                                                "objeto_bruto_sha256": sha, "resposta_id": rid}})
        return mapa

    def variacao(self, exercicio, anterior, posterior, entidade=None, metrica="s1", em=None, limite=50, deslocamento=0,
                 top=TOP_DA_VARIACAO):
        """Variation of a metric between two cut-offs of the SAME fiscal year, explained by each commitment's
        contributions (sub-stage 05.5; contract M-09 to M-11).
        * Pair chosen explicitly (earlier < later), adjacent or not. It is unavailable, with the reason, if one side
          has no value in the scope; in the Municipality, if the set of summed entities differs (R6); if the same key
          (entidade, anoempenho, empenho) appears more than once on one side (list of the keys; nothing is picked).
        * Total variation = homologated indicator of the later - of the earlier. Contribution per key, always later -
          earlier: in both cut-offs = later - earlier; only in the later = later; only in the earlier = 0 - earlier.
        * Closing to the cent (section 4.2) of the list, the summary groups and the classes; if it fails, the pair is
          blocked (05.5 stopping criterion), never shown with a remainder.
        * Full list (keys with contribution != 0) in descending contribution order, tie-break by key; paginated, with
          the page subtotal and the running total up to it."""
        if metrica not in METRICAS_DA_VARIACAO:
            raise ErroDoPainel(f"metrica precisa ser uma de {sorted(METRICAS_DA_VARIACAO)}")
        if isinstance(top, bool) or not isinstance(top, int) or top < 1:
            raise ErroDoPainel("top precisa ser um inteiro positivo")
        if not (isinstance(anterior, str) and isinstance(posterior, str) and anterior < posterior):
            raise ErroDoPainel("o corte anterior precisa ser anterior ao corte posterior")
        limite, deslocamento = max(1, min(int(limite), LIMITE_LISTA)), max(0, int(deslocamento))
        m = METRICAS_DA_VARIACAO[metrica]
        ctx, em = self.contexto(), instante(em)
        vig, cat = self._vigentes(ctx, em), self._catalogo(ctx, em)
        regs = self._regras_publicaveis(m["regras"])
        saida = {"consulta": {"exercicio": exercicio, "anterior": anterior, "posterior": posterior, "entidade": entidade,
                              "metrica": metrica, "como_estava_em": em},
                 "escopo": f"entidade {entidade}" if entidade is not None else "Município (entidades do catálogo oficial do exercício)",
                 "metrica": {"id": metrica, "rotulo": m["rotulo"], "formula": m["formula"],
                             "natureza_do_operando": m["natureza_do_operando"], "regras": regs},
                 "fonte": fontes.ELOTECH["rotulo"], "natureza": "diferenca", "sinal": "posterior − anterior",
                 "disponivel": False, "motivo_indisponivel": None, "chaves_repetidas": [], "anterior": None,
                 "posterior": None, "variacao_c": None, "resumo": None, "classes": None, "fechamentos": None,
                 "lista": None, "chaves": None, "pares_espelhados": None, "proveniencia": None, "nota": None}
        universo = self._universo_do_exercicio(ctx, vig, exercicio, em)
        faltam = [df for df in (anterior, posterior) if df not in universo]
        if faltam:
            saida["motivo_indisponivel"] = (f"corte sem processamento no exercício {exercicio}: "
                                            + ", ".join(_data_br(df) for df in faltam))
            return saida
        lados = {}
        for nome, df in (("anterior", anterior), ("posterior", posterior)):
            corte = self._corte(ctx, exercicio, df, entidade, em, vig, cat)
            codigo = self._situacao_do_ponto(corte, entidade)
            lados[nome] = {"data_final": df, "situacao": {"codigo": codigo, "texto": SITUACOES_DO_PONTO[codigo]},
                           "tem_valor": codigo in TEM_VALOR, "motivo_indisponivel": None if codigo in TEM_VALOR else corte["motivo"],
                           "retrato": corte["retrato"],
                           "snapshots": self._uids(corte["somar"]) if codigo in TEM_VALOR else [],
                           "entidades_no_total": sorted(e["entidade"] for e in corte["entidades"] if e["entra_no_total"]),
                           "total_c": None, "coletas": corte["somar"]}
            if lados[nome]["tem_valor"]:   # cut-off total: the homologated indicator (shown even with the pair unavailable)
                lados[nome]["total_c"] = self._somas(ctx, corte["somar"])[m["indicador"]]
        publico_ = {nome: {k: v for k, v in l.items() if k != "coletas"} for nome, l in lados.items()}
        saida.update(anterior=publico_["anterior"], posterior=publico_["posterior"])
        sem_valor = [l for l in lados.values() if not l["tem_valor"]]
        if sem_valor:
            saida["motivo_indisponivel"] = "; ".join(
                f"o corte {_data_br(l['data_final'])} não tem valor para o escopo ({l['situacao']['texto']}"
                + (f": {l['motivo_indisponivel']}" if l["motivo_indisponivel"] else "") + ")" for l in sem_valor)
            return saida
        a, b = lados["anterior"]["entidades_no_total"], lados["posterior"]["entidades_no_total"]
        if entidade is None and a != b:
            saida["motivo_indisponivel"] = (f"conjunto de entidades diferente nos dois cortes (R6): só no anterior "
                                            f"{sorted(set(a) - set(b))}, só no posterior {sorted(set(b) - set(a))}")
            return saida
        mapas = {nome: self._valores_por_chave(ctx, l["coletas"], m["sql"]) for nome, l in lados.items()}
        repetidas = sorted({k for mp in mapas.values() for k, occ in mp.items() if len(occ) > 1})
        if repetidas:
            saida["chaves_repetidas"] = [{"chave": dict(zip(("entidade", "anoempenho", "empenho"), k)),
                                          "anterior": len(mapas["anterior"].get(k, ())),
                                          "posterior": len(mapas["posterior"].get(k, ()))} for k in repetidas]
            saida["motivo_indisponivel"] = (f"a mesma chave (entidade, ano, empenho) aparece mais de uma vez num dos "
                                            f"snapshots ({len(repetidas)} chave(s)); nenhuma ocorrência é escolhida")
            return saida
        variacao = diferenca(lados["anterior"]["total_c"], lados["posterior"]["total_c"])
        itens = []
        for k in set(mapas["anterior"]) | set(mapas["posterior"]):
            ant, post = mapas["anterior"].get(k, [None])[0], mapas["posterior"].get(k, [None])[0]
            if ant and post:
                classe, contrib = "nos_dois", diferenca(ant["valor_c"], post["valor_c"])
            elif post:
                classe, contrib = "so_posterior", post["valor_c"]
            else:
                classe, contrib = "so_anterior", 0 - ant["valor_c"]
            itens.append({"chave": {"entidade": k[0], "anoempenho": k[1], "empenho": k[2]}, "classe": classe,
                          "classe_texto": CLASSES_DA_CHAVE[classe], "anterior": ant, "posterior": post,
                          "contribuicao_c": contrib, "natureza": "diferenca", "_k": k})
        itens.sort(key=lambda x: (-x["contribuicao_c"], x["_k"]))
        aumentos = [x for x in itens if x["contribuicao_c"] > 0]
        reducoes = sorted((x for x in itens if x["contribuicao_c"] < 0), key=lambda x: (x["contribuicao_c"], x["_k"]))
        zeros = [x for x in itens if x["contribuicao_c"] == 0]
        lista = aumentos + [x for x in itens if x["contribuicao_c"] < 0]      # contract order: descending
        for i, x in enumerate(lista, 1):
            x["posicao"] = i
        for x in itens:
            del x["_k"]

        def soma(xs):
            return sum(x["contribuicao_c"] for x in xs)

        grupos = [{"id": "top_aumentos", "rotulo": f"maiores aumentos (até {top})", "quantidade": len(aumentos[:top]),
                   "soma_c": soma(aumentos[:top]), "itens": aumentos[:top]},
                  {"id": "outros_aumentos", "rotulo": "outros aumentos", "quantidade": len(aumentos[top:]),
                   "soma_c": soma(aumentos[top:])},
                  {"id": "top_reducoes", "rotulo": f"maiores reduções (até {top})", "quantidade": len(reducoes[:top]),
                   "soma_c": soma(reducoes[:top]), "itens": reducoes[:top]},
                  {"id": "outras_reducoes", "rotulo": "outras reduções", "quantidade": len(reducoes[top:]),
                   "soma_c": soma(reducoes[top:])},
                  {"id": "sem_variacao", "rotulo": "sem variação", "quantidade": len(zeros), "soma_c": 0}]
        classes = [{"id": c, "rotulo": CLASSES_DA_CHAVE[c], "quantidade": sum(1 for x in itens if x["classe"] == c),
                    "soma_c": soma(x for x in itens if x["classe"] == c)} for c in CLASSES_DA_CHAVE]
        fech = {"grupos": fechamento(variacao, [g["soma_c"] for g in grupos]),
                "classes": fechamento(variacao, [c["soma_c"] for c in classes]),
                "lista": fechamento(variacao, [x["contribuicao_c"] for x in lista])}
        saida["fechamentos"] = fech
        if not all(f["fecha"] for f in fech.values()):
            saida["motivo_indisponivel"] = ("as contribuições não fecham com a variação total: o par não é exibido até a "
                                            "causa ser investigada (critério de parada da 05.5)")
            return saida
        pagina = lista[deslocamento:deslocamento + limite]
        saida.update(
            disponivel=True, variacao_c=variacao,
            resumo={"top": top, "grupos": grupos}, classes=classes,
            lista={"itens": pagina, "total_de_chaves": len(lista), "limite": limite, "deslocamento": deslocamento,
                   "subtotal_c": soma(pagina), "acumulado_c": soma(lista[:deslocamento + limite]),
                   "ultima_pagina": deslocamento + limite >= len(lista)},
            chaves={"total": len(itens), "com_variacao": len(lista), "sem_variacao": len(zeros)},
            pares_espelhados={nome: self._pares_no_corte(ctx, exercicio, l["data_final"], entidade)
                              for nome, l in lados.items()},
            proveniencia={nome: self._proveniencia(ctx, l["coletas"], f"{m['formula']} por registro do corte "
                                                                     f"{_data_br(l['data_final'])}")
                          for nome, l in lados.items()},
            nota=("Variação = valor do corte posterior − valor do corte anterior, pela mesma soma do indicador homologado. "
                  "Cada corte é o estado atual da base para aquele corte, na data da coleta: se as duas coletas "
                  "refletem bases diferentes, a variação mistura o movimento do intervalo com mudança retroativa."))
        return saida

    def historico_empenho(self, entidade, anoempenho, empenho, exercicio, em=None):
        """One commitment at each cut-off of the fiscal year (sub-stage 05.5; contract M-12): the record's values at each
        cut-off of the universe (section 2.4), without a new formula. A cut-off without a value for the entity appears
        with its situation; a cut-off with a value where the key does not appear, as 'empenho ausente deste corte'; a
        repeated key shows all occurrences, without choosing."""
        ctx, em = self.contexto(), instante(em)
        vig, cat = self._vigentes(ctx, em), self._catalogo(ctx, em)
        governo = self._naturezas_derivados()
        cortes = []
        for df in self._universo_do_exercicio(ctx, vig, exercicio, em):
            corte = self._corte(ctx, exercicio, df, entidade, em, vig, cat)
            codigo = self._situacao_do_ponto(corte, entidade)
            ponto = {"data_final": df, "situacao": {"codigo": codigo, "texto": SITUACOES_DO_PONTO[codigo]},
                     "tem_valor": codigo in TEM_VALOR, "motivo_indisponivel": None if codigo in TEM_VALOR else corte["motivo"],
                     "retrato": corte["retrato"], "rotulos": [], "presente": False, "motivo_ausencia": None,
                     "ocorrencias": []}
            if ponto["tem_valor"]:
                if corte["retrato"] and corte["retrato"]["corte_posterior_a_coleta"]:
                    ponto["rotulos"].append(ROTULO_POSTERIOR_A_COLETA)
                for reg, prov, _, _ in self._registros(ctx, corte["somar"], " AND r.anoempenho=? AND r.empenho=?",
                                                        (anoempenho, empenho), ordem="empenho"):
                    ponto["ocorrencias"].append({"valores": {c: reg[c] for c in CAMPOS_DO_HISTORICO},
                                                 "categoria": reg["categoria"], "proveniencia": prov})
                ponto["presente"] = bool(ponto["ocorrencias"])
                ponto["motivo_ausencia"] = None if ponto["presente"] else "empenho ausente deste corte"
            cortes.append(ponto)
        campos = [{"coluna": c, "rotulo": fontes.CAMPOS[c][1] if c in fontes.CAMPOS else fontes.DERIVADOS[c][0],
                   "campo_api": fontes.CAMPOS[c][0] if c in fontes.CAMPOS else None,
                   "natureza": "da_fonte" if c in fontes.CAMPOS else governo[c]} for c in CAMPOS_DO_HISTORICO]
        repetida = any(len(x["ocorrencias"]) > 1 for x in cortes)
        return {"chave": {"entidade": entidade, "anoempenho": anoempenho, "empenho": empenho}, "exercicio": exercicio,
                "como_estava_em": em, "fonte": fontes.ELOTECH["rotulo"], "campos": campos, "cortes": cortes,
                "derivacao": {"id": ctx["derivacao"]["id"], "hash_resultado": ctx["derivacao"]["hash_resultado"]},
                "normalizacao_id": ctx["normalizacao"]["id"],
                "nota": ("Mais de uma ocorrência num corte = a mesma chave apareceu mais de uma vez no snapshot; nenhuma é "
                         "descartada.") if repetida else None}
