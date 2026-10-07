"""Painel mixin: Data quality: anomalies, checks and the situation of the differences (05.6)."""
import json

from ... import governanca, regras
from .. import fontes
from .comum import (CONTINUIDADE, ErroDoPainel, _in, INTERPRETACOES_DE_VERIFICACAO, LIMITE_LISTA, NAO_CATALOGADA,
                    SITUACOES_DAS_DIFERENCAS)


class Qualidade:
    """Data quality: anomalies, checks and the situation of the differences (05.6)."""

    # ------------------------------------------------------------------ data quality (05.6)
    def qualidade(self):
        """Anomalies, checks and the situation of the differences with the RREO (sub-stage 05.6; contract section 6), each
        according to its nature and read from the current derivation, with no new rule.
        * Anomalies: one row per occurrence, in EVERY processed snapshot (including earlier snapshots and collections
          by search type); per type, the derivation's count and how many are in current snapshots.
        * Checks: set-level; the situation is interpreted from the description (R5); they never become a list of
          commitments.
        * Differences with the RREO: the five situations apart, counted per column x document x aggregation rule (the
          same rows as the reconciliation); 'sem diferenca' is never counted as explained."""
        ctx = self.contexto()
        did = ctx["derivacao"]["id"]
        governo = governanca.situacao_atual(self.con)
        vig = sorted(set(self._vigentes(ctx, None).values()))
        tipos = {c: {"descricao": d, "status_evidencia": s, "fonte": f} for c, d, s, f in self.con.execute(
            "SELECT codigo, descricao, status_evidencia, fonte FROM anomalia_tipo ORDER BY codigo")}
        por_tipo = []
        for tipo, cod, ver, n, coletas, com_chave, vigentes, anos in self.con.execute(
                "SELECT a.tipo, g.codigo, g.versao, COUNT(*), COUNT(DISTINCT a.coleta_id), SUM(a.entidade IS NOT NULL AND "
                f"a.anoempenho IS NOT NULL AND a.empenho IS NOT NULL), SUM(a.coleta_id IN ({_in(len(vig))})), "
                "GROUP_CONCAT(DISTINCT c.exercicio) FROM anomalia a JOIN regra g ON g.id = a.regra_id LEFT JOIN coleta c "
                "ON c.id = a.coleta_id WHERE a.derivacao_id=? GROUP BY a.tipo, g.codigo, g.versao "
                "ORDER BY a.tipo, g.codigo, g.versao", (*vig, did)):
            t = tipos.get(tipo, {"descricao": None, "status_evidencia": None, "fonte": None})
            por_tipo.append({"tipo": tipo, **t, "regra": f"{cod} v{ver}",
                             "situacao_da_regra": governo.get((cod, ver), {}).get("situacao"), "ocorrencias": n,
                             "em_snapshots_vigentes": vigentes or 0, "com_chave_de_empenho": com_chave or 0,
                             "snapshots": coletas, "exercicios": sorted(int(x) for x in (anos or "").split(",") if x)})
        presentes = {x["tipo"] for x in por_tipo}
        sem_ocorrencia = [{"tipo": c, **t} for c, t in tipos.items() if c not in presentes]
        return {"derivacao": ctx["derivacao"], "normalizacao": ctx["normalizacao"], "fonte": fontes.ELOTECH["rotulo"],
                "anomalias": {"por_tipo": por_tipo, "tipos_sem_ocorrencia": sem_ocorrencia,
                              "total": sum(x["ocorrencias"] for x in por_tipo)},
                "verificacoes": self._verificacoes(did, governo, por_tipo),
                "diferencas_rreo": self._situacao_das_diferencas(did),
                "nota": ("Anomalias e verificações são gravadas pela derivação (regras versionadas) e aqui só são lidas. "
                         "Anomalia não é erro: é um fato registrado, descrito pelo tipo. Verificação é de conjunto: o "
                         "significado de 'falhas' depende da verificação.")}

    def _verificacoes(self, did, governo, por_tipo):
        contagem = {x["tipo"]: x["ocorrencias"] for x in por_tipo}
        grupos = {}
        for cod, ver, descricao, escopo_json, verificados, falhas in self.con.execute(
                "SELECT g.codigo, g.versao, v.descricao, v.escopo_json, v.verificados, v.falhas FROM verificacao v JOIN "
                "regra g ON g.id = v.regra_id WHERE v.derivacao_id=? ORDER BY v.descricao, g.codigo, g.versao, v.rowid",
                (did,)):
            g = grupos.setdefault((descricao, cod, ver), {"descricao": descricao, "regra": f"{cod} v{ver}",
                                                          "situacao_da_regra": governo.get((cod, ver), {}).get("situacao"),
                                                          "itens": []})
            escopo = json.loads(escopo_json)
            snaps = escopo.get("snapshots") or ([escopo["rreo_snapshot"]] if "rreo_snapshot" in escopo else [])
            g["itens"].append({"escopo": escopo, "verificados": verificados, "falhas": falhas, "snapshots": snaps})
        saida = []
        for (descricao, cod, ver), g in grupos.items():
            cat = INTERPRETACOES_DE_VERIFICACAO.get(descricao)
            catalogada = cat is not None and cat["regra"] == (cod, ver)
            v, f = sum(i["verificados"] for i in g["itens"]), sum(i["falhas"] for i in g["itens"])
            natureza = cat["natureza"] if catalogada else None
            for i in g["itens"]:
                i["situacao"] = self._situacao_da_verificacao(natureza, i["verificados"], i["falhas"])
                i["anomalias_do_escopo"] = ([{"tipo": t, **self._escopo_das_anomalias(descricao, i["escopo"])}
                                             for t in cat["anomalias"]] if catalogada and i["falhas"] else [])
            g.update(verificados=v, falhas=f, catalogada=catalogada, natureza=natureza,
                     significado_de_verificados=cat["verificados"] if catalogada else None,
                     significado_de_falhas=cat["falhas"] if catalogada else NAO_CATALOGADA,
                     situacao=self._situacao_da_verificacao(natureza, v, f),
                     anomalias_ligadas=[{"tipo": t, "ocorrencias": contagem.get(t, 0)}
                                        for t in (cat["anomalias"] if catalogada else ())])
            saida.append(g)
        return saida

    def _escopo_das_anomalias(self, descricao, escopo):
        """Filters of the anomaly list that the same rule records for the scope of a check item: continuity records on the
        entity's A+1 opening snapshot; pairing, on the copy entity's snapshot of the cut-off (derivar._continuidade
        and _pareamento)."""
        if descricao == CONTINUIDADE:
            return {"exercicio": escopo["para"], "entidade": escopo["entidade"]}
        par = regras.parametros(self.con, "PAR-24", 1)
        return {"exercicio": escopo["exercicio"], "entidade": par["entidade_copia"], "data_final": escopo["data_final"]}

    @staticmethod
    def _situacao_da_verificacao(natureza, verificados, falhas):
        """Displayed situation of a check (contract E-02), by the catalogued nature of the description."""
        if natureza == "conformidade":
            return "sem falha" if falhas == 0 else "com falhas"
        if natureza == "colunas_com_diferenca":
            return f"colunas com diferença: {falhas} de {verificados}"
        if natureza == "pdfs_nao_lidos":
            return f"PDFs não lidos: {falhas}"
        return NAO_CATALOGADA

    def _situacao_das_diferencas(self, did):
        """Contract E-03: the five situations, per aggregation rule (reconciliation rows: column x document x rule) and in
        the consistency between publications; cross-checked with the CONC-RREO check, which counts per PDF snapshot."""
        rec = self.reconciliacao()
        linhas = rec["linhas"]
        regras_ = sorted({x["regra_agregacao"]["regra"] for x in linhas})
        por_regra = {r: {s: sum(1 for x in linhas if x["regra_agregacao"]["regra"] == r and x["situacao_da_diferenca"] == s)
                         for s in SITUACOES_DAS_DIFERENCAS} for r in regras_}
        coe = self.coerencia_entre_publicacoes()["comparacoes"]
        coerencia = {nome: {s: sum(1 for x in lista if x["situacao_da_diferenca"] == s) for s in SITUACOES_DAS_DIFERENCAS}
                     for nome, lista in (("exibida", [x for x in coe if x["mais_recente"]]), ("todas", coe))}
        repetidos = sorted({u for x in linhas for u in x["pdf"]["mesmo_pdf_coletado_tambem_em"]})
        itens = [(json.loads(e), v, f) for e, v, f in self.con.execute(
            "SELECT escopo_json, verificados, falhas FROM verificacao WHERE derivacao_id=? AND descricao=?",
            (did, "conciliação RREO × API (colunas com diferença)"))]
        conf = {"verificacao": {"itens": len(itens), "colunas": sum(v for _, v, _ in itens),
                                "com_diferenca": sum(f for _, _, f in itens)},
                "pdfs_repetidos": {"snapshots": repetidos,
                                   "itens": sum(1 for e, _, _ in itens if e.get("rreo_snapshot") in repetidos),
                                   "colunas": sum(v for e, v, _ in itens if e.get("rreo_snapshot") in repetidos),
                                   "com_diferenca": sum(f for e, _, f in itens if e.get("rreo_snapshot") in repetidos)},
                "reconciliacao": {"colunas": len(linhas), "com_diferenca": sum(1 for x in linhas if x["diferenca_c"])}}
        conf["confere"] = (conf["verificacao"]["colunas"] - conf["pdfs_repetidos"]["colunas"] == conf["reconciliacao"]["colunas"]
                           and conf["verificacao"]["com_diferenca"] - conf["pdfs_repetidos"]["com_diferenca"]
                           == conf["reconciliacao"]["com_diferenca"])
        return {"situacoes": list(SITUACOES_DAS_DIFERENCAS), "por_regra": por_regra,
                "total_por_regra": {r: sum(v.values()) for r, v in por_regra.items()},
                "documentos": len({x["pdf"]["snapshot_uid"] for x in linhas}), "linhas": len(linhas),
                "coerencia": coerencia, "total_coerencia": {k: sum(v.values()) for k, v in coerencia.items()},
                "conferencia_com_a_verificacao": conf,
                "sem_diferenca_contada_como_explicada": sum(1 for x in linhas + coe if x["diferenca_c"] == 0
                                                             and x["situacao_da_diferenca"] != "sem diferença"),
                "nota": ("'Sem diferença' (diferença zero) não é explicação e nunca é somada às explicadas. A contagem é "
                         "por coluna do RREO, documento e regra de agregação (RREO-COL v1 e v2 separadas).")}

    def anomalias(self, tipo, limite=50, deslocamento=0, exercicio=None, entidade=None, data_final=None):
        """Occurrences of ONE anomaly type (contract E-01) WITH a commitment key, paginated, with each one's snapshot; the
        ones without a complete key stay only in the aggregate (`sem_chave` counts the filter's). Optional scope
        filters (fiscal year, entity, cut-off) serve the link coming from a check. The link to the record (drill-down)
        is exact only when the occurrence's snapshot is the current one of the cut-off (the commitment detail shows
        the current snapshot); an occurrence in an earlier snapshot leads to the cut-off's snapshots; in a collection
        that is not a panel cut-off (search type, start date other than 01/01), there is no link."""
        ctx = self.contexto()
        did = ctx["derivacao"]["id"]
        if not self.con.execute("SELECT 1 FROM anomalia_tipo WHERE codigo=?", (tipo,)).fetchone():
            raise ErroDoPainel(f"tipo de anomalia desconhecido: {tipo!r}")
        for nome, valor in (("exercicio", exercicio), ("entidade", entidade)):
            if valor is not None and (isinstance(valor, bool) or not isinstance(valor, int)):
                raise ErroDoPainel(f"{nome} precisa ser inteiro")
        limite, deslocamento = max(1, min(int(limite), LIMITE_LISTA)), max(0, int(deslocamento))
        vig = set(self._vigentes(ctx, None).values())
        filtro, p = "", []
        for coluna, valor in (("c.exercicio", exercicio), ("a.entidade", entidade), ("c.data_final", data_final)):
            if valor is not None:
                filtro, p = filtro + f" AND {coluna} = ?", p + [valor]
        com_chave = " AND a.entidade IS NOT NULL AND a.anoempenho IS NOT NULL AND a.empenho IS NOT NULL"
        base = "FROM anomalia a LEFT JOIN coleta c ON c.id = a.coleta_id WHERE a.derivacao_id=? AND a.tipo=?" + filtro
        total = self.con.execute(f"SELECT COUNT(*) {base}{com_chave}", (did, tipo, *p)).fetchone()[0]
        sem_chave = self.con.execute(f"SELECT COUNT(*) {base} AND NOT (a.entidade IS NOT NULL AND a.anoempenho IS NOT "
                                     "NULL AND a.empenho IS NOT NULL)", (did, tipo, *p)).fetchone()[0]
        itens = []
        for cid, uid, ex, di, df, tp, quando, e, ano, emp, det, cod, ver in self.con.execute(
                "SELECT a.coleta_id, c.snapshot_uid, c.exercicio, c.data_inicial, c.data_final, c.tipo_pesquisa, "
                "c.coletada_em, a.entidade, a.anoempenho, a.empenho, a.detalhe_json, g.codigo, g.versao FROM anomalia a "
                "JOIN regra g ON g.id = a.regra_id LEFT JOIN coleta c ON c.id = a.coleta_id WHERE a.derivacao_id=? AND "
                "a.tipo=?" + filtro + com_chave + " ORDER BY c.exercicio, c.data_final, a.entidade, a.anoempenho, "
                "a.empenho, c.coletada_em, c.snapshot_uid, a.rowid LIMIT ? OFFSET ?", (did, tipo, *p, limite, deslocamento)):
            chave = {"entidade": e, "anoempenho": ano, "empenho": emp}
            corte = cid is not None and tp is None and di == f"{ex}-01-01"
            if not corte:
                retrato = "coleta por tipo de pesquisa ou fora de 01/01 (não é corte do painel)" if cid else "sem snapshot"
            else:
                retrato = "vigente" if cid in vig else "retrato anterior do corte"
            ligacao = {"destino": "empenho" if cid in vig else "retratos", "exercicio": ex, "data_final": df} if corte else None
            itens.append({"snapshot": uid, "exercicio": ex, "data_inicial": di, "data_final": df, "coletada_em": quando,
                          "retrato": retrato, "vigente": cid in vig, "chave": chave,
                          "detalhe": json.loads(det) if det else None, "regra": f"{cod} v{ver}", "ligacao": ligacao})
        t = self.con.execute("SELECT descricao, status_evidencia, fonte FROM anomalia_tipo WHERE codigo=?", (tipo,)).fetchone()
        return {"tipo": tipo, "descricao": t[0], "status_evidencia": t[1], "fonte": t[2],
                "filtros": {k: v for k, v in (("exercicio", exercicio), ("entidade", entidade), ("data_final", data_final))
                            if v is not None},
                "total": total, "sem_chave": sem_chave, "limite": limite, "deslocamento": deslocamento, "itens": itens,
                "derivacao": ctx["derivacao"],
                "nota": ("Uma linha por ocorrência em cada snapshot processado: o mesmo empenho aparece uma vez por "
                         "retrato e por corte em que a condição vale. Ocorrência sem entidade, ano e número do empenho "
                         "fica só na contagem por tipo.")}
