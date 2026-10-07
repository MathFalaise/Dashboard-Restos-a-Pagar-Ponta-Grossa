"""Read infrastructure for the dashboard.

  consulta/       Painel: read-only queries over the database, built from one mixin per topic (nucleo,
                  indicadores, serie, composicao, variacao, qualidade, empenhos, retratos, reconciliacao,
                  documentacao) plus comum (constants, exceptions, helpers)
  fontes.py       data sources, value natures, field dictionary and methodology text
  publico.py      data minimization for the public level
  explicacoes.py  known explanations of the API x RREO differences (transcribed from the reports)

The dashboard reads from this layer; it never calls the Elotech API directly.
"""
from .consulta import Painel

__all__ = ["Painel"]
