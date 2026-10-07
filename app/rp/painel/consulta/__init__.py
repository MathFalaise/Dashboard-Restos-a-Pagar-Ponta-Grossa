"""Dashboard query layer: READ-ONLY over the project database.

Flow:  Elotech API -> collection -> immutable snapshot -> normalization -> derivation -> THIS LAYER -> dashboard.
  * It does not call the API: it reads the database opened read-only (URI mode=ro + PRAGMA query_only). Collecting
    is still the collector's job; no screen depends on the portal being up.
  * Main indicator = records from the Elotech API (sums of fields and the S1-S3 formulas). The RREO only appears in
    the reconciliation, side by side; a divergence never changes the API value.
  * Every value comes out with: nature (da_fonte, publicado, derivado, analitico, diferenca), rules used with their
    governance situation, declared source, snapshot label and provenance (derivation -> normalization -> snapshot ->
    HTTP response -> raw object -> endpoint).
  * A rule that is not 'operacional' with compoe_indicador_publicado = 1 never enters a published indicator
    (RegraNaoOperacional). A value computed by a non-operational rule comes out as 'analitico'.
  * A historical fiscal year is the state of the base on the collection date, not what was known in that year.
  * An entity outside the year's official catalog is NOT an entity with zero RP: it shows as not applicable and does
    not enter the Municipality total.
  * Only snapshots processed by the normalization in use come in: a new, not yet processed snapshot becomes a
    warning (never a cut-off with a zero value).
  * A snapshot with the same commitment key more than once (CHAVE-DUP anomaly) is never the current one, as in the
    derivation: no copy is summed twice nor picked. The previous valid snapshot of the cut-off applies, with a
    warning; without one, the data is 'ambiguo' (unavailable). Critical review, items 1, 13 and 14.
  * The 'publico' level (default) never returns creditor identification in lists or aggregates (see publico.py).

Modules: comum (constants, exceptions, helpers), nucleo (connection, context, cut-offs, provenance)
and one mixin per topic: indicadores, serie, composicao, variacao, qualidade, empenhos, retratos,
reconciliacao, documentacao. Painel joins them; callers keep using `from rp.painel.consulta import ...`.
"""
from .comum import (CADEIA, CAMPOS_DO_HISTORICO, CAMPOS_REGISTRO, CATEGORIAS, CLASSES_DA_CHAVE, COMPOSICOES,
                    CONTINUIDADE, DERIVADOS, diferenca, DIMENSOES, DIMENSOES_ORCAMENTARIAS, DINHEIRO, ErroDoPainel,
                    ESQUEMA_MINIMO, EsquemaAntigo, EXPR_CANCELAMENTOS, EXPR_PAGAMENTOS, FAIXAS, fechamento,
                    INDICADORES_DA_SERIE, INDICADORES_ENTRE_EXERCICIOS, instante, INTERPRETACOES_DE_VERIFICACAO,
                    LIMITE_LISTA, MEDIDAS_DA_COMPOSICAO, MESES, METRICAS_DA_VARIACAO, NAO_CATALOGADA, NIVEIS,
                    NivelInvalido, ORDEM_COLUNAS, RegraNaoOperacional, REGRAS_DO_INDICADOR, ROTULO_CATEGORIA,
                    ROTULO_COMPOSICAO, ROTULO_EXERCICIO_EM_ABERTO, ROTULO_POSTERIOR_A_COLETA, SEM_CLASSIFICACAO,
                    SemProcessamento, SITUACOES_DAS_DIFERENCAS, SITUACOES_DO_DADO, SITUACOES_DO_PONTO, SOMAS,
                    TEM_VALOR, TEXTO_FAIXA, TOP_DA_VARIACAO, VERSAO)
from .nucleo import Nucleo
from .indicadores import Indicadores
from .serie import Serie
from .composicao import Composicao
from .variacao import Variacao
from .qualidade import Qualidade
from .empenhos import Empenhos
from .retratos import Retratos
from .reconciliacao import Reconciliacao
from .documentacao import Documentacao


class Painel(Nucleo, Indicadores, Serie, Composicao, Variacao, Qualidade, Empenhos, Retratos, Reconciliacao,
             Documentacao):
    """Read queries for the dashboard. Use Painel.abrir(database_path) (read-only connection)."""


__all__ = ["Painel", "CADEIA", "CAMPOS_DO_HISTORICO", "CAMPOS_REGISTRO", "CATEGORIAS", "CLASSES_DA_CHAVE",
           "COMPOSICOES", "CONTINUIDADE", "DERIVADOS", "diferenca", "DIMENSOES", "DIMENSOES_ORCAMENTARIAS", "DINHEIRO",
           "ErroDoPainel", "ESQUEMA_MINIMO", "EsquemaAntigo", "EXPR_CANCELAMENTOS", "EXPR_PAGAMENTOS", "FAIXAS",
           "fechamento", "INDICADORES_DA_SERIE", "INDICADORES_ENTRE_EXERCICIOS", "instante",
           "INTERPRETACOES_DE_VERIFICACAO", "LIMITE_LISTA", "MEDIDAS_DA_COMPOSICAO", "MESES", "METRICAS_DA_VARIACAO",
           "NAO_CATALOGADA", "NIVEIS", "NivelInvalido", "ORDEM_COLUNAS", "RegraNaoOperacional", "REGRAS_DO_INDICADOR",
           "ROTULO_CATEGORIA", "ROTULO_COMPOSICAO", "ROTULO_EXERCICIO_EM_ABERTO", "ROTULO_POSTERIOR_A_COLETA",
           "SEM_CLASSIFICACAO", "SemProcessamento", "SITUACOES_DAS_DIFERENCAS", "SITUACOES_DO_DADO",
           "SITUACOES_DO_PONTO", "SOMAS", "TEM_VALOR", "TEXTO_FAIXA", "TOP_DA_VARIACAO", "VERSAO"]
