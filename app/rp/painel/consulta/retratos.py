"""Painel mixin: Snapshots of a cut-off, entities of a cut-off and snapshot comparison."""
from ... import vigencia
from ...comparador import comparar as _comparar
from .. import fontes, publico
from .comum import ErroDoPainel, instante, REGRAS_DO_INDICADOR


class Retratos:
    """Snapshots of a cut-off, entities of a cut-off and snapshot comparison."""

    # ------------------------------------------------------------------ snapshots
    def retratos(self, entidade, exercicio, data_final):
        """All snapshots of a cut-off: each collection is an independent snapshot; none replaces another.
        For each complete and processed snapshot: records, inscription, S1 balance and the difference to the previous
        comparable snapshot (also complete and processed)."""
        ctx = self.contexto()
        di = f"{exercicio}-01-01"
        vig = self._vigentes(ctx, None).get((entidade, exercicio, di, data_final))
        regs = [r for r in self._regras_publicaveis(REGRAS_DO_INDICADOR) if r["codigo"] == "S1"]
        saida, anterior = [], None
        for cid, uid, quando, origem, status, obs in self.con.execute(
                "SELECT id, snapshot_uid, coletada_em, origem_carimbo, status, observacao FROM coleta WHERE "
                "tipo='rp_listagem' AND tipo_pesquisa IS NULL AND entidade=? AND exercicio=? AND data_inicial=? AND "
                "data_final=? ORDER BY " + vigencia.ordem("coleta"), (entidade, exercicio, di, data_final)):
            processado = cid <= ctx["limite_coleta"]
            objetos = [h for (h,) in self.con.execute("SELECT sha256 FROM resposta_bruta WHERE coleta_id=? ORDER BY ordem",
                                                      (cid,))]
            item = {"snapshot_uid": uid, "coletada_em": quando, "origem_carimbo": origem, "status": status,
                    "processado": processado, "vigente": cid == vig, "observacao": obs, "objetos": objetos,
                    "retrato": self._retrato(exercicio, data_final, [quando], None)["texto"],
                    "registros": None, "valores": None, "diferenca_para_o_anterior": None}
            if processado and status == "completa":
                s = self._somas(ctx, [cid])
                item["registros"] = s["registros"]
                item["valores"] = {"natureza": "derivado", "regras": regs,
                                   "inscricao_total_c": s["inscricao_total"], "saldo_total_c": s["saldo_total"]}
                if anterior is not None:
                    item["diferenca_para_o_anterior"] = {
                        "natureza": "diferenca", "anterior": anterior["snapshot_uid"],
                        "registros": s["registros"] - anterior["registros"],
                        "inscricao_total_c": s["inscricao_total"] - anterior["valores"]["inscricao_total_c"],
                        "saldo_total_c": s["saldo_total"] - anterior["valores"]["saldo_total_c"],
                        "bytes_identicos": objetos == anterior["objetos"]}
                anterior = item
            saida.append(item)
        return {"entidade": entidade, "exercicio": exercicio, "data_final": data_final, "retratos": saida,
                "fonte": fontes.ELOTECH["rotulo"],
                "nota": ("O mesmo corte coletado em momentos diferentes são retratos diferentes; o anterior nunca é "
                         "substituído. O vigente é o mais recente completo.")}

    def retratos_multiplos(self):
        """Cut-offs (entity, fiscal year, end date) with more than one processed listing snapshot."""
        ctx = self.contexto()
        return [{"entidade": e, "exercicio": ex, "data_final": df, "retratos": n}
                for e, ex, df, n in self.con.execute(
                    "SELECT entidade, exercicio, data_final, COUNT(*) FROM coleta WHERE tipo='rp_listagem' AND "
                    "tipo_pesquisa IS NULL AND id <= ? AND data_inicial = exercicio || '-01-01' "
                    "GROUP BY entidade, exercicio, data_final HAVING COUNT(*) > 1 ORDER BY exercicio, data_final, entidade",
                    (ctx["limite_coleta"],))]

    def entidades_do_corte(self, exercicio, data_final, em=None):
        """Per-entity view of a cut-off. It distinguishes: an existing entity with RP (values), an existing entity without
        RP (a true zero), an entity outside the year's official catalog (it did not exist: no value, never zero) and an
        entity without a snapshot (not collected: no value)."""
        ctx, em = self.contexto(), instante(em)
        corte = self._corte(ctx, exercicio, data_final, None, em)
        regs = self._regras_publicaveis(REGRAS_DO_INDICADOR)
        linhas = []
        for item in corte["entidades"]:
            linha = {k: item[k] for k in ("entidade", "nome", "situacao_no_exercicio", "snapshot", "entra_no_total",
                                          "retratos_do_corte")}
            linha["situacao_do_dado"] = item["situacao_do_dado"]
            linha["retrato_mais_novo_nao_processado"] = item["retrato_mais_novo_nao_processado"]
            if item["situacao_no_exercicio"] == "fora do catálogo oficial":
                linha.update(situacao_do_valor="não existia no exercício (fora do catálogo oficial)", valores=None)
            elif item["snapshot"] is None:
                linha.update(situacao_do_valor=item["situacao_do_dado"]["texto"], valores=None)
            else:
                cid = self.con.execute("SELECT id FROM coleta WHERE snapshot_uid=?",
                                       (item["snapshot"]["snapshot_uid"],)).fetchone()[0]
                s = self._somas(ctx, [cid])
                regs_s1 = [r for r in regs if r["codigo"] == "S1"]
                linha.update(situacao_do_valor=("existente, sem RP neste corte" if s["registros"] == 0
                                                else "valores do snapshot"),
                             valores={"natureza": "derivado", "regras": regs_s1, **s},
                             proveniencia=self._prov_curta(ctx, [item["snapshot"]["snapshot_uid"]],
                                                           "somas dos campos da API da entidade", regs_s1))
            linhas.append(linha)
        return {"exercicio": exercicio, "data_final": data_final, "como_estava_em": em, "retrato": corte["retrato"],
                "municipio_disponivel": corte["disponivel"], "motivo_indisponivel": corte["motivo"],
                "fonte": fontes.ELOTECH["rotulo"], "linhas": linhas,
                "nota": ("Entidade fora do catálogo oficial do exercício não existia naquele ano: aparece sem valor, "
                         "nunca como zero. Entidade existente sem RP aparece com zero.")}

    def comparar_retratos(self, snapshot_a, snapshot_b):
        """Comparison of two snapshots of the same cut-off (read-only comparator)."""
        ctx = self.contexto()
        for ref in (snapshot_a, snapshot_b):
            row = self.con.execute("SELECT id FROM coleta WHERE snapshot_uid=?", (ref,)).fetchone()
            if not row:
                raise ErroDoPainel(f"snapshot {ref!r} não existe")
            if row[0] > ctx["limite_coleta"]:
                raise ErroDoPainel(f"snapshot {ref} ainda não processado: rode 'python -m rp processar'")
        r = _comparar(self.con, snapshot_a, snapshot_b, ctx["normalizacao"]["id"], ctx["derivacao"]["id"])
        if self.nivel != "interno":   # creditor identification does not go out at the public level
            for alt in r["alterados"]:
                alt["campos"] = [c if c["campo"] not in publico.CAMPOS_RESTRITOS else
                                 {"campo": c["campo"], "antes": "[restrito]", "depois": "[restrito]"} for c in alt["campos"]]
        r["natureza"] = "diferenca"
        r["fonte"] = fontes.ELOTECH["rotulo"]
        return r
