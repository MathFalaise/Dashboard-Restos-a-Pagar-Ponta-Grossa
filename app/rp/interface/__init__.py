"""Public query interface (sub-stage 04.5): read-only WSGI application over the rp.painel layer.

  aplicacao.py  routing, parameter validation, security headers and local server (wsgiref)
  paginas/      pages: estrutura.py (page structure and shared components) and one tela_*.py per screen
                (summary, evolution, series, composition, variation, quality, entities, commitments, commitment
                detail, snapshots, reconciliation with the RREO, mirrored pairs and methodology)
  formato.py    HTML escaping, money in cents (integer arithmetic), source, nature and rule labels
  grafico.py    SVG charts embedded in the HTML
  portal.py     where to check each value on the Transparency Portal (links only, never a request)
  estilo.css    local style sheet

Usage: python -m rp interface [--porta 8050] (inside app/). No page queries the Elotech API.
"""
from .aplicacao import Aplicacao, criar_servidor, servir

__all__ = ["Aplicacao", "criar_servidor", "servir"]
