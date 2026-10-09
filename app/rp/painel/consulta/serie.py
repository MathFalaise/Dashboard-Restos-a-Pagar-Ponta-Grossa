"""Painel mixin: Series: evolution within the fiscal year (05.2) and series across fiscal years (05.3)."""
import json

from ... import regras, vigencia
from .. import fontes
from .comum import (CONTINUIDADE, _data_br, diferenca, INDICADORES_DA_SERIE, INDICADORES_ENTRE_EXERCICIOS, instante,
                    ROTULO_EXERCICIO_EM_ABERTO, ROTULO_POSTERIOR_A_COLETA, SITUACOES_DO_PONTO, SOMAS, TEM_VALOR)


class Serie:
    """Series: evolution within the fiscal year (05.2) and series across fiscal years (05.3)."""

    def evolucao(self, exercicio, entidade=None, em=None):
        """Series of the fiscal year's cut-offs (sub-stage 05.2; contract M-01 and M-02).
        * Universe: ALL processed cut-offs of the fiscal year, of any entity, for any scope. A cut-off without data
          for the scope appears with its situation (R1), never omitted and never with a zero value.
        * Each point: situation, indicator values (None without a value), snapshot, labels (R4) and provenance.
        * Difference to the previous adjacent point: later - earlier, only when both have a value (it never skips a
          gap); nature 'diferenca', with the provenance of both sides."""
        ctx, em = self.contexto(), instante(em)
        universo = self._universo_do_exercicio(ctx, self._vigentes(ctx, em), exercicio, em)
        serie, anterior = [], None
        for df in universo:
            r = self.indicadores(exercicio, df, entidade, em)
            codigo = self._situacao_do_ponto(r, entidade)
            tem_valor = codigo in TEM_VALOR
            posterior_a_coleta = tem_valor and bool(r["retrato"] and r["retrato"]["corte_posterior_a_coleta"])
            ponto = {"data_final": df, "disponivel": r["disponivel"], "motivo_indisponivel": r["motivo_indisponivel"],
                     "situacao": {"codigo": codigo, "texto": SITUACOES_DO_PONTO[codigo]}, "tem_valor": tem_valor,
                     "retrato": r["retrato"], "rotulos": [ROTULO_POSTERIOR_A_COLETA] if posterior_a_coleta else [],
                     "entidades": [{"entidade": e["entidade"], "situacao": e["situacao_do_dado"]["codigo"],
                                    "entra_no_total": e["entra_no_total"]} for e in r["entidades"]],
                     "valores": {k: {x: v[x] for x in ("rotulo", "valor_c", "natureza", "proveniencia")}
                                 for k, v in r["valores"].items()}}
            ponto["diferenca_para_o_anterior"] = None if anterior is None else self._diferenca_de_pontos(anterior, ponto)
            serie.append(ponto)
            anterior = ponto
        par = regras.parametros(self.con, "PAR-24", 1)
        envolve_pares = entidade is None or entidade in (par["entidade_copia"], par["entidade_original"])
        pares = self.con.execute(          # distinct 24xxxxx copies with a pair at some cut-off of the fiscal year
            "SELECT COUNT(DISTINCT anoempenho_a || '/' || empenho_a) FROM espelhamento_par WHERE derivacao_id=? AND "
            "exercicio=?", (ctx["derivacao"]["id"], exercicio)).fetchone()[0] if envolve_pares else 0
        return {"exercicio": exercicio, "entidade": entidade, "como_estava_em": em, "fonte": fontes.ELOTECH["rotulo"],
                "indicadores_da_serie": list(INDICADORES_DA_SERIE), "serie": serie,
                "pares_espelhados_no_exercicio": pares,
                "nota": ("Cada corte é o estado atual da base para aquele corte, na data da coleta. Pagamentos, "
                         "liquidações e cancelamentos são acumulados de 01/01 até o corte; a diferença entre cortes "
                         "vizinhos é o movimento do intervalo, se os dois cortes refletem a mesma base.")}

    @staticmethod
    def _diferenca_de_pontos(anterior, ponto):
        """Difference between adjacent points (contract section 2.6): None values when either side has no value."""
        motivo = None
        if not (anterior["tem_valor"] and ponto["tem_valor"]):
            lacuna = anterior if not anterior["tem_valor"] else ponto
            motivo = (f"sem diferença: o corte {_data_br(lacuna['data_final'])} não tem valor "
                      f"({lacuna['situacao']['texto']})")
        return {"anterior": anterior["data_final"], "natureza": "diferenca", "sinal": "posterior − anterior",
                "motivo_indisponivel": motivo,
                "valores": {k: diferenca(anterior["valores"][k]["valor_c"], ponto["valores"][k]["valor_c"])
                            for k in ponto["valores"]},
                "proveniencia": {"anterior": anterior["valores"]["saldo_total"]["proveniencia"],
                                 "posterior": ponto["valores"]["saldo_total"]["proveniencia"]}}

    def _sem_cobertura(self, exercicio, em):
        """Contract section 2.1: no listing collection for the fiscal year (of any entity and situation) up to `em`."""
        filtro, p = vigencia.filtro_disponivel(em, "coleta")
        return not self.con.execute("SELECT 1 FROM coleta WHERE tipo='rp_listagem' AND tipo_pesquisa IS NULL AND "
                                    "exercicio=? AND data_inicial=?" + filtro + " LIMIT 1",
                                    (exercicio, f"{exercicio}-01-01", *p)).fetchone()

    def _corte_representativo(self, ctx, vig, cat, exercicio, em):
        fim = f"{exercicio}-12-31"
        cortes = self._universo_do_exercicio(ctx, vig, exercicio, em)
        base = {"exercicio": exercicio, "data_final": None, "aberto": None, "motivo": None}
        if not cortes:
            return {**base, "motivo": ("exercício sem cobertura" if self._sem_cobertura(exercicio, em)
                                       else "nenhum corte processado do exercício")}
        disponiveis = [df for df in cortes if self._corte(ctx, exercicio, df, None, em, vig, cat)["disponivel"]]
        if fim in disponiveis:
            return {**base, "data_final": fim, "aberto": False}
        if disponiveis:
            return {**base, "data_final": disponiveis[-1], "aberto": True}
        return {**base, "motivo": "Município indisponível em todos os cortes do exercício"}

    def corte_representativo(self, exercicio, em=None):
        """Cut-off that represents the fiscal year in the series across years (contract section 2.5; R8): 31/12 if the
        Municipality is available there; otherwise the last cut-off with the Municipality available ('exercicio em
        aberto'); otherwise none (a gap for every scope). The same cut-off applies to every scope."""
        ctx, em = self.contexto(), instante(em)
        return self._corte_representativo(ctx, self._vigentes(ctx, em), self._catalogo(ctx, em), exercicio, em)

    def serie_entre_exercicios(self, entidade=None, em=None):
        """Series by fiscal year (sub-stage 05.3; contract M-03 and M-04).
        * Universe: every fiscal year between the first and the last with a listing collection; a year without any
          collection appears as 'exercicio_sem_cobertura'.
        * Each fiscal year at its representative cut-off (R8), the same for every scope; None values without data.
        * Every point with a value carries the snapshot 'Estado atual da base para o exercicio de A, corte ...,
          coletado em ...': the past is the current state of the base, not what was known at the time.
        * Closing of A x opening of A+1: (a)+(f)(A+1) - S1(A) by FAIXA v1 (R2); in the Municipality, only with the
          entities exclusive to one side having no records (R7); with the derivation's continuity check (ANOM-CONT v1)."""
        ctx, em = self.contexto(), instante(em)
        vig, cat = self._vigentes(ctx, em), self._catalogo(ctx, em)
        filtro, p = vigencia.filtro_disponivel(em, "coleta")
        anos = [ex for (ex,) in self.con.execute(
            "SELECT DISTINCT exercicio FROM coleta WHERE tipo='rp_listagem' AND tipo_pesquisa IS NULL AND "
            "data_inicial = exercicio || '-01-01'" + filtro, p)]
        pontos = []
        for ex in (range(min(anos), max(anos) + 1) if anos else []):
            pontos.append(self._ponto_do_exercicio(ctx, vig, cat, ex, entidade, em))
        fechamentos = [self._fechamento_abertura(ctx, vig, cat, a, b, entidade, em) for a, b in zip(pontos, pontos[1:])]
        par = regras.parametros(self.con, "PAR-24", 1)
        pares = {}
        if entidade is None or entidade in (par["entidade_copia"], par["entidade_original"]):
            pares = dict(self.con.execute(
                "SELECT exercicio, COUNT(DISTINCT anoempenho_a || '/' || empenho_a) FROM espelhamento_par "
                "WHERE derivacao_id=? GROUP BY exercicio", (ctx["derivacao"]["id"],)).fetchall())
        return {"entidade": entidade, "como_estava_em": em, "fonte": fontes.ELOTECH["rotulo"],
                "indicadores": list(INDICADORES_ENTRE_EXERCICIOS), "exercicios": pontos,
                "fechamento_abertura": fechamentos, "pares_espelhados_por_exercicio": pares,
                "nota": fontes.METODOLOGIA["importante"]}

    def _ponto_do_exercicio(self, ctx, vig, cat, ex, entidade, em):
        rep = self._corte_representativo(ctx, vig, cat, ex, em)
        # same format as the series within the fiscal year (05.2): every indicator present, with valor_c None when there is no value
        ponto = {"exercicio": ex, "data_final": rep["data_final"], "aberto": rep["aberto"], "retrato": None,
                 "rotulos": [], "entidades": [], "tem_valor": False,
                 "valores": {i["id"]: {"rotulo": i["rotulo"], "valor_c": None, "natureza": "derivado",
                                       "proveniencia": None} for i in SOMAS}}
        if self._sem_cobertura(ex, em):
            codigo, motivo = "exercicio_sem_cobertura", SITUACOES_DO_PONTO["exercicio_sem_cobertura"]
        elif rep["data_final"] is None:
            codigo, motivo = "municipio_indisponivel", rep["motivo"]
        else:
            r = self.indicadores(ex, rep["data_final"], entidade, em)
            codigo, motivo = self._situacao_do_ponto(r, entidade), r["motivo_indisponivel"]
            ponto.update(retrato=r["retrato"],
                         entidades=[{"entidade": e["entidade"], "situacao": e["situacao_do_dado"]["codigo"],
                                     "entra_no_total": e["entra_no_total"]} for e in r["entidades"]],
                         valores={k: {x: v[x] for x in ("rotulo", "valor_c", "natureza", "proveniencia")}
                                  for k, v in r["valores"].items()})
        ponto.update(situacao={"codigo": codigo, "texto": SITUACOES_DO_PONTO[codigo]}, tem_valor=codigo in TEM_VALOR,
                     motivo_indisponivel=None if codigo in TEM_VALOR else motivo)
        if ponto["tem_valor"]:
            ponto["rotulos"] = ([ROTULO_EXERCICIO_EM_ABERTO] if rep["aberto"] else []) + (
                [ROTULO_POSTERIOR_A_COLETA] if ponto["retrato"]["corte_posterior_a_coleta"] else [])
        return ponto

    def _fechamento_abertura(self, ctx, vig, cat, a, b, entidade, em):
        """Contract M-04: (a)+(f)(A+1) - S1(A), each at its representative cut-off; R7 in the Municipality."""
        item = {"de": a["exercicio"], "para": b["exercicio"], "natureza": "diferenca",
                "sinal": "(a)+(f) da abertura de A+1 − S1 do fechamento de A", "regras": ["S1 v1", "FAIXA v1"],
                "s1_de_c": None, "a_mais_f_para_c": None, "diferenca_c": None, "motivo_indisponivel": None,
                "entidades_que_entram": [], "entidades_que_saem": [], "proveniencia": None,
                "continuidade": self._continuidade(ctx, a["exercicio"], entidade,
                                                   {e["entidade"] for e in a["entidades"] + b["entidades"]})}
        if not (a["tem_valor"] and b["tem_valor"]):
            falta = a if not a["tem_valor"] else b
            item["motivo_indisponivel"] = f"exercício {falta['exercicio']} sem valor ({falta['situacao']['texto']})"
            return item
        if entidade is None:
            ea = {e["entidade"]: e["situacao"] for e in a["entidades"] if e["entra_no_total"]}
            eb = {e["entidade"]: e["situacao"] for e in b["entidades"] if e["entra_no_total"]}
            item["entidades_que_saem"], item["entidades_que_entram"] = sorted(set(ea) - set(eb)), sorted(set(eb) - set(ea))
            com_registros = ([e for e in item["entidades_que_saem"] if ea[e] != "sem_rp"]
                             + [e for e in item["entidades_que_entram"] if eb[e] != "sem_rp"])
            if com_registros:
                item["motivo_indisponivel"] = ("conjunto de entidades diferente nos dois exercícios, com registros na(s) "
                                               f"entidade(s) {sorted(com_registros)} (R7)")
                return item
        coletas_b = self._corte(ctx, b["exercicio"], b["data_final"], entidade, em, vig, cat)["somar"]
        _, af = self._s1_e_a_mais_f(ctx, coletas_b)
        s1 = a["valores"]["saldo_total"]["valor_c"]
        item.update(s1_de_c=s1, a_mais_f_para_c=af, diferenca_c=diferenca(s1, af),
                    proveniencia={"de": a["valores"]["saldo_total"]["proveniencia"],
                                  "para": {**b["valores"]["saldo_total"]["proveniencia"],
                                           "consulta": "Σ proc com faixa 'a' + Σ aproc com faixa 'f' (FAIXA v1)"}})
        return item

    def _continuidade(self, ctx, de, entidade, entidades):
        """ANOM-CONT v1 check recorded by the derivation ("derivacao" regime): one row per entity and pair of fiscal years;
        here it is only read and summed for the Municipality."""
        linhas = []
        for escopo_json, verificados, falhas in self.con.execute(
                "SELECT escopo_json, verificados, falhas FROM verificacao WHERE derivacao_id=? AND descricao=?",
                (ctx["derivacao"]["id"], CONTINUIDADE)):
            esc = json.loads(escopo_json)
            if esc["de"] == de and (esc["entidade"] == entidade if entidade is not None else esc["entidade"] in entidades):
                linhas.append({"entidade": esc["entidade"], "verificados": verificados, "falhas": falhas,
                               "snapshots": esc.get("snapshots")})
        linhas.sort(key=lambda x: x["entidade"])
        return {"regra": "ANOM-CONT v1", "descricao": CONTINUIDADE, "linhas": linhas,
                "verificados": sum(x["verificados"] for x in linhas), "falhas": sum(x["falhas"] for x in linhas),
                "nota": "a abertura usada pela derivação é o snapshot de A+1 de maior data final"}
