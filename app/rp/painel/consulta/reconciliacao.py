"""Painel mixin: RREO x API reconciliation, RREO documents, consistency between publications
and the analytical views."""
import json

from ... import governanca, regras
from .. import explicacoes, fontes
from .comum import instante, MESES, ORDEM_COLUNAS


class Reconciliacao:
    """RREO x API reconciliation, RREO documents, consistency between publications"""

    def _linhas_conciliacao(self, did, nid, filtros, params):
        """Reconciliation rows. The same PDF (same SHA-256) collected in more than one snapshot appears once, with the
        other snapshots listed in pdf.mesmo_pdf_coletado_tambem_em (the values are the same bytes)."""
        governo = governanca.situacao_atual(self.con)
        pdfs, extracoes, vistos = {}, {}, {}
        saida = []
        for (rc, escopo, ent, ex, df, api_json, col, vr, va, dif, cod, ver) in self.con.execute(
                "SELECT c.rreo_coleta_id, c.escopo, c.entidade, c.exercicio, c.data_final, c.coletas_api_json, "
                "c.coluna, c.valor_rreo_c, c.valor_api_c, c.diferenca_c, g.codigo, g.versao "
                "FROM conciliacao_rreo c JOIN regra g ON g.id = c.regra_agregacao_id JOIN coleta k ON k.id = c.rreo_coleta_id "
                "WHERE c.derivacao_id=?" + filtros +
                " ORDER BY c.exercicio, c.data_final, c.escopo, g.versao, c.coluna, k.coletada_em, k.snapshot_uid",
                (did, *params)):
            if rc not in pdfs:
                s = self._snapshot(rc)
                emit = self.con.execute("SELECT emitido_em FROM rreo_valor WHERE normalizacao_id=? AND coleta_id=? LIMIT 1",
                                        (nid, rc)).fetchone()
                pdfs[rc] = {"snapshot_uid": s["snapshot_uid"], "id_arquivo": s["parametros"].get("id_arquivo"),
                            "rotulo": s["parametros"].get("rotulo"), "data_arquivo": s["parametros"].get("dataArquivo"),
                            "emitido_em": emit[0] if emit else None, "coletada_em": s["coletada_em"],
                            "objeto_bruto_sha256": s["respostas"][0]["objeto_bruto_sha256"] if s["respostas"] else None,
                            "url": s["respostas"][0]["url"] if s["respostas"] else None,
                            "mesmo_pdf_coletado_tambem_em": []}
                extracoes[rc] = self._extracao(nid, rc)
            chave = (pdfs[rc]["objeto_bruto_sha256"], escopo, ex, df, api_json, col, cod, ver)
            if chave in vistos:
                outro = vistos[chave]["pdf"]
                if pdfs[rc]["snapshot_uid"] not in outro["mesmo_pdf_coletado_tambem_em"]:
                    outro["mesmo_pdf_coletado_tambem_em"].append(pdfs[rc]["snapshot_uid"])
                continue
            regra = f"{cod} v{ver}"
            g = governo.get((cod, ver), {})
            operacional = g.get("situacao") == "operacional"
            achadas, situacao = explicacoes.explicar(ex, df, escopo, col, regra) if dif else ([], "sem diferença")
            vistos[chave] = {
                "exercicio": ex, "data_final": df, "periodo": f"janeiro a {MESES[int(df[5:7]) - 1]} de {ex}",
                "escopo": escopo, "entidade": ent, "coluna": col,
                "api_c": va, "rreo_c": vr, "diferenca_c": dif, "texto": f"API = {va}, RREO = {vr}, Diferença = {dif}",
                "api_natureza": "derivado" if operacional else "analitico",
                "rreo_natureza": "publicado", "diferenca_natureza": "diferenca",
                "api_descricao": f"registros da API agregados na coluna ({col}) do RREO pela regra {regra}",
                "regra_agregacao": {"regra": regra, "situacao": g.get("situacao"),
                                    "status_evidencia": g.get("status_evidencia")},
                "snapshots_api": json.loads(api_json), "pdf": pdfs[rc], "extracao": extracoes[rc],
                "situacao_da_diferenca": situacao,
                "explicacoes": [{k: e[k] for k in explicacoes.CAMPOS_SAIDA} for e in achadas],
                "nota": "A diferença é registro; o valor da API nunca é alterado para coincidir com o RREO."}
            saida.append(vistos[chave])
        saida.sort(key=lambda x: (x["exercicio"], x["data_final"], x["escopo"], x["regra_agregacao"]["regra"],
                                  ORDEM_COLUNAS.index(x["coluna"])))
        return saida

    def _extracao(self, nid, rreo_coleta_id):
        row = self.con.execute("SELECT extrator_versao, biblioteca, biblioteca_versao, sha256_pdf, id_arquivo, rotulo, "
                               "extraida_em, valores, erro FROM rreo_extracao WHERE normalizacao_id=? AND coleta_id=?",
                               (nid, rreo_coleta_id)).fetchone()
        if not row:
            return {"registrada": False, "nota": "normalização anterior ao registro da extração (esquema v4)"}
        return {**dict(zip(("extrator_versao", "biblioteca", "biblioteca_versao", "sha256_pdf", "id_arquivo", "rotulo",
                            "extraida_em", "valores", "erro"), row)), "registrada": True}

    def _reconciliacao_do_corte(self, ctx, exercicio, data_final, entidade, em):
        conc = regras.parametros(self.con, "CONC-RREO", 1)
        if entidade is None:
            escopo = "consolidado"
        elif entidade == conc["entidade_do_rreo_por_entidade"]:
            escopo = "entidade"
        else:
            return {"resumo": "sem RREO individual desta entidade no projeto", "linhas": []}
        did, nid = self._derivacao_da_vigencia(ctx, em)
        if did is None:
            return {"resumo": f"não há derivação 'como estava em' {em}; rode 'python -m rp processar --em ...'",
                    "linhas": []}
        linhas = self._linhas_conciliacao(did, nid, " AND c.exercicio=? AND c.data_final=? AND c.escopo=?",
                                          (exercicio, data_final, escopo))
        if not linhas:
            return {"resumo": "sem RREO transcrito para este corte e escopo", "linhas": []}
        return {"resumo": f"{len(linhas)} comparações coluna a coluna com o RREO ({escopo}); ver 'reconciliacao_rreo' "
                          "em cada valor", "linhas": linhas}

    def reconciliacao(self, exercicio=None, data_final=None, escopo=None, somente_diferencas=False, em=None):
        """Elotech API x RREO reconciliation area: each side's value, difference, rule, PDF, extraction and explanation."""
        ctx, em = self.contexto(), instante(em)
        did, nid = self._derivacao_da_vigencia(ctx, em)
        if did is None:
            return {"linhas": [], "nota": f"não há derivação 'como estava em' {em}"}
        filtros, params = "", []
        for col, val in (("c.exercicio", exercicio), ("c.data_final", data_final), ("c.escopo", escopo)):
            if val is not None:
                filtros += f" AND {col}=?"
                params.append(val)
        if somente_diferencas:
            filtros += " AND c.diferenca_c <> 0"
        sem = [{"snapshot_uid": uid, "exercicio": ex, "rotulo": json.loads(pj).get("rotulo"), "extracao": self._extracao(nid, c)}
               for c, uid, ex, pj in self.con.execute(
                   "SELECT c.id, c.snapshot_uid, c.exercicio, c.parametros_json FROM coleta c WHERE c.tipo='rreo_pdf' AND "
                   "c.status='completa' AND c.id <= ? AND NOT EXISTS (SELECT 1 FROM rreo_valor v WHERE "
                   "v.normalizacao_id=? AND v.coleta_id=c.id) ORDER BY c.exercicio, c.snapshot_uid",
                   (ctx["limite_coleta"], nid))]
        return {"fonte_primaria": fontes.ELOTECH["rotulo"], "fonte_de_reconciliacao": fontes.RREO["rotulo"],
                "derivacao_id": did, "como_estava_em": em, "linhas": self._linhas_conciliacao(did, nid, filtros, params),
                "pdfs_sem_valores_transcritos": sem,
                "nota": ("O lado API é a projeção dos registros nas colunas do RREO pela regra indicada; enquanto "
                         "nenhuma versão de RREO-COL for operacional, essa projeção é valor analítico. O indicador "
                         "principal (somas dos campos da API) não depende dela.")}

    def documentos_rreo(self, em=None):
        """Index of the reconciled RREOs: one item per document (PDF) and scope, with how many columns differ in each
        aggregation rule. The column-by-column detail lives in `reconciliacao`."""
        r = self.reconciliacao(em=em)
        docs = {}
        for x in r["linhas"]:
            k = (x["exercicio"], x["data_final"], x["escopo"], x["pdf"]["snapshot_uid"])
            d = docs.setdefault(k, {"exercicio": x["exercicio"], "data_final": x["data_final"], "periodo": x["periodo"],
                                    "escopo": x["escopo"], "entidade": x["entidade"], "pdf": x["pdf"],
                                    "extracao": x["extracao"], "colunas_com_diferenca": {}, "colunas_comparadas": {}})
            regra = x["regra_agregacao"]["regra"]
            d["colunas_comparadas"][regra] = d["colunas_comparadas"].get(regra, 0) + 1
            d["colunas_com_diferenca"][regra] = d["colunas_com_diferenca"].get(regra, 0) + (x["diferenca_c"] != 0)
        return {"fonte_primaria": r.get("fonte_primaria"), "fonte_de_reconciliacao": r.get("fonte_de_reconciliacao"),
                "como_estava_em": r.get("como_estava_em"),
                "documentos": [docs[k] for k in sorted(docs, key=lambda k: (k[0], k[1], k[2]), reverse=True)],
                "pdfs_sem_valores_transcritos": r.get("pdfs_sem_valores_transcritos", []), "nota": r.get("nota")}

    def _api_do_corte(self, ctx, vig, cat, escopo, exercicio, data_final, ent_rreo):
        """Sum of S1 and (a)+(f) (RP of previous years by the FAIXA rule) from the API at the cut-off, or None if unavailable."""
        corte = self._corte(ctx, exercicio, data_final, ent_rreo if escopo == "entidade" else None, None, vig, cat)
        if not corte["disponivel"]:
            return None
        s1, af = self._s1_e_a_mais_f(ctx, corte["somar"])
        return {"s1_c": s1, "a_mais_f_c": af, "snapshots": self._uids(corte["somar"]),
                "retrato": corte["retrato"]["texto"]}

    def coerencia_entre_publicacoes(self):
        """Closing balance L of December's RREO of A x (a)+(f) (RP of previous years) of each RREO of A+1: two
        publications compared with each other. Next to them, the same aggregates computed today with the API (sum of
        S1 at the closing of A and (a)+(f) at the cut-off of A+1), to show which publication the current base
        reproduces."""
        ctx = self.contexto()
        nid = ctx["normalizacao"]["id"]
        regs = self._regras_publicaveis({("S1", 1), ("FAIXA", 1)})
        vig, cat = self._vigentes(ctx, None), self._catalogo(ctx, None)
        ent_rreo = regras.parametros(self.con, "CONC-RREO", 1)["entidade_do_rreo_por_entidade"]
        docs, vistos = {}, set()
        for rc, escopo, ex, df, emit, sha in self.con.execute(
                "SELECT DISTINCT v.coleta_id, v.escopo, v.exercicio, v.data_final, v.emitido_em, "
                "(SELECT sha256 FROM resposta_bruta b WHERE b.coleta_id = v.coleta_id ORDER BY ordem LIMIT 1) "
                "FROM rreo_valor v JOIN coleta c ON c.id = v.coleta_id WHERE v.normalizacao_id=? AND "
                "v.linha='TOTAL (III)' ORDER BY v.exercicio, v.data_final, c.coletada_em, c.snapshot_uid", (nid,)):
            if sha in vistos:   # the same PDF collected again: a single document
                continue
            vistos.add(sha)
            docs.setdefault((escopo, ex), []).append({"coleta_id": rc, "data_final": df, "emitido_em": emit, "sha256": sha})

        def valores(rc):
            return dict(self.con.execute("SELECT coluna, valor_c FROM rreo_valor WHERE normalizacao_id=? AND coleta_id=? "
                                         "AND linha='TOTAL (III)'", (nid, rc)).fetchall())

        saida = []
        for (escopo, ex), lista in sorted(docs.items()):
            for fim in [d for d in lista if d["data_final"] == f"{ex}-12-31"]:
                va = valores(fim["coleta_id"])
                api_de = self._api_do_corte(ctx, vig, cat, escopo, ex, f"{ex}-12-31", ent_rreo)
                for prox in docs.get((escopo, ex + 1), []):
                    vb = valores(prox["coleta_id"])
                    if "L" not in va or "a" not in vb or "f" not in vb:
                        continue
                    dif = vb["a"] + vb["f"] - va["L"]
                    achadas, situacao = explicacoes.explicar_coerencia(escopo, ex) if dif else ([], "sem diferença")
                    api_para = self._api_do_corte(ctx, vig, cat, escopo, ex + 1, prox["data_final"], ent_rreo)
                    saida.append({
                        "escopo": escopo, "de": ex, "para": ex + 1,
                        "rreo_L_de_c": va["L"], "emitido_de": fim["emitido_em"],
                        "rreo_a_mais_f_para_c": vb["a"] + vb["f"], "data_final_para": prox["data_final"],
                        "emitido_para": prox["emitido_em"], "diferenca_c": dif,
                        "natureza": {"rreo": "publicado", "diferenca": "diferenca", "api": "derivado"},
                        "entre": "duas publicações (RREO × RREO)",
                        "pdfs": self._uids([fim["coleta_id"], prox["coleta_id"]]),
                        "pdfs_arquivo": [self.con.execute("SELECT id_arquivo FROM coleta WHERE id=?", (c,)).fetchone()[0]
                                         for c in (fim["coleta_id"], prox["coleta_id"])],
                        "api_s1_de_c": api_de and api_de["s1_c"], "api_a_mais_f_para_c": api_para and api_para["a_mais_f_c"],
                        "api_snapshots": {"de": api_de and api_de["snapshots"], "para": api_para and api_para["snapshots"]},
                        "api_regras": regs, "situacao_da_diferenca": situacao,
                        "explicacoes": [{k: e[k] for k in explicacoes.CAMPOS_SAIDA} for e in achadas],
                        "nota": ("O saldo que fecha A deveria ser o RP de exercícios anteriores que abre A+1; diferença "
                                 "indica alteração da base entre as duas emissões. Os valores da API são o estado atual "
                                 "da base, não o da época de cada emissão.")})
        ultima = {}   # per (scope, A): the comparison with the most recent publication of A+1 (the first one, on a tie)
        for x in saida:
            k = (x["escopo"], x["de"])
            if k not in ultima or x["data_final_para"] > ultima[k]["data_final_para"]:
                ultima[k] = x
        for x in saida:
            x["mais_recente"] = ultima[(x["escopo"], x["de"])] is x
        return {"fonte": fontes.RREO["rotulo"], "comparacoes": saida,
                "limitacao": ("Só entram PDFs com valores transcritos pelo extrator de produção; os RREOs de 2016 "
                              "(entidade), 2018 e 2019 não são lidos por ele (ver 'pdfs_sem_valores_transcritos' na "
                              "reconciliação).")}

    def visao_analitica(self, exercicio, data_final, em=None):
        """Municipality views computed by the derivation: projection onto the RREO columns (RREO-COL v1/v2) and the
        CONS-PAR analytical views. None of them is a published indicator."""
        ctx, em = self.contexto(), instante(em)
        did, _ = self._derivacao_da_vigencia(ctx, em)
        if did is None:
            return {"valores": [], "nota": f"não há derivação 'como estava em' {em}"}
        governo = governanca.situacao_atual(self.con)
        saida = []
        for visao, ga, va, gc, vc, comp, valor, snaps in self.con.execute(
                "SELECT v.visao, a.codigo, a.versao, c.codigo, c.versao, v.componente, v.valor_c, v.coletas_json "
                "FROM visao_valor v JOIN regra a ON a.id=v.regra_agregacao_id LEFT JOIN regra c ON c.id=v.regra_consolidacao_id "
                "WHERE v.derivacao_id=? AND v.exercicio=? AND v.data_final=? AND v.visao IN ('publicado', 'analitico') "
                "ORDER BY v.visao DESC, a.versao, c.versao, v.componente", (did, exercicio, data_final)):
            usadas = [(ga, va)] + ([(gc, vc)] if gc else [])
            operacional = all(governo.get(k, {}).get("situacao") == "operacional" for k in usadas)
            saida.append({"visao": visao, "componente": comp, "valor_c": valor,
                          "regras": [{"regra": f"{c} v{v}", "situacao": governo.get((c, v), {}).get("situacao")}
                                     for c, v in usadas],
                          "natureza": "derivado" if (visao == "publicado" and operacional) else "analitico",
                          "rotulo_da_visao": ("projeção dos registros da API nas colunas do RREO (NÃO é o valor publicado)"
                                              if visao == "publicado" else
                                              "visão analítica consolidada dos pares espelhados (hipótese experimental)"),
                          "snapshots": json.loads(snaps)})
        return {"exercicio": exercicio, "data_final": data_final, "como_estava_em": em, "derivacao_id": did,
                "valores": saida,
                "nota": ("Na derivação, a visão chamada 'publicado' é calculada a partir da API no formato do RREO; o "
                         "valor publicado de fato está na reconciliação. Nenhuma visão analítica entra no indicador "
                         "publicado, e o lado original de um par nunca é apagado.")}
