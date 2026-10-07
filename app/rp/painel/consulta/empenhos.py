"""Painel mixin: Commitment lists, commitment detail, mirrored pairs and creditors."""
import re

from ... import governanca, regras
from .. import fontes, publico
from .comum import (CADEIA, CAMPOS_REGISTRO, CATEGORIAS, DERIVADOS, DIMENSOES_ORCAMENTARIAS, DINHEIRO, ErroDoPainel,
                    FAIXAS, instante, LIMITE_LISTA, REGRAS_DO_INDICADOR)


class Empenhos:
    """Commitment lists, commitment detail, mirrored pairs and creditors."""

    @staticmethod
    def _filtros_empenho(categoria=None, fonte_recurso=None, programatica=None, tipo_credor=None, cnpj=None,
                         anoempenho=None, empenho=None, faixa=None, orgao=None, funcao=None, programa=None,
                         elemento=None, sem_classificacao=None):
        """SQL (always parameterized) of the commitment list filters. A filter only chooses records; it never changes a
        value.
        cnpj: only a complete CNPJ (14 digits) of a legal entity; a CPF is never accepted as a filter.
        anoempenho / empenho: search for a commitment by year and/or number (exact match).
        faixa (05.4): a/b choose by the processed band, f/g by the not processed band (FAIXA v1).
        orgao, funcao, programa, elemento (05.4): exact code as the API returns it (text of digits).
        sem_classificacao (05.4): records without the field of the indicated budget dimension (null value)."""
        sql, params, eco = "", [], {}
        for nome, valor in (("anoempenho", anoempenho), ("empenho", empenho)):
            if valor is not None:
                if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
                    raise ErroDoPainel(f"{nome} precisa ser um inteiro nao negativo")
                sql, eco[nome] = sql + f" AND r.{nome} = ?", valor
                params.append(valor)
        if categoria is not None:
            if categoria not in CATEGORIAS:
                raise ErroDoPainel(f"categoria precisa ser uma de {CATEGORIAS}")
            sql, eco["categoria"] = sql + " AND d.categoria = ?", categoria
            params.append(categoria)
        if fonte_recurso is not None:
            if isinstance(fonte_recurso, bool) or not isinstance(fonte_recurso, int):
                raise ErroDoPainel("fonte de recurso precisa ser o codigo inteiro")
            sql, eco["fonte_recurso"] = sql + " AND r.fonte_recurso = ?", fonte_recurso
            params.append(fonte_recurso)
        if programatica:
            if not re.fullmatch(r"\d{1,28}", str(programatica)):
                raise ErroDoPainel("programacao orcamentaria: informe de 1 a 28 digitos (inicio do codigo)")
            sql, eco["programatica_comeca_com"] = sql + " AND substr(r.programatica, 1, ?) = ?", programatica
            params += [len(programatica), programatica]
        if tipo_credor is not None:
            if tipo_credor not in publico.TIPOS_CREDOR:
                raise ErroDoPainel(f"tipo de credor precisa ser um de {publico.TIPOS_CREDOR}")
            sql, eco["tipo_credor"] = sql + " AND tipo_credor(r.cnpj) = ?", tipo_credor
            params.append(tipo_credor)
        if cnpj:
            d = re.sub(r"\D", "", str(cnpj))
            if len(d) != 14:
                raise ErroDoPainel("filtro de credor aceita so CNPJ completo (14 digitos) de pessoa juridica")
            formatado = f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
            sql, eco["cnpj"] = sql + " AND r.cnpj = ?", formatado
            params.append(formatado)
        if faixa is not None:
            if faixa not in FAIXAS:
                raise ErroDoPainel(f"faixa precisa ser uma de {FAIXAS}")
            coluna = "d.faixa_processado" if faixa in ("a", "b") else "d.faixa_nao_processado"
            sql, eco["faixa"] = sql + f" AND {coluna} = ?", faixa
            params.append(faixa)
        for nome, valor in (("orgao", orgao), ("funcao", funcao), ("programa", programa), ("elemento", elemento)):
            if valor is not None:
                if not re.fullmatch(r"\d{1,20}", str(valor)):
                    raise ErroDoPainel(f"{nome}: informe o código como a API devolve (de 1 a 20 dígitos)")
                sql, eco[nome] = sql + f" AND r.{nome} = ?", str(valor)
                params.append(str(valor))
        if sem_classificacao is not None:
            if sem_classificacao not in DIMENSOES_ORCAMENTARIAS:
                raise ErroDoPainel(f"sem_classificacao precisa ser uma de {DIMENSOES_ORCAMENTARIAS}")
            sql, eco["sem_classificacao"] = sql + f" AND r.{sem_classificacao} IS NULL", sem_classificacao
        return sql, tuple(params), eco

    def empenhos(self, exercicio, data_final, entidade=None, em=None, limite=100, deslocamento=0, ordem="saldo",
                 categoria=None, fonte_recurso=None, programatica=None, tipo_credor=None, cnpj=None, anoempenho=None,
                 empenho=None, faixa=None, orgao=None, funcao=None, programa=None, elemento=None,
                 sem_classificacao=None):
        """Paginated list of the cut-off's records, with optional filters, and the totals of the filtered set.
        At the public level, with no creditor identification at all (only the type).
        An empty set: `sem_resultado` and None totals (never R$ 0,00), with the reason message."""
        limite, deslocamento = max(1, min(int(limite), LIMITE_LISTA)), max(0, int(deslocamento))
        filtro, params, eco = self._filtros_empenho(categoria, fonte_recurso, programatica, tipo_credor, cnpj,
                                                    anoempenho, empenho, faixa, orgao, funcao, programa, elemento,
                                                    sem_classificacao)
        ctx, em = self.contexto(), instante(em)
        corte = self._corte(ctx, exercicio, data_final, entidade, em)
        if not corte["disponivel"]:
            return {"disponivel": False, "motivo_indisponivel": corte["motivo"], "filtros": eco, "registros": []}
        regs = [{**reg, "proveniencia": prov} for reg, prov, _, _ in
                self._registros(ctx, corte["somar"], filtro, params, limite=limite, deslocamento=deslocamento, ordem=ordem)]
        totais = self._somas(ctx, corte["somar"], filtro, params) if filtro else self._somas(ctx, corte["somar"])
        regs_ind = self._regras_publicaveis(REGRAS_DO_INDICADOR)
        vazio = totais["registros"] == 0
        if not vazio:
            mensagem = None
        elif eco:
            mensagem = "nenhum registro do corte atende aos filtros aplicados"
        else:
            mensagem = "nenhum registro de RP neste corte: a API devolveu zero registros para as entidades do escopo"
        return {"disponivel": True, "retrato": corte["retrato"], "fonte": fontes.ELOTECH["rotulo"], "nivel": self.nivel,
                "filtros": eco, "entidades": corte["entidades"],
                "naturezas": {**{c: "da_fonte" for c in CAMPOS_REGISTRO + DINHEIRO}, **self._naturezas_derivados(),
                              "cancelamentos_c": "derivado"},
                "total": totais["registros"], "sem_resultado": vazio, "mensagem_sem_resultado": mensagem,
                "totais": {"natureza": "derivado", "regras": [r for r in regs_ind if r["codigo"] in ("S1", "CAT")],
                           "valores": None if vazio else {k: v for k, v in totais.items() if k != "registros"}},
                "limite": limite, "deslocamento": deslocamento, "registros": regs,
                "proveniencia": self._proveniencia(ctx, corte["somar"], "registros dos snapshots do corte; filtro so "
                                                                        "escolhe linhas")}

    def detalhe_empenho(self, entidade, anoempenho, empenho, exercicio, data_final=None, em=None):
        """Detail of ONE commitment at a cut-off (default: the entity's last processed cut-off of the fiscal year): source
        fields with technical and friendly names, derived values with the rule, mirrored pair, movements and provenance."""
        ctx, em = self.contexto(), instante(em)
        if data_final is None:
            cortes = sorted(df for (e, ex, d0, df) in self._vigentes(ctx, em)
                            if e == entidade and ex == exercicio and d0 == f"{exercicio}-01-01")
            if not cortes:
                return {"encontrado": False, "motivo_indisponivel": "nenhum corte processado desta entidade no exercício"}
            data_final = cortes[-1]
        corte = self._corte(ctx, exercicio, data_final, entidade, em)
        if not corte["disponivel"]:
            return {"encontrado": False, "motivo_indisponivel": corte["motivo"]}
        ocorrencias = list(self._registros(ctx, corte["somar"], " AND r.anoempenho=? AND r.empenho=?",
                                           (anoempenho, empenho), ordem="empenho"))
        chave = {"entidade": entidade, "anoempenho": anoempenho, "empenho": empenho}
        if not ocorrencias:
            return {"encontrado": False, "chave": chave, "motivo_indisponivel": "empenho ausente deste corte",
                    "retrato": corte["retrato"]}
        governo = governanca.situacao_atual(self.con)
        saida = []
        for reg, prov, nome, cnpj in ocorrencias:
            campos = {c: {"campo_api": fontes.CAMPOS[c][0], "rotulo": fontes.CAMPOS[c][1], "valor": reg[c],
                          "natureza": "da_fonte", "significado": fontes.CAMPOS[c][2], "status_semantica": fontes.CAMPOS[c][3]}
                      for c in CAMPOS_REGISTRO + DINHEIRO}
            derivados = {}
            for c in DERIVADOS:
                rot, formula, (cod, ver) = fontes.DERIVADOS[c]
                g = governo.get((cod, ver), {})
                derivados[c] = {"rotulo": rot, "valor": reg[c], "formula": formula, "regra": f"{cod} v{ver}",
                                "situacao_da_regra": g.get("situacao"), "status_evidencia": g.get("status_evidencia"),
                                "natureza": "derivado" if g.get("compoe_indicador_publicado") else "analitico"}
            credor = {"tipo": reg["tipo_credor"], "nome_publico": publico.nome_publico(nome, cnpj)}
            if self.nivel == "interno":
                credor.update({c: reg[c] for c in publico.CAMPOS_RESTRITOS})
            cid = self.con.execute("SELECT id FROM coleta WHERE snapshot_uid=?", (prov["snapshot_uid"],)).fetchone()[0]
            saida.append({"campos": campos, "derivados": derivados, "credor": credor,
                          "par_espelhado": self._par(ctx, prov["resposta_id"], prov["indice_no_content"]),
                          "proveniencia": {**prov, "snapshot": self._snapshot(cid), "cadeia": CADEIA}})
        return {"encontrado": True, "retrato": corte["retrato"], "fonte": fontes.ELOTECH["rotulo"], "nivel": self.nivel,
                "chave": chave, "exercicio": exercicio, "data_final": data_final,
                "ocorrencias": saida, "movimentacao": self._movimentacao(ctx, entidade, anoempenho, empenho, em),
                "nota": ("Mais de uma ocorrência = a mesma chave apareceu mais de uma vez no snapshot; nenhuma é "
                         "descartada.") if len(saida) > 1 else None}

    def _par(self, ctx, resposta_id, indice):
        row = self.con.execute(
            "SELECT entidade_a, anoempenho_a, empenho_a, entidade_b, anoempenho_b, empenho_b, relacao_inscricao, "
            "lado_com_execucao, inscrito_a_c, inscrito_b_c, mesma_inscricao, "
            "CASE WHEN resposta_a_id=? AND indice_a=? THEN 'A' ELSE 'B' END "
            "FROM espelhamento_par WHERE derivacao_id=? AND ((resposta_a_id=? AND indice_a=?) OR "
            "(resposta_b_id=? AND indice_b=?))",
            (resposta_id, indice, ctx["derivacao"]["id"], resposta_id, indice, resposta_id, indice)).fetchone()
        if not row:
            return None
        par = regras.parametros(self.con, "PAR-24", 1)
        return {"este_registro_e_o_lado": row[11],
                "a": {"entidade": row[0], "anoempenho": row[1], "empenho": row[2], "inscrito_c": row[8]},
                "b": {"entidade": row[3], "anoempenho": row[4], "empenho": row[5], "inscrito_c": row[9]},
                "mesma_inscricao": bool(row[10]), "relacao_inscricao": row[6], "lado_com_execucao": row[7],
                "regra": "PAR-24 v1", "parametros_da_regra": par,
                "nota": ("Os dois registros continuam separados no bruto, na normalização e nos indicadores (a API "
                         "conta os dois); a natureza das cópias 24xxxxx não está determinada.")}

    def _movimentacao(self, ctx, entidade, anoempenho, empenho, em):
        filtro, p = (" AND coletada_em <= ?", (em,)) if em else ("", ())
        c = self.con.execute("SELECT id FROM coleta WHERE tipo='movimentacao' AND status='completa' AND entidade=? AND "
                             "anoempenho=? AND empenho=? AND id <= ?" + filtro +
                             " ORDER BY coletada_em DESC, snapshot_uid DESC LIMIT 1",
                             (entidade, anoempenho, empenho, ctx["limite_coleta"], *p)).fetchone()
        if not c:
            return {"coletada": False, "nota": "movimentação deste empenho não coletada"}
        lanc = [{"data": d, "tipo_lancamento": t, "descricao": desc, "valor_c": v, "natureza": "da_fonte",
                 "efeito": ef, "valor_com_sinal_c": vs,
                 "liquidacao_referida": f"{ln}/{le}" if ln is not None and le is not None else None,
                 "interpretacao": "derivado (MOV-REF v1: nos lançamentos 40/41 a liquidação está nos rótulos de pagamento)"}
                for d, t, desc, v, ef, vs, le, ln in self.con.execute(
                    "SELECT m.data, m.tipo_lancamento, m.descricao_tipo, m.valor_c, i.efeito, i.valor_com_sinal_c, "
                    "i.liquidacao_exercicio, i.liquidacao_numero FROM movimentacao_lancamento m LEFT JOIN "
                    "movimentacao_interpretada i ON i.derivacao_id=? AND i.resposta_id=m.resposta_id AND i.indice=m.indice "
                    "WHERE m.normalizacao_id=? AND m.coleta_id=? ORDER BY m.data, m.resposta_id, m.indice",
                    (ctx["derivacao"]["id"], ctx["normalizacao"]["id"], c[0]))]
        return {"coletada": True, "snapshot": self._snapshot(c[0]), "lancamentos": lanc}

    def pares(self, exercicio, data_final, em=None):
        """Mirrored pairs (rule PAR-24) of the cut-off: both sides stay separate records; nothing is removed nor summed
        twice by this query. The nature of the copies is still not determined."""
        ctx, em = self.contexto(), instante(em)
        did, _ = self._derivacao_da_vigencia(ctx, em)
        if did is None:
            return {"pares": [], "nota": f"não há derivação 'como estava em' {em}"}
        par = regras.parametros(self.con, "PAR-24", 1)
        governo = governanca.situacao_atual(self.con).get(("PAR-24", 1), {})
        pares = [{"a": {"entidade": ea, "anoempenho": aa, "empenho": pa, "inscrito_c": ia},
                  "b": {"entidade": eb, "anoempenho": ab, "empenho": pb, "inscrito_c": ib},
                  "mesma_inscricao": bool(mesma), "relacao_inscricao": rel, "lado_com_execucao": lado,
                  "snapshots": self._uids([ca, cb])}
                 for ea, aa, pa, ia, eb, ab, pb, ib, mesma, rel, lado, ca, cb in self.con.execute(
                     "SELECT entidade_a, anoempenho_a, empenho_a, inscrito_a_c, entidade_b, anoempenho_b, empenho_b, "
                     "inscrito_b_c, mesma_inscricao, relacao_inscricao, lado_com_execucao, coleta_a_id, coleta_b_id "
                     "FROM espelhamento_par WHERE derivacao_id=? AND exercicio=? AND data_inicial=? AND data_final=? "
                     "ORDER BY anoempenho_a, empenho_a", (did, exercicio, f"{exercicio}-01-01", data_final))]
        resumo = {"pares": len(pares), "relacao": {}, "lado_com_execucao": {}, "anoempenho": {}}
        for p in pares:
            for k, v in (("relacao", p["relacao_inscricao"]), ("lado_com_execucao", p["lado_com_execucao"]),
                         ("anoempenho", p["a"]["anoempenho"])):
                resumo[k][v] = resumo[k].get(v, 0) + 1
        coletas = sorted({c for (c,) in self.con.execute(
            "SELECT coleta_a_id FROM espelhamento_par WHERE derivacao_id=? AND exercicio=? AND data_final=? UNION "
            "SELECT coleta_b_id FROM espelhamento_par WHERE derivacao_id=? AND exercicio=? AND data_final=?",
            (did, exercicio, data_final, did, exercicio, data_final))})
        return {"exercicio": exercicio, "data_final": data_final, "como_estava_em": em, "regra": "PAR-24 v1",
                "situacao_da_regra": governo.get("situacao"), "parametros_da_regra": par, "natureza": "derivado",
                "resumo": resumo, "pares": pares,
                "proveniencia": {**self._proveniencia(ctx, coletas, "tabela espelhamento_par da derivacao"),
                                 "derivacao_usada": did},
                "nota": ("Os dois lados de cada par continuam separados no bruto, na normalização e nos indicadores "
                         "(a API devolve os dois). A natureza das cópias (duplicidade ou transferência) não está "
                         "determinada; a consolidação só existe como visão analítica experimental (CONS-PAR).")}

    def fornecedores(self, exercicio, data_final, entidade=None, em=None, limite=100):
        """Totals per creditor. At the public level, only per creditor type (without identification)."""
        ctx, em = self.contexto(), instante(em)
        corte = self._corte(ctx, exercicio, data_final, entidade, em)
        if not corte["disponivel"]:
            return {"disponivel": False, "motivo_indisponivel": corte["motivo"], "linhas": []}
        grupos = {}
        for reg, _, nome, cnpj in self._registros(ctx, corte["somar"]):
            chave = (reg.get("fornecedor"), cnpj, nome) if self.nivel == "interno" else (reg["tipo_credor"],)
            g = grupos.setdefault(chave, {"registros": 0, "saldo_total_c": 0, "pagamentos_c": 0})
            g["registros"] += 1
            g["saldo_total_c"] += reg["s1_saldo_total_c"]
            g["pagamentos_c"] += reg["pago_proc_c"] + reg["pago_aproc_c"]
        rotulo = ("fornecedor", "cnpj", "nome") if self.nivel == "interno" else ("tipo_credor",)
        linhas = sorted(({**dict(zip(rotulo, k)), **v, "natureza": "derivado"} for k, v in grupos.items()),
                        key=lambda x: (-x["saldo_total_c"], str(x.get(rotulo[0]))))
        return {"disponivel": True, "nivel": self.nivel, "retrato": corte["retrato"], "fonte": fontes.ELOTECH["rotulo"],
                "linhas": linhas[:max(1, min(int(limite), LIMITE_LISTA))],
                "proveniencia": self._proveniencia(ctx, corte["somar"], "somas por credor")}
