"""Official consolidated Municipality (SICONFI) next to the Executive from the Elotech source - corrective audit of
13/10/2026, item 5.1. See rp/siconfi.py for the source and the scope of each side.

Two series, never mixed:
  * 'consolidado_oficial': the RREO Annex VII declared to SICONFI, row (I) = all powers except intra-budgetary, with
    the Executive and Legislative rows and TOTAL (III), as declared;
  * 'executivo_elotech': the panel's Municipality indicator at the bimester's cut-off (Executive, Elotech source,
    scope rules in force), compared ONLY with the SICONFI 'PODER EXECUTIVO' row - the same scope.
No value of one series enters the other: the Legislative (Câmara Municipal) is shown as declared, never estimated
nor added to the Elotech total.
"""
import calendar

from ... import siconfi
from .comum import ErroDoPainel

# panel indicator -> SICONFI column group (rp.siconfi.grupos): same meaning, independent of the processed/non-processed split
CORRESPONDENCIA = {"inscricao": "inscricao_total", "pagos": "pagamentos", "cancelados": "cancelamentos",
                   "liquidados": "liquidacoes", "saldo": "saldo_total"}


class Oficial:
    def consolidado_oficial(self, exercicio, pasta=None, em=None):
        """Per bimester of `exercicio`: the newest SICONFI reading's declaration (rows, file, SHA-256, delivery
        situation) and the Elotech Executive at the bimester's cut-off, with the differences against the Executive
        row. Earlier readings that changed are listed (a rectification is never replaced silently)."""
        try:
            todas = siconfi.leituras(pasta)
        except siconfi.LeituraInvalida as e:
            raise ErroDoPainel(str(e)) from e
        if not todas:
            return {"exercicio": exercicio, "bimestres": [], "nota": "nenhuma leitura do Siconfi disponível"}
        atual = todas[-1]
        cortes = {c["data_final"] for c in self.cortes(em)["cortes"] if c["exercicio"] == exercicio}
        saida = []
        for bim in range(1, 7):
            try:
                dec = siconfi.declaracao(atual, exercicio, bim)
                entrega = siconfi.situacao_da_entrega(atual, exercicio, bim)
                anteriores = [siconfi.declaracao(x, exercicio, bim) for x in todas[:-1]]
            except siconfi.LeituraInvalida as e:
                raise ErroDoPainel(str(e)) from e
            mudou = [a["arquivo"] for a in anteriores if a and dec and a["linhas"] != dec["linhas"]]
            mes = 2 * bim
            df = f"{exercicio}-{mes:02d}-{calendar.monthrange(exercicio, mes)[1]:02d}"
            item = {"bimestre": bim, "data_final": df, "declaracao": None, "entrega": entrega,
                    "leituras_anteriores_diferentes": mudou, "executivo_elotech": None, "diferencas": None}
            if dec:
                item["declaracao"] = {"arquivo": dec["arquivo"], "sha256": dec["sha256"],
                                      "colunas_omitidas": dec["colunas_omitidas"],
                                      "linhas": {k: siconfi.grupos(v) for k, v in dec["linhas"].items()},
                                      "colunas": dec["linhas"]}
            if df in cortes:
                r = self.indicadores(exercicio, df, em=em)
                if r["disponivel"]:
                    elo = {g: r["valores"][ind]["valor_c"] for g, ind in CORRESPONDENCIA.items()}
                    item["executivo_elotech"] = {"valores": elo, "escopo": r["escopo"], "com_ressalva": r["com_ressalva"],
                                                 "retrato": r["retrato"]["texto"]}
                    exe = (dec or {}).get("linhas", {}).get("executivo")
                    if exe:
                        g = siconfi.grupos(exe)
                        item["diferencas"] = {k: (None if g[k] is None or elo[k] is None else elo[k] - g[k]) for k in g}
            saida.append(item)
        return {"exercicio": exercicio, "leitura": atual.name, "leituras": [x.name for x in todas],
                "bimestres": saida,
                "nota": ("Consolidado oficial = declaração ao Siconfi (linha I: todos os Poderes, exceto "
                         "intraorçamentários). O painel da fonte Elotech cobre o Poder Executivo e é comparado só com a "
                         "linha PODER EXECUTIVO; o Poder Legislativo (Câmara Municipal) aparece como declarado, sem "
                         "estimativa e sem entrar nos valores da fonte Elotech. Diferença = Elotech − Siconfi.")}
