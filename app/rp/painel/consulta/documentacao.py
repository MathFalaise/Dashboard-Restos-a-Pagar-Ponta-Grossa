"""Painel mixin: Rules, evidence, sources, methodology and the field dictionary."""
import json

from ... import governanca
from .. import fontes, publico
from .comum import SITUACOES_DO_DADO, SITUACOES_DO_PONTO


class Documentacao:
    """Rules, evidence, sources, methodology and the field dictionary."""

    # ------------------------------------------------------------------ catalog, sources, methodology
    def regras(self):
        atual = governanca.situacao_atual(self.con)
        params = {}
        for cod, ver, nome, valor in self.con.execute("SELECT r.codigo, r.versao, p.nome, p.valor_json FROM "
                                                      "regra_parametro p JOIN regra r ON r.id = p.regra_id"):
            params.setdefault((cod, ver), {})[nome] = json.loads(valor)
        definicoes = {(c, v): (t, d, f) for c, v, t, d, f in self.con.execute(
            "SELECT codigo, versao, tipo, definicao, fonte FROM regra")}
        return [{**item, "tipo": definicoes[k][0], "definicao": definicoes[k][1], "fonte_da_regra": definicoes[k][2],
                 "parametros": params.get(k, {})} for k, item in sorted(atual.items())]

    def evidencias(self):
        cols = ("id", "tipo", "descricao", "data_documento", "caminho_arquivo", "sha256", "registrada_em", "origem",
                "observacao", "manifesto", "evidencia_uid")
        return [dict(zip(cols, r)) for r in self.con.execute(f"SELECT {', '.join(cols)} FROM evidencia_externa ORDER BY id")]

    @staticmethod
    def fontes():
        return {"fontes": fontes.FONTES, "naturezas": fontes.NATUREZAS,
                "hierarquia": ["API Elotech/Oxy Transparência do Portal da Transparência de Ponta Grossa -> fonte "
                               "primária dos dados operacionais de RP",
                               "RREO Anexo VII -> publicação oficial independente / fonte de reconciliação",
                               "e-SIC, normas e notas técnicas -> fonte externa (evidência registrada)"]}

    def metodologia(self):
        """Methodology texts and the 'as it was on' dates with their own derivation (historical reconciliation)."""
        datas = [v for (v,) in self.con.execute("SELECT DISTINCT vigencia_em FROM derivacao_execucao WHERE vigencia_em "
                                                "IS NOT NULL ORDER BY vigencia_em")]
        return {**fontes.METODOLOGIA, "datas_como_estava_em_com_derivacao": datas,
                "situacoes_do_dado": {**SITUACOES_DO_DADO, **SITUACOES_DO_PONTO}}

    @staticmethod
    def dicionario_campos():
        return {"campos": {c: {"campo_api": a, "rotulo": r, "significado": s, "status": st,
                               "restrito_no_nivel_publico": c in publico.CAMPOS_RESTRITOS}
                           for c, (a, r, s, st) in fontes.CAMPOS.items()},
                "derivados": {c: {"rotulo": r, "formula": f, "regra": f"{cod} v{ver}"}
                              for c, (r, f, (cod, ver)) in fontes.DERIVADOS.items()},
                "unidade_monetaria": "centavos (inteiros); nenhum valor é arredondado"}
