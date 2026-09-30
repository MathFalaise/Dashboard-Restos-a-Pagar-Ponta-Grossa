"""Infraestrutura de leitura para o futuro dashboard (nao ha frontend no projeto).

  consulta.py     Painel: consultas somente leitura sobre o banco (indicadores, cortes, entidades, empenhos,
                  retratos, reconciliacao, coerencia entre publicacoes, visoes analiticas, regras, evidencias)
  fontes.py       fontes de dados, naturezas de valor, dicionario de campos e texto de metodologia
  publico.py      minimizacao de dados do nivel publico
  explicacoes.py  explicacoes conhecidas das diferencas API x RREO (transcricao dos relatorios)

O dashboard le desta camada; nunca chama a API da Elotech diretamente.
"""
from .consulta import Painel

__all__ = ["Painel"]
