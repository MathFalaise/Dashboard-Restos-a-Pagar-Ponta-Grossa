"""Interface publica de consulta (Subetapa 04.5): aplicacao WSGI somente leitura sobre a camada rp.painel.

  aplicacao.py  roteamento, validacao dos parametros, cabecalhos de seguranca e servidor local (wsgiref)
  paginas.py    paginas: resumo, entidades, empenhos, detalhe de empenho, retratos, comparacao de retratos,
                reconciliacao com o RREO, pares espelhados (tecnico) e metodologia
  formato.py    escape de HTML, moeda em centavos (aritmetica inteira), rotulos de fonte, natureza e regra
  estilo.css    folha de estilo local

Uso: python -m rp interface [--porta 8050] (dentro de app/). Nenhuma pagina consulta a API da Elotech.
"""
from .aplicacao import Aplicacao, criar_servidor, servir

__all__ = ["Aplicacao", "criar_servidor", "servir"]
