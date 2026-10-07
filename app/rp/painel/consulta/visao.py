"""Painel mixin: the overview (stage 06, docs/stages/06-bi/SCOPE.md) - key numbers, partitions for pie charts and
the series for column charts, assembled from the homologated queries of this layer.

Only three things are computed here, all in integers and checked:
  * partitions: the parts must add up EXACTLY to the total (`fechamento`); otherwise the block is unavailable with
    the reason. A negative part never goes into a pie (the block says so and keeps the values for a column chart);
  * shares in tenths of a percentage point, by the largest remainder: the shares of a pie always add up to 1000
    (100,0%);
  * the "demais" group of a long dimension: the sum of the groups outside the top, checked against the total.
Everything else (indicators, series, composition, entities) comes unchanged from the other methods.
"""
from .. import classificacao
from .comum import fechamento

TOPO_FONTES = 6
TOPO_FUNCOES = 8
TOPO_ENTIDADES = 8          # pies never have more than 8 groups + "demais" (8 colors)
DIMENSOES_DA_VISAO = (("categoria", None), ("tipo_credor", None), ("fonte_recurso", TOPO_FONTES),
                      ("funcao", TOPO_FUNCOES))
ROTULO_DEMAIS = "demais"


def decimos_de_percentual(valores, total):
    """Shares of `total` in tenths of a percentage point (int), by the largest remainder: they add up to exactly 1000.
    Ties in the remainder go to the earlier item. Only for non-negative parts with a positive total."""
    if total <= 0 or any(v < 0 for v in valores):
        raise ValueError("percentual exige total positivo e partes nao negativas")
    pisos = [v * 1000 // total for v in valores]
    restos = [v * 1000 % total for v in valores]
    faltam = 1000 - sum(pisos)
    for i in sorted(range(len(valores)), key=lambda i: (-restos[i], i))[:faltam]:
        pisos[i] += 1
    return pisos


def razao_em_decimos(parte, total):
    """parte / total in tenths of a percentage point, rounded half up (e.g. 383 = 38,3%). None if total <= 0."""
    if total is None or parte is None or total <= 0:
        return None
    return (2 * parte * 1000 + total) // (2 * total)


def particao(total, itens, topo=None):
    """itens: [{"chave", "rotulo", "valor_c", ...}]. Returns the block for a pie: the items (with "decimos"), whether
    the parts close against the total, and whether a pie can be drawn (and why not)."""
    itens = [dict(i) for i in itens]
    if topo is not None and len(itens) > topo + 1:
        ordenados = sorted(itens, key=lambda i: (-i["valor_c"], str(i["chave"])))
        resto = ordenados[topo:]
        itens = ordenados[:topo] + [{"chave": ROTULO_DEMAIS, "rotulo": f"{ROTULO_DEMAIS} ({len(resto)} grupos)",
                                     "valor_c": sum(i["valor_c"] for i in resto), "agrupa": len(resto),
                                     "filtro": None}]
    conferencia = fechamento(total, [i["valor_c"] for i in itens])
    bloco = {"total_c": total, "fechamento": conferencia, "itens": itens, "pizza": False, "motivo": None}
    if not conferencia["fecha"]:
        bloco["motivo"] = (f"as partes não somam o total (diferença de {conferencia['diferenca']} centavos): o "
                           "gráfico não é desenhado")
    elif total == 0:
        bloco["motivo"] = "total zero: não há o que dividir"
    elif any(i["valor_c"] < 0 for i in itens):
        bloco["motivo"] = "há parte negativa, que um gráfico de pizza não representa: veja as colunas"
    else:
        bloco["pizza"] = True
        for i, d in zip(itens, decimos_de_percentual([i["valor_c"] for i in itens], total)):
            i["decimos"] = d
    return bloco


class Visao:
    """Overview (stage 06): key numbers, partitions and series for the charts."""

    def visao_geral(self, exercicio, data_final, entidade=None, em=None):
        ind = self.indicadores(exercicio, data_final, entidade, em)
        res = {"consulta": "visao_geral", "exercicio": exercicio, "data_final": data_final, "entidade": entidade,
               "como_estava_em": em, "disponivel": ind["disponivel"],
               "motivo_indisponivel": ind["motivo_indisponivel"], "retrato": ind["retrato"], "fonte": ind["fonte"],
               "entidades": ind["entidades"],
               "avisos": ind["avisos"], "proveniencia": ind["proveniencia"], "numeros": None, "destino": None,
               "situacao_do_saldo": None, "por_entidade": None, "composicao": {},
               "fonte_das_funcoes": classificacao.FONTE_FUNCOES}
        if ind["disponivel"]:
            v = {k: x["valor_c"] for k, x in ind["valores"].items()}
            res["numeros"] = {k: v[k] for k in ("inscricao_total", "pagamentos", "cancelamentos", "saldo_total",
                                                "saldo_a_liquidar", "saldo_liquidado_a_pagar", "registros")}
            res["numeros"]["pago_do_inscrito_decimos"] = razao_em_decimos(v["pagamentos"], v["inscricao_total"])
            res["destino"] = particao(v["inscricao_total"], [
                {"chave": "pago", "rotulo": "pago", "valor_c": v["pagamentos"]},
                {"chave": "cancelado", "rotulo": "cancelado", "valor_c": v["cancelamentos"]},
                {"chave": "em_aberto", "rotulo": "em aberto (saldo)", "valor_c": v["saldo_total"]}])
            res["situacao_do_saldo"] = particao(v["saldo_total"], [
                {"chave": "a_liquidar", "rotulo": "a liquidar", "valor_c": v["saldo_a_liquidar"]},
                {"chave": "liquidado_a_pagar", "rotulo": "liquidado, a pagar",
                 "valor_c": v["saldo_liquidado_a_pagar"]}])
            if entidade is None:
                res["por_entidade"] = self._saldo_por_entidade(exercicio, data_final, em, v["saldo_total"])
            res["composicao"] = self._composicao_da_visao(exercicio, data_final, entidade, em)
        res["evolucao"] = self._evolucao_da_visao(exercicio, entidade, em)
        res["entre_exercicios"] = self._serie_da_visao(entidade, em)
        return res

    def _saldo_por_entidade(self, exercicio, data_final, em, total):
        linhas = self.entidades_do_corte(exercicio, data_final, em)["linhas"]
        itens = [{"chave": x["entidade"], "rotulo": x["nome"] or f"entidade {x['entidade']}",
                  "valor_c": x["valores"]["saldo_total"], "entidade": x["entidade"]}
                 for x in linhas if x["entra_no_total"] and x["valores"]]
        return particao(total, itens, TOPO_ENTIDADES)

    def _composicao_da_visao(self, exercicio, data_final, entidade, em):
        comp = self.composicao(exercicio, data_final, entidade, em)
        if not comp["disponivel"]:
            return {}
        res = {}
        for dimensao, topo in DIMENSOES_DA_VISAO:
            d = comp["dimensoes"][dimensao]
            if not d["exibida"]:
                res[dimensao] = {"pizza": False, "motivo": d["motivo_nao_exibida"], "itens": [],
                                 "total_c": comp["total"]["saldo_total_c"], "rotulo": d["rotulo"]}
                continue
            itens = []
            for g in d["grupos"]:
                rotulo = g["rotulo"]
                if dimensao == "funcao" and g["chave"] is not None:
                    nome = classificacao.nome_da_funcao(g["chave"])
                    rotulo = f"{nome} (função {g['chave']})" if nome else rotulo
                itens.append({"chave": g["ident"], "rotulo": rotulo, "valor_c": g["saldo_total_c"],
                              "filtro": g["filtro"]})
            bloco = particao(comp["total"]["saldo_total_c"], itens, topo)
            bloco["rotulo"] = d["rotulo"]
            res[dimensao] = bloco
        return res

    def _evolucao_da_visao(self, exercicio, entidade, em):
        ev = self.evolucao(exercicio, entidade, em)
        return [{"data_final": x["data_final"], "tem_valor": x["tem_valor"], "situacao": x["situacao"],
                 "rotulos": x["rotulos"],
                 "saldo_total": x["valores"]["saldo_total"]["valor_c"] if x["tem_valor"] else None,
                 "pagamentos": x["valores"]["pagamentos"]["valor_c"] if x["tem_valor"] else None}
                for x in ev["serie"]]

    def _serie_da_visao(self, entidade, em):
        s = self.serie_entre_exercicios(entidade, em)
        return [{"exercicio": x["exercicio"], "data_final": x["data_final"], "aberto": x["aberto"],
                 "tem_valor": x["tem_valor"], "situacao": x["situacao"], "rotulos": x["rotulos"],
                 "inscricao_total": x["valores"]["inscricao_total"]["valor_c"] if x["tem_valor"] else None,
                 "saldo_total": x["valores"]["saldo_total"]["valor_c"] if x["tem_valor"] else None}
                for x in s["exercicios"]]
