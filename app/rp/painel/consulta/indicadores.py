"""Painel mixin: Indicators of a cut-off (the main screen)."""
from .. import explicacoes, fontes
from .comum import instante, REGRAS_DO_INDICADOR, SITUACOES_DO_DADO, SOMAS


def _reais(centavos):
    """R$ 1.234,56 (Brazilian format) for a notice text."""
    return "R$ " + f"{centavos / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class Indicadores:
    """Indicators of a cut-off (the main screen)."""

    def indicadores(self, exercicio, data_final, entidade=None, em=None):
        """Cut-off indicators (one entity or the Municipality) from the Elotech API records."""
        ctx, em = self.contexto(), instante(em)
        corte = self._corte(ctx, exercicio, data_final, entidade, em)
        regras_usadas = self._regras_publicaveis(REGRAS_DO_INDICADOR)
        uids = self._uids(corte["somar"])
        somas = self._somas(ctx, corte["somar"]) if corte["disponivel"] else {}
        rec = self._reconciliacao_do_corte(ctx, exercicio, data_final, entidade, em) if corte["disponivel"] else {}
        valores = {}
        for s in SOMAS:
            regs = [r for r in regras_usadas if (r["codigo"], r["versao"]) in set(s["regras"])]
            consulta = f"{s['formula']} sobre os registros dos snapshots do corte"
            valores[s["id"]] = {
                "id": s["id"], "rotulo": s["rotulo"], "valor_c": somas.get(s["id"]), "unidade": "centavos",
                "natureza": "derivado", "campos": self._campos(s["colunas"]), "formula": s["formula"], "regras": regs,
                "fonte": fontes.ELOTECH["rotulo"], "retrato": corte["retrato"],
                "motivo_indisponivel": None if corte["disponivel"] else corte["motivo"],
                "proveniencia": self._prov_curta(ctx, uids, consulta, regs),
                "reconciliacao_rreo": [x for x in rec.get("linhas", []) if x["coluna"] in s.get("rreo", [])],
            }
        categorias = []
        if corte["disponivel"]:
            regs_cat = [r for r in regras_usadas if r["codigo"] in ("CAT", "S1")]
            for g in sorted(self._por_grupo(ctx, corte["somar"], ["d.categoria"]), key=lambda g: str(g["chave"][0])):
                categorias.append({"categoria": g["chave"][0], "registros": g["registros"],
                                   "inscricao_total_c": g["inscricao_total_c"], "saldo_total_c": g["saldo_total_c"],
                                   "natureza": "derivado", "regras": regs_cat,
                                   "proveniencia": self._prov_curta(ctx, uids, "agrupamento por categoria (CAT v1)",
                                                                    regs_cat)})
        avisos = [fontes.METODOLOGIA["importante"]] + corte["avisos"]
        consolidados = self._consolidados(ctx, corte["somar"]) if corte["disponivel"] else (0, 0)
        if consolidados[0]:
            par = self._escopo_aplicado()["pares"]
            avisos.append(f"{consolidados[0]} registro(s) da entidade {par['entidade_original']} "
                          f"({_reais(consolidados[1])} de inscrição) não são somados no Município: são originais de pares "
                          f"cujas cópias estão na entidade {par['entidade_copia']}, com a mesma inscrição e onde o RP é "
                          "executado; cada par conta uma vez (regra CONS-PAR v4). Na visão da entidade eles continuam.")
        if entidade is None and corte["disponivel"]:
            r = self._pares_com_ressalva(ctx, corte["somar"])
            par = self._escopo_aplicado()["pares"]
            if r["nao_consolidados"]:
                avisos.append(f"Município com ressalva (CONS-PAR v4): {r['nao_consolidados']} par(es) "
                              f"{par['entidade_copia']}↔{par['entidade_original']} não consolidado(s), por execução no "
                              "original ou inscrição diferente nos dois lados: os dois lados entram no total "
                              f"({_reais(r['inscricao_original_c'])} de inscrição do original). Pode haver dupla "
                              "contagem enquanto a natureza das cópias não for confirmada.")
            if r["evidencia_incompleta"]:
                avisos.append(f"Município com ressalva (CONS-PAR v4): {r['evidencia_incompleta']} par(es) consolidado(s) "
                              f"com campo de conferência nulo ({', '.join(par['campos_de_conferencia'])}): a igualdade de "
                              "dois campos vazios não prova que é o mesmo credor e a mesma data.")
        if self._pendentes(ctx):
            avisos.append("Há snapshots de listagem ainda não processados; rode 'python -m rp processar'.")
        return {"consulta": {"exercicio": exercicio, "data_final": data_final, "entidade": entidade, "como_estava_em": em},
                "escopo": f"entidade {entidade}" if entidade is not None else self._texto_escopo_municipio(),
                "regras_de_escopo": self.regras_de_escopo(),
                "disponivel": corte["disponivel"], "motivo_indisponivel": corte["motivo"], "retrato": corte["retrato"],
                "fonte": fontes.ELOTECH["rotulo"], "entidades": corte["entidades"], "valores": valores,
                "categorias": categorias, "reconciliacao": rec.get("resumo"),
                "conferencia_rreo": (self._conferencia_saldo(somas, rec, exercicio, data_final,
                                                             {f"{r['codigo']} v{r['versao']}" for r in self.regras_de_escopo()})
                                     if corte["disponivel"] else None),
                "avisos": avisos,
                "com_ressalva": any(a.startswith("Município com ressalva") for a in avisos),
                "proveniencia": self._proveniencia(ctx, corte["somar"], "somas sobre rp_registro + rp_derivado")}

    def _texto_escopo_municipio(self):
        esc = self._escopo_aplicado()
        if not esc["municipio"] and not esc["copias"] and not esc["pares"]:
            return "Município — Poder Executivo, fonte Elotech (entidades do catálogo oficial do exercício)"
        partes = ["entidades do catálogo oficial do exercício"]
        if esc["municipio"]:
            m = esc["municipio"]
            if m["versao"] == 1:
                partes.append(f"entidade {m['entidade']} até {m['ate_exercicio']} (ESCOPO-MUN v1)")
            else:
                partes.append(f"entidade {m['entidade']} nos períodos em que o demonstrativo oficial a inclui "
                              "(ESCOPO-MUN v2)")
        if esc["copias"]:
            partes.append(f"sem as cópias 24xxxxx antes de {esc['copias']['primeiro_exercicio']} (COPIA-ORIGEM v1)")
        if esc["pares"]:
            partes.append(f"pares {esc['pares']['entidade_copia']}↔{esc['pares']['entidade_original']} contados uma vez "
                          "(CONS-PAR v4)")
        return "Município — Poder Executivo, fonte Elotech (" + "; ".join(partes) + ")"

    @staticmethod
    def _conferencia_saldo(somas, rec, exercicio, data_final, aplicadas=frozenset()):
        """API S1 balance (indicator, operational rule) next to the RREO's L column of the same cut-off: a comparison,
        never a replacement. It does not use RREO-COL: the balance is the S1 formula's and L is the one printed in
        the PDF. `aplicadas`: scope rules in the published indicator (an explanation that depends on one of them
        only applies while it is applied)."""
        linhas = [x for x in rec.get("linhas", []) if x["coluna"] == "L"]
        if not linhas:
            return None
        x = linhas[0]              # the RREO's L is the same in the RREO-COL v1 and v2 rows (same PDF)
        dif = somas["saldo_total"] - x["rreo_c"]
        achadas, situacao = explicacoes.explicar(exercicio, data_final, x["escopo"], "L", "S1 v1",
                                                                   aplicadas) if dif else ([], "sem diferença")
        return {"escopo": x["escopo"], "periodo": x["periodo"],
                "api": {"rotulo": "Saldo de RP no corte (S1)", "valor_c": somas["saldo_total"], "natureza": "derivado",
                        "fonte": fontes.ELOTECH["rotulo"], "regra": "S1 v1"},
                "rreo": {"rotulo": "Coluna L do RREO Anexo VII (saldo de RP)", "valor_c": x["rreo_c"],
                         "natureza": "publicado", "fonte": fontes.RREO["rotulo"], "pdf": x["pdf"], "extracao": x["extracao"]},
                "diferenca_c": dif, "diferenca_natureza": "diferenca", "situacao_da_diferenca": situacao,
                "situacao_do_dado": ({"codigo": "divergente", "texto": SITUACOES_DO_DADO["divergente"]} if dif else
                                     {"codigo": "com_dados", "texto": "dado existente, igual ao RREO"}),
                "explicacoes": [{k: e[k] for k in explicacoes.CAMPOS_SAIDA} for e in achadas],
                "nota": ("Fonte primária: API Elotech. Fonte de reconciliação: RREO Anexo VII. A diferença é mostrada; "
                         "o saldo da API nunca é trocado pelo valor do RREO.")}
